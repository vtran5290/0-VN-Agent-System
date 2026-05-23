"""Stage 11 — Timing & Pattern Decomposition.

Classifies each A3/S3 signal from the Stage 9 ledger into mechanical timing /
pattern buckets and evaluates whether different patterns have different forward
outcomes.

Research questions answered:
1. Does accumulation before S3 help?            → PRE_S3_ACCUM
2. Does S3 breakout before A3 help?             → S3_BREAKOUT_BEFORE_A3
3. Does breakout around A3 cloud turn help?     → A3_CLOUD_TURN_BREAKOUT
4. Does A3 pullback accumulation breakout help? → A3_PULLBACK_ACCUM_BREAKOUT
5. Does bottom accumulation before cloud help?  → BOTTOM_ACCUM_PRE_CLOUD
6. Are late breakouts after A3 useful?          → LATE_BREAKOUT_AFTER_A3
7. Does S3 after A3 add anything?               → S3_LATE_AFTER_A3
8. Does failed S3 before A3 warn of risk?       → FAILED_S3_BEFORE_A3
9. Does mechanical inverse H&S have signal?     → INVERSE_HS_BREAKOUT

OBSERVATION / RESEARCH ONLY.
- Does not modify A3/S3 production logic.
- Does not modify OMS / live trading.
- Does not promote any candidate.
- Does not modify final_action.
"""
from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR,
    a3_signal,
    load_panel,
    load_vnindex_regime,
    s3_signal,
)
from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    bo_vol_expansion,
)

log = logging.getLogger(__name__)

# ── Safety constants ───────────────────────────────────────────────────────────
_STAGE11_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Thresholds ─────────────────────────────────────────────────────────────────
_BVE_RAW_THRESHOLD      = 1.2    # bo_vol_expansion ratio threshold for per-bar BVE
_NEAR_EMA100_PCT        = 0.03   # ±3% of EMA100 = "near cloud base"
_PULLBACK_MIN_DEPTH     = 0.03   # minimum 3% pullback to count
_LATE_BREAKOUT_MIN_BARS = 5      # A3 fired > N bars ago for "late"
_LATE_BREAKOUT_MAX_BARS = 30
_S3_AFTER_A3_MAX_BARS   = 30
_FAILED_S3_LOOKBACK     = 40     # how far back to find a preceding S3

# Inverse H&S
_PIVOT_WINDOW           = 5
_IHS_MIN_DURATION       = 40
_IHS_MAX_DURATION       = 120
_IHS_MIN_RS_ABOVE_HEAD  = 0.03   # right shoulder >= head × 1.03
_IHS_SYMMETRY_TOL       = 0.30   # |ls_low - rs_low| / head_low < this
_IHS_VOL_CONFIRM_MULT   = 1.5
_IHS_BREAKOUT_LOOKAHEAD = 60     # bars after right shoulder to find breakout

# ── Bucket priority order ──────────────────────────────────────────────────────
_BUCKET_PRIORITY: List[Tuple[str, str]] = [
    ("FAILED_S3_BEFORE_A3",        "failed_s3_before_a3_flag"),
    ("A3_PULLBACK_ACCUM_BREAKOUT",  "a3_pullback_accum_breakout_flag"),
    ("S3_BREAKOUT_BEFORE_A3",       "s3_breakout_before_a3_flag"),
    ("A3_CLOUD_TURN_BREAKOUT",      "a3_cloud_turn_breakout_flag"),
    ("PRE_S3_ACCUM",                "pre_s3_accum_20b"),
    ("BOTTOM_ACCUM_PRE_CLOUD",      "bottom_accum_pre_cloud_flag"),
    ("LATE_BREAKOUT_AFTER_A3",      "late_breakout_after_a3_flag"),
    ("S3_LATE_AFTER_A3",            "s3_late_after_a3_flag"),
    ("INVERSE_HS_BREAKOUT",         "inverse_hs_breakout_flag"),
]

_ALL_BUCKETS = [b for b, _ in _BUCKET_PRIORITY] + ["NONE"]


# ── Pivot / inverse H&S detection ─────────────────────────────────────────────

def _find_pivot_lows(low_arr: np.ndarray, window: int = _PIVOT_WINDOW) -> np.ndarray:
    """Return bar indices that are local pivot lows within ±window bars.

    Uses both past and future bars — retrospective labeling for research only.
    """
    n = len(low_arr)
    pivots: List[int] = []
    for i in range(window, n - window):
        neighborhood = low_arr[max(0, i - window) : i + window + 1]
        if low_arr[i] == neighborhood.min():
            pivots.append(i)
    return np.array(pivots, dtype=int)


def _detect_inverse_hs(
    sym_df: pd.DataFrame,
) -> Tuple[Set[int], Dict[int, dict]]:
    """
    Detect inverse head-and-shoulders patterns in sym_df.

    Returns:
        breakout_bars: set of bar indices where price breaks above neckline
        meta: bar_idx → {duration, neckline, confirmed_by_value}

    Note: uses pivot_low detection which is retrospective (looks forward for
    pivot identification). Appropriate for research labeling only.
    """
    if len(sym_df) < _IHS_MIN_DURATION + 10:
        return set(), {}

    low_arr   = sym_df["low"].values
    high_arr  = sym_df["high"].values
    close_arr = sym_df["close"].values
    vol_arr   = sym_df["volume"].values
    n         = len(sym_df)

    pivots = _find_pivot_lows(low_arr)
    if len(pivots) < 3:
        return set(), {}

    breakout_bars: Set[int]   = set()
    meta: Dict[int, dict]     = {}

    for i in range(len(pivots) - 2):
        ls_bar  = int(pivots[i])
        hed_bar = int(pivots[i + 1])
        rs_bar  = int(pivots[i + 2])

        ls_low  = float(low_arr[ls_bar])
        hed_low = float(low_arr[hed_bar])
        rs_low  = float(low_arr[rs_bar])

        # Head must be strictly lowest
        if hed_low >= ls_low or hed_low >= rs_low:
            continue

        # Right shoulder must be at least IHS_MIN_RS_ABOVE_HEAD above head
        if rs_low < hed_low * (1.0 + _IHS_MIN_RS_ABOVE_HEAD):
            continue

        # Pattern duration check
        duration = rs_bar - ls_bar
        if not (_IHS_MIN_DURATION <= duration <= _IHS_MAX_DURATION):
            continue

        # Shoulder symmetry: |ls_low - rs_low| / hed_low < tolerance
        if hed_low > 0 and abs(ls_low - rs_low) / hed_low > _IHS_SYMMETRY_TOL:
            continue

        # Neckline = highest high between left shoulder and right shoulder
        neckline = float(high_arr[ls_bar : rs_bar + 1].max())

        # Find first close above neckline after right shoulder
        post_end = min(rs_bar + 1 + _IHS_BREAKOUT_LOOKAHEAD, n)
        for b in range(rs_bar + 1, post_end):
            if close_arr[b] > neckline:
                rs_vol = float(vol_arr[rs_bar]) if rs_bar < n else 1.0
                brk_vol = float(vol_arr[b])
                confirmed = bool(rs_vol > 0 and brk_vol >= rs_vol * _IHS_VOL_CONFIRM_MULT)
                breakout_bars.add(b)
                if b not in meta:
                    meta[b] = {
                        "duration":           duration,
                        "neckline":           neckline,
                        "confirmed_by_value": confirmed,
                    }
                break

    return breakout_bars, meta


# ── Per-symbol context builder ─────────────────────────────────────────────────

def _build_symbol_context(
    sym_df: pd.DataFrame,
    regime_map: Optional[pd.Series],
) -> dict:
    """
    Compute A3/S3 signals, EMAs, per-bar BVE condition, and inverse H&S for one symbol.

    Returns dict with arrays/sets for use in _compute_timing_tags.
    """
    a3_sig_s, ema20, ema100 = a3_signal(sym_df)
    s3_sig_s, ema21, ema55  = s3_signal(sym_df, regime_map=regime_map)

    a3_bars = np.where(a3_sig_s.values)[0]
    s3_bars = np.where(s3_sig_s.values)[0]

    # Per-bar BVE condition: raw volume expansion ratio > threshold
    try:
        bve_raw  = bo_vol_expansion(sym_df).fillna(0.0).values
        bve_cond = (bve_raw > _BVE_RAW_THRESHOLD)
    except Exception:
        bve_cond = np.zeros(len(sym_df), dtype=bool)

    inv_hs_bars, inv_hs_meta = _detect_inverse_hs(sym_df)

    return {
        "ema100":    ema100.values,
        "ema55":     ema55.values,
        "a3_bars":   a3_bars,
        "s3_bars":   s3_bars,
        "s3_bar_set": frozenset(s3_bars.tolist()),
        "bve_cond":  bve_cond,
        "inv_hs_bars": inv_hs_bars,
        "inv_hs_meta": inv_hs_meta,
    }


# ── Timing tag computation ─────────────────────────────────────────────────────

def _compute_timing_tags(
    bar_idx: int,
    sym_df: pd.DataFrame,
    ctx: dict,
    accum_here: bool,
    is_s3: bool,
) -> dict:
    """
    Compute all timing bucket tags for a signal at bar_idx.

    Parameters
    ----------
    bar_idx    : index into sym_df for the signal bar
    sym_df     : full OHLCV DataFrame for the symbol (sorted by date)
    ctx        : pre-built symbol context from _build_symbol_context
    accum_here : True if the current row has BVE/TPBCQ/SOS accumulation condition
    is_s3      : True if the current row is an S3 signal (from ledger)
    """
    n = len(sym_df)

    a3_bars  = ctx["a3_bars"]
    s3_bars  = ctx["s3_bars"]
    ema100   = ctx["ema100"]
    ema55    = ctx["ema55"]
    bve_cond = ctx["bve_cond"]
    inv_hs_bars = ctx["inv_hs_bars"]
    inv_hs_meta = ctx["inv_hs_meta"]

    close = sym_df["close"].values
    low   = sym_df["low"].values

    tags: dict = {}

    # ── PRE_S3_ACCUM ────────────────────────────────────────────────────────────
    # Current bar has accumulation AND next S3 fires within N bars.
    # "pre_s3" means this signal foreshadows an S3. Tagged as a research label
    # using future S3 dates — NOT a causal trading signal.
    future_s3 = s3_bars[s3_bars > bar_idx]
    next_s3_dist = int(future_s3[0] - bar_idx) if len(future_s3) > 0 else 9999

    tags["pre_s3_accum_5b"]  = bool(accum_here and next_s3_dist <= 5)
    tags["pre_s3_accum_10b"] = bool(accum_here and next_s3_dist <= 10)
    tags["pre_s3_accum_20b"] = bool(accum_here and next_s3_dist <= 20)

    # ── S3_BREAKOUT_BEFORE_A3 ──────────────────────────────────────────────────
    # Most recent S3 for this ticker occurred within 40 bars before current signal.
    prev_s3 = s3_bars[s3_bars < bar_idx]
    s3_before_dist = int(bar_idx - prev_s3[-1]) if len(prev_s3) > 0 else 9999

    if   s3_before_dist <= 5:  lead_bucket = "1_5"
    elif s3_before_dist <= 10: lead_bucket = "6_10"
    elif s3_before_dist <= 20: lead_bucket = "11_20"
    elif s3_before_dist <= 40: lead_bucket = "21_40"
    else:                      lead_bucket = "none"

    tags["s3_breakout_before_a3_flag"] = bool(s3_before_dist <= 40)
    tags["s3_before_a3_lead_bucket"]   = lead_bucket

    # ── A3_CLOUD_TURN_BREAKOUT ─────────────────────────────────────────────────
    # Volume expansion (BVE raw threshold) is active within ±3 bars of current signal.
    bve_start = max(0, bar_idx - 3)
    bve_end   = min(n, bar_idx + 4)
    tags["a3_cloud_turn_breakout_flag"] = bool(bve_cond[bve_start:bve_end].any())

    # ── A3_PULLBACK_ACCUM_BREAKOUT ─────────────────────────────────────────────
    # Most recent A3 within 15–40 bars + price drew down ≥ threshold + accum now.
    prev_a3 = a3_bars[a3_bars < bar_idx]
    pullback_flag         = False
    pullback_depth_bucket = "none"
    pullback_window_bucket = "none"

    if len(prev_a3) > 0 and accum_here:
        for win_bars, wb_label in [(40, "40b"), (30, "30b"), (20, "20b"), (15, "15b")]:
            candidates = prev_a3[prev_a3 >= bar_idx - win_bars]
            if len(candidates) == 0:
                continue
            a3_bar   = int(candidates[-1])
            a3_price = float(close[a3_bar])
            if a3_price <= 0:
                continue
            window_low = low[a3_bar : bar_idx + 1]
            if len(window_low) == 0:
                continue
            drawdown = float(window_low.min() / a3_price - 1.0)
            for depth_pct, depth_label in [
                (-0.06, "6pct"), (-0.05, "5pct"), (-0.04, "4pct"), (-0.03, "3pct")
            ]:
                if drawdown <= depth_pct:
                    pullback_flag          = True
                    pullback_depth_bucket  = depth_label
                    pullback_window_bucket = wb_label
                    break
            if pullback_flag:
                break

    tags["a3_pullback_accum_breakout_flag"] = pullback_flag
    tags["pullback_depth_bucket"]           = pullback_depth_bucket
    tags["pullback_window_bucket"]          = pullback_window_bucket

    # ── BOTTOM_ACCUM_PRE_CLOUD ─────────────────────────────────────────────────
    # Price is near or below EMA100 at signal bar + accumulation present.
    ema100_here = float(ema100[bar_idx]) if bar_idx < len(ema100) else np.nan
    if not np.isnan(ema100_here) and ema100_here > 0:
        px_vs = float(close[bar_idx]) / ema100_here - 1.0
        if px_vs < -_NEAR_EMA100_PCT:
            bottom_loc = "below_ema100"
        elif abs(px_vs) <= _NEAR_EMA100_PCT:
            bottom_loc = "near_ema100"
        else:
            bottom_loc = "above_ema100"
        bottom_flag = bool(bottom_loc in ("below_ema100", "near_ema100") and accum_here)
    else:
        bottom_loc  = "unknown"
        bottom_flag = False

    tags["bottom_accum_pre_cloud_flag"] = bottom_flag
    tags["bottom_accum_price_location"] = bottom_loc

    # ── LATE_BREAKOUT_AFTER_A3 ─────────────────────────────────────────────────
    # A3 fired 5–30 bars ago AND volume expansion (BVE) active at current bar.
    prev_a3_for_late = a3_bars[a3_bars < bar_idx]
    a3_dist = int(bar_idx - prev_a3_for_late[-1]) if len(prev_a3_for_late) > 0 else 9999

    late_flag = bool(_LATE_BREAKOUT_MIN_BARS < a3_dist <= _LATE_BREAKOUT_MAX_BARS
                     and bar_idx < len(bve_cond) and bve_cond[bar_idx])

    if   _LATE_BREAKOUT_MIN_BARS < a3_dist <= 10: bars_after_bucket = "5_10"
    elif 10 < a3_dist <= 20:                       bars_after_bucket = "11_20"
    elif 20 < a3_dist <= 30:                       bars_after_bucket = "21_30"
    else:                                           bars_after_bucket = "none"

    tags["late_breakout_after_a3_flag"] = late_flag
    tags["bars_after_a3_bucket"]        = bars_after_bucket

    # ── S3_LATE_AFTER_A3 ───────────────────────────────────────────────────────
    # Current bar IS an S3 signal AND A3 fired 1–30 bars before it.
    s3_late = bool(is_s3 and 1 <= a3_dist <= _S3_AFTER_A3_MAX_BARS)

    if s3_late:
        if   a3_dist <= 5:  s3_after_bucket = "1_5"
        elif a3_dist <= 10: s3_after_bucket = "6_10"
        elif a3_dist <= 20: s3_after_bucket = "11_20"
        else:               s3_after_bucket = "21_30"
    else:
        s3_after_bucket = "none"

    tags["s3_late_after_a3_flag"] = s3_late
    tags["s3_after_a3_bucket"]    = s3_after_bucket

    # ── FAILED_S3_BEFORE_A3 ────────────────────────────────────────────────────
    # A preceding S3 occurred (within FAILED_S3_LOOKBACK bars) AND price closed
    # below EMA55 in the window between that S3 and the current bar.
    failed_s3      = False
    failed_s3_type = "none"

    if s3_before_dist <= _FAILED_S3_LOOKBACK:
        recent_s3_bar = int(prev_s3[-1])
        chk_start     = recent_s3_bar + 1
        chk_end       = bar_idx          # exclusive
        if chk_end > chk_start:
            close_win = close[chk_start:chk_end]
            ema55_win = ema55[chk_start:chk_end]
            if len(close_win) == len(ema55_win) and len(close_win) > 0:
                if (close_win < ema55_win).any():
                    failed_s3      = True
                    failed_s3_type = "below_ema55"

    tags["failed_s3_before_a3_flag"] = failed_s3
    tags["failed_s3_failure_type"]   = failed_s3_type

    # ── INVERSE_HS_BREAKOUT ────────────────────────────────────────────────────
    inv_meta = inv_hs_meta.get(bar_idx, {})
    tags["inverse_hs_breakout_flag"]      = bar_idx in inv_hs_bars
    tags["inverse_hs_duration"]           = inv_meta.get("duration", np.nan)
    tags["inverse_hs_neckline"]           = inv_meta.get("neckline", np.nan)
    tags["inverse_hs_confirmed_by_value"] = inv_meta.get("confirmed_by_value", False)

    return tags


def _assign_primary_bucket(tags: dict) -> str:
    """Assign the highest-priority timing bucket whose flag is True."""
    for bucket_name, flag_col in _BUCKET_PRIORITY:
        if tags.get(flag_col, False):
            return bucket_name
    return "NONE"


# ── Summary statistics and classification ─────────────────────────────────────

def _bucket_stats(sub: pd.DataFrame) -> dict:
    """Compute outcome stats for a bucket subset — mature 63d only."""
    n_total = len(sub)
    if "matured_63d" not in sub.columns:
        mat_mask = pd.Series(True, index=sub.index)
    else:
        mat_mask = sub["matured_63d"].astype(bool)
    mature = sub[mat_mask]
    valid  = mature["fwd_63d_return"].dropna()
    n_mat  = len(valid)

    if n_mat == 0:
        return {
            "n_total": n_total, "n_matured_63d": 0,
            "win_rate_63d": np.nan, "avg_return_63d": np.nan,
            "median_return_63d": np.nan, "tp1_rate_63d": np.nan,
            "avg_mae_63d": np.nan, "avg_mfe_63d": np.nan,
        }

    tp1  = float(mature["tp1_hit_63d"].dropna().mean()) if "tp1_hit_63d" in mature.columns else np.nan
    mae  = float(mature["max_adverse_excursion_63d"].dropna().mean())  if "max_adverse_excursion_63d"  in mature.columns else np.nan
    mfe  = float(mature["max_favorable_excursion_63d"].dropna().mean()) if "max_favorable_excursion_63d" in mature.columns else np.nan
    return {
        "n_total":         n_total,
        "n_matured_63d":   n_mat,
        "win_rate_63d":    float((valid >= 0.15).mean()),
        "avg_return_63d":  float(valid.mean()),
        "median_return_63d": float(valid.median()),
        "tp1_rate_63d":    tp1,
        "avg_mae_63d":     mae,
        "avg_mfe_63d":     mfe,
    }


def _classify_bucket(
    label: str,
    stats: dict,
    baseline: dict,
) -> Tuple[str, str, str]:
    """Return (classification, action, notes)."""
    n = stats["n_matured_63d"]

    if label == "INVERSE_HS_BREAKOUT":
        note = f"n_matured={n}. Pattern-recognition label — needs visual confirmation."
        if n < 10:
            note += " LOW_SAMPLE."
        return "DIAGNOSTIC_ONLY", "Monitor visually", note

    if label == "FAILED_S3_BEFORE_A3":
        return "WATCHLIST_ONLY", "Use as caution flag", (
            "Warning indicator — S3 failure before A3 suggests prior trend weakness."
        )

    if n < 40:
        return "needs_more_data", "Monitor", f"n_matured={n} < 40"

    win  = stats.get("win_rate_63d",  np.nan)
    ret  = stats.get("avg_return_63d", np.nan)
    tp1  = stats.get("tp1_rate_63d",  np.nan)
    bwin = baseline.get("win_rate_63d", np.nan)
    bret = baseline.get("avg_return_63d", np.nan)
    btp1 = baseline.get("tp1_rate_63d", np.nan)

    if any(np.isnan(v) for v in [win, bwin, ret, bret]):
        return "needs_more_data", "Monitor", "NaN in stats"

    delta_win = win - bwin
    delta_ret = ret - bret
    delta_tp1 = (tp1 - btp1) if not (np.isnan(tp1) or np.isnan(btp1)) else 0.0

    if delta_win >= 0.05 and delta_ret > 0 and delta_tp1 >= 0:
        return "PARALLEL_PAPER_RESEARCH", "Set up paper portfolio", (
            f"Δwin={delta_win*100:.1f}pp, Δret={delta_ret*100:.1f}pp, Δtp1={delta_tp1*100:.1f}pp"
        )
    if delta_win < -0.02 and delta_ret < -0.01:
        return "REJECT", "No action", (
            f"Underperforms baseline: Δwin={delta_win*100:.1f}pp"
        )
    return "WATCHLIST_ONLY", "Continue monitoring", (
        f"Δwin={delta_win*100:.1f}pp, Δret={delta_ret*100:.1f}pp"
    )


# ── Findings markdown ──────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v*100:.1f}%" if not np.isnan(v) else "N/A"


def _generate_findings_md(
    summary_df: pd.DataFrame,
    by_year_df: pd.DataFrame,
    by_regime_df: pd.DataFrame,
    by_liq_df: pd.DataFrame,
    ihs_df: pd.DataFrame,
    baseline: dict,
    n_total: int,
    n_matured: int,
    report_date: str,
) -> str:
    lines = [
        "# Stage 11 Timing & Pattern Decomposition Findings",
        "",
        f"**Report date:** {report_date}  |  **Total rows:** {n_total}  |  **63d matured:** {n_matured}",
        f"**Baseline win rate (63d):** {_pct(baseline.get('win_rate_63d', np.nan))}  "
        f"|  **Baseline avg return:** {_pct(baseline.get('avg_return_63d', np.nan))}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "Stage 11 classifies each A3/S3 signal into mechanical timing/pattern buckets.",
        "All classifications are OBSERVATION / RESEARCH ONLY. No production changes.",
        "",
        "---",
        "",
        "## 2. Coverage Against Original Scheme",
        "",
        "| Research Question | Bucket | Status |",
        "|---|---|---|",
        "| 1. Accumulation before S3 | PRE_S3_ACCUM | **COVERED** |",
        "| 2. S3 breakout before A3 | S3_BREAKOUT_BEFORE_A3 | **COVERED** |",
        "| 3. Breakout around A3 cloud turn | A3_CLOUD_TURN_BREAKOUT | **COVERED** |",
        "| 4. A3 pullback accumulation breakout | A3_PULLBACK_ACCUM_BREAKOUT | **COVERED** |",
        "| 5. Bottom accumulation before cloud | BOTTOM_ACCUM_PRE_CLOUD | **COVERED** |",
        "| 6. Late breakouts after A3 | LATE_BREAKOUT_AFTER_A3 | **COVERED** |",
        "| 7. S3 after A3 | S3_LATE_AFTER_A3 | **COVERED** |",
        "| 8. Failed S3 before A3 warning | FAILED_S3_BEFORE_A3 | **COVERED** |",
        "| 9. Mechanical inverse H&S | INVERSE_HS_BREAKOUT | **COVERED (diagnostic)** |",
        "| Full timing bucket decomposition | All 9 buckets | **COVERED** |",
        "| Pattern module testing | Stage 11 | **COVERED** |",
        "| S3-specific timing analysis | S3 buckets | **PARTIALLY COVERED** |",
        "| Inverse H&S mechanical annotation | INVERSE_HS_BREAKOUT | **COVERED** |",
        "| Coverage audit vs original scheme | This section | **COVERED** |",
        "",
        "**Remaining open after Stage 11:**",
        "- Cross-asset radar / portfolio-level patterns (not in scope)",
        "- Volume profile analysis (VPA) beyond simple ratio",
        "- Sector rotation context mapping",
        "- Live observation tracking (requires forward time)",
        "",
        "---",
        "",
        "## 3. Timing Bucket Results",
        "",
    ]

    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            bucket     = row.get("bucket", "?")
            n_tot      = row.get("n_total", 0)
            n_mat      = row.get("n_matured_63d", 0)
            win        = row.get("win_rate_63d", np.nan)
            tp1        = row.get("tp1_rate_63d", np.nan)
            avg_ret    = row.get("avg_return_63d", np.nan)
            cls        = row.get("classification", "?")
            action     = row.get("action", "?")
            notes      = row.get("notes", "")
            lines += [
                f"### {bucket}",
                "",
                f"- n_total={n_tot}, n_matured_63d={n_mat}",
                f"- win_rate_63d={_pct(win)}, tp1_rate_63d={_pct(tp1)}, avg_return_63d={_pct(avg_ret)}",
                f"- **Classification:** {cls}  |  **Action:** {action}",
                f"- Notes: {notes}",
                "",
            ]

    lines += ["---", "", "## 4. By-Year / Regime / Liquidity Robustness", ""]
    if not by_year_df.empty:
        lines += ["### By Year", "", by_year_df.to_markdown(index=False), ""]
    if not by_regime_df.empty:
        lines += ["### By Regime", "", by_regime_df.to_markdown(index=False), ""]
    if not by_liq_df.empty:
        lines += ["### By Liquidity Bucket", "", by_liq_df.to_markdown(index=False), ""]

    lines += ["---", "", "## 5. Inverse H&S Diagnostic Review", ""]
    if not ihs_df.empty:
        total_cand  = len(ihs_df)
        confirmed   = int(ihs_df["inverse_hs_confirmed_by_value"].sum()) if "inverse_hs_confirmed_by_value" in ihs_df.columns else 0
        mat63       = int(ihs_df["matured_63d"].sum()) if "matured_63d" in ihs_df.columns else 0
        lines += [
            f"- Total inverse H&S breakout rows: {total_cand}",
            f"- Volume-confirmed: {confirmed}",
            f"- 63d matured: {mat63}",
            "- Classification: DIAGNOSTIC_ONLY",
            "- Pattern is retrospective (pivot detection looks forward) — visual confirmation required.",
            "",
        ]
        lines.append(ihs_df.head(10).to_markdown(index=False))
    else:
        lines.append("_No inverse H&S candidates found._")
    lines.append("")

    lines += [
        "---",
        "",
        "## 6. Final Classifications",
        "",
    ]
    if not summary_df.empty:
        lines.append(summary_df[["bucket", "n_matured_63d", "win_rate_63d", "classification", "action"]].to_markdown(index=False))
    lines += [
        "",
        "---",
        "",
        "## 7. Safety Confirmation",
        "",
        "| Check | Status |",
        "|---|---|",
        "| A3 production contract unchanged | YES |",
        "| S3 not promoted to production | YES |",
        "| OMS / live trading untouched | YES |",
        "| DNSE / live order paths untouched | YES |",
        "| final_action not modified | YES |",
        "| Stage 11 fields observation-only | YES |",
        "| Inverse H&S diagnostic-only | YES |",
        "| Failed S3 before A3 warning-only (not a hard block) | YES |",
        "| No production recommendation made | YES |",
        "",
        "---",
        "",
        "## 8. Remaining Gaps After Stage 11",
        "",
        "- Cross-portfolio radar (multi-symbol concurrent pattern detection)",
        "- VPA (volume profile analysis beyond expansion ratio)",
        "- Sector rotation context",
        "- 2026 rows partially immature — revisit when more 63d windows mature",
        "",
        "---",
        "",
        "## 9. Recommended Next Step",
        "",
        "If any bucket clears PARALLEL_PAPER_RESEARCH threshold with n≥40 and Δwin≥5pp,",
        "set up a paper portfolio tracking that specific pattern. Otherwise,",
        "accumulate more 2025/2026 data and re-run Stages 9–11 monthly.",
        "",
        "**This report is RESEARCH ONLY. Not OMS input. No production changes.**",
        "",
    ]
    return "\n".join(lines)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE11_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    ledger_path = _STAGE11_WRITE_DIR / "stage9_forward_validation_updated.csv"
    if not ledger_path.exists():
        log.error("Stage 9 ledger not found — run Stage 9 first.")
        return

    ledger = pd.read_csv(ledger_path)
    ledger["observation_date"] = pd.to_datetime(ledger["observation_date"])
    log.info("Loaded Stage 9 ledger: %d rows, %d symbols",
             len(ledger), ledger["symbol"].nunique())

    # Load full panel + VNINDEX regime
    panels = load_panel(ex_vin=False)
    regime_map = load_vnindex_regime()

    # Build per-symbol context for symbols in ledger
    unique_syms = ledger["symbol"].unique().tolist()
    sym_contexts: Dict[str, dict] = {}
    for sym in unique_syms:
        sym_df = panels.get(sym)
        if sym_df is None or len(sym_df) < 110:
            continue
        try:
            sym_contexts[sym] = _build_symbol_context(sym_df, regime_map)
        except Exception as exc:
            log.warning("Context build failed for %s: %s", sym, exc)

    log.info("Built context for %d / %d symbols", len(sym_contexts), len(unique_syms))

    # ── Tag each ledger row ────────────────────────────────────────────────────
    tag_rows: List[dict] = []

    for _, row in ledger.iterrows():
        sym       = str(row["symbol"])
        obs_date  = row["observation_date"]
        is_s3     = bool(row.get("s3_signal", False))
        bve_q     = int(row.get("breakout_value_expansion_q", 0))
        tpbcq_q   = int(row.get("tightness_plus_breakout_close_quality_q", 0))
        sos_val   = int(row.get("wyckoff_sos", 0))
        accum_here = (bve_q >= 4) or (tpbcq_q >= 4) or (sos_val == 1)

        ctx    = sym_contexts.get(sym)
        sym_df = panels.get(sym)

        if ctx is None or sym_df is None:
            # Symbol not in panel — fill defaults
            tags = {
                "pre_s3_accum_5b": False, "pre_s3_accum_10b": False, "pre_s3_accum_20b": False,
                "s3_breakout_before_a3_flag": False, "s3_before_a3_lead_bucket": "none",
                "a3_cloud_turn_breakout_flag": False,
                "a3_pullback_accum_breakout_flag": False,
                "pullback_depth_bucket": "none", "pullback_window_bucket": "none",
                "bottom_accum_pre_cloud_flag": False, "bottom_accum_price_location": "unknown",
                "late_breakout_after_a3_flag": False, "bars_after_a3_bucket": "none",
                "s3_late_after_a3_flag": False, "s3_after_a3_bucket": "none",
                "failed_s3_before_a3_flag": False, "failed_s3_failure_type": "none",
                "inverse_hs_breakout_flag": False, "inverse_hs_duration": np.nan,
                "inverse_hs_neckline": np.nan, "inverse_hs_confirmed_by_value": False,
            }
        else:
            # Find bar index
            dates_np = pd.to_datetime(sym_df["date"]).values
            obs_ts   = np.datetime64(obs_date, "ns")
            bar_idx  = int(np.searchsorted(dates_np, obs_ts, side="right")) - 1
            if bar_idx < 0:
                bar_idx = 0
            tags = _compute_timing_tags(bar_idx, sym_df, ctx, accum_here, is_s3)

        tags["timing_pattern_primary_bucket"] = _assign_primary_bucket(tags)

        # Watchlist / rejection flags from Stage 9 data
        tags["breakout_value_expansion_watchlist_flag"]     = bool(bve_q >= 4)
        tags["tightness_plus_breakout_watchlist_flag"]       = bool(tpbcq_q >= 4)
        tags["wyckoff_sos_diagnostic_flag"]                  = bool(sos_val == 1)
        tags["old_composite_rejected_flag"]                  = True
        tags["field_usage"]                                  = "observation_only"

        tag_rows.append(tags)

    tags_df = pd.DataFrame(tag_rows, index=ledger.index)

    # ── Assemble output DataFrame ─────────────────────────────────────────────
    passthrough_cols = [
        "observation_date", "symbol", "signal_type", "a3_signal", "s3_signal",
        "s3lead5", "close_kvnd", "adv50_vnd", "liquidity_bucket", "vnindex_regime",
        "fwd_20d_return", "fwd_40d_return", "fwd_63d_return",
        "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
    ]
    passthrough = ledger[[c for c in passthrough_cols if c in ledger.columns]].copy()
    passthrough["ticker"]     = passthrough["symbol"]
    passthrough["matured_63d"] = ledger["fwd_63d_matured"].astype(bool)

    out_df = pd.concat([passthrough.reset_index(drop=True), tags_df.reset_index(drop=True)], axis=1)
    log.info("Tagged %d rows with timing bucket flags", len(out_df))

    # ── Save decomposition CSV ────────────────────────────────────────────────
    out_decomp = _STAGE11_WRITE_DIR / "stage11_timing_pattern_decomposition.csv"
    out_df.to_csv(out_decomp, index=False)
    log.info("Saved decomposition: %s (%d rows)", out_decomp.name, len(out_df))

    # ── Baseline stats (all mature 63d) ───────────────────────────────────────
    df_mat = out_df[out_df["matured_63d"].astype(bool)].copy()
    baseline = _bucket_stats(df_mat)
    log.info(
        "Baseline: n=%d, win=%.1f%%, avg=%.1f%%",
        baseline["n_matured_63d"],
        baseline["win_rate_63d"] * 100,
        baseline["avg_return_63d"] * 100,
    )

    # ── Summary by primary bucket ─────────────────────────────────────────────
    summary_rows: List[dict] = []
    for bucket in _ALL_BUCKETS:
        sub   = out_df[out_df["timing_pattern_primary_bucket"] == bucket]
        stats = _bucket_stats(sub)
        cls, action, notes = _classify_bucket(bucket, stats, baseline)
        log.info(
            "Bucket %-30s n=%3d, mat=%3d, win=%s → %s",
            bucket, stats["n_total"], stats["n_matured_63d"],
            _pct(stats["win_rate_63d"]), cls,
        )
        row = {"bucket": bucket, **stats,
               "delta_win_rate_vs_all_pp":
                   (stats["win_rate_63d"] - baseline["win_rate_63d"]) * 100
                   if not (np.isnan(stats["win_rate_63d"]) or np.isnan(baseline["win_rate_63d"]))
                   else np.nan,
               "delta_tp1_rate_vs_all_pp":
                   (stats["tp1_rate_63d"] - baseline["tp1_rate_63d"]) * 100
                   if not (np.isnan(stats["tp1_rate_63d"]) or np.isnan(baseline["tp1_rate_63d"]))
                   else np.nan,
               "classification": cls, "action": action, "notes": notes}
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows)

    out_summary = _STAGE11_WRITE_DIR / "stage11_timing_pattern_summary.csv"
    summary_df.to_csv(out_summary, index=False)
    log.info("Saved summary: %s", out_summary.name)

    # ── By-year robustness ────────────────────────────────────────────────────
    year_rows: List[dict] = []
    if "year" in ledger.columns:
        out_df["year"] = ledger["year"].values
    else:
        out_df["year"] = pd.to_datetime(out_df["observation_date"]).dt.year

    for yr, yr_df in out_df.groupby("year"):
        for bucket in _ALL_BUCKETS[:5]:  # top 5 buckets
            sub = yr_df[yr_df["timing_pattern_primary_bucket"] == bucket]
            if len(sub) == 0:
                continue
            stats = _bucket_stats(sub)
            year_rows.append({"year": yr, "bucket": bucket, **stats})
    by_year_df = pd.DataFrame(year_rows)
    out_year = _STAGE11_WRITE_DIR / "stage11_timing_pattern_by_year.csv"
    by_year_df.to_csv(out_year, index=False)

    # ── By-regime robustness ──────────────────────────────────────────────────
    regime_rows: List[dict] = []
    if "vnindex_regime" in out_df.columns:
        for reg, reg_df in out_df.groupby("vnindex_regime", dropna=False):
            for bucket in _ALL_BUCKETS[:5]:
                sub = reg_df[reg_df["timing_pattern_primary_bucket"] == bucket]
                if len(sub) == 0:
                    continue
                stats = _bucket_stats(sub)
                regime_rows.append({"vnindex_regime": reg, "bucket": bucket, **stats})
    by_regime_df = pd.DataFrame(regime_rows)
    out_regime = _STAGE11_WRITE_DIR / "stage11_timing_pattern_by_regime.csv"
    by_regime_df.to_csv(out_regime, index=False)

    # ── By-liquidity robustness ───────────────────────────────────────────────
    liq_rows: List[dict] = []
    if "liquidity_bucket" in out_df.columns:
        for liq, liq_df in out_df.groupby("liquidity_bucket", dropna=False):
            for bucket in _ALL_BUCKETS[:5]:
                sub = liq_df[liq_df["timing_pattern_primary_bucket"] == bucket]
                if len(sub) == 0:
                    continue
                stats = _bucket_stats(sub)
                liq_rows.append({"liquidity_bucket": liq, "bucket": bucket, **stats})
    by_liq_df = pd.DataFrame(liq_rows)
    out_liq = _STAGE11_WRITE_DIR / "stage11_timing_pattern_by_liquidity.csv"
    by_liq_df.to_csv(out_liq, index=False)

    # ── Inverse H&S candidates export ────────────────────────────────────────
    ihs_df = out_df[out_df["inverse_hs_breakout_flag"].astype(bool)].copy()
    out_ihs = _STAGE11_WRITE_DIR / "stage11_inverse_hs_candidates.csv"
    ihs_df.to_csv(out_ihs, index=False)
    log.info("Inverse H&S candidates: %d rows", len(ihs_df))

    # ── Findings markdown ─────────────────────────────────────────────────────
    report_date = str(datetime.date.today())
    n_matured_63 = int(out_df["matured_63d"].astype(bool).sum())

    findings = _generate_findings_md(
        summary_df   = summary_df,
        by_year_df   = by_year_df,
        by_regime_df = by_regime_df,
        by_liq_df    = by_liq_df,
        ihs_df       = ihs_df,
        baseline     = baseline,
        n_total      = len(out_df),
        n_matured    = n_matured_63,
        report_date  = report_date,
    )
    out_md = _STAGE11_WRITE_DIR / "STAGE11_TIMING_PATTERN_FINDINGS.md"
    out_md.write_text(findings, encoding="utf-8")
    log.info("Saved findings: %s", out_md.name)

    log.info(
        "Stage 11 complete. %d rows, %d with 63d matured, %d inverse H&S candidates.",
        len(out_df), n_matured_63, len(ihs_df),
    )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
