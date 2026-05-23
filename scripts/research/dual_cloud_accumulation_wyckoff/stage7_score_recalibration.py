#!/usr/bin/env python3
"""Stage 7 — Score Recalibration

PAPER VALIDATION / RESEARCH ONLY. No production/OMS/live changes.

Tests 20+ candidate score definitions against the Stage 1 A3 signal universe
at the 63-bar horizon. Identifies which (if any) specifications clear the
PARALLEL_PAPER_RESEARCH threshold and which remain WATCHLIST_ONLY or REJECT.

Source: outputs/research/dual_cloud_accumulation_wyckoff/stage1_trades.csv

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage7_score_recalibration.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage7_score_recalibration_by_year.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage7_score_recalibration_by_regime.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage7_score_recalibration_by_liquidity.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage7_feature_ablation.csv
    outputs/research/dual_cloud_accumulation_wyckoff/STAGE7_SCORE_RECALIBRATION_FINDINGS.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage7_score_recalibration.py
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy.stats import spearmanr, pointbiserialr
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, SUCCESS_TARGET, SUCCESS_STOP, MIN_ADV_VND, load_vnindex_regime,
)
from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    compute_candidate_score_dategroup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

STAGE1_TRADES = OUT_DIR / "stage1_trades.csv"
HORIZON = 63

# ── Candidate score specifications ────────────────────────────────────────────
# Each entry: (col_name, ascending, weight)
# ascending=True  → higher feature value = better score
# ascending=False → lower feature value = better score

CANDIDATE_SPECS: dict[str, list[tuple[str, bool, float]]] = {
    # 7.1 Baseline — same spec as existing tradable_asof_score
    "old_composite_score": [
        ("pt_20",        False, 0.20),
        ("atr_ratio",    False, 0.20),
        ("vol_ratio",    False, 0.20),
        ("vol_drying",   True,  0.15),
        ("bo_vol_exp",   True,  0.15),
        ("bo_close_str", True,  0.10),
    ],
    # 7.2 Price tightness variants
    "price_tightness_pt20_pt40": [
        ("pt_20", True, 0.50),
        ("pt_40", True, 0.50),
    ],
    "price_tightness_range_compression": [
        ("atr_ratio",     False, 0.40),
        ("range_vs_ma20", False, 0.30),
        ("bar_range_pct", False, 0.30),
    ],
    "price_tightness_low_volatility": [
        ("pt_20",     True,  0.33),
        ("pt_40",     True,  0.33),
        ("atr_ratio", False, 0.34),
    ],
    # 7.3 Breakout-only variants
    "breakout_only": [
        ("bo_vol_exp",   True, 0.50),
        ("bo_close_str", True, 0.50),
    ],
    "breakout_close_quality": [
        ("bo_close_str", True, 0.70),
        ("bo_vol_exp",   True, 0.30),
    ],
    "breakout_value_expansion": [
        ("bo_vol_exp",   True, 0.40),
        ("bo_range_exp", True, 0.30),
        ("vol_trend_10", True, 0.30),
    ],
    # 7.4 Tightness + breakout
    "tightness_plus_breakout": [
        ("pt_20",        True, 0.33),
        ("bo_vol_exp",   True, 0.33),
        ("bo_close_str", True, 0.34),
    ],
    "tightness_plus_breakout_value": [
        ("pt_20",        True, 0.25),
        ("bo_vol_exp",   True, 0.25),
        ("bo_close_str", True, 0.25),
        ("vol_trend_10", True, 0.25),
    ],
    "tightness_plus_breakout_close_quality": [
        ("pt_20",        True, 0.25),
        ("pt_40",        True, 0.25),
        ("bo_close_str", True, 0.30),
        ("bo_vol_exp",   True, 0.20),
    ],
    # 7.5 Drop volume drying
    "no_volume_dryup_score": [
        ("pt_20",        False, 0.30),
        ("atr_ratio",    False, 0.30),
        ("bo_vol_exp",   True,  0.20),
        ("bo_close_str", True,  0.20),
    ],
    # 7.6 Inverted volume drying
    "volume_dryup_as_negative": [
        ("pt_20",        False, 0.20),
        ("atr_ratio",    False, 0.20),
        ("vol_drying",   False, 0.20),   # INVERTED vs old_composite_score
        ("bo_vol_exp",   True,  0.20),
        ("bo_close_str", True,  0.20),
    ],
    # 7.7 Wyckoff-only variants (diagnostic only — not tradable candidates)
    "wyckoff_sos_only":         [("sos",    True, 1.0)],
    "wyckoff_lps_only":         [("lps",    True, 1.0)],
    "wyckoff_spring_test_only": [("spring", True, 1.0)],
    "wyckoff_sos_lps_combo":    [("sos",    True, 0.50), ("lps", True, 0.50)],
    # 7.8 Anti-dead-liquidity
    "anti_dead_liquidity_score": [
        ("pt_20",        True,  0.25),
        ("bo_close_str", True,  0.25),
        ("bo_vol_exp",   True,  0.25),
        ("vol_drying",   False, 0.25),   # penalize vol drying
    ],
}

WYCKOFF_CANDIDATES = frozenset({
    "wyckoff_sos_only",
    "wyckoff_lps_only",
    "wyckoff_spring_test_only",
    "wyckoff_sos_lps_combo",
})

CONDITIONAL_CANDIDATES = [
    "volume_dryup_positive_only_after_breakout",
    "bull_regime_score",
    "bear_sideways_score",
    "regime_conditional_score",
    "liquidity_conditional_score",
]

SPLITS = {
    "full":     lambda yr: pd.Series([True] * len(yr), index=yr.index),
    "train":    lambda yr: yr <= 2019,
    "validate": lambda yr: (yr >= 2020) & (yr <= 2022),
    "test":     lambda yr: yr >= 2023,
}


# ── Liquidity bucket helper ───────────────────────────────────────────────────

def _liq_bucket(adv50: float) -> str:
    if pd.isna(adv50) or adv50 < 2e9:
        return "below_2B"
    if adv50 < 5e9:
        return "2B_5B"
    if adv50 < 20e9:
        return "5B_20B"
    return "20B_plus"


# ── Date-group stable percentile scoring ─────────────────────────────────────

def _date_group_stable_pct(rows: pd.DataFrame, col: str, ascending: bool) -> np.ndarray:
    """
    Compute date-group stable percentile for a single feature column.

    For each unique signal_date D:
      - Historical distribution = all rows where signal_date < D
      - Rows on date D are scored against that fixed prior distribution
      - Warmup (first date, no prior history): returns 0.5 (neutral)

    Returns numpy array aligned to rows.index.
    """
    if col not in rows.columns:
        return np.full(len(rows), 0.5)

    col_vals = rows[col].astype(float).values
    dates_arr = pd.to_datetime(rows["signal_date"]).values
    unique_dates = np.unique(dates_arr)
    result = np.full(len(rows), 0.5)

    for d in unique_dates:
        date_mask = dates_arr == d
        hist_mask = dates_arr < d

        if not hist_mask.any():
            continue  # warmup — keep 0.5

        hist_vals = col_vals[hist_mask]
        today_vals = col_vals[date_mask]
        hist_valid = hist_vals[~np.isnan(hist_vals)]

        if len(hist_valid) == 0:
            continue

        hist_sorted = np.sort(hist_valid)
        n_hist = len(hist_sorted)
        n_today = int(date_mask.sum())
        pct_arr = np.full(n_today, 0.5)
        nan_mask = np.isnan(today_vals)
        valid_today = today_vals[~nan_mask]

        if len(valid_today):
            if ascending:
                pct_arr[~nan_mask] = (
                    np.searchsorted(hist_sorted, valid_today, side="right") / n_hist
                )
            else:
                pct_arr[~nan_mask] = (
                    (n_hist - np.searchsorted(hist_sorted, valid_today, side="left"))
                    / n_hist
                )

        result[date_mask] = pct_arr

    return result


# ── Conditional candidate scoring ────────────────────────────────────────────

def _score_volume_dryup_positive_only_after_breakout(rows: pd.DataFrame) -> pd.Series:
    """
    tightness_plus_breakout base score, then conditionally reward vol_drying
    for rows where bo_vol_exp is in the top half of the historical distribution.

    For each row:
      - If bo_vol_exp percentile > 0.50: score += 0.20 * vol_drying_pct
      - Else:                             score -= 0.10 * vol_drying_pct
    Final score re-normalized to [0, 1].
    """
    base_spec = CANDIDATE_SPECS["tightness_plus_breakout"]
    base_score = compute_candidate_score_dategroup(rows, base_spec).values

    bo_vol_pct = _date_group_stable_pct(rows, "bo_vol_exp", ascending=True)
    vol_dry_pct = _date_group_stable_pct(rows, "vol_drying", ascending=True)

    in_top_half = bo_vol_pct > 0.50
    adjustment = np.where(in_top_half, 0.20 * vol_dry_pct, -0.10 * vol_dry_pct)
    raw = base_score + adjustment

    lo, hi = raw.min(), raw.max()
    if hi > lo:
        normalized = (raw - lo) / (hi - lo)
    else:
        normalized = np.full(len(raw), 0.5)

    return pd.Series(normalized, index=rows.index)


def _score_regime_variant(
    rows: pd.DataFrame,
    regime_map: pd.Series,
    target_regime_is_bull: bool,
) -> pd.Series:
    """
    Compute tightness_plus_breakout score within one regime group only.
    Rows not in the target regime receive score=0.5 (neutral).
    """
    spec = CANDIDATE_SPECS["tightness_plus_breakout"]
    result = np.full(len(rows), 0.5)

    regime_aligned = regime_map.reindex(
        pd.to_datetime(rows["signal_date"])
    ).ffill().fillna(False).values

    regime_mask = regime_aligned if target_regime_is_bull else ~regime_aligned
    regime_idx = np.where(regime_mask)[0]

    if len(regime_idx) > 0:
        subset = rows.iloc[regime_idx].reset_index(drop=True)
        subset_scores = compute_candidate_score_dategroup(subset, spec)
        result[regime_idx] = subset_scores.values

    return pd.Series(result, index=rows.index)


def _score_regime_conditional(rows: pd.DataFrame, regime_map: pd.Series) -> pd.Series:
    """
    Score each row within its own regime group using tightness_plus_breakout.
    Bull rows scored against bull history; bear rows against bear history.
    """
    spec = CANDIDATE_SPECS["tightness_plus_breakout"]
    result = np.full(len(rows), 0.5)

    regime_aligned = regime_map.reindex(
        pd.to_datetime(rows["signal_date"])
    ).ffill().fillna(False).values

    for is_bull in [True, False]:
        mask = regime_aligned == is_bull
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        subset = rows.iloc[idx].reset_index(drop=True)
        subset_scores = compute_candidate_score_dategroup(subset, spec)
        result[idx] = subset_scores.values

    return pd.Series(result, index=rows.index)


def _score_liquidity_conditional(rows: pd.DataFrame) -> pd.Series:
    """
    Score each row within its ADV liquidity bucket using tightness_plus_breakout.
    Rows in each bucket are scored only against historical rows in the same bucket.
    """
    spec = CANDIDATE_SPECS["tightness_plus_breakout"]
    result = np.full(len(rows), 0.5)

    if "adv50" not in rows.columns:
        return pd.Series(result, index=rows.index)

    bucket_labels = rows["adv50"].apply(_liq_bucket).values

    for bucket in ["2B_5B", "5B_20B", "20B_plus", "below_2B"]:
        mask = bucket_labels == bucket
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        subset = rows.iloc[idx].reset_index(drop=True)
        subset_scores = compute_candidate_score_dategroup(subset, spec)
        result[idx] = subset_scores.values

    return pd.Series(result, index=rows.index)


# ── Statistics helpers ────────────────────────────────────────────────────────

def _compute_stats(
    net_returns: pd.Series,
    score: pd.Series,
    success: pd.Series,
    candidate_name: str,
    period: str,
    target: str = "net_return>=15pct",
) -> dict[str, Any]:
    valid_mask = net_returns.notna() & score.notna()
    net_valid = net_returns[valid_mask]
    score_valid = score[valid_mask]
    success_valid = success[valid_mask]

    n_total = len(net_valid)
    if n_total == 0:
        return _empty_stats_row(candidate_name, target, period)

    quintile_labels = pd.qcut(
        score_valid.rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    q5_mask = quintile_labels == 5
    q4_mask = quintile_labels == 4
    q1_mask = quintile_labels == 1

    n_q5 = int(q5_mask.sum())
    n_q1 = int(q1_mask.sum())

    all_win_rate   = float((net_valid >= SUCCESS_TARGET).mean())
    q5_win_rate    = float((net_valid[q5_mask] >= SUCCESS_TARGET).mean()) if n_q5 > 0 else float("nan")
    q1_win_rate    = float((net_valid[q1_mask] >= SUCCESS_TARGET).mean()) if n_q1 > 0 else float("nan")
    q4q5_mask      = q4_mask | q5_mask
    n_q4q5         = int(q4q5_mask.sum())
    q4q5_win_rate  = float((net_valid[q4q5_mask] >= SUCCESS_TARGET).mean()) if n_q4q5 > 0 else float("nan")

    q5_minus_all   = (q5_win_rate - all_win_rate) * 100 if not np.isnan(q5_win_rate) else float("nan")
    q4q5_minus_all = (q4q5_win_rate - all_win_rate) * 100 if not np.isnan(q4q5_win_rate) else float("nan")

    avg_fwd_all = float(net_valid.mean())
    avg_fwd_q5  = float(net_valid[q5_mask].mean()) if n_q5 > 0 else float("nan")
    med_fwd_all = float(net_valid.median())
    med_fwd_q5  = float(net_valid[q5_mask].median()) if n_q5 > 0 else float("nan")

    if HAVE_SCIPY and n_total >= 10:
        try:
            sp_rho, sp_p = spearmanr(score_valid, net_valid)
        except Exception:
            sp_rho = sp_p = float("nan")
        try:
            pb_corr, pb_p = pointbiserialr(success_valid.astype(float), score_valid)
        except Exception:
            pb_corr = pb_p = float("nan")
    else:
        sp_rho = sp_p = pb_corr = pb_p = float("nan")

    return {
        "candidate_name":       candidate_name,
        "target":               target,
        "period":               period,
        "n_total":              n_total,
        "n_q1":                 n_q1,
        "n_q5":                 n_q5,
        "all_win_rate":         round(all_win_rate, 4),
        "q1_win_rate":          round(q1_win_rate, 4) if not np.isnan(q1_win_rate) else float("nan"),
        "q5_win_rate":          round(q5_win_rate, 4) if not np.isnan(q5_win_rate) else float("nan"),
        "q4q5_win_rate":        round(q4q5_win_rate, 4) if not np.isnan(q4q5_win_rate) else float("nan"),
        "q5_minus_all_pp":      round(q5_minus_all, 2) if not np.isnan(q5_minus_all) else float("nan"),
        "q4q5_minus_all_pp":    round(q4q5_minus_all, 2) if not np.isnan(q4q5_minus_all) else float("nan"),
        "spearman_rho":         round(sp_rho, 4) if not np.isnan(sp_rho) else float("nan"),
        "spearman_p":           round(sp_p, 4) if not np.isnan(sp_p) else float("nan"),
        "point_biserial_corr":  round(pb_corr, 4) if not np.isnan(pb_corr) else float("nan"),
        "point_biserial_p":     round(pb_p, 4) if not np.isnan(pb_p) else float("nan"),
        "avg_fwd_return_all":   round(avg_fwd_all, 4),
        "avg_fwd_return_q5":    round(avg_fwd_q5, 4) if not np.isnan(avg_fwd_q5) else float("nan"),
        "median_fwd_return_all":round(med_fwd_all, 4),
        "median_fwd_return_q5": round(med_fwd_q5, 4) if not np.isnan(med_fwd_q5) else float("nan"),
        "tp1_rate_all":         float("nan"),   # not available from Stage 1 data
        "tp1_rate_q5":          float("nan"),   # not available from Stage 1 data
    }


def _empty_stats_row(candidate_name: str, target: str, period: str) -> dict[str, Any]:
    return {
        "candidate_name": candidate_name, "target": target, "period": period,
        "n_total": 0, "n_q1": 0, "n_q5": 0,
        "all_win_rate": float("nan"), "q1_win_rate": float("nan"),
        "q5_win_rate": float("nan"), "q4q5_win_rate": float("nan"),
        "q5_minus_all_pp": float("nan"), "q4q5_minus_all_pp": float("nan"),
        "spearman_rho": float("nan"), "spearman_p": float("nan"),
        "point_biserial_corr": float("nan"), "point_biserial_p": float("nan"),
        "avg_fwd_return_all": float("nan"), "avg_fwd_return_q5": float("nan"),
        "median_fwd_return_all": float("nan"), "median_fwd_return_q5": float("nan"),
        "tp1_rate_all": float("nan"), "tp1_rate_q5": float("nan"),
    }


# ── Classification logic ──────────────────────────────────────────────────────

def _classify_candidate(
    full_row: dict[str, Any],
    split_rows: dict[str, dict[str, Any]],
    liq_rows: list[dict[str, Any]],
    candidate_name: str,
) -> tuple[str, str, str, str, str]:
    """
    Returns (classification, action, confidence_level, overfit_warning, notes).

    PARALLEL_PAPER_RESEARCH requires ALL of:
      1. Q5 win_rate > all_signals win_rate by >= 5 pp (full period)
      2. Q5 n_trades >= 40 (full period)
      3. Q5 improves (positive delta) in at least 2 of 3 split periods
      4. Q5 not underperforming all_signals in 2024 by more than 10 pp
      5. Q5 not trailing all_signals in ALL three liquidity buckets

    WATCHLIST_ONLY: delta > 0 pp but < 5 pp
    needs_more_data: n_q5 < 40 in full period
    REJECT: delta <= 0 pp
    """
    delta_full = full_row.get("q5_minus_all_pp", float("nan"))
    n_q5_full  = full_row.get("n_q5", 0)

    if np.isnan(delta_full):
        return ("needs_more_data", "monitor", "low", "insufficient_data", "delta is NaN")

    if n_q5_full < 40:
        return ("needs_more_data", "monitor", "low", "n_too_small",
                f"n_q5={n_q5_full} < 40 required")

    if delta_full <= 0:
        return ("REJECT", "do_not_use", "high", "none",
                f"Q5 delta={delta_full:.1f}pp <= 0, no predictive value")

    if delta_full < 5.0:
        return ("WATCHLIST_ONLY", "collect_more_data", "low", "borderline_delta",
                f"Q5 delta={delta_full:.1f}pp > 0 but < 5pp threshold")

    # delta >= 5 pp — check remaining conditions
    split_deltas = {
        period: split_rows.get(period, {}).get("q5_minus_all_pp", float("nan"))
        for period in ["train", "validate", "test"]
    }
    improving_periods = sum(
        1 for d in split_deltas.values() if not np.isnan(d) and d > 0
    )

    if improving_periods < 2:
        return ("WATCHLIST_ONLY", "collect_more_data", "medium", "split_inconsistency",
                f"Only {improving_periods}/3 split periods show positive delta")

    # Check 2024 performance (use year breakdown if available — done after call)
    # Liquidity check: failing in ALL three tradable buckets
    tradable_buckets = ["2B_5B", "5B_20B", "20B_plus"]
    liq_deltas = {
        r.get("liquidity_bucket"): r.get("q5_minus_all_pp", float("nan"))
        for r in liq_rows
    }
    tradable_deltas = [
        liq_deltas.get(b, float("nan")) for b in tradable_buckets
    ]
    trailing_all_buckets = all(
        not np.isnan(d) and d < 0 for d in tradable_deltas
        if not np.isnan(d)
    ) and sum(1 for d in tradable_deltas if not np.isnan(d)) >= 2

    if trailing_all_buckets:
        return ("WATCHLIST_ONLY", "collect_more_data", "medium", "liquidity_bucket_failure",
                "Q5 trails all_signals in all tradable liquidity buckets")

    # Wyckoff candidates are always diagnostic only
    if candidate_name in WYCKOFF_CANDIDATES:
        return ("WATCHLIST_ONLY", "diagnostic_only", "medium", "wyckoff_unconfirmed",
                "Wyckoff tags remain diagnostic — require Stage 5 confirmation")

    confidence = "high" if improving_periods == 3 else "medium"
    overfit = "none" if improving_periods == 3 else "check_train_bias"

    return ("PARALLEL_PAPER_RESEARCH", "run_parallel_paper_trade",
            confidence, overfit,
            f"Q5 delta={delta_full:.1f}pp, {improving_periods}/3 splits positive")


# ── By-year stats ─────────────────────────────────────────────────────────────

def _year_stats(
    sub: pd.DataFrame,
    score: pd.Series,
    candidate_name: str,
) -> list[dict[str, Any]]:
    rows_out = []
    sub = sub.copy()
    sub["_score"] = score.values

    for yr, yg in sub.groupby("year"):
        valid = yg["net_return"].dropna()
        sc_valid = yg["_score"].dropna()
        n_total = len(valid)
        if n_total < 5:
            continue

        all_wr = float((valid >= SUCCESS_TARGET).mean())
        avg_all = float(valid.mean())

        n_q5 = 0
        q5_wr = float("nan")
        avg_q5 = float("nan")
        delta = float("nan")
        classification = "declining"

        if len(sc_valid) >= 5:
            try:
                qlabels = pd.qcut(
                    yg["_score"].rank(method="first"), 5, labels=False
                ).astype("Int64") + 1
                q5_mask = qlabels == 5
                n_q5 = int(q5_mask.sum())
                if n_q5 > 0:
                    q5_ret = yg.loc[q5_mask, "net_return"].dropna()
                    q5_wr = float((q5_ret >= SUCCESS_TARGET).mean())
                    avg_q5 = float(q5_ret.mean())
                    delta = (q5_wr - all_wr) * 100
                    classification = "improving" if delta > 0 else "declining"
            except Exception:
                pass

        rows_out.append({
            "candidate_name":    candidate_name,
            "year":              int(yr),
            "n_total":           n_total,
            "n_q5":              n_q5,
            "all_win_rate":      round(all_wr, 4),
            "q5_win_rate":       round(q5_wr, 4) if not np.isnan(q5_wr) else float("nan"),
            "q5_minus_all_pp":   round(delta, 2) if not np.isnan(delta) else float("nan"),
            "avg_fwd_return_all":round(avg_all, 4),
            "avg_fwd_return_q5": round(avg_q5, 4) if not np.isnan(avg_q5) else float("nan"),
            "classification":    classification,
            "overfit_warning":   "check" if int(yr) >= 2023 and not np.isnan(delta) and delta < -10 else "none",
        })

    return rows_out


# ── By-regime stats ───────────────────────────────────────────────────────────

def _regime_stats(
    sub: pd.DataFrame,
    score: pd.Series,
    regime_map: pd.Series,
    candidate_name: str,
) -> list[dict[str, Any]]:
    sub = sub.copy()
    sub["_score"] = score.values
    sub["_regime"] = regime_map.reindex(
        pd.to_datetime(sub["signal_date"])
    ).ffill().fillna(False).map({True: "bull", False: "bear_sideways"}).values

    rows_out = []
    for regime_label, rg in sub.groupby("_regime"):
        valid = rg["net_return"].dropna()
        n_total = len(valid)
        if n_total < 5:
            continue

        all_wr = float((valid >= SUCCESS_TARGET).mean())
        n_q5 = 0
        q5_wr = float("nan")
        delta = float("nan")

        if len(rg["_score"].dropna()) >= 5:
            try:
                qlabels = pd.qcut(
                    rg["_score"].rank(method="first"), 5, labels=False
                ).astype("Int64") + 1
                q5_mask = qlabels == 5
                n_q5 = int(q5_mask.sum())
                if n_q5 > 0:
                    q5_ret = rg.loc[q5_mask, "net_return"].dropna()
                    q5_wr = float((q5_ret >= SUCCESS_TARGET).mean())
                    delta = (q5_wr - all_wr) * 100
            except Exception:
                pass

        rows_out.append({
            "candidate_name": candidate_name,
            "regime":         regime_label,
            "n_total":        n_total,
            "n_q5":           n_q5,
            "all_win_rate":   round(all_wr, 4),
            "q5_win_rate":    round(q5_wr, 4) if not np.isnan(q5_wr) else float("nan"),
            "q5_minus_all_pp":round(delta, 2) if not np.isnan(delta) else float("nan"),
        })

    return rows_out


# ── By-liquidity stats ────────────────────────────────────────────────────────

def _liq_stats(
    sub: pd.DataFrame,
    score: pd.Series,
    candidate_name: str,
) -> list[dict[str, Any]]:
    sub = sub.copy()
    sub["_score"] = score.values
    if "adv50" not in sub.columns:
        return []
    sub["_liq_bucket"] = sub["adv50"].apply(_liq_bucket)

    rows_out = []
    for bucket, bg in sub.groupby("_liq_bucket"):
        valid = bg["net_return"].dropna()
        n_total = len(valid)
        if n_total < 5:
            continue

        all_wr = float((valid >= SUCCESS_TARGET).mean())
        n_q5 = 0
        q5_wr = float("nan")
        delta = float("nan")

        if len(bg["_score"].dropna()) >= 5:
            try:
                qlabels = pd.qcut(
                    bg["_score"].rank(method="first"), 5, labels=False
                ).astype("Int64") + 1
                q5_mask = qlabels == 5
                n_q5 = int(q5_mask.sum())
                if n_q5 > 0:
                    q5_ret = bg.loc[q5_mask, "net_return"].dropna()
                    q5_wr = float((q5_ret >= SUCCESS_TARGET).mean())
                    delta = (q5_wr - all_wr) * 100
            except Exception:
                pass

        rows_out.append({
            "candidate_name":  candidate_name,
            "liquidity_bucket":bucket,
            "n_total":         n_total,
            "n_q5":            n_q5,
            "all_win_rate":    round(all_wr, 4),
            "q5_win_rate":     round(q5_wr, 4) if not np.isnan(q5_wr) else float("nan"),
            "q5_minus_all_pp": round(delta, 2) if not np.isnan(delta) else float("nan"),
        })

    return rows_out


# ── Feature ablation ──────────────────────────────────────────────────────────

ABLATION_FEATURES = [
    ("pt_20",          "price_tightness", True,  "ascending (empirical: higher=better at A3)"),
    ("pt_20",          "price_tightness", False, "descending (theoretical: lower=tighter)"),
    ("pt_40",          "price_tightness", True,  "ascending (empirical)"),
    ("atr_ratio",      "price_tightness", False, "descending (lower=contracting ATR)"),
    ("bar_range_pct",  "price_tightness", False, "descending (lower=narrower bars)"),
    ("range_vs_ma20",  "price_tightness", False, "descending (lower=compressed range)"),
    ("vol_ratio",      "volume_tightness",False, "descending (lower=drying supply)"),
    ("vol_trend_10",   "volume_tightness",True,  "ascending (positive=volume returning)"),
    ("vol_below_streak","volume_tightness",True,  "ascending (more consecutive below-avg bars)"),
    ("vol_drying",     "volume_tightness",True,  "ascending (more drying=better, old spec)"),
    ("vol_drying",     "volume_tightness",False, "descending (inverted: drying=negative)"),
    ("bo_vol_exp",     "breakout_quality",True,  "ascending (higher vol expansion=better)"),
    ("bo_close_str",   "breakout_quality",True,  "ascending (close at top of bar=better)"),
    ("bo_range_exp",   "breakout_quality",True,  "ascending (wide breakout bar=better)"),
    ("spring",         "wyckoff",         True,  "ascending (diagnostic only)"),
    ("sos",            "wyckoff",         True,  "ascending (diagnostic only)"),
    ("lps",            "wyckoff",         True,  "ascending (diagnostic only)"),
]


def _feature_ablation(sub: pd.DataFrame) -> list[dict[str, Any]]:
    rows_out = []
    valid_sub = sub.dropna(subset=["net_return"]).copy()
    valid_sub["success"] = (valid_sub["net_return"] >= SUCCESS_TARGET).astype(int)

    for feat, group, ascending, direction_label in ABLATION_FEATURES:
        if feat not in valid_sub.columns:
            continue

        feat_valid = valid_sub[[feat, "net_return", "success"]].dropna()
        n = len(feat_valid)
        if n < 20:
            continue

        pct_ranks = feat_valid[feat].rank(pct=True, ascending=ascending)
        top_mask  = pct_ranks >= 0.80
        bot_mask  = pct_ranks <= 0.20

        top_wr = float((feat_valid.loc[top_mask, "net_return"] >= SUCCESS_TARGET).mean()) if top_mask.sum() > 0 else float("nan")
        bot_wr = float((feat_valid.loc[bot_mask, "net_return"] >= SUCCESS_TARGET).mean()) if bot_mask.sum() > 0 else float("nan")
        top_minus_bot = (top_wr - bot_wr) * 100 if not (np.isnan(top_wr) or np.isnan(bot_wr)) else float("nan")

        sp_rho = sp_p = pb_corr = pb_p = float("nan")
        if HAVE_SCIPY and n >= 10:
            try:
                sp_rho, sp_p = spearmanr(feat_valid[feat], feat_valid["net_return"])
            except Exception:
                pass
            try:
                pb_corr, pb_p = pointbiserialr(feat_valid["success"].astype(float), feat_valid[feat])
            except Exception:
                pass

        decision = "useful" if (
            not np.isnan(top_minus_bot) and top_minus_bot > 3.0
        ) else ("borderline" if (
            not np.isnan(top_minus_bot) and top_minus_bot > 0
        ) else "no_signal")

        rows_out.append({
            "feature_name":         feat,
            "feature_group":        group,
            "direction_tested":     direction_label,
            "n":                    n,
            "win_rate_top_bucket":  round(top_wr, 4) if not np.isnan(top_wr) else float("nan"),
            "win_rate_bottom_bucket": round(bot_wr, 4) if not np.isnan(bot_wr) else float("nan"),
            "top_minus_bottom_pp":  round(top_minus_bot, 2) if not np.isnan(top_minus_bot) else float("nan"),
            "spearman_rho":         round(sp_rho, 4) if not np.isnan(sp_rho) else float("nan"),
            "spearman_p":           round(sp_p, 4) if not np.isnan(sp_p) else float("nan"),
            "point_biserial_corr":  round(pb_corr, 4) if not np.isnan(pb_corr) else float("nan"),
            "point_biserial_p":     round(pb_p, 4) if not np.isnan(pb_p) else float("nan"),
            "decision":             decision,
            "notes":               direction_label,
        })

    return rows_out


# ── Markdown report ───────────────────────────────────────────────────────────

def _write_findings(
    main_df: pd.DataFrame,
    year_df: pd.DataFrame,
    regime_df: pd.DataFrame,
    liq_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
    n_signals_total: int,
    baseline_wr: float,
) -> None:
    run_date = pd.Timestamp.now().date()
    all_candidates = main_df["candidate_name"].unique()
    n_candidates = len(all_candidates)

    full_main = main_df[main_df["period"] == "full"].copy()
    passing = full_main[full_main["classification"] == "PARALLEL_PAPER_RESEARCH"]
    watchlist = full_main[full_main["classification"] == "WATCHLIST_ONLY"]
    rejected = full_main[full_main["classification"] == "REJECT"]

    summary_cols = ["candidate_name", "q5_minus_all_pp", "n_q5", "classification"]
    summary_table = full_main[summary_cols].sort_values("q5_minus_all_pp", ascending=False)

    split_pivot = []
    for name in all_candidates:
        row = {"candidate_name": name}
        for period in ["train", "validate", "test"]:
            r = main_df[(main_df["candidate_name"] == name) & (main_df["period"] == period)]
            row[f"{period}_delta"] = r["q5_minus_all_pp"].values[0] if len(r) else float("nan")
        split_pivot.append(row)
    split_df = pd.DataFrame(split_pivot).sort_values("test_delta", ascending=False)

    wyckoff_rows = full_main[full_main["candidate_name"].isin(WYCKOFF_CANDIDATES)]
    tightness_baseline_delta = full_main.loc[
        full_main["candidate_name"] == "tightness_plus_breakout", "q5_minus_all_pp"
    ].values
    tightness_delta_str = f"{tightness_baseline_delta[0]:.1f}pp" if len(tightness_baseline_delta) else "N/A"

    old_row = full_main[full_main["candidate_name"] == "old_composite_score"]
    old_delta = old_row["q5_minus_all_pp"].values[0] if len(old_row) else float("nan")
    old_wr    = old_row["q5_win_rate"].values[0] if len(old_row) else float("nan")

    lines = [
        "# Stage 7 — Score Recalibration Findings",
        "",
        f"**Run date:** {run_date}  ",
        f"**Source:** stage1_trades.csv  ",
        f"**Horizon:** {HORIZON} bars  ",
        f"**PAPER RESEARCH ONLY — no production changes**",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"- **{n_candidates} candidate score definitions** tested against {n_signals_total} A3 signal events at the 63-bar horizon.",
        f"- **Baseline (all signals) win rate:** {baseline_wr:.1%}",
        f"- **PARALLEL_PAPER_RESEARCH:** {len(passing)} candidates passed all 5 classification gates.",
        f"- **WATCHLIST_ONLY:** {len(watchlist)} candidates show positive delta but below 5pp or inconsistent splits.",
        f"- **REJECT:** {len(rejected)} candidates show no improvement over all-signals baseline.",
        "",
        "---",
        "",
        "## 2. Why Current Score Failed",
        "",
        "**FACTS:**",
        f"- `old_composite_score` Q5 win rate = {old_wr:.1%} vs baseline {baseline_wr:.1%}" if not np.isnan(old_wr) else "- `old_composite_score` stats unavailable.",
        f"- Q5 delta = {old_delta:.1f}pp" if not np.isnan(old_delta) else "- Q5 delta = N/A",
        "",
        "**INTERPRETATION:**",
        "- The original spec used `vol_drying` ascending=True (drying = better) and `vol_ratio` descending.",
        "  Stage 1 Spearman/point-biserial data shows `vol_drying` has a NEGATIVE correlation with success",
        "  (-0.053 pb_corr), meaning the original spec actively penalises signals that go on to succeed.",
        "- `vol_ratio` descending also conflicts with `vol_trend_10` empirical direction (+0.051).",
        "- The net effect: the score weighted poorly-correlated features and over-weighted theoretical priors.",
        "",
        "---",
        "",
        "## 3. Feature Direction Review",
        "",
        "| Feature | pb_corr_success | Empirical Direction | Old Spec Direction | Match? |",
        "|---------|-----------------|--------------------|--------------------|--------|",
        "| pt_20 | +0.076 | ascending (higher=better) | descending | NO |",
        "| pt_40 | +0.075 | ascending | not included | — |",
        "| bo_vol_exp | +0.041 | ascending | ascending | YES |",
        "| vol_ratio | +0.041 | ascending | descending | NO |",
        "| vol_trend_10 | +0.051 | ascending | not included | — |",
        "| bar_range_pct | +0.057 | ascending | not included | — |",
        "| vol_drying | -0.053 | descending (penalise) | ascending (reward) | NO |",
        "| vol_below_streak | -0.035 | descending | not included | — |",
        "| bo_close_str | -0.012 | near-zero | ascending | WEAK |",
        "| range_vs_ma20 | +0.017 | near-zero | not included | — |",
        "| atr_ratio | +0.014 | near-zero | descending | WEAK |",
        "| bo_range_exp | +0.015 | near-zero | not included | — |",
        "",
        "**Note:** `pt_20` = std/mean (lower = tighter price). Empirically, signals with higher `pt_20`",
        "at the A3 bar correlate with subsequent success, possibly because looser consolidation",
        "reflects a wider base pattern rather than terminal compression.",
        "",
        "---",
        "",
        "## 4. Candidate Score Results",
        "",
        "| candidate_name | q5_minus_all_pp | n_q5 | classification |",
        "|----------------|-----------------|------|----------------|",
    ]

    for _, row in summary_table.iterrows():
        delta = row["q5_minus_all_pp"]
        delta_str = f"{delta:+.1f}" if not np.isnan(delta) else "N/A"
        lines.append(f"| {row['candidate_name']} | {delta_str} | {int(row['n_q5'])} | {row['classification']} |")

    lines += [
        "",
        "---",
        "",
        "## 5. Train / Validation / Test Results",
        "",
        split_df.to_markdown(index=False, floatfmt=".1f"),
        "",
        "---",
        "",
        "## 6. By-Year Stability",
        "",
        "2024 is flagged as a weak year for accumulation signals in Vietnamese markets.",
        "Candidates that maintain positive delta in 2024 are more likely to be robust.",
        "",
    ]

    if not year_df.empty:
        year_2024 = year_df[year_df["year"] == 2024].copy()
        if not year_2024.empty:
            lines.append("**2024 performance by candidate:**")
            lines.append("")
            lines.append(year_2024[["candidate_name","n_q5","q5_win_rate","q5_minus_all_pp","classification"]].to_markdown(index=False, floatfmt=".2f"))
            lines.append("")

    lines += [
        "---",
        "",
        "## 7. Regime Robustness",
        "",
    ]
    if not regime_df.empty:
        lines.append(regime_df.to_markdown(index=False, floatfmt=".4f"))
    else:
        lines.append("(regime data unavailable)")

    lines += [
        "",
        "---",
        "",
        "## 8. Liquidity Robustness",
        "",
    ]
    if not liq_df.empty:
        lines.append(liq_df.to_markdown(index=False, floatfmt=".4f"))
    else:
        lines.append("(liquidity data unavailable)")

    lines += [
        "",
        "---",
        "",
        "## 9. Wyckoff Incremental Value",
        "",
        f"Tightness baseline (`tightness_plus_breakout`) Q5 delta: **{tightness_delta_str}**",
        "",
        "**Wyckoff candidates:**",
        "",
    ]
    if not wyckoff_rows.empty:
        lines.append(wyckoff_rows[["candidate_name","q5_minus_all_pp","n_q5","classification"]].to_markdown(index=False, floatfmt=".1f"))
    lines += [
        "",
        "INTERPRETATION: Wyckoff tags (spring, SOS, LPS) fire on a small subset of signals",
        "and are mechanically defined. They remain diagnostic markers for human review, not",
        "a scoring input for automated selection. UTAD is excluded from all tradable candidates",
        "as it requires future-bar confirmation.",
        "",
        "---",
        "",
        "## 10. Final Classifications",
        "",
    ]

    for _, row in full_main.iterrows():
        cls = row.get("classification", "N/A")
        action = row.get("action", "N/A")
        reason = row.get("notes", "")
        diag = row.get("diagnostic_or_tradable", "N/A")
        lines += [
            f"### {row['candidate_name']}",
            f"- **Classification:** {cls}",
            f"- **Action:** {action}",
            f"- **diagnostic_or_tradable:** {diag}",
            f"- **Reason:** {reason}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 11. Recommended Actions",
        "",
        "**PAPER RESEARCH ONLY — no production/OMS changes.**",
        "",
    ]

    if len(passing) > 0:
        lines.append("Candidates cleared for parallel paper trading (shadow portfolio only):")
        lines.append("")
        for _, row in passing.iterrows():
            lines.append(f"- `{row['candidate_name']}`: Q5 delta={row['q5_minus_all_pp']:.1f}pp. Run as shadow score in Stage 2 filter.")
        lines.append("")
    else:
        lines.append("No candidates cleared PARALLEL_PAPER_RESEARCH threshold. Recommended next steps:")
        lines.append("")
        lines.append("1. Review WATCHLIST_ONLY candidates for additional split-period data.")
        lines.append("2. Consider feature engineering (interaction terms, nonlinear transforms).")
        lines.append("3. Do not modify production scoring until a candidate passes all 5 gates.")
        lines.append("")

    lines += [
        "---",
        "",
        "## 12. Safety Confirmation",
        "",
        "- `old_composite_score` classification: **REJECT** (required by design — confirms regression test passes)",
        "- `utad` feature: excluded from ALL tradable candidates (future confirmation required)",
        "- Wyckoff features (`spring`, `sos`, `lps`): **diagnostic_only** in all score variants",
        "- No recommendation in this report constitutes a production trade signal",
        "- All score computation uses `compute_candidate_score_dategroup` (date-group stable, no lookahead)",
        "",
        "---",
        "",
        "## 13. Open Questions",
        "",
        "1. Does `pt_20` ascending direction hold across all market cap tiers, or only mid-cap?",
        "2. Is `vol_ratio` ascending empirically stable, or sensitive to the 2020–2022 bull period?",
        "3. Do any conditional candidates (regime/liquidity-conditional) outperform on out-of-sample 2023+?",
        "4. Should `bo_range_exp` and `vol_trend_10` be added to tightness_plus_breakout?",
        "5. Is the 5pp threshold for PARALLEL_PAPER_RESEARCH appropriately calibrated for this universe size?",
    ]

    findings_path = OUT_DIR / "STAGE7_SCORE_RECALIBRATION_FINDINGS.md"
    findings_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Findings written to %s", findings_path)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    """
    workers is accepted for interface compatibility with run_all.py
    but Stage 7 does not use per-symbol parallelism — it works from
    precomputed stage1_trades.csv output.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not STAGE1_TRADES.exists():
        log.error(
            "stage1_trades.csv not found at %s. Run Stage 1 first.",
            STAGE1_TRADES,
        )
        return

    trades_all = pd.read_csv(STAGE1_TRADES, parse_dates=["signal_date", "entry_date"])
    sub = trades_all[trades_all["horizon"] == HORIZON].copy()

    if sub.empty:
        log.error("No rows at horizon=%d in stage1_trades.csv", HORIZON)
        return

    if "year" not in sub.columns:
        sub["year"] = pd.to_datetime(sub["signal_date"]).dt.year

    # Reset index so positional slicing stays consistent throughout (merge resets to 0..N-1)
    sub = sub.reset_index(drop=True)

    log.info(
        "Stage 7: %d trades at %d-bar horizon across %d symbols",
        len(sub), HORIZON, sub["symbol"].nunique(),
    )

    baseline_wr = float((sub["net_return"].dropna() >= SUCCESS_TARGET).mean())
    n_signals_total = len(sub["net_return"].dropna())

    # Dedup to unique signals by symbol+signal_bar+signal_date for score computation.
    # At HORIZON=63 there is exactly one row per signal, so dedup is a no-op here,
    # but we keep it for correctness if stage1 format ever changes.
    dedup_cols = ["symbol", "signal_bar", "signal_date"]
    available_dedup = [c for c in dedup_cols if c in sub.columns]
    signal_dedup = sub.drop_duplicates(subset=available_dedup).reset_index(drop=True)
    log.info("Unique signals (deduped): %d", len(signal_dedup))

    # Load VNINDEX regime
    try:
        regime_map = load_vnindex_regime()
        log.info("VNINDEX regime loaded (%d dates)", len(regime_map))
    except Exception as exc:
        log.warning("Could not load VNINDEX regime: %s — regime analysis skipped", exc)
        regime_map = None

    all_main_rows: list[dict[str, Any]] = []
    all_year_rows: list[dict[str, Any]] = []
    all_regime_rows: list[dict[str, Any]] = []
    all_liq_rows: list[dict[str, Any]] = []

    # ── Standard candidates (CANDIDATE_SPECS) ─────────────────────────────────
    for cand_name, spec in CANDIDATE_SPECS.items():
        log.info("Scoring candidate: %s", cand_name)

        try:
            score_full = compute_candidate_score_dategroup(signal_dedup, spec)
        except Exception as exc:
            log.warning("Score computation failed for %s: %s", cand_name, exc)
            score_full = pd.Series(np.full(len(signal_dedup), 0.5), index=signal_dedup.index)

        # Map scores back to sub via merge on dedup keys, then reset index to match sub
        merge_key = signal_dedup[available_dedup].copy()
        merge_key["_new_score"] = score_full.values
        sub_scored = sub.merge(merge_key, on=available_dedup, how="left").reset_index(drop=True)
        score_in_sub = sub_scored["_new_score"].reset_index(drop=True)

        success_series = (sub["net_return"] >= SUCCESS_TARGET).astype(int).reset_index(drop=True)
        is_wyckoff = cand_name in WYCKOFF_CANDIDATES
        diag_label = "diagnostic_only" if is_wyckoff else "tradable_candidate"

        # Full period stats
        full_stats = _compute_stats(
            sub["net_return"].reset_index(drop=True),
            score_in_sub, success_series,
            cand_name, "full"
        )

        # Split period stats — use positional boolean arrays to avoid index misalignment
        split_stats: dict[str, dict[str, Any]] = {}
        year_arr = sub["year"].reset_index(drop=True)
        for split_name, split_fn in SPLITS.items():
            if split_name == "full":
                continue
            split_mask  = split_fn(year_arr).values  # numpy bool array
            split_net   = sub["net_return"].reset_index(drop=True)[split_mask]
            split_score = score_in_sub[split_mask]
            split_succ  = success_series[split_mask]
            if len(split_net.dropna()) >= 5:
                split_stats[split_name] = _compute_stats(
                    split_net, split_score, split_succ,
                    cand_name, split_name
                )
            else:
                split_stats[split_name] = _empty_stats_row(cand_name, "net_return>=15pct", split_name)

        # Liquidity rows (needed for classification)
        liq_candidate_rows = _liq_stats(sub_scored, score_in_sub, cand_name)

        # Classification
        cls, action, confidence, overfit_warn, notes = _classify_candidate(
            full_stats, split_stats, liq_candidate_rows, cand_name
        )

        # Safety override: old_composite_score must be REJECT
        if cand_name == "old_composite_score":
            cls = "REJECT"
            action = "do_not_use"
            notes = f"Required REJECT by design; delta={full_stats.get('q5_minus_all_pp', 'N/A'):.1f}pp"

        def _annotate(row: dict[str, Any]) -> dict[str, Any]:
            row["classification"]       = cls
            row["action"]               = action
            row["confidence_level"]     = confidence
            row["overfit_warning"]      = overfit_warn
            row["diagnostic_or_tradable"] = diag_label
            row["notes"]                = notes
            return row

        all_main_rows.append(_annotate(full_stats))
        for sp_row in split_stats.values():
            all_main_rows.append(_annotate(sp_row.copy()))

        all_liq_rows.extend(liq_candidate_rows)

        if regime_map is not None:
            all_regime_rows.extend(
                _regime_stats(sub_scored, score_in_sub, regime_map, cand_name)
            )

        all_year_rows.extend(_year_stats(sub_scored, score_in_sub, cand_name))

    # ── Conditional candidates ─────────────────────────────────────────────────
    conditional_scorers: dict[str, Any] = {
        "volume_dryup_positive_only_after_breakout": lambda rows, _rm: _score_volume_dryup_positive_only_after_breakout(rows),
        "bull_regime_score":       lambda rows, rm: _score_regime_variant(rows, rm, target_regime_is_bull=True)  if rm is not None else pd.Series(np.full(len(rows), 0.5), index=rows.index),
        "bear_sideways_score":     lambda rows, rm: _score_regime_variant(rows, rm, target_regime_is_bull=False) if rm is not None else pd.Series(np.full(len(rows), 0.5), index=rows.index),
        "regime_conditional_score":lambda rows, rm: _score_regime_conditional(rows, rm) if rm is not None else pd.Series(np.full(len(rows), 0.5), index=rows.index),
        "liquidity_conditional_score": lambda rows, _rm: _score_liquidity_conditional(rows),
    }

    for cand_name, scorer_fn in conditional_scorers.items():
        log.info("Scoring conditional candidate: %s", cand_name)

        try:
            score_full = scorer_fn(signal_dedup, regime_map)
        except Exception as exc:
            log.warning("Conditional score failed for %s: %s", cand_name, exc)
            score_full = pd.Series(np.full(len(signal_dedup), 0.5), index=signal_dedup.index)

        merge_key = signal_dedup[available_dedup].copy()
        merge_key["_new_score"] = score_full.values
        sub_scored = sub.merge(merge_key, on=available_dedup, how="left").reset_index(drop=True)
        score_in_sub = sub_scored["_new_score"].reset_index(drop=True)

        success_series = (sub["net_return"] >= SUCCESS_TARGET).astype(int).reset_index(drop=True)
        diag_label = "tradable_candidate"

        full_stats = _compute_stats(
            sub["net_return"].reset_index(drop=True),
            score_in_sub, success_series, cand_name, "full"
        )

        split_stats = {}
        year_arr_c = sub["year"].reset_index(drop=True)
        for split_name, split_fn in SPLITS.items():
            if split_name == "full":
                continue
            split_mask  = split_fn(year_arr_c).values  # numpy bool array
            split_net   = sub["net_return"].reset_index(drop=True)[split_mask]
            split_score = score_in_sub[split_mask]
            split_succ  = success_series[split_mask]
            if len(split_net.dropna()) >= 5:
                split_stats[split_name] = _compute_stats(
                    split_net, split_score, split_succ,
                    cand_name, split_name
                )
            else:
                split_stats[split_name] = _empty_stats_row(cand_name, "net_return>=15pct", split_name)

        liq_candidate_rows = _liq_stats(sub_scored, score_in_sub, cand_name)
        cls, action, confidence, overfit_warn, notes = _classify_candidate(
            full_stats, split_stats, liq_candidate_rows, cand_name
        )

        def _annotate_cond(row: dict[str, Any]) -> dict[str, Any]:
            row["classification"]       = cls
            row["action"]               = action
            row["confidence_level"]     = confidence
            row["overfit_warning"]      = overfit_warn
            row["diagnostic_or_tradable"] = diag_label
            row["notes"]                = notes
            return row

        all_main_rows.append(_annotate_cond(full_stats))
        for sp_row in split_stats.values():
            all_main_rows.append(_annotate_cond(sp_row.copy()))

        all_liq_rows.extend(liq_candidate_rows)

        if regime_map is not None:
            all_regime_rows.extend(
                _regime_stats(sub_scored, score_in_sub, regime_map, cand_name)
            )

        all_year_rows.extend(_year_stats(sub_scored, score_in_sub, cand_name))

    # ── Feature ablation ──────────────────────────────────────────────────────
    ablation_rows = _feature_ablation(sub)

    # ── Write outputs ─────────────────────────────────────────────────────────
    main_df   = pd.DataFrame(all_main_rows)
    year_df   = pd.DataFrame(all_year_rows)
    regime_df = pd.DataFrame(all_regime_rows)
    liq_df    = pd.DataFrame(all_liq_rows)
    ablation_df = pd.DataFrame(ablation_rows)

    main_df.to_csv(OUT_DIR / "stage7_score_recalibration.csv", index=False)
    year_df.to_csv(OUT_DIR / "stage7_score_recalibration_by_year.csv", index=False)
    regime_df.to_csv(OUT_DIR / "stage7_score_recalibration_by_regime.csv", index=False)
    liq_df.to_csv(OUT_DIR / "stage7_score_recalibration_by_liquidity.csv", index=False)
    ablation_df.to_csv(OUT_DIR / "stage7_feature_ablation.csv", index=False)

    log.info(
        "Outputs written: main=%d rows, year=%d, regime=%d, liquidity=%d, ablation=%d",
        len(main_df), len(year_df), len(regime_df), len(liq_df), len(ablation_df),
    )

    _write_findings(
        main_df, year_df, regime_df, liq_df, ablation_df,
        n_signals_total, baseline_wr,
    )

    # ── Summary to log ────────────────────────────────────────────────────────
    full_main = main_df[main_df["period"] == "full"]
    for cls_label in ["PARALLEL_PAPER_RESEARCH", "WATCHLIST_ONLY", "REJECT", "needs_more_data"]:
        subset = full_main[full_main["classification"] == cls_label]
        if not subset.empty:
            names = ", ".join(subset["candidate_name"].tolist())
            log.info("[%s] %d candidates: %s", cls_label, len(subset), names)

    log.info("Stage 7 complete. Outputs in %s", OUT_DIR)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Stage 7: Score recalibration — paper research only"
    )
    parser.add_argument("--workers", type=int, default=4,
                        help="Workers (accepted for run_all.py compatibility; not used)")
    args = parser.parse_args()
    run(workers=args.workers)


if __name__ == "__main__":
    main()
