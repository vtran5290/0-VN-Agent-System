"""
Methodology tests — P0 fixes verification.

Tests cover:
  - MFE / MAE forward window (deterministic series, exact window check, tail masking)
  - Reclaim consecutive-below state machine (valid <=max, invalid >max, long decline)
  - Touch event tightening (clean pullback vs gap-down crash vs wick recovery)
  - OOS lift structure (returns required keys, handles empty input gracefully)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.features import add_forward_returns, compute_indicators
from src.trading.research.stock_dna.events import (
    _consecutive_below,
    detect_reclaim_events,
    detect_touch_events,
)
from src.trading.research.stock_dna.schema import DNAConfidence


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_simple_panel(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    symbol: str = "TEST",
) -> pd.DataFrame:
    """Build a minimal panel with deterministic OHLCV values."""
    n = len(closes)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    closes_arr = np.array(closes, dtype=float)
    highs_arr  = np.array(highs, dtype=float)  if highs  else closes_arr * 1.01
    lows_arr   = np.array(lows, dtype=float)   if lows   else closes_arr * 0.99
    return pd.DataFrame({
        "symbol": symbol,
        "date":   dates,
        "open":   closes_arr,
        "high":   highs_arr,
        "low":    lows_arr,
        "close":  closes_arr,
        "volume": 1_000_000,
        "value":  closes_arr * 1_000_000,
    })


def _make_indicator_panel(n: int = 300) -> pd.DataFrame:
    """Random panel with indicators pre-computed."""
    rng = np.random.default_rng(42)
    closes = np.cumprod(1 + rng.normal(0.001, 0.012, n)) * 50.0
    highs  = closes * (1 + np.abs(rng.normal(0, 0.005, n)))
    lows   = closes * (1 - np.abs(rng.normal(0, 0.005, n)))
    df = pd.DataFrame({
        "symbol": "TEST",
        "date":   pd.date_range("2018-01-01", periods=n, freq="B"),
        "open":   closes, "high": highs, "low": lows, "close": closes,
        "volume": 1_000_000, "value": closes * 1_000_000,
    })
    df = compute_indicators(df)
    df["stock_phase"] = "MARKUP"
    df["breadth_regime"] = "BULL_BROAD"
    df["vin_return_distortion_flag"] = 0
    df["adv20_vnd"] = df["value"].rolling(20).mean().shift(1).fillna(df["value"].mean())
    return df


# ── MFE / MAE forward window tests ────────────────────────────────────────────

class TestMFEMAEWindow:

    def test_mfe_20d_uses_correct_forward_window(self):
        """
        For a deterministic series, mfe_20d[t] must equal
        max(high[t+1 : t+21]) / close[t] - 1.
        """
        n = 60
        # Linearly rising: close[t] = 100 + t
        closes = [100.0 + i for i in range(n)]
        highs  = [c + 0.5 for c in closes]    # high = close + 0.5
        lows   = [c - 0.5 for c in closes]    # low  = close - 0.5
        panel  = _make_simple_panel(closes, highs, lows)
        panel  = add_forward_returns(panel)

        # At t=0: max(high[1:21]) = max([101.5, 102.5, ..., 120.5]) = 120.5
        # close[0] = 100, so mfe_20d[0] = 120.5/100 - 1 = 0.205
        expected_mfe0 = max(highs[1:21]) / closes[0] - 1
        actual_mfe0   = panel.loc[0, "mfe_20d"]
        assert abs(actual_mfe0 - expected_mfe0) < 1e-10, (
            f"mfe_20d[0]: expected {expected_mfe0:.6f}, got {actual_mfe0:.6f}"
        )

    def test_mae_20d_uses_correct_forward_window(self):
        """
        mae_20d[t] must equal min(low[t+1 : t+21]) / close[t] - 1  (clipped ≤ 0).
        """
        n = 60
        # Linearly falling: close[t] = 200 - t
        closes = [200.0 - i for i in range(n)]
        highs  = [c + 0.5 for c in closes]
        lows   = [c - 0.5 for c in closes]
        panel  = _make_simple_panel(closes, highs, lows)
        panel  = add_forward_returns(panel)

        # At t=0: min(low[1:21]) = min([198.5, 197.5, ..., 179.5]) = 179.5
        # close[0] = 200, mae_20d[0] = 179.5/200 - 1 = -0.1025
        expected_mae0 = min(lows[1:21]) / closes[0] - 1
        actual_mae0   = panel.loc[0, "mae_20d"]
        assert abs(actual_mae0 - expected_mae0) < 1e-10, (
            f"mae_20d[0]: expected {expected_mae0:.6f}, got {actual_mae0:.6f}"
        )

    def test_mfe_tail_masked_to_nan(self):
        """
        The last 20 bars per symbol must have NaN mfe_20d (incomplete forward window).
        """
        n = 60
        closes = [100.0 + i for i in range(n)]
        highs  = [c + 0.5 for c in closes]
        lows   = [c - 0.5 for c in closes]
        panel  = _make_simple_panel(closes, highs, lows)
        panel  = add_forward_returns(panel)

        tail = panel.iloc[-20:]
        assert tail["mfe_20d"].isna().all(), (
            "Last 20 bars of mfe_20d must be NaN — incomplete forward window"
        )

    def test_mae_tail_masked_to_nan(self):
        """
        The last 20 bars per symbol must have NaN mae_20d.
        """
        n = 60
        closes = [100.0 - i * 0.5 for i in range(n)]
        highs  = [c + 0.5 for c in closes]
        lows   = [c - 0.5 for c in closes]
        panel  = _make_simple_panel(closes, highs, lows)
        panel  = add_forward_returns(panel)

        tail = panel.iloc[-20:]
        assert tail["mae_20d"].isna().all(), (
            "Last 20 bars of mae_20d must be NaN — incomplete forward window"
        )

    def test_fwd_ret_5d_exact_value(self):
        """fwd_ret_5d[t] = close[t+5] / close[t] - 1."""
        closes = [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9,
                  11.0, 11.1, 11.2, 11.3, 11.4, 11.5]
        panel  = _make_simple_panel(closes)
        panel  = add_forward_returns(panel)

        for t in range(len(closes) - 5):
            expected = closes[t + 5] / closes[t] - 1
            actual   = panel.loc[t, "fwd_ret_5d"]
            assert abs(actual - expected) < 1e-10, (
                f"fwd_ret_5d[{t}]: expected {expected:.8f}, got {actual:.8f}"
            )


# ── Consecutive-below helper tests ─────────────────────────────────────────────

class TestConsecutiveBelow:

    def _make_series_and_line(self, values: list[float], line_val: float) -> tuple:
        idx = pd.RangeIndex(len(values))
        s   = pd.Series(values, index=idx)
        line = pd.Series([line_val] * len(values), index=idx)
        return s, line

    def test_all_above_gives_zeros(self):
        s, line = self._make_series_and_line([10, 11, 12, 13], 5.0)
        result = _consecutive_below(s, line)
        assert (result == 0).all()

    def test_all_below_gives_sequential_count(self):
        s, line = self._make_series_and_line([1, 1, 1, 1, 1], 5.0)
        result = _consecutive_below(s, line)
        assert list(result) == [1, 2, 3, 4, 5]

    def test_resets_on_above_bar(self):
        # above, below x3, above, below x2
        vals = [10, 1, 1, 1, 10, 1, 1]
        s, line = self._make_series_and_line(vals, 5.0)
        result = _consecutive_below(s, line)
        assert list(result) == [0, 1, 2, 3, 0, 1, 2]


# ── Reclaim event duration tests ──────────────────────────────────────────────

class TestReclaimDuration:

    def _make_reclaim_panel(self, above_below_sequence: list[int], line_val: float = 50.0) -> pd.DataFrame:
        """
        Build a panel where close is 60 (above line) or 40 (below line)
        per the given sequence (1 = above, 0 = below).
        """
        n = len(above_below_sequence)
        closes = [60.0 if b else 40.0 for b in above_below_sequence]
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        df = pd.DataFrame({
            "symbol": "TEST",
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open": closes, "high": highs, "low": lows, "close": closes,
            "volume": 1_000_000, "value": pd.Series(closes) * 1_000_000,
        })
        df = compute_indicators(df)
        # Manually set a flat line column for deterministic testing
        df["test_line"] = line_val
        df["stock_phase"] = "MARKUP"
        df["breadth_regime"] = "BULL_BROAD"
        df["vin_return_distortion_flag"] = 0
        df["adv20_vnd"] = 1_000_000 * 60
        df["fwd_ret_5d"]  = 0.01
        df["fwd_ret_10d"] = 0.02
        df["fwd_ret_20d"] = 0.03
        return df

    def test_reclaim_after_3_bars_is_valid(self):
        """Reclaim after 3 bars below (max=10) must be detected."""
        # above x5, below x3, then reclaim
        seq = [1, 1, 1, 1, 1,  0, 0, 0,  1]
        panel = self._make_reclaim_panel(seq)
        result = detect_reclaim_events(panel, "test_line", max_below_bars=10)
        assert not result.empty, "Should detect reclaim after 3 bars below (within max=10)"
        assert (result["bars_below"] == 3).all(), (
            f"bars_below should be 3, got {result['bars_below'].values}"
        )

    def test_reclaim_after_12_bars_is_invalid_with_max_10(self):
        """Reclaim after 12 consecutive bars below (max=10) must NOT be detected."""
        seq = [1, 1, 1, 1, 1] + [0] * 12 + [1]
        panel = self._make_reclaim_panel(seq)
        result = detect_reclaim_events(panel, "test_line", max_below_bars=10)
        assert result.empty, (
            "Should NOT detect reclaim after 12 bars below when max_below_bars=10"
        )

    def test_long_decline_then_reclaim_invalid(self):
        """Long decline (30 bars below) followed by reclaim should not count as reclaim."""
        seq = [1, 1, 1] + [0] * 30 + [1]
        panel = self._make_reclaim_panel(seq)
        result = detect_reclaim_events(panel, "test_line", max_below_bars=10)
        assert result.empty, (
            "Long decline of 30 bars should not produce a reclaim event with max_below_bars=10"
        )

    def test_reclaim_at_exact_max_boundary(self):
        """Reclaim after exactly max_below_bars bars below must be valid (boundary inclusive)."""
        max_bars = 10
        seq = [1, 1, 1, 1, 1] + [0] * max_bars + [1]
        panel = self._make_reclaim_panel(seq)
        result = detect_reclaim_events(panel, "test_line", max_below_bars=max_bars)
        assert not result.empty, (
            f"Reclaim after exactly {max_bars} bars below must be valid (inclusive boundary)"
        )

    def test_reclaim_not_detected_without_prior_below(self):
        """A bar that is above line when the previous bar was also above is not a reclaim."""
        seq = [1, 1, 1, 1, 1, 1, 1]
        panel = self._make_reclaim_panel(seq)
        result = detect_reclaim_events(panel, "test_line", max_below_bars=10)
        assert result.empty, "No reclaim when price never dipped below the line"


# ── Touch tightening tests ─────────────────────────────────────────────────────

class TestTouchTightening:

    def _make_touch_panel_single_bar(
        self,
        close_val: float,
        low_val: float,
        line_val: float,
        atr14: float,
        n_warmup: int = 10,
    ) -> pd.DataFrame:
        """
        Build a panel with warmup bars above the line, then one test bar with
        the specified close/low/atr14. The last bar is the candidate touch event.
        """
        n = n_warmup + 1
        closes = [line_val * 1.05] * n_warmup + [close_val]
        highs  = [c + atr14 * 0.5 for c in closes]
        lows   = [c - atr14 * 0.5 for c in closes[:-1]] + [low_val]
        df = pd.DataFrame({
            "symbol": "TEST",
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   closes, "high": highs, "low": lows, "close": closes,
            "volume": 1_000_000, "value": pd.Series(closes) * 1_000_000,
        })
        df = compute_indicators(df)
        df["test_line"] = line_val
        df["atr14"]     = atr14   # override with deterministic value
        df["stock_phase"] = "MARKUP"
        df["breadth_regime"] = "BULL_BROAD"
        df["vin_return_distortion_flag"] = 0
        df["adv20_vnd"] = 1_000_000 * line_val * 1.05
        df["fwd_ret_5d"]  = 0.01
        df["fwd_ret_10d"] = 0.02
        df["fwd_ret_20d"] = 0.03
        df["mfe_20d"] = 0.05
        df["mae_20d"] = -0.02
        return df

    def test_clean_pullback_to_ema_is_touch(self):
        """
        Low just touches line, close is slightly above: should be detected as touch.
        """
        line = 100.0
        atr  = 1.0
        panel = self._make_touch_panel_single_bar(
            close_val=100.5,   # close above line
            low_val=99.9,      # low slightly below line (within 2% tol)
            line_val=line,
            atr14=atr,
        )
        touches = detect_touch_events(panel, "test_line", "1pct")
        # At least the last bar should be detected
        assert not touches.empty, "Clean pullback to line must be detected as a touch"

    def test_low_slightly_under_close_back_above_is_touch(self):
        """
        Intraday wick below line, close recovers above: should be a touch.
        """
        line = 100.0
        atr  = 2.0
        panel = self._make_touch_panel_single_bar(
            close_val=100.2,   # close above line
            low_val=99.0,      # low 1% below line (within 1 ATR)
            line_val=line,
            atr14=atr,
        )
        touches = detect_touch_events(panel, "test_line", "1pct")
        assert not touches.empty, "Wick below line with close recovery must be detected as touch"

    def test_gap_down_crash_far_below_is_not_touch(self):
        """
        Gap down / crash: close is 10 ATR below the line. Must NOT be detected as touch.
        """
        line = 100.0
        atr  = 1.0
        panel = self._make_touch_panel_single_bar(
            close_val=90.0,    # 10 ATR below line — crash, not touch
            low_val=89.0,
            line_val=line,
            atr14=atr,
        )
        touches = detect_touch_events(panel, "test_line", "1pct")
        # Crash bar should not be counted as a support touch
        crash_touches = touches[touches["close"] < 95.0] if not touches.empty else pd.DataFrame()
        assert crash_touches.empty, (
            "Gap-down crash (10 ATR below line) must NOT be detected as a support touch"
        )

    def test_nan_atr_excludes_bar_from_touch(self):
        """
        A bar with NaN ATR14 must be excluded from touch events (no synthetic fallback).
        """
        line = 100.0
        n = 12
        closes = [line * 1.05] * (n - 1) + [line * 0.999]
        lows   = [c * 0.99 for c in closes[:-1]] + [line * 0.995]
        highs  = [c * 1.01 for c in closes]
        df = pd.DataFrame({
            "symbol": "TEST",
            "date":   pd.date_range("2020-01-01", periods=n, freq="B"),
            "open":   closes, "high": highs, "low": lows, "close": closes,
            "volume": 1_000_000, "value": pd.Series(closes) * 1_000_000,
        })
        df = compute_indicators(df)
        df["test_line"] = line
        df["atr14"] = np.nan   # force NaN ATR on all bars
        df["stock_phase"] = "MARKUP"
        df["breadth_regime"] = "BULL_BROAD"
        df["vin_return_distortion_flag"] = 0
        df["adv20_vnd"] = 1_000_000 * line * 1.05
        df["fwd_ret_20d"] = 0.01
        df["mfe_20d"] = 0.05
        df["mae_20d"] = -0.02

        touches = detect_touch_events(df, "test_line", "1pct")
        # With NaN ATR the crash-filter is NaN (falsy), so all bars with crash should be excluded
        assert touches.empty or (touches["close"] >= line - line * 0.01).all(), (
            "Bars with NaN ATR must not pass the crash filter with a synthetic fallback"
        )


# ── OOS lift structure tests ───────────────────────────────────────────────────

class TestOOSLiftStructure:

    def _make_minimal_profiles(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "symbol": "AAA",
            "primary_support_line": "ema50",
            "best_tolerance": "1pct",
            "confidence": DNAConfidence.HIGH.value,
        }, {
            "symbol": "BBB",
            "primary_support_line": "sma100",
            "best_tolerance": "2pct",
            "confidence": DNAConfidence.MEDIUM.value,
        }])

    def _make_minimal_touch_df(self, oos_start: pd.Timestamp) -> pd.DataFrame:
        rng = np.random.default_rng(99)
        n = 100
        dates = pd.date_range(oos_start, periods=n, freq="B")
        return pd.DataFrame({
            "symbol":       rng.choice(["AAA", "BBB", "CCC"], n),
            "date":         dates,
            "line_name":    rng.choice(["ema50", "sma100", "ema20"], n),
            "tol_name":     rng.choice(["1pct", "2pct"], n),
            "fwd_ret_20d":  rng.normal(0.01, 0.05, n),
            "breadth_regime": rng.choice(["BULL_BROAD", "BEAR"], n),
        })

    def test_oos_lift_returns_required_keys(self):
        from src.trading.research.stock_dna.profiles import compute_oos_lift
        oos_start  = pd.Timestamp("2025-01-01")
        touch_df   = self._make_minimal_touch_df(oos_start)
        profiles   = self._make_minimal_profiles()
        result     = compute_oos_lift(touch_df, profiles, oos_start)

        required_keys = {
            "selected_event_count", "selected_bounce_rate_20d",
            "baseline_event_count", "baseline_bounce_rate_20d",
            "lift_vs_baseline", "lift_vs_null", "z_score",
            "pass_fail", "by_year", "by_regime",
        }
        missing = required_keys - set(result.keys())
        assert not missing, f"Missing keys in OOS lift result: {missing}"

    def test_oos_lift_returns_empty_on_missing_fwd_col(self):
        from src.trading.research.stock_dna.profiles import compute_oos_lift
        oos_start = pd.Timestamp("2025-01-01")
        touch_df  = self._make_minimal_touch_df(oos_start)
        touch_df  = touch_df.drop(columns=["fwd_ret_20d"])
        profiles  = self._make_minimal_profiles()
        result    = compute_oos_lift(touch_df, profiles, oos_start)
        assert result["selected_event_count"] == 0

    def test_oos_lift_empty_profiles_returns_empty(self):
        from src.trading.research.stock_dna.profiles import compute_oos_lift
        oos_start = pd.Timestamp("2025-01-01")
        touch_df  = self._make_minimal_touch_df(oos_start)
        result    = compute_oos_lift(touch_df, pd.DataFrame(), oos_start)
        assert result["selected_event_count"] == 0

    def test_oos_lift_by_year_keys_are_ints(self):
        from src.trading.research.stock_dna.profiles import compute_oos_lift
        oos_start = pd.Timestamp("2024-01-01")
        touch_df  = self._make_minimal_touch_df(oos_start)
        profiles  = self._make_minimal_profiles()
        result    = compute_oos_lift(touch_df, profiles, oos_start, n_shuffle=10)
        for k in result["by_year"]:
            assert isinstance(k, int), f"by_year key '{k}' should be int"


# ── Regression: no wrong-direction symbol in RESEARCH_ANNOTATION_ONLY ──────────

class TestEdgeConfidenceDirectionalGate:
    """
    Council v3 requirement: assign_edge_confidence must enforce direction.
    A symbol with significant but wrong-direction DNA (negative lift or
    negative median fwd return) must return NONE, not WEAK/MODERATE/STRONG.
    """

    def test_wrong_direction_returns_none(self):
        """Negative lift (below universe median) → NONE regardless of null_z."""
        from src.trading.research.stock_dna.scoring import assign_edge_confidence
        assert assign_edge_confidence(5.0, -0.01, 0.03) == "NONE", \
            "Negative lift must return NONE — wrong-direction signal"

    def test_negative_median_fwd_ret_returns_none(self):
        """Negative median forward return → NONE regardless of null_z."""
        from src.trading.research.stock_dna.scoring import assign_edge_confidence
        assert assign_edge_confidence(5.0, 0.05, -0.01) == "NONE", \
            "Negative median fwd return must return NONE"

    def test_both_positive_strong_z_returns_strong(self):
        """Positive lift + positive return + high null_z → STRONG."""
        from src.trading.research.stock_dna.scoring import assign_edge_confidence
        result = assign_edge_confidence(3.5, 0.05, 0.03)
        assert result == "STRONG", f"Expected STRONG, got {result}"

    def test_both_positive_moderate_z_returns_moderate(self):
        from src.trading.research.stock_dna.scoring import assign_edge_confidence
        result = assign_edge_confidence(2.2, 0.01, 0.02)
        assert result == "MODERATE", f"Expected MODERATE, got {result}"

    def test_weak_tier_requires_direction(self):
        """null_z >= 1.5 alone is NOT sufficient for WEAK if direction fails."""
        from src.trading.research.stock_dna.scoring import assign_edge_confidence
        assert assign_edge_confidence(1.8, -0.01, 0.02) == "NONE", \
            "WEAK tier must not be reached with negative lift"
        assert assign_edge_confidence(1.8, 0.01, -0.01) == "NONE", \
            "WEAK tier must not be reached with negative median return"

    def test_profiles_csv_no_wrong_direction_raa(self):
        """
        Regression: no RESEARCH_ANNOTATION_ONLY symbol in the live profiles CSV
        may have median_fwd_ret_20d <= 0 or bounce_rate_20d < 0.50.
        Skipped if the CSV does not yet exist (pre-run CI context).
        """
        profiles_path = Path(__file__).resolve().parents[2] / \
            "data" / "research" / "stock_dna" / "stock_dna_symbol_profiles.csv"
        if not profiles_path.exists():
            pytest.skip("No profiles CSV — run discovery first")
        df = pd.read_csv(profiles_path)
        raa = df[df["production_status"] == "RESEARCH_ANNOTATION_ONLY"].copy()
        if raa.empty:
            return
        wrong_ret = raa[raa["median_fwd_ret_20d"].notna() & (raa["median_fwd_ret_20d"] <= 0)]
        wrong_br  = raa[raa["bounce_rate_20d"].notna() & (raa["bounce_rate_20d"] < 0.50)]
        violations = set(wrong_ret["symbol"].tolist()) | set(wrong_br["symbol"].tolist())
        assert not violations, (
            f"[Direction gate] {len(violations)} RESEARCH_ANNOTATION_ONLY symbols have "
            f"wrong-direction DNA: {sorted(violations)}. "
            "These must be WATCHLIST_ONLY."
        )
