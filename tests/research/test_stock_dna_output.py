"""
Tests 12-15, 17-18: Output integrity, determinism, empty data handling,
shuffled-null benchmark, and regime-split reporting.
  Test 12: Output schemas are stable
  Test 13: Deterministic results with same input
  Test 14: Empty / missing data handled gracefully
  Test 15: No HIGH confidence with insufficient sample (also in events test)
  Test 17: Shuffled-null benchmark correctness
  Test 18: Regime-split reporting
"""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.events import (
    aggregate_line_scores,
    attach_bounce_outcomes,
    detect_breakdown_events,
    detect_touch_events,
)
from src.trading.research.stock_dna.features import compute_indicators
from src.trading.research.stock_dna.profiles import (
    collect_all_touch_events,
    score_symbol_line,
)
from src.trading.research.stock_dna.scoring import (
    assign_confidence,
    compute_line_obedience_score,
    run_shuffled_null_benchmark,
)
from src.trading.research.stock_dna.schema import DNAConfidence


def _make_panel(n: int = 300, seed: int = 42, sym: str = "TEST") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2018-01-01", periods=n, freq="B")
    close = np.cumprod(1 + rng.normal(0.001, 0.015, n)) * 50
    high  = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low   = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    df = pd.DataFrame({
        "symbol": sym,
        "date":   dates,
        "open":   close,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": rng.uniform(1e5, 1e6, n),
        "value":  close * rng.uniform(1e5, 1e6, n),
    })
    df = compute_indicators(df)
    df["fwd_ret_5d"]  = df["close"].shift(-5)  / df["close"] - 1
    df["fwd_ret_10d"] = df["close"].shift(-10) / df["close"] - 1
    df["fwd_ret_20d"] = df["close"].shift(-20) / df["close"] - 1
    df["mfe_20d"] = rng.uniform(0.01, 0.10, n)
    df["mae_20d"] = -rng.uniform(0.01, 0.05, n)
    df["stock_phase"] = "MARKUP"
    df["breadth_regime"] = np.where(
        np.tile([1, 0] * (n // 2 + 1), 1)[:n] == 1, "BULL_BROAD", "BEAR"
    )
    df["vin_return_distortion_flag"] = 0
    df["adv20_vnd"] = df["value"].rolling(20).mean().shift(1)
    df["adv50_vnd"] = df["value"].rolling(50).mean().shift(1)
    return df.reset_index(drop=True)


# ── Test 12: Output schemas are stable ───────────────────────────────────────

EXPECTED_PROFILE_COLS = [
    "symbol", "data_start", "data_end", "n_bars", "liquidity_bucket",
    "primary_support_line", "danger_line", "best_tolerance",
    "confidence", "line_obedience_score_raw", "n_touch",
    "bounce_rate_20d", "median_fwd_ret_20d",
    "regime_obedience_bull", "regime_obedience_bear",
    "oos_lift", "instability_penalty", "vin_distortion_flag",
    "production_status", "operator_note",
]

class TestOutputSchemas:

    def test_touch_event_schema(self):
        panel = _make_panel()
        touches = detect_touch_events(panel, "ema20", "1pct")
        if not touches.empty:
            for col in ["symbol", "date", "line_name", "tol_name"]:
                assert col in touches.columns

    def test_score_symbol_line_schema(self):
        panel = _make_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        sym  = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]
        result = score_symbol_line(touch_df, sym, line, tol)

        required = ["symbol", "line_name", "tol_name", "n_touch", "confidence",
                    "line_obedience_score_raw", "regime_obedience_bull", "regime_obedience_bear"]
        for k in required:
            assert k in result, f"Missing key in score_symbol_line output: {k}"

    def test_profile_columns_match_expected(self):
        from src.trading.research.stock_dna.profiles import build_symbol_profiles
        panel = _make_panel(n=400, seed=7)
        touch_df = collect_all_touch_events(panel)

        if touch_df.empty:
            pytest.skip("No touch events for profile schema test")

        from src.trading.research.stock_dna.profiles import build_walkforward_line_scores
        wf = build_walkforward_line_scores(panel, touch_df)
        if wf.empty:
            pytest.skip("No walk-forward scores for profile schema test")

        profiles = build_symbol_profiles(touch_df, wf, panel)
        if profiles.empty:
            pytest.skip("No profiles built")

        for col in EXPECTED_PROFILE_COLS:
            assert col in profiles.columns, (
                f"Profile schema missing column: {col}. "
                f"Present: {list(profiles.columns)}"
            )


# ── Test 13: Deterministic results with same input ────────────────────────────

class TestDeterministicResults:

    def test_touch_events_are_deterministic(self):
        panel = _make_panel()
        r1 = detect_touch_events(panel.copy(), "ema20", "1pct")
        r2 = detect_touch_events(panel.copy(), "ema20", "1pct")
        pd.testing.assert_frame_equal(r1, r2, check_like=False)

    def test_score_symbol_line_is_deterministic(self):
        panel = _make_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        sym  = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]

        r1 = score_symbol_line(touch_df, sym, line, tol)
        r2 = score_symbol_line(touch_df, sym, line, tol)
        assert r1["line_obedience_score_raw"] == r2["line_obedience_score_raw"]
        assert r1["confidence"] == r2["confidence"]

    def test_shuffled_null_benchmark_deterministic(self):
        """With the same rng_seed, shuffled-null should produce identical results."""
        panel = _make_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        scores = pd.DataFrame([
            {"symbol": touch_df["symbol"].iloc[0], "confidence": "MEDIUM", "line_obedience_score_raw": 0.6}
        ])
        r1 = run_shuffled_null_benchmark(touch_df, scores, n_runs=50, rng_seed=42)
        r2 = run_shuffled_null_benchmark(touch_df, scores, n_runs=50, rng_seed=42)
        assert r1["null_mean"] == r2["null_mean"]


# ── Test 14: Empty / missing data handled gracefully ─────────────────────────

class TestEmptyDataHandling:

    def test_touch_events_on_empty_panel(self):
        panel = pd.DataFrame(columns=["symbol", "date", "close", "high", "low", "value",
                                       "ema20", "atr14", "adv20_vnd"])
        result = detect_touch_events(panel, "ema20", "1pct")
        assert isinstance(result, pd.DataFrame)

    def test_breakdown_events_on_empty_panel(self):
        panel = pd.DataFrame(columns=["symbol", "date", "close", "high", "low", "ema20"])
        result = detect_breakdown_events(panel, "ema20")
        assert isinstance(result, pd.DataFrame)

    def test_shuffled_null_on_empty_inputs(self):
        result = run_shuffled_null_benchmark(pd.DataFrame(), pd.DataFrame())
        assert result["passes_null_test"] is False
        assert result["z_score"] is None or pd.isna(result["z_score"])

    def test_score_symbol_line_missing_symbol(self):
        touch_df = pd.DataFrame(columns=["symbol", "date", "line_name", "tol_name"])
        result = score_symbol_line(touch_df, "NONEXISTENT", "ema20", "1pct")
        assert result["n_touch"] == 0
        assert result["confidence"] == DNAConfidence.NONE.value

    def test_collect_all_touch_events_on_minimal_panel(self):
        """Very short panel should return empty or minimal touch events without crashing."""
        panel = _make_panel(n=30)  # Too short for most indicators
        result = collect_all_touch_events(panel)
        assert isinstance(result, pd.DataFrame)


# ── Test 17: Shuffled-null benchmark ─────────────────────────────────────────

class TestShuffledNullBenchmark:

    def test_shuffled_null_returns_required_keys(self):
        panel = _make_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")

        scores = pd.DataFrame([{
            "symbol": "TEST", "confidence": "MEDIUM", "line_obedience_score_raw": 0.6
        }])
        result = run_shuffled_null_benchmark(touch_df, scores, n_runs=20)
        for key in ["real_mean_score", "null_mean", "null_std", "z_score", "passes_null_test"]:
            assert key in result, f"Missing key in null benchmark output: {key}"

    def test_shuffled_null_z_score_is_float_or_nan(self):
        panel = _make_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        scores = pd.DataFrame([{"symbol": "TEST", "confidence": "LOW"}])
        result = run_shuffled_null_benchmark(touch_df, scores, n_runs=10)
        z = result["z_score"]
        assert z is None or isinstance(z, float) or pd.isna(z)

    def test_shuffled_null_with_no_medium_plus_returns_not_passing(self):
        """If no MEDIUM/HIGH profiles, benchmark should not pass."""
        touch_df = pd.DataFrame({"symbol": ["A"] * 20, "fwd_ret_20d": [0.01] * 20})
        scores   = pd.DataFrame([{"symbol": "A", "confidence": "NONE"}])
        result   = run_shuffled_null_benchmark(touch_df, scores)
        assert result["passes_null_test"] is False


# ── Test 18: Regime-split reporting ──────────────────────────────────────────

class TestRegimeSplitReporting:

    def test_score_has_regime_obedience_bull_and_bear(self):
        """score_symbol_line must return regime_obedience_bull and regime_obedience_bear."""
        panel = _make_panel(n=400)
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        sym  = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]
        result = score_symbol_line(touch_df, sym, line, tol)
        assert "regime_obedience_bull" in result
        assert "regime_obedience_bear" in result

    def test_regime_obedience_is_in_valid_range_or_nan(self):
        """regime_obedience_bull/bear must be in [0, 1] or NaN."""
        panel = _make_panel(n=400)
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")
        sym  = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]
        result = score_symbol_line(touch_df, sym, line, tol)

        for regime_key in ["regime_obedience_bull", "regime_obedience_bear"]:
            val = result[regime_key]
            if not pd.isna(val):
                assert 0.0 <= val <= 1.0, f"{regime_key}={val} outside [0,1]"

    def test_bull_and_bear_use_different_data(self):
        """
        Bull and bear regime obedience should differ when panel has mixed regimes.
        (Not always different, but pipeline should produce non-identical NaN-free results
        when enough data from each regime exists.)
        """
        panel = _make_panel(n=800, seed=5)  # Long panel with mixed regimes
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")

        sym  = touch_df["symbol"].iloc[0]
        bull_touch = touch_df[(touch_df["symbol"] == sym) &
                               (touch_df["breadth_regime"].isin(["BULL_BROAD", "BULL_NARROW"]))]
        bear_touch = touch_df[(touch_df["symbol"] == sym) &
                               (touch_df["breadth_regime"].isin(["BEAR", "STRESS"]))]

        if len(bull_touch) < 5 or len(bear_touch) < 5:
            pytest.skip("Not enough bull/bear events to compare")

        # Check that regime filtering produces different sample sizes
        assert len(bull_touch) != len(bear_touch), (
            "Bull and bear regime touch counts are equal — regime filtering may not be working"
        )
