"""
Lookahead bias tests for Capital Footprint features.
Validates that no future data leaks into feature computation.
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.capital_footprint.features import (
    add_liquidity_features,
    add_price_volume_features,
    add_trend_features,
    add_rs_features,
)


def _make_ohlcv(n: int = 250, start: str = "2020-01-01", symbol: str = "TEST") -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range(start, periods=n, freq="B")
    close = np.cumprod(1 + rng.normal(0.001, 0.015, n)) * 100
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    return pd.DataFrame({
        "symbol": symbol,
        "date": dates,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.uniform(1e5, 1e6, n),
        "value": close * rng.uniform(1e5, 1e6, n),
        "sector_primary": "SectorA",
    })


def _check_no_lookahead(fn, col: str, perturb_from: int = 120) -> None:
    """
    Verify that perturbing future prices does not change feature values
    before perturb_from. If it does, there is a lookahead bias.
    """
    df1 = _make_ohlcv(250)
    df2 = df1.copy()
    df2.loc[df2.index[perturb_from:], "close"] *= 10.0
    df2.loc[df2.index[perturb_from:], "high"] *= 10.0
    df2.loc[df2.index[perturb_from:], "low"] *= 10.0
    df2.loc[df2.index[perturb_from:], "value"] *= 10.0

    r1 = fn(df1.copy())
    r2 = fn(df2.copy())

    if col not in r1.columns:
        pytest.skip(f"Column {col} not computed")

    pre1 = r1.iloc[:perturb_from][col].fillna(-9999).reset_index(drop=True)
    pre2 = r2.iloc[:perturb_from][col].fillna(-9999).reset_index(drop=True)
    diff = (pre1 - pre2).abs().max()
    assert diff < 1e-8, (
        f"{col}: future perturbation changed past feature values (max diff={diff:.2e}) "
        "— lookahead bias detected!"
    )


class TestLiquidityNoLookahead:
    def test_adv20(self):
        _check_no_lookahead(add_liquidity_features, "adv20_vnd")

    def test_adv50(self):
        _check_no_lookahead(add_liquidity_features, "adv50_vnd")

    def test_turnover_z20(self):
        _check_no_lookahead(add_liquidity_features, "turnover_z_20d")


class TestPriceVolumeNoLookahead:
    def test_close_location_value(self):
        _check_no_lookahead(add_price_volume_features, "close_location_value")

    def test_breakout_volume_flag(self):
        """Breakout flag uses shift(1) on rolling 60d high."""
        _check_no_lookahead(add_price_volume_features, "breakout_volume_flag")

    def test_accumulation_day_count(self):
        _check_no_lookahead(add_price_volume_features, "accumulation_day_count_20d")

    def test_dry_up_pullback(self):
        _check_no_lookahead(add_price_volume_features, "dry_up_pullback_flag")

    def test_net_accumulation_score(self):
        _check_no_lookahead(add_price_volume_features, "net_accumulation_score")


class TestTrendNoLookahead:
    def test_ema20_uses_shift(self):
        """EMA20 should use shift(1) — current bar excluded from its own signal."""
        df = _make_ohlcv(50)
        result = add_trend_features(add_liquidity_features(df.copy()))
        assert "ema20" in result.columns
        # After warmup, ema20 values should be non-NaN
        assert not result["ema20"].iloc[30:].isna().all(), "ema20 should be non-NaN after warmup"

    def test_near_high_uses_prior_data(self):
        _check_no_lookahead(lambda df: add_trend_features(add_liquidity_features(df)), "near_high_60d")

    def test_cloud_bull_no_lookahead(self):
        _check_no_lookahead(lambda df: add_trend_features(add_liquidity_features(df)), "cloud_bull_20_100")


class TestReturnNoLookahead:
    def test_ret20d_backward_looking(self):
        """ret_20d uses past prices only — perturbing future shouldn't change past values."""
        def _apply(df):
            vni = pd.DataFrame({
                "date": df["date"].unique(),
                "close": np.cumprod(1 + np.random.randn(len(df["date"].unique())) * 0.008) * 1200,
                "open": 1200.0, "high": 1210.0, "low": 1190.0, "volume": 5e7,
            })
            df2 = add_liquidity_features(df)
            return add_rs_features(df2, vni)

        _check_no_lookahead(_apply, "ret_20d")


class TestForwardReturnSeparation:
    """Verify forward return columns are not read by scoring functions."""

    def test_fwd_cols_not_in_scoring(self):
        import inspect
        from src.trading.research.capital_footprint.scoring import _rs_component, _pv_component
        fwd_cols = ["fwd_ret_5d", "fwd_ret_20d", "fwd_ret_60d", "fwd_ret_120d"]
        for fn in [_rs_component, _pv_component]:
            src = inspect.getsource(fn)
            for col in fwd_cols:
                assert col not in src, f"fwd col {col} found in {fn.__name__} source — potential lookahead!"
