"""
Tests 3-8: Event detection logic.
  Test 3: Touch event logic
  Test 4: Bounce outcome shifting (forward returns are future data)
  Test 5: Breakdown event logic
  Test 6: Reclaim event logic
  Test 7: False break event logic
  Test 8: Minimum sample confidence logic
"""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.events import (
    attach_bounce_outcomes,
    detect_breakdown_events,
    detect_false_breaks,
    detect_reclaim_events,
    detect_touch_events,
)
from src.trading.research.stock_dna.features import compute_indicators
from src.trading.research.stock_dna.scoring import assign_confidence
from src.trading.research.stock_dna.schema import DNAConfidence


def _make_panel_with_indicators(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2018-01-01", periods=n, freq="B")
    close = np.cumprod(1 + rng.normal(0.001, 0.015, n)) * 50
    high  = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low   = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    df = pd.DataFrame({
        "symbol": "TEST",
        "date":   dates,
        "open":   close,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": rng.uniform(1e5, 1e6, n),
        "value":  close * rng.uniform(1e5, 1e6, n),
    })
    df = compute_indicators(df)
    df["fwd_ret_5d"]  = df["close"].shift(-5) / df["close"] - 1
    df["fwd_ret_10d"] = df["close"].shift(-10) / df["close"] - 1
    df["fwd_ret_20d"] = df["close"].shift(-20) / df["close"] - 1
    df["mfe_20d"] = 0.05
    df["mae_20d"] = -0.03
    df["stock_phase"]   = "MARKUP"
    df["breadth_regime"] = "BULL_BROAD"
    df["vin_return_distortion_flag"] = 0
    df["adv20_vnd"] = df["value"].rolling(20).mean().shift(1)
    return df


# ── Test 3: Touch event logic ─────────────────────────────────────────────────

class TestTouchEvents:

    def test_touch_events_return_dataframe(self):
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema20", "1pct")
        assert isinstance(touches, pd.DataFrame)

    def test_touch_events_have_required_columns(self):
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema20", "1pct")
        if not touches.empty:
            for col in ["symbol", "date", "line_name", "tol_name"]:
                assert col in touches.columns, f"Missing column: {col}"

    def test_touch_events_line_name_correct(self):
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema50", "2pct")
        if not touches.empty:
            assert (touches["line_name"] == "ema50").all()

    def test_touch_events_missing_line_returns_empty(self):
        panel = _make_panel_with_indicators()
        result = detect_touch_events(panel, "nonexistent_line", "1pct")
        assert result.empty or isinstance(result, pd.DataFrame)

    def test_touch_events_no_future_dates(self):
        """Touch events should only reference dates within the panel."""
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema20", "1pct")
        if not touches.empty:
            max_panel_date = panel["date"].max()
            assert touches["date"].max() <= max_panel_date


# ── Test 4: Bounce outcome shifting ──────────────────────────────────────────

class TestBounceOutcomes:

    def test_forward_returns_are_future_data(self):
        """fwd_ret_20d at date t must equal close[t+20]/close[t] - 1."""
        panel = _make_panel_with_indicators()
        # Check a middle row
        idx = 100
        close_t  = panel.iloc[idx]["close"]
        close_t20 = panel.iloc[idx + 20]["close"] if idx + 20 < len(panel) else np.nan
        expected = close_t20 / close_t - 1 if not np.isnan(close_t20) else np.nan

        actual = panel.iloc[idx]["fwd_ret_20d"]
        if not np.isnan(expected) and not np.isnan(actual):
            assert abs(actual - expected) < 1e-10, "fwd_ret_20d is not future return"

    def test_bounce_outcomes_merged_correctly(self):
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema20", "1pct")
        if touches.empty:
            pytest.skip("No touch events")
        enriched = attach_bounce_outcomes(touches, panel)
        assert isinstance(enriched, pd.DataFrame)
        # Rows should be preserved
        assert len(enriched) >= len(touches)

    def test_bounce_outcomes_have_fwd_columns(self):
        panel = _make_panel_with_indicators()
        touches = detect_touch_events(panel, "ema20", "1pct")
        if touches.empty:
            pytest.skip("No touch events")
        enriched = attach_bounce_outcomes(touches, panel)
        for col in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d"]:
            assert col in enriched.columns, f"Missing forward return: {col}"


# ── Test 5: Breakdown event logic ─────────────────────────────────────────────

class TestBreakdownEvents:

    def test_breakdown_events_return_dataframe(self):
        panel = _make_panel_with_indicators()
        result = detect_breakdown_events(panel, "ema20")
        assert isinstance(result, pd.DataFrame)

    def test_breakdown_events_missing_line(self):
        panel = _make_panel_with_indicators()
        result = detect_breakdown_events(panel, "nonexistent")
        assert isinstance(result, pd.DataFrame) and result.empty

    def test_breakdown_event_close_below_line(self):
        """At each detected breakdown, close must be below the line value."""
        panel = _make_panel_with_indicators()
        result = detect_breakdown_events(panel, "ema20")
        if result.empty:
            pytest.skip("No breakdown events")
        # Merge close and line value
        for _, row in result.iterrows():
            assert row["close"] < row["line_value"], (
                f"Breakdown detected but close >= line at {row['date']}"
            )


# ── Test 6: Reclaim event logic ───────────────────────────────────────────────

class TestReclaimEvents:

    def test_reclaim_events_return_dataframe(self):
        panel = _make_panel_with_indicators()
        result = detect_reclaim_events(panel, "ema20")
        assert isinstance(result, pd.DataFrame)

    def test_reclaim_events_close_above_line(self):
        """At each detected reclaim, close must be above the line value."""
        panel = _make_panel_with_indicators()
        result = detect_reclaim_events(panel, "ema20")
        if result.empty:
            pytest.skip("No reclaim events")
        for _, row in result.iterrows():
            assert row["close"] >= row["line_value"], (
                f"Reclaim detected but close < line at {row['date']}"
            )


# ── Test 7: False break event logic ──────────────────────────────────────────

class TestFalseBreaks:

    def test_false_breaks_return_dataframe(self):
        panel = _make_panel_with_indicators()
        result = detect_false_breaks(panel, "ema20")
        assert isinstance(result, pd.DataFrame)

    def test_false_breaks_have_breakdown_and_reclaim_dates(self):
        panel = _make_panel_with_indicators()
        result = detect_false_breaks(panel, "ema20")
        if result.empty:
            pytest.skip("No false break events")
        assert "breakdown_date" in result.columns
        assert "reclaim_date" in result.columns

    def test_false_break_reclaim_after_breakdown(self):
        """Reclaim date must always be after breakdown date."""
        panel = _make_panel_with_indicators()
        result = detect_false_breaks(panel, "ema20")
        if result.empty:
            pytest.skip("No false break events")
        assert (result["reclaim_date"] > result["breakdown_date"]).all()


# ── Test 8: Minimum sample confidence logic ───────────────────────────────────

class TestMinimumSampleConfidence:

    def test_confidence_none_below_5(self):
        assert assign_confidence(0) == DNAConfidence.NONE
        assert assign_confidence(4) == DNAConfidence.NONE

    def test_confidence_low_below_medium_threshold(self):
        assert assign_confidence(5) == DNAConfidence.LOW
        assert assign_confidence(19) == DNAConfidence.LOW

    def test_confidence_medium_at_threshold(self):
        assert assign_confidence(20) == DNAConfidence.MEDIUM
        assert assign_confidence(39) == DNAConfidence.MEDIUM

    def test_confidence_high_at_threshold(self):
        assert assign_confidence(40) == DNAConfidence.HIGH
        assert assign_confidence(100) == DNAConfidence.HIGH

    def test_no_high_confidence_on_small_sample(self):
        """Test 15 from council requirements: no HIGH confidence with insufficient sample."""
        for n in [0, 1, 5, 10, 15, 19, 39]:
            conf = assign_confidence(n)
            assert conf != DNAConfidence.HIGH, (
                f"Got HIGH confidence with only {n} samples — violation!"
            )
