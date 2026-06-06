"""
Stock DNA Event Detection
==========================
Detects support touch, bounce, breakdown, reclaim, and false-break events
per (symbol, line, tolerance).

Event definitions:
  touch       : low came within tolerance of the line, close was above line in prior N bars
  bounce      : after touch, forward return > 0 at 5d / 10d / 20d horizon
  breakdown   : close crossed below the line after being above it
  reclaim     : close crossed back above line after being below within N bars
  false_break : breakdown followed by reclaim within M bars, forward return positive

All events use bar-t line values that are already backward-looking (shift(1) in features.py).
Forward return outcomes use labeled columns (fwd_ret_*) — no additional lookahead introduced here.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.schema import (
    CANDIDATE_LINES,
    TOLERANCE_ATR,
    TOLERANCE_PCT,
    StockPhase,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

PRIOR_ABOVE_BARS: int = 5    # require close was above line in last N bars for support touch
RECLAIM_MAX_BARS: int = 10   # max consecutive bars below line before reclaim counts
FALSE_BREAK_MAX_BARS: int = 10
MIN_VOL_RATIO_BREAKDOWN: float = 1.2   # volume > 1.2x ADV20 to flag "confirmed breakdown"

# Touch tightening: close must not breach the line by more than this many ATR units
TOUCH_CLOSE_BELOW_LINE_MAX_ATR: float = 2.0


# ── Tolerance resolver ────────────────────────────────────────────────────────

def _resolve_tolerance(panel_row_tol: float, atr: float, tol_name: str) -> float:
    """Return absolute tolerance in price terms."""
    if tol_name in TOLERANCE_PCT:
        return float(panel_row_tol)   # already in pct form — caller passes line * pct
    if tol_name in TOLERANCE_ATR:
        return TOLERANCE_ATR[tol_name] * float(atr) if (atr and not np.isnan(atr)) else float(panel_row_tol)
    return float(panel_row_tol)


# ── Touch event detection ─────────────────────────────────────────────────────

def detect_touch_events(
    panel: pd.DataFrame,
    line_name: str,
    tol_name: str,
) -> pd.DataFrame:
    """
    Detect support-touch events for one (line_name, tol_name) combination.

    A touch occurs at bar t when ALL of:
      1. close was above the line for at least 1 of the prior PRIOR_ABOVE_BARS bars
      2. low[t] <= line[t] + tolerance  (low came within reach of the line)
      3. close is near the line (not a crash far below):
           (a) close >= line - tolerance, OR
           (b) low  >= line - 1.5 * tolerance  (intraday wick with recovery)
      4. close did not break below by more than TOUCH_CLOSE_BELOW_LINE_MAX_ATR * ATR14
         (ATR NaN → row excluded, not synthesized)

    Returns DataFrame with columns:
        symbol, date, line_name, tol_name, line_value, close, low,
        stock_phase, breadth_regime, volume_ratio
    """
    if line_name not in panel.columns:
        logger.warning("Line %s not in panel — skipping touch detection", line_name)
        return pd.DataFrame()

    line_val = panel[line_name]

    # Tolerance in price units
    if tol_name in TOLERANCE_PCT:
        tol_pct = TOLERANCE_PCT[tol_name]
        tol_price = line_val * tol_pct
    else:
        atr_mult = TOLERANCE_ATR.get(tol_name, 1.0)
        tol_price = panel["atr14"] * atr_mult   # NaN ATR → NaN tol_price → row excluded

    # Condition 2: low comes within tolerance of line (may touch below)
    touch_cond = panel["low"] <= (line_val + tol_price)

    # Condition 3: close is near the line — not a crash far below
    close_near_line = (
        (panel["close"] >= line_val - tol_price) |
        (panel["low"] >= line_val - 1.5 * tol_price)
    )

    # Condition 4: close did not crash more than ATR threshold below line.
    # NaN ATR propagates to NaN (row excluded) — no synthetic fallback.
    atr14 = panel["atr14"]
    close_not_crashed = (line_val - panel["close"]) <= (TOUCH_CLOSE_BELOW_LINE_MAX_ATR * atr14)

    # Prior-above check: was close above line in any of last PRIOR_ABOVE_BARS bars?
    above_line_series = (panel["close"] > panel[line_name]).astype(float)
    prior_above_cond = above_line_series.groupby(panel["symbol"]).transform(
        lambda s: s.rolling(PRIOR_ABOVE_BARS, min_periods=1).max().shift(1)
    ).fillna(0) >= 1

    # Combined touch event
    is_touch = touch_cond & close_near_line & close_not_crashed & prior_above_cond & line_val.notna()

    touches = panel[is_touch].copy()
    if touches.empty:
        return pd.DataFrame()

    touches["line_name"] = line_name
    touches["tol_name"] = tol_name
    touches["line_value"] = line_val[is_touch].values

    vol_ratio = (panel["value"] / panel["adv20_vnd"].replace(0, np.nan)).fillna(1.0)
    touches["volume_ratio"] = vol_ratio[is_touch].values

    keep_cols = [
        "symbol", "date", "line_name", "tol_name", "line_value",
        "close", "low", "high", "stock_phase", "breadth_regime",
        "volume_ratio", "vin_return_distortion_flag",
    ]
    keep_cols = [c for c in keep_cols if c in touches.columns]
    return touches[keep_cols].reset_index(drop=True)


def attach_bounce_outcomes(
    touch_df: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join forward return labels to touch events.
    Forward returns come from pre-computed columns (fwd_ret_5d, fwd_ret_10d, fwd_ret_20d).
    """
    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d", "mfe_20d", "mae_20d"]
                if c in panel.columns]
    if not fwd_cols:
        logger.warning("No forward return columns found — bounce outcomes unavailable")
        return touch_df

    fwd_df = panel[["symbol", "date"] + fwd_cols].copy()
    merged = touch_df.merge(fwd_df, on=["symbol", "date"], how="left")
    return merged


# ── Breakdown event detection ─────────────────────────────────────────────────

def detect_breakdown_events(
    panel: pd.DataFrame,
    line_name: str,
    require_volume_confirm: bool = False,
) -> pd.DataFrame:
    """
    Detect breakdown events: close crosses below line after being above it.

    A breakdown at t requires:
      - close[t-1] > line[t-1] (was above — using prior bar)
      - close[t]   < line[t]   (now below)
      - Optionally: volume[t] > MIN_VOL_RATIO_BREAKDOWN * adv20

    Note: we use close and line values at bar t, which are already correct since
    line values are shift(1) of the EMA/SMA — they reflect data through t-1.
    For breakdown we want: close[t] crosses below what was the line yesterday.
    """
    if line_name not in panel.columns:
        return pd.DataFrame()

    line_val = panel[line_name]

    # Prev close and prev line (1 more shift)
    prev_close = panel.groupby("symbol")["close"].transform(lambda s: s.shift(1))
    prev_line  = panel.groupby("symbol")[line_name].transform(lambda s: s.shift(1))

    was_above = prev_close > prev_line
    now_below = panel["close"] < line_val

    is_breakdown = was_above & now_below & line_val.notna()

    if require_volume_confirm:
        vol_ratio = panel["value"] / panel["adv20_vnd"].replace(0, np.nan)
        is_breakdown = is_breakdown & (vol_ratio >= MIN_VOL_RATIO_BREAKDOWN)

    breakdowns = panel[is_breakdown].copy()
    if breakdowns.empty:
        return pd.DataFrame()

    breakdowns["line_name"] = line_name
    breakdowns["line_value"] = line_val[is_breakdown].values
    vol_ratio = (panel["value"] / panel["adv20_vnd"].replace(0, np.nan)).fillna(1.0)
    breakdowns["volume_ratio"] = vol_ratio[is_breakdown].values

    # Attach forward returns
    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d", "mfe_20d", "mae_20d"]
                if c in panel.columns]
    keep_cols = [
        "symbol", "date", "line_name", "line_value",
        "close", "stock_phase", "breadth_regime", "volume_ratio",
    ] + fwd_cols
    keep_cols = [c for c in keep_cols if c in breakdowns.columns]
    return breakdowns[keep_cols].reset_index(drop=True)


# ── Reclaim event detection ───────────────────────────────────────────────────

def _consecutive_below(s: pd.Series, line: pd.Series) -> pd.Series:
    """
    Vectorized consecutive-bars-below count using cumsum-reset trick.
    Returns a Series where each value is the count of consecutive bars the close
    has been <= line ending at that bar (0 when above).
    """
    below = (s <= line.loc[s.index]).astype(int)
    # Each run of above-bars starts a new group; cumsum of (below==0) gives a group id
    group_id = (below == 0).cumsum()
    return below.groupby(group_id).cumsum()


def detect_reclaim_events(
    panel: pd.DataFrame,
    line_name: str,
    max_below_bars: int = RECLAIM_MAX_BARS,
) -> pd.DataFrame:
    """
    Detect reclaim events: close crosses back above line after being below for a
    consecutive run of 1 to max_below_bars bars.

    Uses vectorized cumsum-reset to count consecutive bars below (not a rolling
    window sum, which cannot distinguish a long unbroken decline from isolated dips).
    Uses an explicit per-symbol loop to avoid pandas MultiIndex issues from groupby.apply.
    """
    if line_name not in panel.columns:
        return pd.DataFrame()

    line_val = panel[line_name]

    # Build a working frame — avoids MultiIndex surprises from groupby.apply
    work = pd.DataFrame({
        "symbol": panel["symbol"],
        "above":  (panel["close"] > line_val).astype(int),
    }, index=panel.index)
    work["below"] = 1 - work["above"]
    work["consec_cur"] = 0.0

    # Per-symbol consecutive-below count using cumsum-reset trick
    for sym, grp_idx in panel.groupby("symbol", sort=False).groups.items():
        b = work.loc[grp_idx, "below"]
        group_id = (b == 0).cumsum()
        work.loc[grp_idx, "consec_cur"] = b.groupby(group_id).cumsum().values

    # Shift within each symbol to get "consecutive below BEFORE this bar"
    work["consec_prior"] = work.groupby("symbol")["consec_cur"].shift(1).fillna(0)
    work["prev_above"]   = work.groupby("symbol")["above"].shift(1).fillna(0)

    is_reclaim = (
        (work["above"] == 1) &
        (work["prev_above"] == 0) &
        (work["consec_prior"] >= 1) &
        (work["consec_prior"] <= max_below_bars) &
        line_val.notna()
    )

    reclaims = panel[is_reclaim].copy()
    if reclaims.empty:
        return pd.DataFrame()

    reclaims["line_name"] = line_name
    reclaims["line_value"] = line_val.loc[is_reclaim].values
    reclaims["bars_below"] = work.loc[is_reclaim, "consec_prior"].values

    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d"] if c in panel.columns]
    keep_cols = [
        "symbol", "date", "line_name", "line_value", "bars_below",
        "close", "stock_phase", "breadth_regime",
    ] + fwd_cols
    keep_cols = [c for c in keep_cols if c in reclaims.columns]
    return reclaims[keep_cols].reset_index(drop=True)


# ── False break detection ─────────────────────────────────────────────────────

def detect_false_breaks(
    panel: pd.DataFrame,
    line_name: str,
    max_recovery_bars: int = FALSE_BREAK_MAX_BARS,
) -> pd.DataFrame:
    """
    Detect false breaks: breakdown followed by reclaim within max_recovery_bars bars.
    Outcome: forward return after the reclaim.
    """
    breakdowns = detect_breakdown_events(panel, line_name)
    reclaims   = detect_reclaim_events(panel, line_name, max_below_bars=max_recovery_bars)

    if breakdowns.empty or reclaims.empty:
        return pd.DataFrame()

    # For each breakdown, find if there is a reclaim within max_recovery_bars bars for same symbol
    bd = breakdowns[["symbol", "date"]].copy().rename(columns={"date": "breakdown_date"})
    rc = reclaims[["symbol", "date"]].copy().rename(columns={"date": "reclaim_date"})

    merged = bd.merge(rc, on="symbol", how="inner")
    merged["days_gap"] = (merged["reclaim_date"] - merged["breakdown_date"]).dt.days

    false_breaks = merged[
        (merged["days_gap"] > 0) & (merged["days_gap"] <= max_recovery_bars * 2)
    ].copy()

    if false_breaks.empty:
        return pd.DataFrame()

    # Pick earliest reclaim per breakdown
    false_breaks = (
        false_breaks.sort_values("days_gap")
        .groupby(["symbol", "breakdown_date"])
        .first()
        .reset_index()
    )

    # Attach forward returns from the reclaim date
    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d"] if c in panel.columns]
    rc_with_fwd = reclaims[["symbol", "date"] + fwd_cols].rename(columns={"date": "reclaim_date"})
    false_breaks = false_breaks.merge(rc_with_fwd, on=["symbol", "reclaim_date"], how="left")
    false_breaks["line_name"] = line_name
    return false_breaks.reset_index(drop=True)


# ── Aggregate line scores ─────────────────────────────────────────────────────

def aggregate_line_scores(
    touch_df: pd.DataFrame,
    line_name: str,
    tol_name: str,
    phase: Optional[str] = None,
    regime: Optional[str] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Aggregate touch event outcomes into per-(symbol, line, phase, tolerance) statistics.

    Returns DataFrame with one row per symbol (filtered by phase/regime/year if given).
    """
    df = touch_df.copy()
    if df.empty:
        return pd.DataFrame()

    if phase:
        df = df[df["stock_phase"] == phase]
    if regime:
        df = df[df["breadth_regime"] == regime]
    if year is not None:
        df = df[pd.to_datetime(df["date"]).dt.year < year]  # walk-forward: only prior years

    if df.empty:
        return pd.DataFrame()

    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d", "mfe_20d", "mae_20d"]
                if c in df.columns]

    rows = []
    for symbol, grp in df.groupby("symbol"):
        n = len(grp)
        row: dict = {
            "symbol":    symbol,
            "line_name": line_name,
            "tol_name":  tol_name,
            "phase":     phase or "ALL",
            "regime":    regime or "ALL",
            "year_cutoff": year,
            "n_touch":   n,
        }
        for fc in fwd_cols:
            vals = grp[fc].dropna()
            if len(vals) > 0:
                row[f"bounce_rate_{fc}"]    = (vals > 0).mean()
                row[f"median_{fc}"]         = vals.median()
            else:
                row[f"bounce_rate_{fc}"]    = np.nan
                row[f"median_{fc}"]         = np.nan

        if "mfe_20d" in df.columns and "mae_20d" in df.columns:
            mfe = grp["mfe_20d"].dropna()
            mae = grp["mae_20d"].dropna().abs()
            if len(mfe) > 0 and mae.sum() > 0:
                row["mfe_mae_ratio"] = mfe.mean() / mae.mean()
            else:
                row["mfe_mae_ratio"] = np.nan

        rows.append(row)

    return pd.DataFrame(rows)
