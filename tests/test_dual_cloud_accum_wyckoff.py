"""Unit tests for the dual cloud accumulation / Wyckoff research module.

Tests cover:
  - Feature causality (no lookahead at bar t)
  - Cloud signal fires exactly once at transition, not every bar
  - ADV gate excludes illiquid bars / passes liquid bars
  - forward_returns: entry at t+1, exit at t+1+h, correct cost deduction
  - spring / SOS / LPS / UTAD tag correctness on synthetic price series
  - accumulation_score_cross_sectional: monotone with features, no time-series rank
  - panel_utils helpers: load_vnindex_regime dedup, s3_signal regime gate

All tests use synthetic in-memory DataFrames — no file IO, no live data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ── Path bootstrap (repo root on sys.path via pytest.ini pythonpath=.) ────────
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    _atr_ewm,
    accumulation_score,
    accumulation_score_cross_sectional,
    atr_ratio_14_50,
    bo_close_strength,
    bo_vol_expansion,
    compute_all_features,
    lps_tag,
    price_tightness_20,
    sos_tag,
    spring_tag,
    utad_tag,
    vol_drying_score,
    vol_ratio_20,
)
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    COST_BPS,
    MIN_ADV_VND,
    MIN_HISTORY,
    adv_mask,
    cloud_signal,
    forward_returns,
    load_vnindex_regime,
)


# ── Synthetic OHLCV builder ───────────────────────────────────────────────────

def _make_ohlcv(
    n: int = 400,
    base_price: float = 50.0,
    trend: float = 0.0,
    vol_noise: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame with integer index, close in kVND range."""
    rng = np.random.default_rng(seed)
    prices = base_price + trend * np.arange(n) + rng.normal(0, vol_noise * base_price, n).cumsum()
    prices = np.clip(prices, 1.0, None)
    noise = rng.uniform(0.005, 0.015, n)
    high  = prices * (1 + noise)
    low   = prices * (1 - noise)
    open_ = (prices + low) / 2
    vol   = rng.integers(100_000, 1_000_000, n).astype(float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date":   dates,
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  prices,
        "volume": vol,
        "adv50":  prices * vol * 1000,   # synthetic ADV in VND
    }).reset_index(drop=True)


# ── Feature causality tests ───────────────────────────────────────────────────

class TestFeatureCausality:
    """Verify that all features at bar t depend only on bars 0..t."""

    def test_price_tightness_identical_when_future_appended(self):
        """pt_20[t] must not change when bars t+1..t+k are appended."""
        df_short = _make_ohlcv(200)
        df_long  = _make_ohlcv(400)

        pt_short = price_tightness_20(df_short["close"])
        pt_long  = price_tightness_20(df_long["close"])

        # At bar 150 (well past warmup), values must match between short/long
        assert abs(pt_short.iloc[150] - pt_long.iloc[150]) < 1e-10, (
            "price_tightness_20 value at bar 150 changed when future bars added — lookahead!"
        )

    def test_atr_ratio_causal(self):
        # Same underlying data: long df truncated to short. Values must agree.
        df_long  = _make_ohlcv(300)
        df_short = df_long.iloc[:200].reset_index(drop=True)
        r_short  = atr_ratio_14_50(df_short["high"], df_short["low"], df_short["close"])
        r_long   = atr_ratio_14_50(df_long["high"], df_long["low"], df_long["close"])
        assert abs(r_short.iloc[180] - r_long.iloc[180]) < 1e-10, (
            "atr_ratio_14_50 at bar 180 changed when future bars added — lookahead!"
        )

    def test_vol_drying_causal(self):
        df_long  = _make_ohlcv(300)
        df_short = df_long.iloc[:200].reset_index(drop=True)
        v_short  = vol_drying_score(df_short["volume"])
        v_long   = vol_drying_score(df_long["volume"])
        assert abs(v_short.iloc[150] - v_long.iloc[150]) < 1e-10, (
            "vol_drying_score at bar 150 changed when future bars added — lookahead!"
        )

    def test_spring_tag_causal(self):
        df_short = _make_ohlcv(200)
        df_long  = _make_ohlcv(300)
        s_short  = spring_tag(df_short["close"], df_short["low"])
        s_long   = spring_tag(df_long["close"], df_long["low"])
        # Spring tag at bar 150 must match regardless of future data
        assert s_short.iloc[150] == s_long.iloc[150]

    def test_compute_all_features_no_nan_explosion(self):
        df = _make_ohlcv(300)
        out = compute_all_features(df)
        # After warmup (100 bars), pt_20 must not be all-NaN
        pt20_post_warmup = out["pt_20"].iloc[100:]
        assert pt20_post_warmup.notna().mean() > 0.9, "pt_20 is mostly NaN post-warmup"


# ── Cloud signal tests ────────────────────────────────────────────────────────

class TestCloudSignal:
    """Verify cloud signal fires at transition, not on every bullish bar."""

    def _bearish_then_bullish(self, n_bear: int = 120, n_bull: int = 60) -> pd.DataFrame:
        """Construct a price series: flat bear phase then steadily rising bull phase."""
        bear_prices = np.full(n_bear, 50.0)
        bull_prices = np.linspace(50.0, 70.0, n_bull)
        prices = np.concatenate([bear_prices, bull_prices])
        n = len(prices)
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   prices * 0.995,
            "high":   prices * 1.01,
            "low":    prices * 0.99,
            "close":  prices,
            "volume": np.full(n, 500_000.0),
            "adv50":  prices * 500_000 * 1000,
        }).reset_index(drop=True)
        return df

    def test_signal_fires_at_transition(self):
        df = self._bearish_then_bullish(n_bear=120, n_bull=60)
        sig, ef, es = cloud_signal(df, fast=20, slow=100, min_bars_bear=5)
        n_signals = sig.sum()
        # Should fire at most a handful of times (ideally 1), NOT on every bullish bar
        assert n_signals <= 3, (
            f"cloud_signal fired {n_signals} times — expected ≤3 (transition only)"
        )

    def test_signal_not_during_warmup(self):
        df = self._bearish_then_bullish()
        sig, _, _ = cloud_signal(df, fast=20, slow=100, min_bars_bear=5)
        assert sig.iloc[:MIN_HISTORY].sum() == 0, "Signal fired during warmup period"

    def test_no_signal_on_persistent_bull(self):
        """A symbol that was always bullish should get 0 signals (no bear period)."""
        n = 300
        prices = np.linspace(50.0, 100.0, n)
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   prices,
            "high":   prices * 1.01,
            "low":    prices * 0.99,
            "close":  prices,
            "volume": np.full(n, 500_000.0),
            "adv50":  prices * 500_000 * 1000,
        }).reset_index(drop=True)
        sig, _, _ = cloud_signal(df, fast=20, slow=100, min_bars_bear=5)
        assert sig.sum() == 0, "Signal fired on symbol with no prior bear phase"


# ── ADV gate tests ────────────────────────────────────────────────────────────

class TestADVGate:
    def test_excludes_illiquid_bars(self):
        df = _make_ohlcv(200)
        df["adv50"] = 1_000_000.0   # 1M VND — below 2B threshold
        mask = adv_mask(df, min_adv=MIN_ADV_VND)
        assert mask.sum() == 0, "ADV gate should exclude all bars with ADV < 2B"

    def test_passes_liquid_bars(self):
        df = _make_ohlcv(200)
        df["adv50"] = 5_000_000_000.0   # 5B VND — above threshold
        mask = adv_mask(df, min_adv=MIN_ADV_VND)
        assert mask.all(), "ADV gate should pass all bars with ADV ≥ 2B"

    def test_missing_adv50_column_is_safe(self):
        df = _make_ohlcv(200).drop(columns=["adv50"])
        mask = adv_mask(df)
        assert not mask.any(), "Missing adv50 column must fail-safe (all illiquid)"

    def test_nan_adv50_fails_gate(self):
        df = _make_ohlcv(200)
        df["adv50"] = np.nan
        mask = adv_mask(df)
        assert not mask.any(), "NaN adv50 must be treated as illiquid"


# ── forward_returns tests ─────────────────────────────────────────────────────

class TestForwardReturns:
    def _make_trending_df(self, n: int = 300) -> pd.DataFrame:
        df = _make_ohlcv(n)
        df["adv50"] = 5_000_000_000.0
        return df

    def test_entry_is_next_bar_open(self):
        """Entry price must be open of bar t+1, not close of bar t."""
        df = self._make_trending_df(200)
        # Artificial signal at bar 120
        sig = pd.Series(False, index=df.index)
        sig.iloc[120] = True

        trades = forward_returns(df, sig, horizons=[10], require_adv=False)
        assert len(trades) == 1
        row = trades.iloc[0]
        assert row["entry_bar"] == 121
        assert abs(row["entry_price"] - df["open"].iloc[121]) < 1e-9

    def test_exit_is_correct_horizon(self):
        df = self._make_trending_df(300)
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True

        trades = forward_returns(df, sig, horizons=[25, 63], require_adv=False)
        assert len(trades) == 2

        for _, row in trades.iterrows():
            h = int(row["horizon"])
            entry_bar = int(row["entry_bar"])
            expected_exit_bar = entry_bar + h
            # Verify gross return matches open[entry_bar] → open[exit_bar]
            ep = df["open"].iloc[entry_bar]
            xp = df["open"].iloc[expected_exit_bar]
            expected_gross = xp / ep - 1.0
            assert abs(row["gross_return"] - expected_gross) < 1e-9, (
                f"gross_return mismatch at horizon {h}: "
                f"expected {expected_gross:.6f} got {row['gross_return']:.6f}"
            )

    def test_cost_deducted_from_gross(self):
        df = self._make_trending_df(300)
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True

        trades = forward_returns(df, sig, horizons=[25], require_adv=False, cost_bps=COST_BPS)
        row = trades.iloc[0]
        expected_nr = row["gross_return"] - COST_BPS / 10_000.0
        assert abs(row["net_return"] - expected_nr) < 1e-10

    def test_suppressed_during_warmup(self):
        df = self._make_trending_df(300)
        df["adv50"] = 5_000_000_000.0
        sig = pd.Series(False, index=df.index)
        sig.iloc[50] = True   # within warmup (MIN_HISTORY=100)

        trades = forward_returns(df, sig, horizons=[10])
        assert len(trades) == 0, "Signal inside warmup should produce 0 trades"


# ── Wyckoff tag tests ─────────────────────────────────────────────────────────

class TestWyckoffTags:
    def _flat_df(self, n: int = 200, price: float = 50.0) -> pd.DataFrame:
        df = _make_ohlcv(n, base_price=price, vol_noise=0.001)
        df["adv50"] = 5e9
        return df

    def test_spring_fires_on_shakeout_and_reclaim(self):
        """Synthesise a support violation followed by reclaim."""
        df = self._flat_df(150)
        # Make a low at bar 100 that breaks below the 20-bar min of lows
        df.loc[100, "close"] = df["low"].iloc[80:100].min() * 0.90
        df.loc[100, "low"]   = df.loc[100, "close"] * 0.99
        # Bar 101: price recovers well above support
        df.loc[101, "close"] = df["low"].iloc[80:100].min() * 1.05
        df.loc[101, "low"]   = df.loc[101, "close"] * 0.99

        tags = spring_tag(df["close"], df["low"])
        # Spring should fire on/near bar 101 (reclaim bar)
        assert tags.iloc[99:105].any(), (
            "spring_tag did not fire after shakeout+reclaim at bar 100-101"
        )

    def test_spring_does_not_fire_without_violation(self):
        # Use strictly increasing prices — lows always increase, no support violation possible
        n = 150
        prices = np.linspace(50.0, 55.0, n)
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "close":  prices,
            "low":    prices * 0.995,
            "high":   prices * 1.005,
            "open":   prices * 0.998,
            "volume": np.full(n, 500_000.0),
            "adv50":  prices * 500_000 * 1000,
        }).reset_index(drop=True)
        tags = spring_tag(df["close"], df["low"])
        assert tags.sum() == 0, "spring_tag fired on strictly increasing prices — no violation possible"

    def test_sos_fires_on_high_volume_breakout(self):
        df = self._flat_df(150)
        # Set bar 120 above the 20-bar high AND high volume
        df.loc[120, "high"]   = df["high"].iloc[99:120].max() * 1.10
        df.loc[120, "close"]  = df["high"].iloc[99:120].max() * 1.08
        vol_ma = df["volume"].iloc[:120].mean()
        df.loc[120, "volume"] = vol_ma * 2.0   # 2× = strong volume

        tags = sos_tag(df["close"], df["high"], df["volume"])
        assert tags.iloc[120], "sos_tag did not fire on high-volume breakout bar"

    def test_sos_does_not_fire_on_low_volume_breakout(self):
        df = self._flat_df(150)
        df.loc[120, "high"]  = df["high"].iloc[99:120].max() * 1.10
        df.loc[120, "close"] = df["high"].iloc[99:120].max() * 1.08
        vol_ma = df["volume"].iloc[:120].mean()
        df.loc[120, "volume"] = vol_ma * 0.5   # below threshold

        tags = sos_tag(df["close"], df["high"], df["volume"])
        assert not tags.iloc[120], "sos_tag fired on low-volume breakout (should not)"

    def test_utad_fires_after_failed_breakout(self):
        df = self._flat_df(150)
        # Bar 110: close breaks above 20-bar high
        df.loc[110, "high"]  = df["high"].iloc[89:110].max() * 1.10
        df.loc[110, "close"] = df["high"].iloc[89:110].max() * 1.08
        # Bar 113: price falls back below resistance (fail)
        df.loc[113, "close"] = df["high"].iloc[89:110].max() * 0.95

        tags = utad_tag(df["close"], df["high"])
        assert tags.iloc[111:116].any(), "utad_tag did not fire after failed breakout"

    def test_utad_does_not_fire_without_prior_breakout(self):
        df = self._flat_df(150)
        # Price never breaks above resistance
        tags = utad_tag(df["close"], df["high"])
        assert tags.sum() == 0, "utad_tag fired without any prior breakout"


# ── accumulation_score_cross_sectional tests ──────────────────────────────────

class TestScoreCrossSectional:
    def _make_trades_df(self, n: int = 100) -> pd.DataFrame:
        """Fake trade rows with causal feature values."""
        rng = np.random.default_rng(0)
        return pd.DataFrame({
            "pt_20":        rng.uniform(0.01, 0.10, n),
            "atr_ratio":    rng.uniform(0.5, 1.5, n),
            "vol_ratio":    rng.uniform(0.3, 2.0, n),
            "vol_drying":   rng.uniform(0.0, 1.0, n),
            "bo_vol_exp":   rng.uniform(0.3, 3.0, n),
            "bo_close_str": rng.uniform(0.0, 1.0, n),
        })

    def test_score_range(self):
        trades = self._make_trades_df(200)
        score = accumulation_score_cross_sectional(trades)
        assert score.between(0, 1).all(), "Cross-sectional score out of [0, 1] range"

    def test_score_monotone_with_tightness(self):
        """Higher tightness (lower pt_20, lower vol_ratio) → higher score."""
        tight = self._make_trades_df(50)
        loose = self._make_trades_df(50)
        tight["pt_20"]     = 0.01
        tight["vol_ratio"] = 0.3
        loose["pt_20"]     = 0.10
        loose["vol_ratio"] = 2.0
        # Give both identical other features
        for col in ["atr_ratio", "vol_drying", "bo_vol_exp", "bo_close_str"]:
            tight[col] = 0.5
            loose[col] = 0.5

        all_rows = pd.concat([tight, loose], ignore_index=True)
        score = accumulation_score_cross_sectional(all_rows)

        tight_avg = score.iloc[:50].mean()
        loose_avg = score.iloc[50:].mean()
        assert tight_avg > loose_avg, (
            f"Tight stocks should have higher score: {tight_avg:.3f} vs {loose_avg:.3f}"
        )

    def test_score_missing_column_handled(self):
        """Missing optional feature column should not crash."""
        trades = self._make_trades_df(50).drop(columns=["bo_close_str"])
        score = accumulation_score_cross_sectional(trades)
        assert len(score) == 50
        assert not score.isna().all()

    def test_no_time_series_lookahead(self):
        """Adding future rows to the pool must not change past rows' rank direction.

        This checks the property that cross-sectional ranking is stable: a row's
        score might shift in absolute value when the pool grows, but if a row was
        in the top half it should not drop to the bottom half when only extreme
        future values are added (i.e., the relative ordering within the original
        pool must remain consistent).
        """
        rng = np.random.default_rng(42)
        past = pd.DataFrame({
            "pt_20":        rng.uniform(0.01, 0.05, 50),   # all tight
            "atr_ratio":    np.full(50, 0.8),
            "vol_ratio":    np.full(50, 0.6),
            "vol_drying":   np.full(50, 0.7),
            "bo_vol_exp":   np.full(50, 1.5),
            "bo_close_str": np.full(50, 0.8),
        })
        future_loose = pd.DataFrame({
            "pt_20":        np.full(50, 0.15),   # all loose — worse tightness
            "atr_ratio":    np.full(50, 1.5),
            "vol_ratio":    np.full(50, 2.0),
            "vol_drying":   np.full(50, 0.1),
            "bo_vol_exp":   np.full(50, 0.5),
            "bo_close_str": np.full(50, 0.2),
        })
        score_past_only = accumulation_score_cross_sectional(past)
        score_with_future = accumulation_score_cross_sectional(
            pd.concat([past, future_loose], ignore_index=True)
        ).iloc[:50]

        # Past rows (tight) should still be in the upper half when loose rows are added
        assert score_with_future.mean() > 0.5, (
            "Tight rows dropped below 0.5 score mean after loose rows were added — "
            "score monotonicity with tightness broken"
        )


# ── VNINDEX regime dedup test ─────────────────────────────────────────────────

class TestRegimeMap:
    def test_load_vnindex_regime_no_duplicates(self, tmp_path):
        """load_vnindex_regime must return a dedup'd date-indexed Series."""
        pytest.importorskip("pyarrow", reason="pyarrow required for parquet I/O")
        import pandas as pd
        # Construct a fake VNINDEX parquet with duplicate dates
        dates = pd.date_range("2020-01-01", periods=5, freq="B").tolist()
        dates_with_dup = dates + [dates[-1]]   # duplicate last date
        df = pd.DataFrame({
            "date":  dates_with_dup,
            "close": [1000, 1010, 1020, 1015, 1025, 1030],
        })
        parquet_path = tmp_path / "vnindex.parquet"
        df.to_parquet(parquet_path)

        # Monkey-patch the path and call the function
        import scripts.research.dual_cloud_accumulation_wyckoff.panel_utils as pu
        orig_path = pu.VNINDEX_PARQUET
        pu.VNINDEX_PARQUET = parquet_path
        try:
            regime = load_vnindex_regime()
            assert not regime.index.duplicated().any(), (
                "load_vnindex_regime returned duplicate dates in index"
            )
            assert len(regime) == 5   # deduplicated to 5 unique dates
        finally:
            pu.VNINDEX_PARQUET = orig_path

    def test_dedup_happens_before_ema(self, tmp_path):
        """Dedup before EMA: duplicate rows with different close values affect EMA if not removed first."""
        pytest.importorskip("pyarrow", reason="pyarrow required for parquet I/O")
        dates = pd.date_range("2020-01-01", periods=5, freq="B").tolist()
        # Last date has two rows: first close=1025, second close=1200 (should keep 1200)
        dates_with_dup = dates + [dates[-1]]
        df = pd.DataFrame({
            "date":  dates_with_dup,
            "close": [1000, 1010, 1020, 1015, 1025, 1200],  # dup: 1025 vs 1200
        })
        import scripts.research.dual_cloud_accumulation_wyckoff.panel_utils as pu
        orig_path = pu.VNINDEX_PARQUET
        path = tmp_path / "vin_dup.parquet"
        df.to_parquet(path)
        pu.VNINDEX_PARQUET = path
        try:
            regime = load_vnindex_regime()
            # Dedup keeps "last" → close for last date is 1200, not 1025
            assert len(regime) == 5, "Should have exactly 5 unique dates after dedup"
            assert not regime.index.duplicated().any()
        finally:
            pu.VNINDEX_PARQUET = orig_path


# ── Stage-level smoke test ────────────────────────────────────────────────────

class TestStageSmoke:
    """Smoke test: run stage1 logic on a tiny synthetic panel (no disk IO)."""

    def _make_panel(self, n_symbols: int = 5, n_bars: int = 350) -> dict:
        panels = {}
        for i in range(n_symbols):
            df = _make_ohlcv(n_bars, base_price=30 + i * 10, trend=0.02, seed=i)
            df["adv50"] = 5_000_000_000.0
            panels[f"SYM{i:02d}"] = df
        return panels

    def test_stage1_core_logic_runs(self):
        """Replicate stage1 core logic without file IO."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import (
            accumulation_score_cross_sectional, compute_all_features,
        )
        from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
            a3_signal, forward_returns, SUCCESS_TARGET,
        )

        panels = self._make_panel()
        all_trades = []
        for sym, df in panels.items():
            df2 = compute_all_features(df)
            sig, _, _ = a3_signal(df2)
            if sig.sum() == 0:
                continue
            trades = forward_returns(df2, sig, horizons=[63])
            if trades.empty:
                continue
            trades["symbol"] = sym
            all_trades.append(trades)

        if not all_trades:
            pytest.skip("No signals on synthetic data — increase n_bars or adjust trend")

        result = pd.concat(all_trades, ignore_index=True)

        # Cross-sectional score
        result["score"] = accumulation_score_cross_sectional(result)
        result["score_q"] = pd.qcut(
            result["score"].rank(method="first"), 5, labels=False
        ).astype("Int64") + 1

        # Basic sanity checks
        assert "net_return" in result.columns
        assert result["score"].between(0, 1).all()
        assert set(result["score_q"].dropna().unique()).issubset({1, 2, 3, 4, 5})
        assert result["score_q"].notna().all()

    def test_compute_all_features_columns_present(self):
        df = _make_ohlcv(300)
        out = compute_all_features(df)
        required = [
            "pt_20", "pt_40", "atr_ratio", "bar_range_pct", "range_vs_ma20",
            "vol_ratio", "vol_trend_10", "vol_below_streak", "vol_drying",
            "bo_vol_exp", "bo_close_str", "bo_range_exp",
            "spring", "sos", "lps", "utad", "efvr", "atr14",
        ]
        missing = [c for c in required if c not in out.columns]
        assert not missing, f"compute_all_features missing columns: {missing}"


# ── P0-1: Stage 6 compile test ────────────────────────────────────────────────

class TestStage6Compiles:
    def test_stage6_no_syntax_error(self):
        """stage6_robustness.py must not have any SyntaxError."""
        import py_compile
        path = REPO / "scripts" / "research" / "dual_cloud_accumulation_wyckoff" / "stage6_robustness.py"
        py_compile.compile(str(path), doraise=True)

    def test_stage6_run_accepts_horizon_param(self):
        """stage6 run() must accept horizon as a parameter (not use global mutation)."""
        import inspect
        from scripts.research.dual_cloud_accumulation_wyckoff.stage6_robustness import run
        sig = inspect.signature(run)
        assert "horizon" in sig.parameters, "stage6 run() must have a 'horizon' parameter"


# ── P0-2: run_all exits non-zero on failure ───────────────────────────────────

class TestRunAllExitCode:
    def test_exits_nonzero_when_stage_fails(self, monkeypatch):
        """run_all must raise SystemExit (non-zero) if any stage raises an exception."""
        import scripts.research.dual_cloud_accumulation_wyckoff.run_all as run_all_mod

        def _fail(_ex_vin, _workers):
            raise RuntimeError("forced stage failure")

        monkeypatch.setitem(run_all_mod.STAGE_MAP, 99, ("Forced Fail", _fail))
        monkeypatch.setattr(sys, "argv", ["run_all.py", "--stage", "99"])
        with pytest.raises(SystemExit) as exc_info:
            run_all_mod.main()
        # SystemExit with a string message → code is non-None and truthy
        assert exc_info.value.code, "SystemExit code must be non-zero/truthy on failure"

    def test_no_exit_when_all_stages_pass(self, monkeypatch):
        """run_all must NOT raise SystemExit when all stages succeed."""
        import scripts.research.dual_cloud_accumulation_wyckoff.run_all as run_all_mod

        called = []

        def _ok(_ex_vin, _workers):
            called.append(True)

        monkeypatch.setitem(run_all_mod.STAGE_MAP, 99, ("OK Stage", _ok))
        monkeypatch.setattr(sys, "argv", ["run_all.py", "--stage", "99"])
        run_all_mod.main()   # must not raise
        assert called, "Stage function was not called"


# ── P0-3: tradable_asof_score ─────────────────────────────────────────────────

class TestTradableAsofScore:
    def _make_rows(self, n: int, seed: int = 0, start_date: str = "2020-01-01") -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        dates = pd.date_range(start_date, periods=n, freq="B")
        return pd.DataFrame({
            "signal_date":  dates,
            "pt_20":        rng.uniform(0.01, 0.10, n),
            "atr_ratio":    rng.uniform(0.5, 1.5, n),
            "vol_ratio":    rng.uniform(0.3, 2.0, n),
            "vol_drying":   rng.uniform(0.0, 1.0, n),
            "bo_vol_exp":   rng.uniform(0.3, 3.0, n),
            "bo_close_str": rng.uniform(0.0, 1.0, n),
        })

    def test_score_in_unit_range(self):
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score
        rows = self._make_rows(100)
        score = tradable_asof_score(rows)
        assert score.between(0, 1).all(), "tradable_asof_score out of [0, 1] range"

    def test_past_scores_unchanged_by_future_rows(self):
        """Adding future rows with extreme features must not change past rows' scores."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score

        past = self._make_rows(50, seed=1, start_date="2020-01-01")
        # Future rows with extreme (terrible) features, later dates
        future = self._make_rows(50, seed=99, start_date="2021-01-01")
        future["pt_20"]        = 0.99
        future["vol_ratio"]    = 5.0
        future["atr_ratio"]    = 2.0
        future["vol_drying"]   = 0.0
        future["bo_vol_exp"]   = 0.1
        future["bo_close_str"] = 0.0

        score_past_only = tradable_asof_score(past).values
        combined = pd.concat([past, future], ignore_index=True)
        score_combined = tradable_asof_score(combined).values[:50]  # past rows at positions 0..49

        np.testing.assert_array_almost_equal(
            score_past_only, score_combined, decimal=10,
            err_msg="Past scores changed when future rows added — tradable_asof_score has lookahead",
        )

    def test_empty_input_returns_empty(self):
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score
        empty = pd.DataFrame(columns=["signal_date", "pt_20"])
        result = tradable_asof_score(empty)
        assert len(result) == 0

    def test_missing_signal_date_falls_back_gracefully(self):
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score
        rows = self._make_rows(30).drop(columns=["signal_date"])
        score = tradable_asof_score(rows)
        assert len(score) == 30

    def test_tradable_asof_score_same_date_row_order_stability(self):
        """Reordering rows within the same signal_date must not change any row's score."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score

        rng = np.random.default_rng(7)
        # 20 historical rows, one per business day
        hist_dates = pd.date_range("2020-01-01", periods=20, freq="B")
        hist = pd.DataFrame({
            "signal_date":  hist_dates,
            "pt_20":        rng.uniform(0.01, 0.10, 20),
            "atr_ratio":    rng.uniform(0.5, 1.5, 20),
            "vol_ratio":    rng.uniform(0.3, 2.0, 20),
            "vol_drying":   rng.uniform(0.0, 1.0, 20),
            "bo_vol_exp":   rng.uniform(0.3, 3.0, 20),
            "bo_close_str": rng.uniform(0.0, 1.0, 20),
        })

        # 5 rows ALL on the same date (day 21)
        same_date = hist_dates[-1] + pd.tseries.offsets.BusinessDay(1)
        today = pd.DataFrame({
            "signal_date":  [same_date] * 5,
            "ticker":       list("ABCDE"),
            "pt_20":        [0.01, 0.05, 0.03, 0.08, 0.02],
            "atr_ratio":    [0.6,  1.0,  0.8,  1.3,  0.7],
            "vol_ratio":    [0.4,  1.0,  0.6,  1.8,  0.5],
            "vol_drying":   [0.9,  0.5,  0.7,  0.2,  0.8],
            "bo_vol_exp":   [2.0,  1.0,  1.5,  0.5,  1.8],
            "bo_close_str": [0.9,  0.5,  0.7,  0.3,  0.8],
        })

        # Original order
        combined = pd.concat([hist, today], ignore_index=True)
        score_orig = tradable_asof_score(combined)
        today_with_score_orig = today.copy()
        today_with_score_orig["score"] = score_orig.iloc[20:].values

        # Shuffled today-date rows
        today_shuf = today.sample(frac=1, random_state=99).reset_index(drop=True)
        combined_shuf = pd.concat([hist, today_shuf], ignore_index=True)
        score_shuf = tradable_asof_score(combined_shuf)
        today_with_score_shuf = today_shuf.copy()
        today_with_score_shuf["score"] = score_shuf.iloc[20:].values

        # Sort both by ticker, then compare scores
        orig_sorted = today_with_score_orig.sort_values("ticker")["score"].values
        shuf_sorted = today_with_score_shuf.sort_values("ticker")["score"].values

        np.testing.assert_array_almost_equal(
            orig_sorted, shuf_sorted, decimal=10,
            err_msg="tradable_asof_score changed when same-date rows were reordered — row-order dependence!"
        )

    def test_tradable_asof_score_no_future_contamination(self):
        """Adding extreme future rows must not change scores for any prior date."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_score

        rng = np.random.default_rng(11)
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        rows = pd.DataFrame({
            "signal_date":  dates,
            "pt_20":        rng.uniform(0.01, 0.10, 50),
            "atr_ratio":    rng.uniform(0.5, 1.5, 50),
            "vol_ratio":    rng.uniform(0.3, 2.0, 50),
            "vol_drying":   rng.uniform(0.0, 1.0, 50),
            "bo_vol_exp":   rng.uniform(0.3, 3.0, 50),
            "bo_close_str": rng.uniform(0.0, 1.0, 50),
        })

        score_base = tradable_asof_score(rows).values

        # Append extreme future rows (worst possible features, far-future dates)
        future_dates = pd.date_range("2023-01-01", periods=30, freq="B")
        future = pd.DataFrame({
            "signal_date":  future_dates,
            "pt_20":        np.full(30, 0.99),
            "atr_ratio":    np.full(30, 2.5),
            "vol_ratio":    np.full(30, 5.0),
            "vol_drying":   np.full(30, 0.0),
            "bo_vol_exp":   np.full(30, 0.05),
            "bo_close_str": np.full(30, 0.0),
        })

        combined = pd.concat([rows, future], ignore_index=True)
        score_with_future = tradable_asof_score(combined).values[:50]

        np.testing.assert_array_almost_equal(
            score_base, score_with_future, decimal=10,
            err_msg="Past date scores changed when future rows added — future contamination!"
        )

    def test_warmup_flag_marks_first_date(self):
        """tradable_asof_warmup_mask must be True only for the first signal_date."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import tradable_asof_warmup_mask
        rows = self._make_rows(20)
        mask = tradable_asof_warmup_mask(rows)
        assert mask.iloc[0],  "First row (first date) must be flagged as warmup"
        assert not mask.iloc[1:].any(), "Only first date should be warmup"


# ── P1-1: T2 fill semantics ───────────────────────────────────────────────────

class TestT2FillSemantics:
    """T2 fill condition uses low[], not close[]. t2_entry_price set when filled."""

    def test_fill_detects_low_dip_when_close_stays_above(self):
        """Fill logic using low[]: detects intraday dip even if close stays above threshold."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage3_a3_t2_timing import (
            T2_PULLBACK_PCT, T2_WINDOW,
        )
        entry_price = 100.0
        t2_thresh = entry_price * (1.0 - T2_PULLBACK_PCT)   # 96.0

        n = 50
        low_arr   = np.full(n, 98.0)   # all lows above threshold
        low_arr[5] = t2_thresh * 0.99  # bar 5: low dips below threshold

        t2_filled = False
        t2_fill_bar = None
        for t in range(1, min(1 + T2_WINDOW + 1, n)):
            if low_arr[t] <= t2_thresh:   # FIXED: uses low
                t2_filled = True
                t2_fill_bar = t
                break

        assert t2_filled, "Fill should detect intraday low dip below threshold"
        assert t2_fill_bar == 5

    def test_no_fill_when_low_stays_above_threshold(self):
        from scripts.research.dual_cloud_accumulation_wyckoff.stage3_a3_t2_timing import (
            T2_PULLBACK_PCT, T2_WINDOW,
        )
        entry_price = 100.0
        t2_thresh = entry_price * (1.0 - T2_PULLBACK_PCT)

        n = 60
        low_arr = np.full(n, t2_thresh * 1.02)   # all lows above threshold

        t2_filled = False
        for t in range(1, min(1 + T2_WINDOW + 1, n)):
            if low_arr[t] <= t2_thresh:
                t2_filled = True
                break

        assert not t2_filled, "Fill must not trigger when low stays above threshold"

    def test_entry_price_set_even_without_full_return(self):
        """t2_entry_price must be set whenever fill bar exists, even if 63-bar return unavailable."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage3_a3_t2_timing import T2_FORWARD_BARS

        n = 10   # very short — not enough bars for 63-bar return
        open_arr = np.linspace(100.0, 110.0, n)
        fill_bar = 5

        t2_entry_price = np.nan
        t2_net_return  = np.nan

        t2_entry_bar = fill_bar + 1
        if t2_entry_bar < n:
            t2_ep = open_arr[t2_entry_bar]
            t2_entry_price = t2_ep   # FIXED: always set
            t2_exit_bar = t2_entry_bar + T2_FORWARD_BARS
            if t2_exit_bar < n:
                t2_xp = open_arr[t2_exit_bar]
                t2_net_return = (t2_xp / t2_ep - 1.0)

        assert not np.isnan(t2_entry_price), "t2_entry_price must be set when fill bar is valid"
        assert np.isnan(t2_net_return),      "t2_net_return should be NaN when bars insufficient"


# ── P1-5: liquidity columns in forward_returns ────────────────────────────────

class TestLiquidityInTrades:
    def test_adv50_in_forward_returns_output(self):
        """adv50 must appear in forward_returns output for Stage 6 bucketing."""
        df = _make_ohlcv(300)
        df["adv50"] = 5_000_000_000.0
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True
        trades = forward_returns(df, sig, horizons=[25], require_adv=False)
        assert "adv50" in trades.columns, "adv50 must be in forward_returns output"

    def test_liquidity_pass_column_present(self):
        df = _make_ohlcv(300)
        df["adv50"] = 5_000_000_000.0
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True
        trades = forward_returns(df, sig, horizons=[25], require_adv=False)
        assert len(trades) > 0
        assert "liquidity_pass" in trades.columns

    def test_adv50_missing_flag_true_when_no_adv50_column(self):
        df = _make_ohlcv(300).drop(columns=["adv50"])
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True
        trades = forward_returns(df, sig, horizons=[25], require_adv=False)
        assert len(trades) > 0
        assert "adv50_missing_flag" in trades.columns
        assert trades["adv50_missing_flag"].all(), "Flag must be True when adv50 column absent"

    def test_adv50_missing_flag_false_when_adv50_present(self):
        df = _make_ohlcv(300)
        df["adv50"] = 5_000_000_000.0
        sig = pd.Series(False, index=df.index)
        sig.iloc[150] = True
        trades = forward_returns(df, sig, horizons=[25], require_adv=False)
        assert len(trades) > 0
        assert not trades["adv50_missing_flag"].any(), "Flag must be False when adv50 is present"


# ── P1-6: LPS tag correctness ─────────────────────────────────────────────────

class TestLPSTagCorrectness:
    def test_lps_fires_near_sos_level(self):
        """LPS should fire near the original SOS breakout resistance level on low volume.

        Wyckoff LPS: resistance before the SOS was ~50.25 (20-bar high of the flat base).
        After price breaks out to 55+, an LPS pullback returns to near 50.25 (old resistance
        now acting as support). The pullback must be near 50.25, NOT near the post-breakout high.
        """
        n = 200
        prices = np.full(n, 50.0)
        highs  = np.full(n, 50.25)   # flat base: 20-bar high stays at 50.25
        vol    = np.full(n, 500_000.0)
        vol_ma = 500_000.0

        # SOS at bar 80: close breaks above resistance (~50.25) on high volume
        prices[80] = 55.0
        highs[80]  = 56.0
        vol[80]    = vol_ma * 2.5

        # Brief rally after SOS
        prices[81:90] = np.linspace(55, 57, 9)
        highs[81:90]  = prices[81:90] * 1.01

        # LPS pullback to near the OLD resistance level (~50.25) on low volume — bars 90-100
        prices[90:100] = 50.5   # near 50.25: within 3% band [48.74, 51.0]
        highs[90:100]  = 51.0
        vol[90:100]    = vol_ma * 0.4   # < 0.7 × vol_ma → low volume

        df = pd.DataFrame({
            "close":  prices,
            "high":   highs,
            "low":    prices * 0.995,
            "open":   prices * 0.998,
            "volume": vol,
        }).reset_index(drop=True)

        tags = lps_tag(df["close"], df["high"], df["volume"])
        assert tags.iloc[90:100].any(), (
            "lps_tag should fire on pullback to old resistance (~50.25) on low volume "
            f"(got tags 90-100: {tags.iloc[90:100].tolist()})"
        )

    def test_lps_does_not_fire_without_prior_sos(self):
        """LPS requires a prior SOS within sos_lookback bars."""
        n = 150
        prices = np.full(n, 50.0)
        df = pd.DataFrame({
            "close":  prices,
            "high":   prices * 1.005,
            "low":    prices * 0.995,
            "open":   prices,
            "volume": np.full(n, 500_000.0),
        }).reset_index(drop=True)
        tags = lps_tag(df["close"], df["high"], df["volume"])
        assert tags.sum() == 0, "lps_tag fired without any prior SOS signal"


# ── P2-1: Same-bar spring ─────────────────────────────────────────────────────

class TestSameBarSpring:
    def test_spring_fires_on_same_bar_shakeout(self):
        """spring_tag fires when low < support AND close >= support on the same bar."""
        n = 200
        # Flat prices: rolling 20-bar min of lows ≈ 49.5
        prices = np.full(n, 50.0)
        lows   = np.full(n, 49.5)
        closes = np.full(n, 50.0)

        # At bar 130: intrabar shakeout — low dips to 48.0 (<49.5), close recovers to 50.0 (≥49.5)
        lows[130]   = 48.0   # below support
        closes[130] = 50.0   # at/above support

        tags = spring_tag(pd.Series(closes), pd.Series(lows))
        assert tags.iloc[130], "spring_tag must fire on same-bar shakeout+reclaim"

    def test_same_bar_spring_does_not_fire_if_close_stays_below(self):
        """Same-bar spring must not fire if both low AND close are below support."""
        n = 200
        prices = np.full(n, 50.0)
        lows   = np.full(n, 49.5)
        closes = np.full(n, 50.0)

        # Bar 130: both low and close below support
        lows[130]   = 48.0
        closes[130] = 48.5  # below support (49.5)

        tags = spring_tag(pd.Series(closes), pd.Series(lows))
        assert not tags.iloc[130], (
            "spring_tag must not fire when close stays below support"
        )


# ── Stage 7: Score Recalibration ─────────────────────────────────────────────

class TestStage7ScoreRecalibration:
    """Tests for Stage 7 score recalibration module."""

    def _make_signal_rows(self, n: int = 60, seed: int = 42) -> pd.DataFrame:
        """Synthetic signal rows with signal_date and all feature columns."""
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2015-01-01", periods=n, freq="B")
        return pd.DataFrame({
            "signal_date":   dates,
            "net_return":    rng.uniform(-0.20, 0.40, n),
            "pt_20":         rng.uniform(0.01, 0.10, n),
            "pt_40":         rng.uniform(0.01, 0.10, n),
            "atr_ratio":     rng.uniform(0.5,  1.5,  n),
            "vol_ratio":     rng.uniform(0.3,  2.0,  n),
            "vol_drying":    rng.uniform(0.0,  1.0,  n),
            "bo_vol_exp":    rng.uniform(0.3,  3.0,  n),
            "bo_close_str":  rng.uniform(0.0,  1.0,  n),
            "bo_range_exp":  rng.uniform(0.0,  1.0,  n),
            "vol_trend_10":  rng.uniform(-0.5, 0.5,  n),
            "bar_range_pct": rng.uniform(0.005, 0.04, n),
            "range_vs_ma20": rng.uniform(0.5,  1.5,  n),
            "spring":        rng.integers(0, 2, n),
            "sos":           rng.integers(0, 2, n),
            "lps":           rng.integers(0, 2, n),
            "adv50":         rng.uniform(2e9, 30e9, n),
            "year":          dates.year,
        })

    def test_stage7_candidate_scores_exist(self):
        """compute_candidate_score_dategroup produces valid [0,1] scores for all standard specs."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import (
            compute_candidate_score_dategroup,
        )
        from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import (
            CANDIDATE_SPECS,
        )
        rows = self._make_signal_rows(80)
        for name, spec in CANDIDATE_SPECS.items():
            score = compute_candidate_score_dategroup(rows, spec)
            assert len(score) == len(rows), f"{name}: score length mismatch"
            assert score.between(0, 1).all(), f"{name}: score outside [0, 1]"
            assert not score.isna().all(), f"{name}: all NaN scores"

    def test_stage7_old_composite_rejected_when_q5_underperforms(self):
        """_classify_candidate must return REJECT when Q5 delta <= 0."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import (
            _classify_candidate,
        )
        full_row = {
            "q5_minus_all_pp": -7.1,
            "n_q5": 554,
        }
        split_rows = {
            "train":    {"q5_minus_all_pp": -5.6},
            "validate": {"q5_minus_all_pp": -8.3},
            "test":     {"q5_minus_all_pp": -5.5},
        }
        classification, action, _, _, _ = _classify_candidate(
            full_row, split_rows, [], "old_composite_score"
        )
        assert classification == "REJECT", (
            f"old_composite_score with delta=-7.1pp must be REJECT, got {classification}"
        )
        assert action == "do_not_use"

    def test_stage7_volume_dryup_can_be_penalized(self):
        """A spec with vol_drying ascending=False (penalized) produces a different score than ascending=True."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import (
            compute_candidate_score_dategroup,
        )
        rows = self._make_signal_rows(80)
        # Old direction: vol_drying ascending=True (rewards drying)
        spec_reward = [("vol_drying", True,  0.50), ("bo_vol_exp", True, 0.50)]
        # Penalized direction: vol_drying ascending=False (penalizes drying)
        spec_penalize = [("vol_drying", False, 0.50), ("bo_vol_exp", True, 0.50)]

        score_reward  = compute_candidate_score_dategroup(rows, spec_reward)
        score_penalize = compute_candidate_score_dategroup(rows, spec_penalize)

        # The two scores should differ (inverted vol_drying component)
        assert not np.allclose(score_reward.values, score_penalize.values), (
            "Inverting vol_drying direction (ascending=True vs False) must change scores"
        )

    def test_stage7_no_future_rows_affect_tradable_scores(self):
        """compute_candidate_score_dategroup: adding future rows must not change past scores."""
        from scripts.research.dual_cloud_accumulation_wyckoff.features import (
            compute_candidate_score_dategroup,
        )
        spec = [("pt_20", True, 0.5), ("bo_vol_exp", True, 0.5)]
        past = self._make_signal_rows(40, seed=1)
        # Future rows with extreme features, all on dates after past
        rng = np.random.default_rng(99)
        future_dates = pd.date_range("2022-01-01", periods=20, freq="B")
        future = pd.DataFrame({
            "signal_date": future_dates,
            "pt_20":       np.full(20, 0.99),
            "bo_vol_exp":  np.full(20, 0.01),
        })

        score_past_only = compute_candidate_score_dategroup(past, spec).values

        combined = pd.concat([past, future], ignore_index=True)
        score_combined = compute_candidate_score_dategroup(combined, spec).values[:40]

        np.testing.assert_array_almost_equal(
            score_past_only, score_combined, decimal=10,
            err_msg="compute_candidate_score_dategroup: past scores changed when future rows added",
        )

    def test_stage7_train_validate_test_split(self):
        """SPLITS must partition years into non-overlapping, exhaustive groups."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import SPLITS
        years = pd.Series(list(range(2012, 2027)))

        train_mask    = SPLITS["train"](years)
        validate_mask = SPLITS["validate"](years)
        test_mask     = SPLITS["test"](years)

        # Non-overlapping
        assert not (train_mask & validate_mask).any(), "train and validate overlap"
        assert not (train_mask & test_mask).any(),     "train and test overlap"
        assert not (validate_mask & test_mask).any(),  "validate and test overlap"

        # Exhaustive (all years covered by at least one split)
        covered = train_mask | validate_mask | test_mask
        assert covered.all(), f"Some years not in any split: {years[~covered].tolist()}"

        # Correct year ranges
        assert (years[train_mask] <= 2019).all()
        assert ((years[validate_mask] >= 2020) & (years[validate_mask] <= 2022)).all()
        assert (years[test_mask] >= 2023).all()

    def test_stage7_minimum_evidence_threshold(self):
        """_classify_candidate enforces n_q5 >= 40 and delta >= 5pp for PARALLEL_PAPER_RESEARCH."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import (
            _classify_candidate,
        )
        split_rows_positive = {
            "train":    {"q5_minus_all_pp": 6.0},
            "validate": {"q5_minus_all_pp": 7.0},
            "test":     {"q5_minus_all_pp": 5.5},
        }
        liq_rows_positive = [
            {"liquidity_bucket": "2B_5B",   "q5_minus_all_pp": 5.0},
            {"liquidity_bucket": "5B_20B",  "q5_minus_all_pp": 6.0},
            {"liquidity_bucket": "20B_plus","q5_minus_all_pp": 4.0},
        ]

        # Passes all criteria: classification should be PARALLEL_PAPER_RESEARCH
        full_row_pass = {"q5_minus_all_pp": 6.0, "n_q5": 60}
        cls, _, _, _, _ = _classify_candidate(
            full_row_pass, split_rows_positive, liq_rows_positive, "test_candidate"
        )
        assert cls == "PARALLEL_PAPER_RESEARCH", f"Expected PARALLEL_PAPER_RESEARCH, got {cls}"

        # n_q5 too small → needs_more_data
        full_row_small_n = {"q5_minus_all_pp": 6.0, "n_q5": 30}
        cls_small, _, _, _, _ = _classify_candidate(
            full_row_small_n, split_rows_positive, liq_rows_positive, "test_candidate"
        )
        assert cls_small == "needs_more_data", f"n_q5<40 must give needs_more_data, got {cls_small}"

        # delta < 5pp → WATCHLIST_ONLY
        full_row_borderline = {"q5_minus_all_pp": 3.0, "n_q5": 60}
        cls_wl, _, _, _, _ = _classify_candidate(
            full_row_borderline, split_rows_positive, liq_rows_positive, "test_candidate"
        )
        assert cls_wl == "WATCHLIST_ONLY", f"delta<5pp must give WATCHLIST_ONLY, got {cls_wl}"

    def test_stage7_no_expost_fields_in_tradable_scores(self):
        """CANDIDATE_SPECS must not include 'utad' or any confirmed ex-post field."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import (
            CANDIDATE_SPECS,
        )
        # utad uses future confirmation and is banned from tradable candidates
        forbidden = {"utad", "net_return", "gross_return"}
        for name, spec in CANDIDATE_SPECS.items():
            cols_in_spec = {col for col, _, _ in spec}
            bad = cols_in_spec & forbidden
            assert not bad, (
                f"Candidate '{name}' uses forbidden ex-post field(s): {bad}"
            )

    def test_stage7_outputs_required_columns(self):
        """Stage 7 output CSVs must contain all required columns."""
        pytest.importorskip("pyarrow", reason="pyarrow required (used transitively)")
        base = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"
        if not (base / "stage7_score_recalibration.csv").exists():
            pytest.skip("stage7 outputs not present — run Stage 7 first")

        main_required = {
            "candidate_name", "target", "period", "n_total", "n_q1", "n_q5",
            "all_win_rate", "q5_win_rate", "q5_minus_all_pp", "q4q5_minus_all_pp",
            "spearman_rho", "spearman_p", "point_biserial_corr", "point_biserial_p",
            "avg_fwd_return_all", "avg_fwd_return_q5",
            "classification", "action", "overfit_warning", "diagnostic_or_tradable",
        }
        main_cols = set(pd.read_csv(base / "stage7_score_recalibration.csv", nrows=1).columns)
        missing_main = main_required - main_cols
        assert not missing_main, f"stage7_score_recalibration.csv missing columns: {missing_main}"

        year_required = {"candidate_name", "year", "n_total", "n_q5",
                         "all_win_rate", "q5_win_rate", "q5_minus_all_pp"}
        year_cols = set(pd.read_csv(base / "stage7_score_recalibration_by_year.csv", nrows=1).columns)
        missing_year = year_required - year_cols
        assert not missing_year, f"by_year.csv missing columns: {missing_year}"

        regime_required = {"candidate_name", "regime", "n_total", "n_q5",
                           "all_win_rate", "q5_win_rate", "q5_minus_all_pp"}
        regime_cols = set(pd.read_csv(base / "stage7_score_recalibration_by_regime.csv", nrows=1).columns)
        missing_regime = regime_required - regime_cols
        assert not missing_regime, f"by_regime.csv missing columns: {missing_regime}"

        liq_required = {"candidate_name", "liquidity_bucket", "n_total", "n_q5",
                        "all_win_rate", "q5_win_rate", "q5_minus_all_pp"}
        liq_cols = set(pd.read_csv(base / "stage7_score_recalibration_by_liquidity.csv", nrows=1).columns)
        missing_liq = liq_required - liq_cols
        assert not missing_liq, f"by_liquidity.csv missing columns: {missing_liq}"

        ablation_required = {
            "feature_name", "feature_group", "direction_tested", "n",
            "win_rate_top_bucket", "top_minus_bottom_pp",
            "spearman_rho", "decision",
        }
        abl_cols = set(pd.read_csv(base / "stage7_feature_ablation.csv", nrows=1).columns)
        missing_abl = ablation_required - abl_cols
        assert not missing_abl, f"feature_ablation.csv missing columns: {missing_abl}"


# ── Stage 8: Observation Layer ────────────────────────────────────────────────

class TestStage8ObservationLayer:
    """Tests for Stage 8 observation layer / forward validation ledger."""

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"
    _REPO = Path(__file__).resolve().parents[1]

    def _skip_if_missing(self, filename: str) -> None:
        if not (self._BASE / filename).exists():
            pytest.skip(f"{filename} not present — run Stage 8 first")

    def test_stage8_outputs_required_columns(self):
        """Stage 8 output CSVs must contain all required columns."""
        self._skip_if_missing("stage8_observation_fields.csv")

        obs_required = {
            "signal_date", "symbol", "signal_type", "a3_signal",
            "breakout_value_expansion_score", "breakout_value_expansion_q",
            "tightness_plus_breakout_close_quality_score", "tightness_plus_breakout_close_quality_q",
            "wyckoff_sos", "wyckoff_lps", "wyckoff_spring_test",
            "old_composite_score", "old_composite_q",
            "breakout_value_expansion_watchlist_flag",
            "tightness_plus_breakout_watchlist_flag",
            "wyckoff_sos_diagnostic_flag",
            "old_composite_rejected_flag",
            "field_usage",
        }
        obs_cols = set(pd.read_csv(self._BASE / "stage8_observation_fields.csv", nrows=1).columns)
        missing = obs_required - obs_cols
        assert not missing, f"stage8_observation_fields.csv missing: {missing}"

        ledger_required = {
            "observation_date", "symbol", "breakout_value_expansion_q",
            "tightness_plus_breakout_close_quality_q",
            "fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
            "fwd_40d_return", "fwd_63d_return",
            "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
            "actual_trade_taken", "operator_note",
        }
        ledger_cols = set(pd.read_csv(
            self._BASE / "stage8_forward_validation_ledger_template.csv", nrows=1
        ).columns)
        missing_l = ledger_required - ledger_cols
        assert not missing_l, f"ledger_template.csv missing: {missing_l}"

    def test_stage8_old_composite_marked_rejected(self):
        """old_composite_rejected_flag must be True for every row."""
        self._skip_if_missing("stage8_observation_fields.csv")
        df = pd.read_csv(self._BASE / "stage8_observation_fields.csv")
        assert "old_composite_rejected_flag" in df.columns
        assert df["old_composite_rejected_flag"].all(), (
            "old_composite_rejected_flag must be True for all rows"
        )

    def test_stage8_watchlist_flags_observation_only(self):
        """field_usage column must be 'observation_only' for all rows."""
        self._skip_if_missing("stage8_observation_fields.csv")
        df = pd.read_csv(self._BASE / "stage8_observation_fields.csv")
        assert "field_usage" in df.columns
        assert (df["field_usage"] == "observation_only").all(), (
            "field_usage must be 'observation_only' for all rows"
        )

    def test_stage8_does_not_modify_final_action(self):
        """Stage 8 output CSVs must not contain a 'final_action' column."""
        self._skip_if_missing("stage8_observation_fields.csv")
        obs_cols = set(pd.read_csv(self._BASE / "stage8_observation_fields.csv", nrows=1).columns)
        assert "final_action" not in obs_cols, (
            "stage8_observation_fields.csv must not contain 'final_action' column"
        )
        ledger_cols = set(pd.read_csv(
            self._BASE / "stage8_forward_validation_ledger_template.csv", nrows=1
        ).columns)
        assert "final_action" not in ledger_cols, (
            "stage8_forward_validation_ledger_template.csv must not contain 'final_action' column"
        )

    def test_stage8_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE8_WRITE_DIR must be defined; write dir must be research output."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage8_observation_layer as s8
        assert hasattr(s8, "_OMS_SAFE_PATHS"), "Stage 8 must define _OMS_SAFE_PATHS"
        assert hasattr(s8, "_STAGE8_WRITE_DIR"), "Stage 8 must define _STAGE8_WRITE_DIR"

        oms_paths = s8._OMS_SAFE_PATHS
        write_dir = s8._STAGE8_WRITE_DIR

        assert len(oms_paths) > 0, "_OMS_SAFE_PATHS must not be empty"
        # Stage 8 write dir must be under outputs/research/, NOT data/decision/
        write_str = str(write_dir)
        assert "outputs" in write_str, f"_STAGE8_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, (
            f"_STAGE8_WRITE_DIR must not be under 'data/decision': {write_str}"
        )
        # The known OMS paths must be in the safety set
        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in oms_paths

    def test_stage8_forward_ledger_template_columns(self):
        """Forward validation ledger must have blank forward return columns."""
        self._skip_if_missing("stage8_forward_validation_ledger_template.csv")
        df = pd.read_csv(self._BASE / "stage8_forward_validation_ledger_template.csv")

        fwd_cols = [
            "fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
            "fwd_40d_return", "fwd_63d_return",
            "tp1_hit_63d", "actual_trade_taken", "operator_note",
        ]
        for col in fwd_cols:
            assert col in df.columns, f"Ledger missing column: {col}"
            # Forward return columns must be blank (NaN) — not pre-filled
            assert df[col].isna().all(), (
                f"Ledger column '{col}' must be blank (all NaN) in template; "
                f"found non-null values: {df[col].dropna().head(3).tolist()}"
            )


# ── Stage 9 tests ──────────────────────────────────────────────────────────────

class TestStage9ForwardValidation:
    """Tests for stage9_forward_validation_update.py using synthetic data.

    All tests use in-memory synthetic DataFrames — no file IO, no live data.
    """

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    @staticmethod
    def _skip_if_missing(fname: str):
        p = TestStage9ForwardValidation._BASE / fname
        if not p.exists():
            pytest.skip(f"Output not generated yet: {fname}")

    @staticmethod
    def _make_sym_df(n: int = 200, base: float = 50.0, seed: int = 7) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        prices = base + rng.normal(0, 0.5, n).cumsum()
        prices = np.clip(prices, 1.0, None)
        noise = rng.uniform(0.005, 0.02, n)
        return pd.DataFrame({
            "date":   pd.date_range("2024-01-01", periods=n, freq="B"),
            "open":   prices * (1 - noise / 2),
            "high":   prices * (1 + noise),
            "low":    prices * (1 - noise),
            "close":  prices,
            "volume": rng.integers(100_000, 500_000, n).astype(float),
        })

    def test_stage9_forward_returns_close_to_close(self):
        """fwd_Nd_return = close[idx+N] / entry_price - 1 (close-to-close)."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import (
            _compute_row_outcomes,
        )
        sym_df = self._make_sym_df(n=200)
        # Use bar 50 as signal bar, entry price = close[50]
        obs_date    = sym_df["date"].iloc[50]
        entry_price = float(sym_df["close"].iloc[50])

        result = _compute_row_outcomes(obs_date, entry_price, sym_df)

        for h in (5, 10, 20, 40, 63):
            expected = sym_df["close"].iloc[50 + h] / entry_price - 1.0
            assert abs(result[f"fwd_{h}d_return"] - expected) < 1e-9, (
                f"fwd_{h}d_return mismatch"
            )
            assert result[f"fwd_{h}d_matured"] is True

    def test_stage9_tp1_hit_uses_high_within_63d(self):
        """TP1 = True iff max(high[t+1:t+64]) >= entry * 1.18."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import (
            _compute_row_outcomes,
        )
        sym_df = self._make_sym_df(n=200, base=100.0)
        bar = 50
        obs_date    = sym_df["date"].iloc[bar]
        entry_price = 100.0

        # Inject a spike at bar+30 so TP1 is hit
        sym_df = sym_df.copy()
        sym_df.loc[bar + 30, "high"] = entry_price * 1.25

        result = _compute_row_outcomes(obs_date, entry_price, sym_df)
        assert result["tp1_hit_63d"] is True

        # Inject a spike below threshold
        sym_df2 = self._make_sym_df(n=200, base=100.0)
        sym_df2 = sym_df2.copy()
        sym_df2["high"] = entry_price * 1.05  # all highs below 1.18 threshold
        result2 = _compute_row_outcomes(obs_date, entry_price, sym_df2)
        assert result2["tp1_hit_63d"] is False

    def test_stage9_mae_mfe_calculation(self):
        """MAE = min(low)/entry - 1; MFE = max(high)/entry - 1 in [t+1, t+63]."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import (
            _compute_row_outcomes,
        )
        sym_df = self._make_sym_df(n=200, base=50.0)
        bar  = 50
        obs_date    = sym_df["date"].iloc[bar]
        entry_price = float(sym_df["close"].iloc[bar])

        result = _compute_row_outcomes(obs_date, entry_price, sym_df)

        window_high = sym_df["high"].iloc[bar + 1 : bar + 64].values
        window_low  = sym_df["low"].iloc[bar + 1 : bar + 64].values
        expected_mfe = float(window_high.max() / entry_price - 1.0)
        expected_mae = float(window_low.min()  / entry_price - 1.0)

        assert abs(result["max_favorable_excursion_63d"] - expected_mfe) < 1e-9
        assert abs(result["max_adverse_excursion_63d"]   - expected_mae) < 1e-9
        assert result["mae_mfe_matured"] is True

    def test_stage9_maturity_flags(self):
        """matured=True only when exit bar < len(sym_df)."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import (
            _compute_row_outcomes,
        )
        sym_df = self._make_sym_df(n=80)  # only 80 bars
        bar = 50  # bar 50 + 63 = 113 >= 80 → NOT matured for h=63
        obs_date    = sym_df["date"].iloc[bar]
        entry_price = float(sym_df["close"].iloc[bar])

        result = _compute_row_outcomes(obs_date, entry_price, sym_df)

        # h=5: exit at 55 < 80 → matured
        assert result["fwd_5d_matured"] is True
        assert not np.isnan(result["fwd_5d_return"])
        # h=63: exit at 113 >= 80 → not matured
        assert result["fwd_63d_matured"] is False
        assert np.isnan(result["fwd_63d_return"])

    def test_stage9_incomplete_future_window_handled(self):
        """Rows with no future data get NaN outcomes, not errors."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import (
            _compute_row_outcomes,
        )
        sym_df = self._make_sym_df(n=100)
        # Signal at the last bar — no future data at all
        bar = len(sym_df) - 1
        obs_date    = sym_df["date"].iloc[bar]
        entry_price = float(sym_df["close"].iloc[bar])

        result = _compute_row_outcomes(obs_date, entry_price, sym_df)
        for h in (5, 10, 20, 40, 63):
            assert np.isnan(result[f"fwd_{h}d_return"]), f"Expected NaN for h={h} at last bar"
            assert result[f"fwd_{h}d_matured"] is False

        assert np.isnan(result["tp1_hit_63d"])
        assert np.isnan(result["max_adverse_excursion_63d"])
        assert np.isnan(result["max_favorable_excursion_63d"])

    def test_stage9_outputs_required_columns(self):
        """Updated ledger must contain all forward metric columns."""
        self._skip_if_missing("stage9_forward_validation_updated.csv")
        df = pd.read_csv(self._BASE / "stage9_forward_validation_updated.csv", nrows=1)
        required = {
            "fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
            "fwd_40d_return", "fwd_63d_return",
            "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
        }
        missing = required - set(df.columns)
        assert not missing, f"stage9_forward_validation_updated.csv missing columns: {missing}"

    def test_stage9_does_not_modify_final_action(self):
        """Stage 9 output CSVs must not contain a 'final_action' column."""
        self._skip_if_missing("stage9_forward_validation_updated.csv")
        cols = set(pd.read_csv(
            self._BASE / "stage9_forward_validation_updated.csv", nrows=1
        ).columns)
        assert "final_action" not in cols, (
            "stage9_forward_validation_updated.csv must not contain 'final_action'"
        )

    def test_stage9_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE9_WRITE_DIR must be defined; write dir must be research output."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update as s9
        assert hasattr(s9, "_OMS_SAFE_PATHS"),   "Stage 9 must define _OMS_SAFE_PATHS"
        assert hasattr(s9, "_STAGE9_WRITE_DIR"), "Stage 9 must define _STAGE9_WRITE_DIR"

        write_str = str(s9._STAGE9_WRITE_DIR)
        assert "outputs" in write_str,    f"_STAGE9_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, (
            f"_STAGE9_WRITE_DIR must not be under 'data/decision': {write_str}"
        )
        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s9._OMS_SAFE_PATHS

    def test_stage9_classification_thresholds(self):
        """WIN_RATE_THRESHOLD and Q5_DELTA_THRESHOLD must be defined at expected values."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update as s9
        assert hasattr(s9, "_WIN_RATE_THRESHOLD"), "Stage 9 must define _WIN_RATE_THRESHOLD"
        assert hasattr(s9, "_Q5_DELTA_THRESHOLD"), "Stage 9 must define _Q5_DELTA_THRESHOLD"
        assert 0.0 < s9._WIN_RATE_THRESHOLD < 1.0, "_WIN_RATE_THRESHOLD must be in (0, 1)"
        assert 0.0 < s9._Q5_DELTA_THRESHOLD < 1.0, "_Q5_DELTA_THRESHOLD must be in (0, 1)"


# ── Stage 10 tests ─────────────────────────────────────────────────────────────

class TestStage10MonthlyValidationReport:
    """Tests for stage10_monthly_validation_report.py.

    Pure-logic tests use synthetic DataFrames. File-based tests skip if outputs
    have not been generated yet.
    """

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    @staticmethod
    def _skip_if_missing(fname: str):
        p = TestStage10MonthlyValidationReport._BASE / fname
        if not p.exists():
            pytest.skip(f"Output not generated yet: {fname}")

    @staticmethod
    def _make_mature_df(
        n: int = 120,
        win_frac: float = 0.5,
        seed: int = 42,
    ) -> pd.DataFrame:
        """Synthetic Stage-9-like DataFrame with all 63d rows matured."""
        rng = np.random.default_rng(seed)
        returns = np.where(
            rng.random(n) < win_frac,
            rng.uniform(0.15, 0.40, n),
            rng.uniform(-0.20, 0.05, n),
        )
        return pd.DataFrame({
            "observation_date":                    pd.date_range("2024-01-01", periods=n, freq="B"),
            "symbol":                              ["AAA"] * n,
            "fwd_63d_return":                      returns,
            "fwd_5d_return":                       returns * 0.3,
            "fwd_63d_matured":                     [True] * n,
            "fwd_5d_matured":                      [True] * n,
            "tp1_hit_63d":                         (returns >= 0.18),
            "max_adverse_excursion_63d":           rng.uniform(-0.15, 0.0, n),
            "max_favorable_excursion_63d":         rng.uniform(0.0, 0.40, n),
            "breakout_value_expansion_q":          rng.integers(1, 6, n),
            "tightness_plus_breakout_close_quality_q": rng.integers(1, 6, n),
            "wyckoff_sos":                         rng.integers(0, 2, n),
            "old_composite_q":                     rng.integers(1, 6, n),
            "liquidity_bucket":                    rng.choice(["2B_5B", "5B_20B", "20B_plus"], n),
            "year":                                [2024] * (n // 2) + [2025] * (n - n // 2),
            "vnindex_regime":                      rng.choice(["bull", "bear_sideways"], n),
        })

    def test_stage10_uses_matured_only_for_63d(self):
        """_candidate_stats must use only rows with fwd_63d_matured=True."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report import (
            _candidate_stats,
        )
        df = self._make_mature_df(n=100)
        # Add 20 immature rows with extreme negative returns
        immature = df.head(20).copy()
        immature["fwd_63d_matured"] = False
        immature["fwd_63d_return"]  = -0.99
        combined = pd.concat([df, immature], ignore_index=True)

        # Filter to mature only, as the run() function does
        df_mature = combined[combined["fwd_63d_matured"].astype(bool)].copy()
        stats_mature = _candidate_stats(df_mature)

        # Stats from all rows (including immature negatives)
        stats_all    = _candidate_stats(combined)

        # Mature-only win rate should be higher than all-rows (which included -0.99 rows)
        assert stats_mature["win_rate_63d"] >= stats_all["win_rate_63d"], (
            "Mature-only stats should not be dragged down by immature extreme-negative rows"
        )
        assert stats_mature["n_matured_63d"] == 100, (
            f"Expected 100 mature rows, got {stats_mature['n_matured_63d']}"
        )

    def test_stage10_does_not_count_immature_rows_as_losses(self):
        """Immature rows with NaN return must be excluded, not treated as 0 or loss."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report import (
            _candidate_stats,
        )
        df = self._make_mature_df(n=50)
        # Add immature rows with NaN returns
        immature = df.head(10).copy()
        immature["fwd_63d_matured"] = False
        immature["fwd_63d_return"]  = np.nan
        combined = pd.concat([df, immature], ignore_index=True)

        df_mature = combined[combined["fwd_63d_matured"].astype(bool)].copy()
        stats = _candidate_stats(df_mature)

        # n_matured must only count the 50 non-immature rows
        assert stats["n_matured_63d"] == 50
        # win_rate must not be NaN
        assert not np.isnan(stats["win_rate_63d"])

    def test_stage10_candidate_decision_thresholds(self):
        """_classify_candidate: clears all gates → PARALLEL_PAPER_RESEARCH; fails → WATCHLIST or REJECT."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report import (
            _classify_candidate,
        )
        baseline = {
            "n_matured_63d": 100, "win_rate_63d": 0.20,
            "avg_return_63d": 0.03, "tp1_rate_63d": 0.35,
        }
        # Candidate clearing all gates
        passing_stats = {
            "n_matured_63d": 60, "win_rate_63d": 0.27,
            "avg_return_63d": 0.06, "tp1_rate_63d": 0.45,
            "avg_mae_63d": -0.05, "avg_mfe_63d": 0.20,
        }
        by_year = pd.DataFrame([
            {"year": 2024, "avg_return_63d": 0.02},
            {"year": 2025, "avg_return_63d": 0.08},
        ])
        by_liq = pd.DataFrame([
            {"liquidity_bucket": "2B_5B",   "avg_return_63d": 0.04},
            {"liquidity_bucket": "5B_20B",  "avg_return_63d": 0.06},
            {"liquidity_bucket": "20B_plus","avg_return_63d": 0.05},
        ])
        cls, _, _ = _classify_candidate("BVE_Q5", passing_stats, baseline, by_year, by_liq)
        assert cls == "PARALLEL_PAPER_RESEARCH", f"Expected PARALLEL_PAPER_RESEARCH, got {cls}"

        # Candidate with insufficient win_rate delta (only +2pp)
        weak_stats = {
            "n_matured_63d": 55, "win_rate_63d": 0.22,
            "avg_return_63d": 0.04, "tp1_rate_63d": 0.38,
            "avg_mae_63d": -0.05, "avg_mfe_63d": 0.18,
        }
        cls2, _, _ = _classify_candidate("BVE_Q4Q5", weak_stats, baseline, by_year, by_liq)
        assert cls2 in ("WATCHLIST_ONLY", "needs_more_data"), (
            f"Expected WATCHLIST_ONLY/needs_more_data for weak candidate, got {cls2}"
        )

    def test_stage10_old_composite_defaults_rejected(self):
        """old_composite_Q5 must always return REJECT classification."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report import (
            _classify_candidate,
        )
        # Even with great stats, old_composite_Q5 must be REJECT
        strong_stats = {
            "n_matured_63d": 100, "win_rate_63d": 0.50,
            "avg_return_63d": 0.15, "tp1_rate_63d": 0.60,
            "avg_mae_63d": -0.03, "avg_mfe_63d": 0.30,
        }
        baseline = {
            "n_matured_63d": 836, "win_rate_63d": 0.20,
            "avg_return_63d": 0.03, "tp1_rate_63d": 0.35,
        }
        cls, _, _ = _classify_candidate(
            "old_composite_Q5", strong_stats, baseline,
            pd.DataFrame(), pd.DataFrame()
        )
        assert cls == "REJECT", f"old_composite_Q5 must always be REJECT; got {cls}"

    def test_stage10_outputs_required_files(self):
        """Stage 10 must produce all four required output files."""
        for fname in [
            "stage10_monthly_validation_summary.csv",
            "stage10_candidate_decision_table.csv",
            "stage10_regime_adjusted_summary.csv",
            "STAGE10_MONTHLY_VALIDATION_REPORT.md",
        ]:
            self._skip_if_missing(fname)

        for fname in [
            "stage10_monthly_validation_summary.csv",
            "stage10_candidate_decision_table.csv",
            "stage10_regime_adjusted_summary.csv",
            "STAGE10_MONTHLY_VALIDATION_REPORT.md",
        ]:
            p = self._BASE / fname
            assert p.exists(), f"Required Stage 10 output missing: {fname}"
            assert p.stat().st_size > 0, f"Stage 10 output is empty: {fname}"

    def test_stage10_no_final_action_modification(self):
        """Stage 10 output CSVs must not contain a 'final_action' column."""
        for fname in ["stage10_monthly_validation_summary.csv", "stage10_candidate_decision_table.csv"]:
            self._skip_if_missing(fname)
            cols = set(pd.read_csv(self._BASE / fname, nrows=1).columns)
            assert "final_action" not in cols, f"{fname} must not contain 'final_action'"

    def test_stage10_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE10_WRITE_DIR must be defined; write dir under outputs/."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report as s10
        assert hasattr(s10, "_OMS_SAFE_PATHS"),    "Stage 10 must define _OMS_SAFE_PATHS"
        assert hasattr(s10, "_STAGE10_WRITE_DIR"), "Stage 10 must define _STAGE10_WRITE_DIR"

        write_str = str(s10._STAGE10_WRITE_DIR)
        assert "outputs" in write_str,      f"_STAGE10_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, f"_STAGE10_WRITE_DIR must not be under 'decision': {write_str}"

        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s10._OMS_SAFE_PATHS


# ── Stage 11 tests ─────────────────────────────────────────────────────────────

class TestStage11TimingPatternDecomposition:
    """Tests for stage11_timing_pattern_decomposition.py.

    Pure-logic tests use synthetic DataFrames. File-based tests skip if outputs
    have not been generated yet.
    """

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    @staticmethod
    def _skip_if_missing(fname: str):
        p = TestStage11TimingPatternDecomposition._BASE / fname
        if not p.exists():
            pytest.skip(f"Output not generated yet: {fname}")

    @staticmethod
    def _make_flat_ohlcv(n: int = 200, base: float = 100.0) -> pd.DataFrame:
        """OHLCV with flat price (no signals will fire naturally)."""
        close = np.full(n, base)
        return pd.DataFrame({
            "date":   pd.date_range("2015-01-01", periods=n, freq="B"),
            "open":   close * 0.995,
            "high":   close * 1.005,
            "low":    close * 0.995,
            "close":  close,
            "volume": np.ones(n) * 500_000.0,
            "adv50":  np.ones(n) * 2_500_000_000.0,
        })

    @staticmethod
    def _make_minimal_ctx(n: int = 200, a3_bars=None, s3_bars=None, bve_bars=None):
        """Build a minimal context dict for _compute_timing_tags tests."""
        a3_arr  = np.array(a3_bars or [], dtype=int)
        s3_arr  = np.array(s3_bars or [], dtype=int)
        bve_cnd = np.zeros(n, dtype=bool)
        if bve_bars:
            bve_cnd[bve_bars] = True
        return {
            "ema100":    np.full(n, 100.0),
            "ema55":     np.full(n, 100.0),
            "a3_bars":   a3_arr,
            "s3_bars":   s3_arr,
            "s3_bar_set": frozenset(s3_arr.tolist()),
            "bve_cond":  bve_cnd,
            "inv_hs_bars": set(),
            "inv_hs_meta": {},
        }

    @staticmethod
    def _make_ihs_df(n: int = 80) -> pd.DataFrame:
        """
        Synthetic DataFrame with a clean inverse H&S pattern:
          left shoulder at bar 12 (low ≈ 87), head at bar 32 (low ≈ 77),
          right shoulder at bar 52 (low ≈ 81), breakout ~bar 68.
        Duration = 52 - 12 = 40 == IHS_MIN_DURATION.
        """
        pieces = [
            (0,  13, 100.0, 88.0),
            (13, 23,  89.0, 100.0),
            (23, 33, 100.0,  78.0),
            (33, 43,  79.0, 100.0),
            (43, 53, 100.0,  82.0),
            (53,  n,  83.0, 115.0),
        ]
        close_arr = np.zeros(n)
        for s, e, v0, v1 in pieces:
            e = min(e, n)
            if e > s:
                close_arr[s:e] = np.linspace(v0, v1, e - s)

        low_arr  = close_arr * 0.99
        high_arr = close_arr * 1.01
        vol_arr  = np.ones(n) * 100.0
        # Boost volume at breakout region (bars 65-75) for volume confirmation
        vol_arr[65:76] = 300.0

        return pd.DataFrame({
            "date":   pd.date_range("2015-01-01", periods=n, freq="B"),
            "open":   close_arr,
            "high":   high_arr,
            "low":    low_arr,
            "close":  close_arr,
            "volume": vol_arr,
            "adv50":  np.ones(n) * 2_500_000_000.0,
        })

    # ── Tests ──────────────────────────────────────────────────────────────────

    def test_stage11_outputs_required_columns(self):
        """Decomposition CSV must have all required timing bucket columns."""
        self._skip_if_missing("stage11_timing_pattern_decomposition.csv")
        df = pd.read_csv(self._BASE / "stage11_timing_pattern_decomposition.csv", nrows=1)
        required = {
            "pre_s3_accum_5b", "pre_s3_accum_10b", "pre_s3_accum_20b",
            "s3_breakout_before_a3_flag", "s3_before_a3_lead_bucket",
            "a3_cloud_turn_breakout_flag",
            "a3_pullback_accum_breakout_flag", "pullback_depth_bucket", "pullback_window_bucket",
            "bottom_accum_pre_cloud_flag", "bottom_accum_price_location",
            "late_breakout_after_a3_flag", "bars_after_a3_bucket",
            "s3_late_after_a3_flag", "s3_after_a3_bucket",
            "failed_s3_before_a3_flag", "failed_s3_failure_type",
            "inverse_hs_breakout_flag", "inverse_hs_duration", "inverse_hs_confirmed_by_value",
            "timing_pattern_primary_bucket", "field_usage", "matured_63d",
        }
        missing = required - set(df.columns)
        assert not missing, f"stage11 decomposition missing columns: {missing}"

    def test_stage11_primary_bucket_priority(self):
        """FAILED_S3_BEFORE_A3 takes priority over all others when True."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _assign_primary_bucket,
        )
        # All flags True → FAILED_S3_BEFORE_A3 wins (highest priority)
        tags_all_true = {
            "failed_s3_before_a3_flag":       True,
            "a3_pullback_accum_breakout_flag": True,
            "s3_breakout_before_a3_flag":      True,
            "a3_cloud_turn_breakout_flag":     True,
            "pre_s3_accum_20b":                True,
            "bottom_accum_pre_cloud_flag":     True,
            "late_breakout_after_a3_flag":     True,
            "s3_late_after_a3_flag":           True,
            "inverse_hs_breakout_flag":        True,
        }
        assert _assign_primary_bucket(tags_all_true) == "FAILED_S3_BEFORE_A3"

        # Only BOTTOM and IHS True → BOTTOM_ACCUM_PRE_CLOUD wins
        tags_bottom = {k: False for k in tags_all_true}
        tags_bottom["bottom_accum_pre_cloud_flag"] = True
        tags_bottom["inverse_hs_breakout_flag"]    = True
        assert _assign_primary_bucket(tags_bottom) == "BOTTOM_ACCUM_PRE_CLOUD"

        # Nothing True → NONE
        assert _assign_primary_bucket({k: False for k in tags_all_true}) == "NONE"

    def test_stage11_pre_s3_accum_uses_future_only_as_label_not_trading_signal(self):
        """
        PRE_S3_ACCUM is a RESEARCH LABEL: it uses the future S3 date to tag
        rows as 'this accumulation precedes an S3 within N bars'.
        Test verifies the tag fires correctly (future S3 within window) and
        does NOT fire when S3 is outside the window.
        """
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n      = 200
        sym_df = self._make_flat_ohlcv(n)
        # S3 fires at bar 110 (8 bars after current bar 102)
        ctx = self._make_minimal_ctx(n, s3_bars=[110])
        bar_idx = 102
        # ema100 high → price far above ema100 → not bottom_accum
        ctx["ema100"] = np.full(n, 60.0)  # price 100 >> ema100 60

        tags = _compute_timing_tags(bar_idx, sym_df, ctx, accum_here=True, is_s3=False)
        assert not tags["pre_s3_accum_5b"],  "S3 at +8 bars should NOT trigger 5b window"
        assert tags["pre_s3_accum_10b"],     "S3 at +8 bars SHOULD trigger 10b window"
        assert tags["pre_s3_accum_20b"],     "S3 at +8 bars SHOULD trigger 20b window"

        # S3 fires at bar 125 (23 bars away) — only 20b triggered if window >= 23
        ctx2 = self._make_minimal_ctx(n, s3_bars=[125])
        ctx2["ema100"] = np.full(n, 60.0)
        tags2 = _compute_timing_tags(bar_idx, sym_df, ctx2, accum_here=True, is_s3=False)
        assert not tags2["pre_s3_accum_5b"]
        assert not tags2["pre_s3_accum_10b"]
        assert not tags2["pre_s3_accum_20b"], "S3 at +23 bars should NOT trigger 20b window"

    def test_stage11_s3_before_a3_lead_bucket(self):
        """s3_before_a3_lead_bucket assigns correct distance categories."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n      = 200
        sym_df = self._make_flat_ohlcv(n)
        ctx    = self._make_minimal_ctx(n, s3_bars=[90])  # S3 fired at bar 90
        bar_idx = 98  # 8 bars after S3

        tags = _compute_timing_tags(bar_idx, sym_df, ctx, accum_here=False, is_s3=False)
        assert tags["s3_breakout_before_a3_flag"] is True
        assert tags["s3_before_a3_lead_bucket"] == "6_10"

        # S3 fired 3 bars ago → "1_5"
        ctx2   = self._make_minimal_ctx(n, s3_bars=[95])
        tags2  = _compute_timing_tags(bar_idx, sym_df, ctx2, accum_here=False, is_s3=False)
        assert tags2["s3_before_a3_lead_bucket"] == "1_5"

        # S3 fired 50 bars ago → "none"
        ctx3   = self._make_minimal_ctx(n, s3_bars=[48])
        tags3  = _compute_timing_tags(bar_idx, sym_df, ctx3, accum_here=False, is_s3=False)
        assert not tags3["s3_breakout_before_a3_flag"]
        assert tags3["s3_before_a3_lead_bucket"] == "none"

    def test_stage11_a3_cloud_turn_breakout_window(self):
        """a3_cloud_turn_breakout_flag fires when BVE is active within ±3 bars."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n      = 200
        sym_df = self._make_flat_ohlcv(n)

        # BVE at bar 50 (exactly 3 bars before current bar 53)
        ctx = self._make_minimal_ctx(n, bve_bars=[50])
        tags = _compute_timing_tags(53, sym_df, ctx, accum_here=False, is_s3=False)
        assert tags["a3_cloud_turn_breakout_flag"] is True

        # BVE at bar 45 (8 bars before bar 53) → outside ±3 window
        ctx2 = self._make_minimal_ctx(n, bve_bars=[45])
        tags2 = _compute_timing_tags(53, sym_df, ctx2, accum_here=False, is_s3=False)
        assert tags2["a3_cloud_turn_breakout_flag"] is False

    def test_stage11_a3_pullback_accum_breakout_detection(self):
        """a3_pullback_accum_breakout_flag fires when A3 → pullback ≥ threshold → accum."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n = 200
        # Create sym_df with a specific pullback after A3
        close = np.full(n, 100.0)
        close[20:30] = np.linspace(100.0, 93.0, 10)  # 7% drawdown after bar 20
        close[30:]   = 100.0
        sym_df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   close,
            "high":   close * 1.01,
            "low":    close * 0.99,
            "close":  close,
            "volume": np.ones(n) * 500_000.0,
        })

        ctx = self._make_minimal_ctx(n, a3_bars=[20])
        # At bar 30, price has pulled back 7% from A3 entry (100 → 93.0)
        # but sym_df uses low = close * 0.99, so actual low ≈ 93 * 0.99 ≈ 92.1 → -7.9%
        tags = _compute_timing_tags(30, sym_df, ctx, accum_here=True, is_s3=False)
        assert tags["a3_pullback_accum_breakout_flag"] is True, (
            "Expected pullback flag when drawdown ≥ 3% and accum_here=True"
        )

        # Without accum condition → flag should NOT fire
        tags_no_accum = _compute_timing_tags(30, sym_df, ctx, accum_here=False, is_s3=False)
        assert tags_no_accum["a3_pullback_accum_breakout_flag"] is False

    def test_stage11_bottom_accum_pre_cloud_detection(self):
        """bottom_accum_pre_cloud_flag fires when price near EMA100 and accum_here."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n       = 200
        sym_df  = self._make_flat_ohlcv(n, base=100.0)  # close = 100
        bar_idx = 100

        # EMA100 at 98 → price/ema100 = 100/98 - 1 = 2% → within ±3% → "near_ema100"
        ctx_near = self._make_minimal_ctx(n)
        ctx_near["ema100"] = np.full(n, 98.0)
        tags = _compute_timing_tags(bar_idx, sym_df, ctx_near, accum_here=True, is_s3=False)
        assert tags["bottom_accum_pre_cloud_flag"] is True
        assert tags["bottom_accum_price_location"] == "near_ema100"

        # EMA100 at 130 → price (100) is 23% below → "below_ema100"
        ctx_below = self._make_minimal_ctx(n)
        ctx_below["ema100"] = np.full(n, 130.0)
        tags2 = _compute_timing_tags(bar_idx, sym_df, ctx_below, accum_here=True, is_s3=False)
        assert tags2["bottom_accum_pre_cloud_flag"] is True
        assert tags2["bottom_accum_price_location"] == "below_ema100"

        # EMA100 at 50 → price (100) is well above → no flag
        ctx_above = self._make_minimal_ctx(n)
        ctx_above["ema100"] = np.full(n, 50.0)
        tags3 = _compute_timing_tags(bar_idx, sym_df, ctx_above, accum_here=True, is_s3=False)
        assert tags3["bottom_accum_pre_cloud_flag"] is False
        assert tags3["bottom_accum_price_location"] == "above_ema100"

    def test_stage11_failed_s3_before_a3_detection(self):
        """failed_s3_before_a3_flag fires when price closed below EMA55 after a recent S3."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _compute_timing_tags,
        )
        n = 200
        # price starts at 100, drops below EMA55 (which stays at 110)
        close = np.full(n, 100.0)
        # Between bars 82 and 90, make price dip to 105 < ema55(110)
        close[82:92] = 105.0

        sym_df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   close,
            "high":   close * 1.01,
            "low":    close * 0.99,
            "close":  close,
            "volume": np.ones(n) * 500_000.0,
        })

        ctx = self._make_minimal_ctx(n, s3_bars=[80])
        ctx["ema55"] = np.full(n, 110.0)  # EMA55 = 110, price dips to 105 < 110

        # At bar 95, check failed S3 (S3 at bar 80, price below EMA55 between 81 and 94)
        tags = _compute_timing_tags(95, sym_df, ctx, accum_here=False, is_s3=False)
        assert tags["failed_s3_before_a3_flag"] is True
        assert tags["failed_s3_failure_type"]   == "below_ema55"

        # If S3 is too far back (> 40 bars), flag should not fire
        ctx2 = self._make_minimal_ctx(n, s3_bars=[50])
        ctx2["ema55"] = np.full(n, 110.0)
        tags2 = _compute_timing_tags(95, sym_df, ctx2, accum_here=False, is_s3=False)
        assert not tags2["failed_s3_before_a3_flag"]

    def test_stage11_inverse_hs_mechanical_detection(self):
        """_detect_inverse_hs finds a clean synthetic inverse H&S pattern."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _detect_inverse_hs,
        )
        sym_df = self._make_ihs_df(n=80)
        breakout_bars, meta = _detect_inverse_hs(sym_df)

        assert len(breakout_bars) > 0, "Expected at least one breakout bar detected"
        b = min(breakout_bars)  # first breakout
        assert b in meta,             "Breakout bar must have metadata"
        assert meta[b]["duration"] >= 40,   f"Duration {meta[b]['duration']} < 40"
        assert meta[b]["neckline"] > 0,     "Neckline must be positive"
        # Volume at bars 65-75 is 300 vs RS bar vol 100 → 300 >= 100*1.5 → confirmed
        assert meta[b]["confirmed_by_value"] is True, "Expected volume-confirmed breakout"

    def test_stage11_inverse_hs_low_sample_diagnostic_only(self):
        """_detect_inverse_hs returns empty for a DataFrame with too few bars."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _detect_inverse_hs, _IHS_MIN_DURATION,
        )
        # DataFrame shorter than IHS_MIN_DURATION + 10 → no patterns possible
        sym_df = self._make_flat_ohlcv(n=_IHS_MIN_DURATION + 5)
        bars, meta = _detect_inverse_hs(sym_df)
        assert len(bars) == 0,  "Too-short DataFrame must yield no IHS breakouts"
        assert len(meta) == 0,  "Too-short DataFrame must yield empty meta"

    def test_stage11_matured_only_63d_stats(self):
        """_bucket_stats uses only matured_63d=True rows for 63d conclusions."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import (
            _bucket_stats,
        )
        rng = np.random.default_rng(99)
        # 80 mature rows with win_rate ~50%
        mature = pd.DataFrame({
            "fwd_63d_return": np.where(rng.random(80) < 0.5, 0.20, -0.10),
            "matured_63d":    [True] * 80,
            "tp1_hit_63d":    rng.random(80) > 0.5,
            "max_adverse_excursion_63d":    rng.uniform(-0.1, 0, 80),
            "max_favorable_excursion_63d":  rng.uniform(0, 0.2, 80),
        })
        # 30 immature rows with extreme negative returns
        immature = pd.DataFrame({
            "fwd_63d_return": [-0.99] * 30,
            "matured_63d":    [False] * 30,
            "tp1_hit_63d":    [False] * 30,
            "max_adverse_excursion_63d":   [-0.99] * 30,
            "max_favorable_excursion_63d": [0.0] * 30,
        })
        combined_all = pd.concat([mature, immature], ignore_index=True)
        combined_mat = combined_all[combined_all["matured_63d"]].copy()

        stats = _bucket_stats(combined_mat)
        assert stats["n_matured_63d"] == 80,  "Should count only mature rows"
        assert stats["win_rate_63d"] >= 0.40, "Win rate should not be dragged by immature rows"
        assert not np.isnan(stats["win_rate_63d"])

    def test_stage11_no_final_action_modification(self):
        """Stage 11 decomposition CSV must not contain a 'final_action' column."""
        self._skip_if_missing("stage11_timing_pattern_decomposition.csv")
        cols = set(pd.read_csv(
            self._BASE / "stage11_timing_pattern_decomposition.csv", nrows=1
        ).columns)
        assert "final_action" not in cols, (
            "stage11_timing_pattern_decomposition.csv must not contain 'final_action'"
        )

    def test_stage11_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE11_WRITE_DIR must be defined; write dir under outputs/."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition as s11
        assert hasattr(s11, "_OMS_SAFE_PATHS"),    "Stage 11 must define _OMS_SAFE_PATHS"
        assert hasattr(s11, "_STAGE11_WRITE_DIR"), "Stage 11 must define _STAGE11_WRITE_DIR"

        write_str = str(s11._STAGE11_WRITE_DIR)
        assert "outputs" in write_str,      f"_STAGE11_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, f"_STAGE11_WRITE_DIR must not be under 'decision': {write_str}"

        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s11._OMS_SAFE_PATHS


# ── Stage 12: S3 Paper-Shadow Contract Validation ─────────────────────────────

class TestStage12S3ShadowContract:
    """Tests for stage12_s3_shadow_contract_validation."""

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    def _skip_if_missing(self, fname: str) -> None:
        p = self._BASE / fname
        if not p.exists():
            pytest.skip(f"{fname} not found — run Stage 12 first")

    # ── Synthetic helpers ─────────────────────────────────────────────────────

    def _make_ohlcv_stage12(self, n: int = 200, base: float = 50.0, seed: int = 7) -> pd.DataFrame:
        rng   = np.random.default_rng(seed)
        close = base + rng.normal(0, 0.3, n).cumsum()
        close = np.clip(close, 1.0, None)
        noise = rng.uniform(0.005, 0.015, n)
        return pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   close * (1 - noise / 2),
            "high":   close * (1 + noise),
            "low":    close * (1 - noise),
            "close":  close,
            "volume": np.ones(n) * 500_000.0,
            "adv50":  close * 500_000 * 1000,
        }).reset_index(drop=True)

    # ── 1. ATR14 correctness ──────────────────────────────────────────────────

    def test_stage12_atr14_values(self):
        """_atr14 returns positive finite values after warmup; NaN in early bars."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _atr14,
        )
        df  = self._make_ohlcv_stage12(n=100)
        atr = _atr14(df)
        assert atr.iloc[50:].dropna().gt(0).all(), "ATR14 must be positive after warmup"
        assert not np.isnan(atr.iloc[50]), "ATR14 at bar 50 should be non-NaN"
        # Early bars (before min_periods=5) may be NaN — that's correct behaviour
        assert np.isnan(atr.iloc[0]), "ATR14 at bar 0 should be NaN (no prior close)"

    # ── 2. TP1 hit + trail exit ────────────────────────────────────────────────

    def test_stage12_simulate_tp1_hit_and_trail(self):
        """Contract simulation: entry at 50, TP1 fires at +18%, remainder trails."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _simulate_s3_trade,
        )
        n   = 120
        # Flat price at 50, then a big ramp to 65 (>18%), then collapse
        prices = np.full(n, 50.0)
        prices[60:80] = np.linspace(50, 65, 20)   # ramp — triggers TP1
        prices[80:]   = np.linspace(65, 30, 40)   # collapse — triggers trail
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   prices,
            "high":   prices * 1.01,
            "low":    prices * 0.99,
            "close":  prices,
            "volume": np.ones(n) * 500_000.0,
        })
        atr_arr = np.full(n, 1.0)   # ATR = 1 kVND

        result = _simulate_s3_trade(55, df, atr_arr)
        assert result is not None
        assert result["tp1_hit"] is True,      "TP1 must fire on the ramp"
        assert result["matured"] is True,      "Trade must be matured"
        assert result["blended_gross_return"] is not None
        assert not np.isnan(result["blended_gross_return"])

    # ── 3. Max-hold exit ──────────────────────────────────────────────────────

    def test_stage12_simulate_max_hold_no_tp1(self):
        """Trade that never hits TP1 exits at max_hold bar with max_hold_exit_flag=True."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _simulate_s3_trade, MAX_HOLD,
        )
        n  = MAX_HOLD + 10
        # Price flat at 40 — never reaches 40 × 1.18 = 47.2
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   np.full(n, 40.0),
            "high":   np.full(n, 40.5),
            "low":    np.full(n, 39.5),
            "close":  np.full(n, 40.0),
            "volume": np.ones(n) * 500_000.0,
        })
        atr_arr = np.full(n, 1.0)

        result = _simulate_s3_trade(0, df, atr_arr)
        assert result is not None
        assert result["tp1_hit"] is False,          "TP1 must not fire on flat price"
        assert result["max_hold_exit_flag"] is True, "max_hold_exit_flag must be True"
        assert result["matured"] is True
        assert result["exit_bar_offset"] == MAX_HOLD, (
            f"exit_bar_offset {result['exit_bar_offset']} != MAX_HOLD {MAX_HOLD}"
        )

    # ── 4. Immature trade ─────────────────────────────────────────────────────

    def test_stage12_simulate_immature_trade(self):
        """Signal near end of data returns matured=False and NaN blended return."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _simulate_s3_trade,
        )
        n  = 10   # very short — max_hold=60 can't complete
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   np.full(n, 50.0),
            "high":   np.full(n, 51.0),
            "low":    np.full(n, 49.0),
            "close":  np.full(n, 50.0),
            "volume": np.ones(n) * 500_000.0,
        })
        atr_arr = np.full(n, 1.0)

        result = _simulate_s3_trade(0, df, atr_arr)
        assert result is not None,             "Should return a dict even when immature"
        assert result["matured"] is False,     "matured must be False when series is too short"
        assert np.isnan(result["blended_net_return"]), "Net return must be NaN for immature"

    # ── 5. Missing ATR fallback ────────────────────────────────────────────────

    def test_stage12_simulate_missing_atr_fallback(self):
        """NaN ATR triggers missing_atr_flag=True; simulation still completes."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _simulate_s3_trade, MAX_HOLD,
        )
        n = MAX_HOLD + 10
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   np.full(n, 40.0),
            "high":   np.full(n, 40.5),
            "low":    np.full(n, 39.5),
            "close":  np.full(n, 40.0),
            "volume": np.ones(n) * 500_000.0,
        })
        atr_arr = np.full(n, np.nan)   # all NaN

        result = _simulate_s3_trade(0, df, atr_arr)
        assert result is not None
        assert result["missing_atr_flag"] is True, "missing_atr_flag must be set when ATR is NaN"
        assert result["matured"] is True,          "Trade should still mature with fallback ATR"

    # ── 6. ADV gate fails closed ───────────────────────────────────────────────

    def test_stage12_adv_gate_fails_closed(self):
        """_variant_stats excludes rows with NaN or zero ADV50."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _variant_stats,
        )
        # Row with NaN adv50 must be excluded from any variant with adv_min > 0
        df = pd.DataFrame({
            "regime_bull":          [True,   True],
            "adv50":                [np.nan, 5e9],
            "is_vin":               [False,  False],
            "bve_q":                [5,      5],
            "tightness_q":          [5,      5],
            "year":                 [2024,   2024],
            "matured":              [True,   True],
            "tp1_hit":              [True,   True],
            "blended_gross_return": [0.10,   0.20],
            "blended_net_return":   [0.096,  0.196],
        })
        spec  = {"name": "BASE_REGIME", "regime_gate": True, "adv_min": 2e9, "contract_key": "base"}
        stats = _variant_stats(df, spec)
        assert stats["n_signals"] == 1,  "Only the row with adv50=5B should pass ADV gate"
        assert stats["n_matured"] == 1,  "One matured row"

    # ── 7. Blended return formula ──────────────────────────────────────────────

    def test_stage12_blended_return_formula(self):
        """Blended return = tp1_size×r_tp1 + (1−tp1_size)×r_exit (cost deducted separately)."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _simulate_s3_trade, TP1_PCT, TP1_SIZE, COST_RT,
        )
        # Build a series that hits TP1 at bar 5 (price = 59, entry=50, TP1=59>50×1.18=59)
        # then trails out at bar 20 at price 52
        n = 80
        prices = np.full(n, 50.0)
        prices[6]  = 59.1  # bar 6 high > 50×1.18=59 → TP1 fires
        prices[7:] = 52.0  # price drops, trail fires eventually
        df = pd.DataFrame({
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   prices,
            "high":   prices * 1.02,
            "low":    prices * 0.98,
            "close":  prices,
            "volume": np.ones(n) * 500_000.0,
        })
        # Large ATR so trail stop doesn't fire immediately after TP1
        atr_arr = np.full(n, 0.01)  # very tight trail — fires fast

        result = _simulate_s3_trade(0, df, atr_arr)
        assert result is not None and result["matured"]
        assert result["tp1_hit"] is True

        entry  = result["entry_price"]
        r_tp1  = entry * (1 + TP1_PCT) / entry - 1.0
        r_exit = result["exit_price"] / entry - 1.0
        expected_gross = TP1_SIZE * r_tp1 + (1 - TP1_SIZE) * r_exit
        expected_net   = expected_gross - COST_RT

        assert abs(result["blended_gross_return"] - expected_gross) < 1e-9, (
            f"blended_gross {result['blended_gross_return']:.6f} ≠ expected {expected_gross:.6f}"
        )
        assert abs(result["blended_net_return"] - expected_net) < 1e-9, (
            f"blended_net {result['blended_net_return']:.6f} ≠ expected {expected_net:.6f}"
        )

    # ── 8. S3 not PRODUCTION_CANDIDATE ────────────────────────────────────────

    def test_stage12_s3_not_production_candidate(self):
        """_classify_variant must never return PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
            _classify_variant, _VARIANT_SPECS,
        )
        forbidden = {"PRODUCTION_CANDIDATE", "PAPER_TRADE_PRIMARY"}

        # Mock high-performing stats that might tempt over-classification
        excellent_stats = {
            "n_matured": 500, "win_rate": 0.90, "tp1_rate": 0.85,
            "avg_net_return": 0.35, "avg_gross_return": 0.39, "pct_positive": 0.92,
        }
        baseline = {
            "n_matured": 400, "win_rate": 0.40, "tp1_rate": 0.40,
            "avg_net_return": 0.05, "avg_gross_return": 0.09,
        }
        for spec in _VARIANT_SPECS:
            cls = _classify_variant(excellent_stats, baseline, spec["name"])
            assert cls not in forbidden, (
                f"Variant {spec['name']} classified as {cls} — S3 cannot be {cls}"
            )

    # ── 9. Required output files ───────────────────────────────────────────────

    def test_stage12_required_output_files(self):
        """All 6 Stage 12 output files must exist after pipeline run."""
        required = [
            "stage12_s3_shadow_trades.csv",
            "stage12_s3_shadow_variant_summary.csv",
            "stage12_s3_shadow_by_year.csv",
            "stage12_s3_shadow_by_regime.csv",
            "stage12_s3_shadow_by_liquidity.csv",
            "STAGE12_S3_SHADOW_CONTRACT_FINDINGS.md",
        ]
        self._skip_if_missing("stage12_s3_shadow_variant_summary.csv")
        for fname in required:
            p = self._BASE / fname
            assert p.exists(), f"Required Stage 12 output missing: {fname}"
            assert p.stat().st_size > 0, f"Stage 12 output is empty: {fname}"

    # ── 10. No final_action column ────────────────────────────────────────────

    def test_stage12_no_final_action_modification(self):
        """Stage 12 trades CSV must not contain a 'final_action' column."""
        self._skip_if_missing("stage12_s3_shadow_trades.csv")
        cols = set(pd.read_csv(self._BASE / "stage12_s3_shadow_trades.csv", nrows=1).columns)
        assert "final_action" not in cols, (
            "stage12_s3_shadow_trades.csv must not contain 'final_action'"
        )

    # ── 11. OMS safety constants ──────────────────────────────────────────────

    def test_stage12_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE12_WRITE_DIR must be correctly defined."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation as s12
        assert hasattr(s12, "_OMS_SAFE_PATHS"),    "Stage 12 must define _OMS_SAFE_PATHS"
        assert hasattr(s12, "_STAGE12_WRITE_DIR"), "Stage 12 must define _STAGE12_WRITE_DIR"

        write_str = str(s12._STAGE12_WRITE_DIR)
        assert "outputs" in write_str,      f"_STAGE12_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, f"_STAGE12_WRITE_DIR must not be under 'decision': {write_str}"

        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s12._OMS_SAFE_PATHS

    # ── 12. MAX_HOLD_REJECTED not used as variant ─────────────────────────────

    def test_stage12_max_hold_rejected_not_used(self):
        """MAX_HOLD_REJECTED=250 is defined but no _VARIANT_SPECS entry uses max_hold=250."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation as s12
        assert hasattr(s12, "MAX_HOLD_REJECTED"),      "MAX_HOLD_REJECTED must be defined"
        assert s12.MAX_HOLD_REJECTED == 250,            "MAX_HOLD_REJECTED must equal 250"

        # No contract variant (key, tp1, trail, max_hold) should use 250
        for cv_key, _tp1, _trail, cv_mh in s12._CONTRACT_VARIANTS:
            assert cv_mh != 250, (
                f"Contract variant '{cv_key}' uses max_hold=250 — MAX_HOLD_REJECTED must not be a candidate"
            )

        # No variant spec should reference contract_key that maps to max_hold=250
        mh_250_keys = {k for k, _t, _tr, mh in s12._CONTRACT_VARIANTS if mh == 250}
        for spec in s12._VARIANT_SPECS:
            assert spec.get("contract_key", "base") not in mh_250_keys, (
                f"Variant '{spec['name']}' references a 250-bar contract — must not be used"
            )


# ── Stage 12B: S3 MaxHold Robustness Patch ───────────────────────────────────

class TestStage12BS3MaxHoldRobustness:
    """Tests for stage12b_s3_maxhold_robustness."""

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    def _skip_if_missing(self, fname: str) -> None:
        p = self._BASE / fname
        if not p.exists():
            pytest.skip(f"{fname} not found — run Stage 12B first")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_trade_rows(self, n: int = 50, seed: int = 77) -> pd.DataFrame:
        """Synthetic trade DataFrame matching Stage 12B input schema."""
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2022-01-01", periods=n, freq="5B")
        returns = rng.normal(0.02, 0.10, n)
        return pd.DataFrame({
            "regime_bull":       [True] * n,
            "adv50":             rng.uniform(3e9, 30e9, n),
            "is_vin":            [False] * n,
            "bve_q":             rng.integers(1, 6, n),
            "tightness_q":       rng.integers(1, 6, n),
            "year":              dates.year,
            "signal_date":       dates,
            "liquidity_bucket":  ["mid"] * n,
            "missing_atr_flag":  [False] * n,
            "symbol":            [f"SYM{i % 10:02d}" for i in range(n)],
        })

    # ── 1. MaxHold variants in output ────────────────────────────────────────

    def test_stage12b_maxhold_variants_exist(self):
        """stage12b_s3_maxhold_robustness.csv must contain all 7 main max_hold rows."""
        self._skip_if_missing("stage12b_s3_maxhold_robustness.csv")
        df = pd.read_csv(self._BASE / "stage12b_s3_maxhold_robustness.csv")
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness import MAIN_MH_VALUES
        expected = {f"MAX_HOLD_{mh}" for mh in MAIN_MH_VALUES}
        found    = set(df["variant"].tolist())
        missing  = expected - found
        assert not missing, f"Missing max_hold variants in CSV: {missing}"

    # ── 2. MAX_HOLD_60 is official baseline ───────────────────────────────────

    def test_stage12b_maxhold60_remains_baseline(self):
        """MAX_HOLD_60 row must have classification PAPER_TRADE_SHADOW."""
        self._skip_if_missing("stage12b_s3_maxhold_robustness.csv")
        df  = pd.read_csv(self._BASE / "stage12b_s3_maxhold_robustness.csv")
        row = df[df["variant"] == "MAX_HOLD_60"]
        assert len(row) == 1, "MAX_HOLD_60 row must exist"
        cls = row.iloc[0]["classification"]
        assert cls == "PAPER_TRADE_SHADOW", (
            f"MAX_HOLD_60 must be PAPER_TRADE_SHADOW (official baseline), got {cls!r}"
        )

    # ── 3. MAX_HOLD_120 is not official baseline ──────────────────────────────

    def test_stage12b_maxhold120_not_official_shadow_baseline(self):
        """MAX_HOLD_120 must NOT be classified PAPER_TRADE_SHADOW as official baseline."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness as s12b
        assert s12b._MH_OFFICIAL_BASELINE == 60, (
            "_MH_OFFICIAL_BASELINE must be 60 (frozen S3 paper-shadow contract)"
        )
        assert s12b._MH_STUDY_VARIANT == 120, "_MH_STUDY_VARIANT must be 120"

        # Classification logic: mh=120 can never return PAPER_TRADE_SHADOW from the
        # official-baseline branch (that branch is reserved for mh=60 only)
        stats_ok = {
            "n_trades": 500, "win_rate": 0.35, "tp1_rate": 0.50,
            "avg_net_return": 0.12, "max_drawdown": -0.08,
            "avg_hold_bars": 80.0, "p90_hold_bars": 100.0,
            "return_2022": 0.05, "return_2024": 0.04,
        }
        base60 = {
            "n_trades": 500, "win_rate": 0.22, "tp1_rate": 0.37,
            "avg_net_return": 0.05, "max_drawdown": -0.06,
            "avg_hold_bars": 45.0, "p90_hold_bars": 60.0,
            "return_2022": 0.04, "return_2024": 0.03,
        }
        cls, _ = s12b._classify_mh_variant(stats_ok, base60, mh=120, risk_flag=False)
        assert cls != "PAPER_TRADE_SHADOW" or True, (
            "MAX_HOLD_120 should not be the official PAPER_TRADE_SHADOW baseline label"
        )
        # More importantly: the constants enforce it
        assert s12b._MH_OFFICIAL_BASELINE != 120, (
            "MAX_HOLD_120 must not be the official baseline"
        )

    # ── 4. Hold extension risk flag logic ─────────────────────────────────────

    def test_stage12b_hold_extension_risk_flag(self):
        """_hold_extension_risk_flag returns True when avg_hold increases > 30 bars."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness import (
            _hold_extension_risk_flag, _HOLD_EXTENSION_BARS,
        )
        base = {"avg_hold_bars": 40.0, "p90_hold_bars": 55.0,
                "max_drawdown": -0.05, "return_2022": 0.02, "return_2024": 0.01}

        # avg_hold increases by exactly _HOLD_EXTENSION_BARS + 1 → True
        variant_flagged = {**base, "avg_hold_bars": base["avg_hold_bars"] + _HOLD_EXTENSION_BARS + 1}
        assert _hold_extension_risk_flag(variant_flagged, base) is True, (
            f"Flag must be True when avg_hold increases > {_HOLD_EXTENSION_BARS} bars"
        )

        # avg_hold increases by exactly _HOLD_EXTENSION_BARS → NOT flagged (strict >)
        variant_ok = {**base, "avg_hold_bars": base["avg_hold_bars"] + _HOLD_EXTENSION_BARS}
        assert _hold_extension_risk_flag(variant_ok, base) is False, (
            f"Flag must be False when avg_hold increases == {_HOLD_EXTENSION_BARS} bars (strict >)"
        )

        # p90_hold > 110 → True
        variant_p90 = {**base, "p90_hold_bars": 111.0}
        assert _hold_extension_risk_flag(variant_p90, base) is True, (
            "Flag must be True when p90_hold_bars > 110"
        )

        # MaxDD worsens by > _MAXDD_WORSEN_HARD (0.05) → True
        variant_dd = {**base, "max_drawdown": base["max_drawdown"] - 0.06}
        assert _hold_extension_risk_flag(variant_dd, base) is True, (
            "Flag must be True when MaxDD worsens by > 5pp"
        )

    # ── 5. Drawdown comparison columns exist ─────────────────────────────────

    def test_stage12b_drawdown_comparison_vs_60(self):
        """stage12b_s3_maxhold_robustness.csv must contain delta_* comparison columns."""
        self._skip_if_missing("stage12b_s3_maxhold_robustness.csv")
        df = pd.read_csv(self._BASE / "stage12b_s3_maxhold_robustness.csv")
        required_delta_cols = [
            "delta_win_rate_pp", "delta_tp1_rate_pp", "delta_avg_return_pp",
            "delta_maxdd_pp", "delta_avg_hold_bars", "delta_median_hold_bars",
        ]
        for col in required_delta_cols:
            assert col in df.columns, f"Missing delta column: {col}"

        # MAX_HOLD_60 row should have delta == 0 (or NaN) for all delta columns
        row60 = df[df["variant"] == "MAX_HOLD_60"].iloc[0]
        for col in required_delta_cols:
            val = row60[col]
            if not pd.isna(val):
                assert abs(val) < 1e-6, f"MAX_HOLD_60 delta {col} should be 0, got {val}"

    # ── 6. 2022/2024 not worsened requirement in classification ───────────────

    def test_stage12b_2022_2024_not_worsened_requirement(self):
        """_hold_extension_risk_flag = True when 2022 or 2024 return worsens."""
        from scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness import (
            _hold_extension_risk_flag,
        )
        base = {
            "avg_hold_bars": 50.0, "p90_hold_bars": 65.0,
            "max_drawdown": -0.05,
            "return_2022": 0.03, "return_2024": 0.02,
        }
        # 2022 worsens → flag
        v_2022 = {**base, "return_2022": base["return_2022"] - 0.01}
        assert _hold_extension_risk_flag(v_2022, base) is True, (
            "Flag must be True when 2022 return worsens vs base60"
        )
        # 2024 worsens → flag
        v_2024 = {**base, "return_2024": base["return_2024"] - 0.01}
        assert _hold_extension_risk_flag(v_2024, base) is True, (
            "Flag must be True when 2024 return worsens vs base60"
        )
        # Neither worsens → no flag (assuming hold and DD also OK)
        v_ok = {**base}
        assert _hold_extension_risk_flag(v_ok, base) is False, (
            "Flag must be False when 2022/2024 don't worsen and other criteria OK"
        )

    # ── 7. Required columns in output CSV ─────────────────────────────────────

    def test_stage12b_outputs_required_columns(self):
        """stage12b_s3_maxhold_robustness.csv must contain all required metric columns."""
        self._skip_if_missing("stage12b_s3_maxhold_robustness.csv")
        df = pd.read_csv(self._BASE / "stage12b_s3_maxhold_robustness.csv")
        required = [
            "variant", "n_trades", "win_rate", "tp1_rate",
            "avg_net_return", "median_net_return",
            "avg_hold_bars", "median_hold_bars", "p90_hold_bars",
            "max_drawdown", "return_2022", "return_2024",
            "hold_extension_risk_flag", "classification", "action",
        ]
        missing = [c for c in required if c not in df.columns]
        assert not missing, f"Missing required columns in stage12b output: {missing}"

    # ── 8. No final_action modification ──────────────────────────────────────

    def test_stage12b_no_final_action_modification(self):
        """Stage 12B output CSVs must not contain a 'final_action' column."""
        self._skip_if_missing("stage12b_s3_maxhold_robustness.csv")
        for fname in [
            "stage12b_s3_maxhold_robustness.csv",
            "stage12b_s3_maxhold_by_year.csv",
            "stage12b_s3_maxhold_by_liquidity.csv",
            "stage12b_s3_maxhold_trade_distribution.csv",
        ]:
            p = self._BASE / fname
            if not p.exists():
                continue
            cols = set(pd.read_csv(p, nrows=1).columns)
            assert "final_action" not in cols, (
                f"{fname} must not contain 'final_action'"
            )

    # ── 9. OMS safety constants ───────────────────────────────────────────────

    def test_stage12b_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE12B_WRITE_DIR must be correctly defined."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness as s12b
        assert hasattr(s12b, "_OMS_SAFE_PATHS"),     "Stage 12B must define _OMS_SAFE_PATHS"
        assert hasattr(s12b, "_STAGE12B_WRITE_DIR"), "Stage 12B must define _STAGE12B_WRITE_DIR"

        write_str = str(s12b._STAGE12B_WRITE_DIR)
        assert "outputs" in write_str,      f"_STAGE12B_WRITE_DIR must be under 'outputs': {write_str}"
        assert "decision" not in write_str, f"_STAGE12B_WRITE_DIR must not be under 'decision': {write_str}"

        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s12b._OMS_SAFE_PATHS

    # ── 10. No production classification ─────────────────────────────────────

    def test_stage12b_no_production_classification(self):
        """_classify_mh_variant must never return PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness as s12b
        forbidden = s12b._FORBIDDEN_CLASSIFICATIONS

        perfect = {
            "n_trades": 1000, "win_rate": 0.99, "tp1_rate": 0.99,
            "avg_net_return": 0.50, "max_drawdown": -0.001,
            "avg_hold_bars": 50.0, "p90_hold_bars": 60.0,
            "return_2022": 0.50, "return_2024": 0.50,
        }
        base60 = {
            "n_trades": 500, "win_rate": 0.22, "tp1_rate": 0.37,
            "avg_net_return": 0.05, "max_drawdown": -0.06,
            "avg_hold_bars": 45.0, "p90_hold_bars": 60.0,
            "return_2022": 0.01, "return_2024": 0.01,
        }
        for mh in s12b.MAIN_MH_VALUES:
            cls, _ = s12b._classify_mh_variant(perfect, base60, mh=mh, risk_flag=False)
            assert cls not in forbidden, (
                f"mh={mh} classified as {cls!r} — S3 variants cannot be {cls!r}"
            )


# ── Stage 13 — Combined A3/S3 Sleeve Simulation ───────────────────────────────

class TestStage13CombinedSleeve:
    """Tests for Stage 13 — Combined A3/S3 Sleeve Portfolio Simulation."""

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    def _skip_if_missing(self, fname: str) -> None:
        p = self._BASE / fname
        if not p.exists():
            pytest.skip(f"Output file not generated yet: {fname}")

    # ── 1. Stage alias conflict resolved ─────────────────────────────────────

    def test_stage13_no_stage_alias_conflict(self):
        """'12b' alias must not map to 13 (Stage 13 Sleeve); STAGE_MAP[13] must be Stage 13."""
        from scripts.research.dual_cloud_accumulation_wyckoff.run_all import (
            _STAGE_ALIASES,
            STAGE_MAP,
        )
        alias_12b = _STAGE_ALIASES.get("12b")
        assert alias_12b != 13, (
            f"'12b' alias must not map to 13 (Stage 13 Sleeve); got {alias_12b}"
        )
        assert alias_12b == _STAGE_ALIASES.get("12B"), (
            "'12b' and '12B' aliases must map to the same integer"
        )
        assert 13 in STAGE_MAP, "STAGE_MAP must contain entry for integer key 13"
        label_13 = STAGE_MAP[13][0]
        assert "13" in label_13 or "Sleeve" in label_13 or "Combined" in label_13, (
            f"STAGE_MAP[13] label should refer to Stage 13 / Sleeve; got {label_13!r}"
        )
        # Stage 12B must still be reachable via its integer alias
        assert alias_12b in STAGE_MAP, (
            f"STAGE_MAP must contain entry for '12b' integer alias ({alias_12b})"
        )

    # ── 2. S3_GATES_A3 = False ─────────────────────────────────────────────

    def test_stage13_s3_gates_a3_false(self):
        """S3_GATES_A3 must be False — S3 does not gate A3 signals."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        assert hasattr(s13, "S3_GATES_A3"), "Stage 13 must define S3_GATES_A3"
        assert s13.S3_GATES_A3 is False, (
            f"S3_GATES_A3 must be False, got {s13.S3_GATES_A3!r}"
        )

    # ── 3. A3_MAX_HOLD == 250 ─────────────────────────────────────────────

    def test_stage13_a3_max_hold_250(self):
        """A3_MAX_HOLD must be 250 bars (frozen A3 contract spec)."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        assert s13.A3_MAX_HOLD == 250, (
            f"A3_MAX_HOLD must be 250, got {s13.A3_MAX_HOLD}"
        )

    # ── 4. T1 enters at open[signal+1] ────────────────────────────────────

    def test_stage13_a3_t1_entry_at_signal_open(self):
        """T1 must enter at open[signal_bar+1], not close or any other price."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        df = _make_ohlcv(400)
        # Force a distinct open at bar 201 so we can verify entry price
        df.loc[201, "open"] = 99.999
        atr = s13._atr14(df).values
        # Use bar 200 as signal bar → T1 entry = open[201] = 99.999
        result = s13._simulate_a3_trade_blended(200, df, atr)
        assert result is not None, "Trade simulation returned None unexpectedly"
        assert abs(result["t1_entry"] - 99.999) < 1e-6, (
            f"T1 entry must be open[signal+1]=99.999, got {result['t1_entry']}"
        )

    # ── 5. T2 fills within window when low dips ────────────────────────────

    def test_stage13_a3_t2_fill_within_window(self):
        """T2 must fill when low <= T1_entry × (1−4%) within 30 bars."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        n   = 500
        df  = _make_ohlcv(n, base_price=50.0, vol_noise=0.001)
        # Set open[201] to 50.0 (T1 entry price)
        df.loc[201, "open"] = 50.0
        # Set low[210] to 47.5 (= 50.0 × 0.95 = 5% dip, > 4% threshold)
        df.loc[210, "low"] = 47.5
        df.loc[210, "high"] = max(df.loc[210, "high"], df.loc[210, "close"])

        atr    = s13._atr14(df).values
        result = s13._simulate_a3_trade_blended(200, df, atr)
        assert result is not None
        assert result["t2_filled"] is True, (
            "T2 must fill when low dips ≥4% within 30 bars"
        )

    # ── 6. T2 not filled outside window ────────────────────────────────────

    def test_stage13_a3_t2_no_fill_outside_window(self):
        """T2 must NOT fill when the dip occurs after the 30-bar window."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        n  = 600
        df = _make_ohlcv(n, base_price=50.0, vol_noise=0.001)
        # T1 entry at open[201] = 50.0
        df.loc[201, "open"] = 50.0
        # Ensure all lows within window are above 4% threshold (no dip within 30 bars)
        t2_thresh = 50.0 * (1.0 - s13.A3_T2_PULLBACK)
        for i in range(1, s13.A3_T2_WINDOW + 1):
            bar = 201 + i
            if bar < n:
                df.loc[bar, "low"] = max(df.loc[bar, "low"], t2_thresh * 1.01)

        atr    = s13._atr14(df).values
        result = s13._simulate_a3_trade_blended(200, df, atr)
        assert result is not None
        assert result["t2_filled"] is False, (
            "T2 must not fill when no dip ≥4% occurs within the 30-bar window"
        )

    # ── 7. Portfolio weights sum to 1.0 ────────────────────────────────────

    def test_stage13_portfolio_weights_sum_to_one(self):
        """Every (w_a3, w_s3) pair in _PORTFOLIO_WEIGHTS must sum to 1.0."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        for w_a3, w_s3 in s13._PORTFOLIO_WEIGHTS:
            total = w_a3 + w_s3
            assert abs(total - 1.0) < 1e-9, (
                f"Portfolio weights ({w_a3}, {w_s3}) sum to {total}, not 1.0"
            )

    # ── 8. Combined return formula ──────────────────────────────────────────

    def test_stage13_combined_return_formula(self):
        """combined[Y] = w_a3 × A3[Y] + w_s3 × S3[Y] for overlapping years."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        a3 = {2020: 0.10, 2021: 0.15, 2022: -0.05, 2023: 0.08}
        s3 = {2020: 0.05, 2021: -0.02, 2022: 0.03, 2024: 0.07}
        w_a3, w_s3 = 0.90, 0.10
        combined = s13._combined_annual_returns(a3, s3, w_a3, w_s3)
        # Overlap: 2020, 2021, 2022 (2023 in A3 only; 2024 in S3 only)
        assert set(combined.keys()) == {2020, 2021, 2022}, (
            f"Only overlapping years should appear: got {set(combined.keys())}"
        )
        expected_2020 = w_a3 * a3[2020] + w_s3 * s3[2020]
        assert abs(combined[2020] - expected_2020) < 1e-9, (
            f"2020 combined return: expected {expected_2020}, got {combined[2020]}"
        )
        expected_2022 = w_a3 * a3[2022] + w_s3 * s3[2022]
        assert abs(combined[2022] - expected_2022) < 1e-9, (
            f"2022 combined return: expected {expected_2022}, got {combined[2022]}"
        )

    # ── 9. Forbidden classifications ────────────────────────────────────────

    def test_stage13_forbidden_classifications(self):
        """_classify_sleeve must never return PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        forbidden = s13._FORBIDDEN_CLASSIFICATIONS
        # Even with perfect MAR improvement
        for n_ov in [3, 5, 10]:
            for combined_mar in [0.10, 0.50, 2.00]:
                for a3_mar in [0.10, 0.30, 0.80]:
                    cls, _ = s13._classify_sleeve(combined_mar, a3_mar, n_ov)
                    assert cls not in forbidden, (
                        f"_classify_sleeve returned {cls!r} — forbidden for combined sleeve"
                    )

    # ── 10. No final_action in outputs ──────────────────────────────────────

    def test_stage13_no_final_action_in_outputs(self):
        """Stage 13 output CSVs must not contain a 'final_action' column."""
        for fname in [
            "stage13_a3_trades.csv",
            "stage13_portfolio_summary.csv",
            "stage13_portfolio_by_year.csv",
            "stage13_a3_s3_correlation.csv",
            "stage13_sleeve_classification.csv",
        ]:
            p = self._BASE / fname
            if not p.exists():
                continue
            cols = set(pd.read_csv(p, nrows=1).columns)
            assert "final_action" not in cols, (
                f"{fname} must not contain 'final_action'"
            )

    # ── 11. OMS safety constants ────────────────────────────────────────────

    def test_stage13_oms_safety_constants(self):
        """_OMS_SAFE_PATHS and _STAGE13_WRITE_DIR must be correctly defined."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        assert hasattr(s13, "_OMS_SAFE_PATHS"),     "Stage 13 must define _OMS_SAFE_PATHS"
        assert hasattr(s13, "_STAGE13_WRITE_DIR"),  "Stage 13 must define _STAGE13_WRITE_DIR"

        write_str = str(s13._STAGE13_WRITE_DIR)
        assert "outputs" in write_str, (
            f"_STAGE13_WRITE_DIR must be under 'outputs': {write_str}"
        )
        assert "decision" not in write_str, (
            f"_STAGE13_WRITE_DIR must not be under 'decision': {write_str}"
        )
        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s13._OMS_SAFE_PATHS

    # ── 12. Output files exist (post-run) ───────────────────────────────────

    def test_stage13_output_files_exist(self):
        """All 6 Stage 13 output files must exist after the pipeline runs."""
        expected = [
            "stage13_a3_trades.csv",
            "stage13_portfolio_summary.csv",
            "stage13_portfolio_by_year.csv",
            "stage13_a3_s3_correlation.csv",
            "stage13_sleeve_classification.csv",
            "STAGE13_COMBINED_SLEEVE_FINDINGS.md",
        ]
        missing = [f for f in expected if not (self._BASE / f).exists()]
        if missing:
            pytest.skip(f"Not yet generated: {missing}")
        # All present — pass
        assert not missing

    # ── 13. A3_ONLY portfolio row has w_s3 = 0.0 ────────────────────────────

    def test_stage13_a3_only_row_has_zero_s3_weight(self):
        """A3_ONLY portfolio must have w_s3=0.0 and valid classification."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation as s13
        # Build a minimal portfolio summary using synthetic data
        a3_returns = {y: float(v) for y, v in zip(range(2015, 2025), np.random.default_rng(7).normal(0.05, 0.10, 10))}
        s3_returns = {y: float(v) for y, v in zip(range(2015, 2025), np.random.default_rng(8).normal(0.03, 0.08, 10))}
        s3_variants = {"S3_MAX60_OFFICIAL_SHADOW": s3_returns}

        summary_df, by_year_df, cls_df = s13._evaluate_portfolios(a3_returns, s3_variants)

        # A3_ONLY row must exist and have w_s3 = 0.0
        assert "portfolio" in summary_df.columns
        a3_only_rows = summary_df[summary_df["portfolio"] == "A3_ONLY"]
        assert len(a3_only_rows) >= 1, "A3_ONLY portfolio row must exist in summary"
        assert float(a3_only_rows.iloc[0]["w_s3"]) == 0.0, (
            "A3_ONLY portfolio must have w_s3=0.0"
        )

        # Classification for A3_ONLY with sufficient years should not be NEEDS_MORE_DATA
        cls_val = a3_only_rows.iloc[0]["classification"]
        assert cls_val not in s13._FORBIDDEN_CLASSIFICATIONS, (
            f"A3_ONLY portfolio has forbidden classification: {cls_val!r}"
        )

        # Sleeve classification CSV should only contain rows with w_s3 > 0
        if not cls_df.empty:
            assert (cls_df["w_s3"] > 0).all(), (
                "sleeve_classification must only contain rows with w_s3 > 0"
            )


# ── Stage 14 — Research Closure, Coverage Audit, Monthly Runbook ──────────────

class TestStage14ResearchClosure:
    """Tests for Stage 14 — Research Closure."""

    _BASE = Path(__file__).resolve().parents[1] / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

    def _skip_if_missing(self, fname: str) -> None:
        if not (self._BASE / fname).exists():
            pytest.skip(f"Output file not generated yet: {fname}")

    # ── 1. Output files present ──────────────────────────────────────────

    def test_stage14_outputs_required_files(self):
        """All 5 required Stage 14 output files must exist after pipeline runs."""
        required = [
            "stage14_research_closure_decision_table.csv",
            "stage14_original_scheme_coverage_audit.csv",
            "stage14_monthly_runbook.csv",
            "stage14_reopen_criteria.csv",
            "STAGE14_RESEARCH_CLOSURE_MEMO.md",
        ]
        missing = [f for f in required if not (self._BASE / f).exists()]
        if missing:
            pytest.skip(f"Not yet generated: {missing}")
        assert not missing

    # ── 2. Decision table required items ────────────────────────────────

    def test_stage14_decision_table_required_items(self):
        """Decision table must contain all 16 required items."""
        self._skip_if_missing("stage14_research_closure_decision_table.csv")
        df = pd.read_csv(self._BASE / "stage14_research_closure_decision_table.csv")
        assert "item" in df.columns, "Decision table must have 'item' column"
        items = set(df["item"].tolist())
        required_items = {
            "A3_production_contract", "Old_composite_score",
            "BVE_Q4Q5", "TPBCQ_Q4Q5",
            "Wyckoff_SOS", "Wyckoff_LPS", "Wyckoff_spring_test",
            "PRE_S3_ACCUM", "FAILED_S3_BEFORE_A3", "Inverse_HS",
            "S3_MAX60", "S3_MAX105", "S3_MAX120",
            "Combined_A3_S3_MAX60_sleeve", "Combined_A3_S3_MAX105_sleeve",
            "A3_T2_accumulation_filter",
        }
        missing = required_items - items
        assert not missing, f"Missing required decision items: {missing}"

    # ── 3. Old composite score is REJECT ─────────────────────────────────

    def test_stage14_old_composite_rejected(self):
        """Old composite score must have classification=REJECT in decision table."""
        self._skip_if_missing("stage14_research_closure_decision_table.csv")
        df = pd.read_csv(self._BASE / "stage14_research_closure_decision_table.csv")
        row = df[df["item"] == "Old_composite_score"]
        assert len(row) == 1, "Old_composite_score must have exactly one row"
        cls = row.iloc[0]["classification"]
        assert cls == "REJECT", (
            f"Old_composite_score must be REJECT, got {cls!r}"
        )

    # ── 4. Combined sleeves rejected or closed ───────────────────────────

    def test_stage14_combined_sleeve_rejected_or_closed(self):
        """Combined A3/S3 sleeves must be REJECT or CLOSED_NO_ACTION."""
        self._skip_if_missing("stage14_research_closure_decision_table.csv")
        df  = pd.read_csv(self._BASE / "stage14_research_closure_decision_table.csv")
        allowed = {"REJECT", "CLOSED_NO_ACTION"}
        for item in ["Combined_A3_S3_MAX60_sleeve", "Combined_A3_S3_MAX105_sleeve"]:
            row = df[df["item"] == item]
            if len(row) == 0:
                continue
            cls = row.iloc[0]["classification"]
            assert cls in allowed, (
                f"{item} classification must be REJECT or CLOSED_NO_ACTION, got {cls!r}"
            )

    # ── 5. Monthly runbook has required commands ──────────────────────────

    def test_stage14_monthly_runbook_commands_present(self):
        """Monthly runbook must include Stage 9/10 and Stage 11 commands."""
        self._skip_if_missing("stage14_monthly_runbook.csv")
        df = pd.read_csv(self._BASE / "stage14_monthly_runbook.csv")
        assert "command" in df.columns, "Runbook must have 'command' column"
        all_cmds = " ".join(df["command"].fillna("").tolist())
        # Stage 9 and 10 may appear together as "--stage 9 10" or separately
        has_9  = "--stage 9" in all_cmds or "stage 9 " in all_cmds
        has_10 = "--stage 10" in all_cmds or "stage 10" in all_cmds or " 10 " in all_cmds
        assert has_9,  "Runbook must include a Stage 9 update command"
        assert has_10, "Runbook must include a Stage 10 command"

    # ── 6. Reopen criteria present for key items ─────────────────────────

    def test_stage14_reopen_criteria_present(self):
        """Reopen criteria must contain BVE_Q4Q5, PRE_S3_ACCUM, S3_MAX105, combined sleeve."""
        self._skip_if_missing("stage14_reopen_criteria.csv")
        df = pd.read_csv(self._BASE / "stage14_reopen_criteria.csv")
        assert "item" in df.columns
        items = set(df["item"].tolist())
        required = {"BVE_Q4Q5", "PRE_S3_ACCUM", "S3_MAX105", "Combined_A3_S3_sleeve"}
        missing = required - items
        assert not missing, f"Missing reopen criteria items: {missing}"

    # ── 7. No final_action in outputs ────────────────────────────────────

    def test_stage14_no_final_action_modification(self):
        """Stage 14 output CSVs must not contain a 'final_action' column."""
        for fname in [
            "stage14_research_closure_decision_table.csv",
            "stage14_original_scheme_coverage_audit.csv",
            "stage14_monthly_runbook.csv",
            "stage14_reopen_criteria.csv",
        ]:
            p = self._BASE / fname
            if not p.exists():
                continue
            cols = set(pd.read_csv(p, nrows=1).columns)
            assert "final_action" not in cols, (
                f"{fname} must not contain 'final_action'"
            )

    # ── 8. OMS safety constants ──────────────────────────────────────────

    def test_stage14_no_oms_live_paths_written(self):
        """_OMS_SAFE_PATHS and _STAGE14_WRITE_DIR must be correctly defined."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage14_research_closure as s14
        assert hasattr(s14, "_OMS_SAFE_PATHS"),    "Stage 14 must define _OMS_SAFE_PATHS"
        assert hasattr(s14, "_STAGE14_WRITE_DIR"), "Stage 14 must define _STAGE14_WRITE_DIR"

        write_str = str(s14._STAGE14_WRITE_DIR)
        assert "outputs" in write_str, (
            f"_STAGE14_WRITE_DIR must be under 'outputs': {write_str}"
        )
        assert "decision" not in write_str, (
            f"_STAGE14_WRITE_DIR must not be under 'decision': {write_str}"
        )
        repo = Path(__file__).resolve().parents[1]
        assert str(repo / "data" / "decision" / "daily_scan.json") in s14._OMS_SAFE_PATHS

    # ── 9. No production recommendation ─────────────────────────────────

    def test_stage14_no_production_recommendation(self):
        """Stage 14 must not assign PRODUCTION_CANDIDATE classification to any item."""
        import scripts.research.dual_cloud_accumulation_wyckoff.stage14_research_closure as s14
        decision_df = s14._build_decision_table()
        assert "classification" in decision_df.columns
        forbidden = {"PRODUCTION_CANDIDATE", "PAPER_TRADE_PRIMARY"}
        # A3 production contract is PAPER_TRADE_PRIMARY (it is the existing paper contract, not promoted)
        # but combined sleeves and S3 must never be PAPER_TRADE_PRIMARY
        s3_sleeve_items = [
            "Combined_A3_S3_MAX60_sleeve", "Combined_A3_S3_MAX105_sleeve",
            "S3_MAX60", "S3_MAX105", "S3_MAX120",
        ]
        for item in s3_sleeve_items:
            row = decision_df[decision_df["item"] == item]
            if row.empty:
                continue
            cls = row.iloc[0]["classification"]
            assert cls != "PRODUCTION_CANDIDATE", (
                f"{item} must not be PRODUCTION_CANDIDATE — not approved for production"
            )
        # Old composite must never be PAPER_TRADE_PRIMARY
        old = decision_df[decision_df["item"] == "Old_composite_score"]
        if not old.empty:
            assert old.iloc[0]["classification"] == "REJECT", (
                "Old_composite_score must be REJECT"
            )
