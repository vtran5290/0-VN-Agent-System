"""
Smoke tests for Capital Footprint pipeline.
Validates that the core modules run without errors on synthetic data.
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _make_synthetic_panel(n_stocks: int = 10, n_days: int = 300) -> pd.DataFrame:
    """Create a synthetic feature panel for smoke testing."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    rows = []
    for sym in [f"S{i:02d}" for i in range(n_stocks)]:
        close = np.cumprod(1 + rng.normal(0.001, 0.015, n_days)) * 50
        high = close * (1 + np.abs(rng.normal(0, 0.005, n_days)))
        low = close * (1 - np.abs(rng.normal(0, 0.005, n_days)))
        val = rng.uniform(1e9, 5e9, n_days)
        for i, d in enumerate(dates):
            rows.append({
                "symbol": sym,
                "date": d,
                "open": close[i],
                "high": high[i],
                "low": low[i],
                "close": close[i],
                "volume": val[i] / close[i],
                "value": val[i],
                "sector_primary": "BanksSector" if int(sym[1:]) < 5 else "TechSector",
            })
    return pd.DataFrame(rows)


class TestFeatureSmoke:
    def test_liquidity_features(self):
        from src.trading.research.capital_footprint.features import add_liquidity_features
        panel = _make_synthetic_panel()
        out = add_liquidity_features(panel)
        assert "adv20_vnd" in out.columns
        assert "adv50_vnd" in out.columns
        assert "turnover_z_20d" in out.columns
        assert "liquidity_rank_market" in out.columns
        # ranks should be in [0, 1]
        rank = out["liquidity_rank_market"].dropna()
        assert rank.min() >= 0 and rank.max() <= 1

    def test_rs_features(self):
        from src.trading.research.capital_footprint.features import add_rs_features, add_liquidity_features
        panel = add_liquidity_features(_make_synthetic_panel())

        # Synthetic VNINDEX
        dates = panel["date"].unique()
        vni = pd.DataFrame({
            "date": sorted(dates),
            "open": 1200.0,
            "high": 1210.0,
            "low": 1190.0,
            "close": np.cumprod(1 + np.random.randn(len(dates)) * 0.008) * 1200,
            "volume": 5e7,
        })

        out = add_rs_features(panel, vni)
        assert "ret_20d" in out.columns
        assert "rel_ret_vnindex_20d" in out.columns
        assert "rs_rank_market_20d" in out.columns
        assert "rs_persistence_score" in out.columns

    def test_pv_features(self):
        from src.trading.research.capital_footprint.features import add_price_volume_features, add_liquidity_features
        panel = add_liquidity_features(_make_synthetic_panel())
        out = add_price_volume_features(panel)
        assert "close_location_value" in out.columns
        assert "breakout_volume_flag" in out.columns
        assert "net_accumulation_score" in out.columns
        assert "up_down_value_ratio_20d" in out.columns
        # CLV should be in [0, 1]
        clv = out["close_location_value"].dropna()
        assert clv.min() >= 0 and clv.max() <= 1

    def test_trend_features(self):
        from src.trading.research.capital_footprint.features import add_trend_features, add_liquidity_features
        panel = add_liquidity_features(_make_synthetic_panel())
        out = add_trend_features(panel)
        assert "ema20" in out.columns
        assert "cloud_bull_20_100" in out.columns
        assert "above_ema50" in out.columns
        assert "new_high_60d_flag" in out.columns
        # Binary flags should be 0 or 1
        flag = out["cloud_bull_20_100"].dropna()
        assert set(flag.unique()).issubset({0, 1})


class TestScoringSmoke:
    def _make_full_panel(self) -> pd.DataFrame:
        from src.trading.research.capital_footprint.features import (
            add_liquidity_features, add_rs_features, add_price_volume_features,
            add_trend_features, add_sector_rotation_features,
        )
        panel = _make_synthetic_panel()
        dates = panel["date"].unique()
        vni = pd.DataFrame({
            "date": sorted(dates),
            "open": 1200.0,
            "high": 1210.0,
            "low": 1190.0,
            "close": np.cumprod(1 + np.random.randn(len(dates)) * 0.008) * 1200,
            "volume": 5e7,
        })
        panel = add_liquidity_features(panel)
        panel = add_rs_features(panel, vni)
        panel = add_price_volume_features(panel)
        panel = add_trend_features(panel)
        panel = add_sector_rotation_features(panel)
        return panel

    def test_scores_in_0_1(self):
        from src.trading.research.capital_footprint.scoring import add_scores
        panel = self._make_full_panel()
        scored = add_scores(panel)
        for col in ["capital_footprint_score_raw", "capital_footprint_score_pure_tech"]:
            if col in scored.columns:
                vals = scored[col].dropna()
                assert vals.min() >= -0.01, f"{col} < 0"
                assert vals.max() <= 1.01, f"{col} > 1"

    def test_no_forward_return_in_scores(self):
        """Ensure scoring doesn't consume fwd_ret columns."""
        from src.trading.research.capital_footprint.scoring import add_scores
        panel = self._make_full_panel()
        # Add fake forward returns
        panel["fwd_ret_20d"] = 0.50  # artificially high — should not inflate score
        panel_copy = panel.copy()
        panel_copy["fwd_ret_20d"] = -0.50  # opposite

        scored1 = add_scores(panel)
        scored2 = add_scores(panel_copy)

        if "capital_footprint_score_raw" in scored1.columns:
            diff = (scored1["capital_footprint_score_raw"].fillna(0) -
                    scored2["capital_footprint_score_raw"].fillna(0)).abs().max()
            assert diff < 1e-6, f"Score changes with fwd_ret manipulation (diff={diff}) — forward return leak!"


class TestBacktestSmoke:
    def _make_scored_panel(self) -> pd.DataFrame:
        from src.trading.research.capital_footprint.features import (
            add_liquidity_features, add_rs_features, add_price_volume_features,
            add_trend_features, add_sector_rotation_features, add_forward_returns,
        )
        from src.trading.research.capital_footprint.scoring import add_scores

        panel = _make_synthetic_panel()
        dates = panel["date"].unique()
        vni = pd.DataFrame({
            "date": sorted(dates),
            "open": 1200.0,
            "high": 1210.0,
            "low": 1190.0,
            "close": np.cumprod(1 + np.random.randn(len(dates)) * 0.008) * 1200,
            "volume": 5e7,
        })
        panel = add_liquidity_features(panel)
        panel = add_rs_features(panel, vni)
        panel = add_price_volume_features(panel)
        panel = add_trend_features(panel)
        panel = add_sector_rotation_features(panel)
        panel = add_forward_returns(panel, vni)
        panel = add_scores(panel)
        return panel

    def test_ic_analysis_runs(self):
        from src.trading.research.capital_footprint.backtest import run_ic_analysis
        panel = self._make_scored_panel()
        result = run_ic_analysis(panel, signal_cols=["capital_footprint_score_raw"], fwd_cols=["fwd_ret_20d"])
        assert isinstance(result, pd.DataFrame)

    def test_quantile_portfolio_runs(self):
        from src.trading.research.capital_footprint.backtest import run_quantile_portfolio
        panel = self._make_scored_panel()
        if "capital_footprint_score_raw" in panel.columns and "fwd_ret_20d" in panel.columns:
            result = run_quantile_portfolio(panel, "capital_footprint_score_raw", "fwd_ret_20d")
            assert isinstance(result, pd.DataFrame)

    def test_event_study_runs(self):
        from src.trading.research.capital_footprint.backtest import run_event_study
        panel = self._make_scored_panel()
        if "capital_footprint_score_raw" in panel.columns:
            result = run_event_study(panel, lookback=5, lookahead=10)
            assert isinstance(result, pd.DataFrame)
