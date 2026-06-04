"""
A3 Enhancement Tests
=====================
Joins Capital Footprint scores to historical A3 institutional accumulation signals.
Tests whether CF ranking improves A3 outcomes.

IMPORTANT: Does NOT modify production A3 logic. Read-only research use.
Source of truth: data/research/institutional_accumulation/panel_scores.parquet
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .backtest import _spearman_ic, _ic_tstat

DATA_DIR = Path("data")
A3_PANEL_PATH = DATA_DIR / "research" / "institutional_accumulation" / "panel_scores.parquet"

TIER1_LABEL = "tier1"   # A3 Tier-1 signals (strongest)
TIER12_LABEL = "tier12"  # Tier1+2 combined
SCORE_COL = "institutional_accumulation_score"
CF_SCORE_COL = "capital_footprint_score_raw"


def load_a3_signals(path: Path = A3_PANEL_PATH) -> pd.DataFrame:
    """Load existing A3 panel scores. These are the historical A3 signal dates."""
    if not path.exists():
        raise FileNotFoundError(f"A3 panel not found: {path}")
    df = pd.read_parquet(path)
    if "scan_date" in df.columns:
        df["date"] = pd.to_datetime(df["scan_date"])
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    else:
        raise ValueError("No date column in A3 panel")
    df = df.rename(columns={"ticker": "symbol"})
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def join_cf_to_a3(
    a3: pd.DataFrame,
    cf_panel: pd.DataFrame,
    cf_score_col: str = CF_SCORE_COL,
) -> pd.DataFrame:
    """Join CF scores to A3 signal dates by (symbol, date). All score cols are optional."""
    optional_cols = [
        cf_score_col,
        "capital_footprint_score_pure_tech",
        "big_individual_footprint_proxy",
        "rs_persistence_score",
        "sector_rotation_score",
        "cloud_bull_20_100",
        "breakout_volume_flag",
        "dry_up_pullback_flag",
        "dry_up_near_high_with_trend_support",
        "distribution_cluster_flag",
        "post_breakout_failure_flag",
        "phase_label",
        "sector_primary",
        "fwd_ret_20d", "fwd_ret_60d", "fwd_ret_120d",
        "fwd_max_gain_60d", "tp1_18pct_hit_120d",
        "fwd_alpha_20d_vs_vnindex", "fwd_alpha_60d_vs_vnindex",
    ]
    keep_cols = ["symbol", "date"] + [c for c in optional_cols if c in cf_panel.columns]
    cf_sub = cf_panel[keep_cols].copy()

    # Merge on symbol + date
    merged = a3.merge(cf_sub, on=["symbol", "date"], how="inner", suffixes=("_a3", "_cf"))
    print(f"  A3-CF join: {len(a3):,} A3 rows -> {len(merged):,} matched rows")
    return merged


# ── Variant A: A3 Baseline ────────────────────────────────────────────────────

def run_a3_baseline(merged: pd.DataFrame, fwd_col: str = "fwd_ret_60d") -> dict:
    """A3 Tier1/2 baseline stats without CF filtering."""
    result = {}
    for tier_col, label in [("is_tier1", "tier1"), ("is_tier12", "tier12"),
                              ("is_tier123", "tier123")]:
        if tier_col not in merged.columns or fwd_col not in merged.columns:
            continue
        df = merged[merged[tier_col] == 1]
        if df.empty:
            continue
        result[f"a3_{label}_count"] = int(len(df))
        result[f"a3_{label}_fwd_ret_{fwd_col}"] = round(df[fwd_col].mean(), 4)
        result[f"a3_{label}_win_rate"] = round((df[fwd_col] > 0).mean(), 3)
        if "tp1_18pct_hit_120d" in df.columns:
            result[f"a3_{label}_tp1_hit_rate"] = round(df["tp1_18pct_hit_120d"].mean(), 3)

    return result


# ── Variant B: A3 Ranking Only ────────────────────────────────────────────────

def run_a3_ranking(
    merged: pd.DataFrame,
    cf_score_col: str = CF_SCORE_COL,
    fwd_col: str = "fwd_ret_60d",
    tier_col: str = "is_tier12",
) -> pd.DataFrame:
    """
    Given A3 candidates, does ranking by CF score improve outcomes?
    Tests whether top-CF A3 candidates outperform bottom-CF A3 candidates.
    """
    if tier_col not in merged.columns or cf_score_col not in merged.columns:
        return pd.DataFrame()

    df = merged[(merged[tier_col] == 1) & merged[cf_score_col].notna()].copy()
    if df.empty or fwd_col not in df.columns:
        return pd.DataFrame()

    # Rank A3 candidates by CF score on each date
    df["cf_rank_pct"] = df.groupby("date")[cf_score_col].rank(pct=True, na_option="bottom")

    records = []
    for q_label, q_lo, q_hi in [
        ("top_20pct", 0.8, 1.0),
        ("top_40pct", 0.6, 1.0),
        ("mid_20pct", 0.4, 0.6),
        ("bottom_40pct", 0.0, 0.4),
        ("bottom_20pct", 0.0, 0.2),
        ("all", 0.0, 1.0),
    ]:
        subset = df[(df["cf_rank_pct"] >= q_lo) & (df["cf_rank_pct"] < q_hi)]
        if len(subset) < 10:
            continue
        records.append({
            "cf_rank_group": q_label,
            "n_signals": len(subset),
            "avg_fwd_ret": round(subset[fwd_col].mean(), 4),
            "win_rate": round((subset[fwd_col] > 0).mean(), 3),
            "tp1_hit_rate": round(subset.get("tp1_18pct_hit_120d", pd.Series(0)).mean(), 3),
            "fwd_ret_std": round(subset[fwd_col].std(), 4),
        })

    result = pd.DataFrame(records)
    if not result.empty:
        # Add IC of CF score vs forward return within A3 candidates
        ic = _spearman_ic(df[cf_score_col], df[fwd_col])
        result.attrs["ic_cf_vs_fwd"] = round(ic, 4) if not np.isnan(ic) else np.nan

    return result


# ── Variant C: Review Priority ────────────────────────────────────────────────

def run_a3_review_priority(
    merged: pd.DataFrame,
    cf_score_col: str = CF_SCORE_COL,
    fwd_col: str = "fwd_ret_60d",
    tier_col: str = "is_tier12",
    top_n_list: list[int] = [5, 10, 20],
) -> pd.DataFrame:
    """
    Test whether reviewing only top-N CF-ranked A3 candidates per day
    captures most of the return without needing to review all candidates.
    """
    if tier_col not in merged.columns or cf_score_col not in merged.columns:
        return pd.DataFrame()

    df = merged[(merged[tier_col] == 1) & merged[cf_score_col].notna()].copy()
    if fwd_col not in df.columns:
        return pd.DataFrame()

    df["cf_rank"] = df.groupby("date")[cf_score_col].rank(ascending=False)

    records = []
    for n in top_n_list + [9999]:
        label = f"top_{n}" if n < 9999 else "all"
        subset = df[df["cf_rank"] <= n] if n < 9999 else df
        if len(subset) < 5:
            continue
        records.append({
            "review_priority": label,
            "n_total_candidates": int(len(df)),
            "n_reviewed": int(len(subset)),
            "coverage_pct": round(len(subset) / max(len(df), 1), 3),
            "avg_fwd_ret": round(subset[fwd_col].mean(), 4),
            "win_rate": round((subset[fwd_col] > 0).mean(), 3),
            "tp1_hit_rate": round(subset.get("tp1_18pct_hit_120d", pd.Series(0)).mean(), 3),
        })

    return pd.DataFrame(records)


# ── Variant D: A3 Soft Filter ─────────────────────────────────────────────────

def run_a3_soft_filter(
    merged: pd.DataFrame,
    cf_score_col: str = CF_SCORE_COL,
    fwd_col: str = "fwd_ret_60d",
    tier_col: str = "is_tier12",
    thresholds: list[float] = [0.50, 0.60, 0.70, 0.80, 0.90],
) -> pd.DataFrame:
    """
    Filter A3 entries by minimum CF score percentile.
    Measures: trades retained, win rate, TP1 hit rate, missed winners, avoided losers.
    RESEARCH ONLY — does not change production rules.
    """
    if tier_col not in merged.columns or cf_score_col not in merged.columns:
        return pd.DataFrame()

    df = merged[(merged[tier_col] == 1) & merged[cf_score_col].notna()].copy()
    if fwd_col not in df.columns:
        return pd.DataFrame()

    df["cf_pct"] = df.groupby("date")[cf_score_col].rank(pct=True, na_option="bottom")
    baseline_wins = (df[fwd_col] > 0.10).sum()  # stocks that gained >10%

    records = []
    for th in thresholds:
        subset = df[df["cf_pct"] >= th]
        rejected = df[df["cf_pct"] < th]
        if len(subset) < 5:
            continue

        missed_winners = int((rejected[fwd_col] > 0.10).sum()) if len(rejected) > 0 else 0
        avoided_losers = int((rejected[fwd_col] < -0.07).sum()) if len(rejected) > 0 else 0

        records.append({
            "cf_threshold_pct": th,
            "n_total": int(len(df)),
            "n_retained": int(len(subset)),
            "pct_retained": round(len(subset) / max(len(df), 1), 3),
            "avg_fwd_ret": round(subset[fwd_col].mean(), 4),
            "win_rate": round((subset[fwd_col] > 0).mean(), 3),
            "tp1_hit_rate": round(subset.get("tp1_18pct_hit_120d", pd.Series(0)).mean(), 3),
            "max_drawdown_avg": round(subset.get("fwd_max_drawdown_60d", pd.Series(0)).mean(), 4) if "fwd_max_drawdown_60d" in subset.columns else np.nan,
            "missed_winners_gt10pct": missed_winners,
            "avoided_losers_lt_neg7pct": avoided_losers,
        })

    return pd.DataFrame(records)


# ── Variant E: T2 Confirmation ────────────────────────────────────────────────

def run_a3_t2_confirmation(
    merged: pd.DataFrame,
    cf_score_col: str = CF_SCORE_COL,
    thresholds: list[float] = [0.50, 0.60, 0.70],
) -> pd.DataFrame:
    """
    Test whether CF score confirms T2 add-on entry has better risk/reward.
    Uses: dry_up_pullback_flag, sector_rotation_score, cloud_bull_20_100.
    RESEARCH ONLY.
    """
    if cf_score_col not in merged.columns:
        return pd.DataFrame()

    df = merged.copy()
    fwd_col = "fwd_ret_60d"
    if fwd_col not in df.columns:
        return pd.DataFrame()

    df["cf_pct"] = df.groupby("date")[cf_score_col].rank(pct=True, na_option="bottom")

    records = []
    for th in thresholds:
        for confirm_col, confirm_label in [
            ("dry_up_pullback_flag", "dry_up_pullback"),
            ("cloud_bull_20_100", "cloud_bull"),
        ]:
            if confirm_col not in df.columns:
                continue
            subset = df[(df["cf_pct"] >= th) & (df[confirm_col] == 1)]
            baseline = df[(df["cf_pct"] >= th)]
            if len(subset) < 5:
                continue

            records.append({
                "cf_threshold": th,
                "t2_confirm_signal": confirm_label,
                "n_signals": int(len(subset)),
                "n_baseline": int(len(baseline)),
                "avg_fwd_ret_confirmed": round(subset[fwd_col].mean(), 4),
                "avg_fwd_ret_baseline": round(baseline[fwd_col].mean(), 4),
                "win_rate_confirmed": round((subset[fwd_col] > 0).mean(), 3),
                "win_rate_baseline": round((baseline[fwd_col] > 0).mean(), 3),
                "incremental_return": round(subset[fwd_col].mean() - baseline[fwd_col].mean(), 4),
            })

    return pd.DataFrame(records)


# ── Variant F: Phase 2 — Extension Risk Warning ───────────────────────────────

def run_a3_extension_risk_warning(
    merged: pd.DataFrame,
    fwd_col: str = "fwd_ret_60d",
    tier_col: str = "is_tier12",
) -> pd.DataFrame:
    """
    Test whether A3 signals labeled EXTENSION_DISTRIBUTION_RISK underperform
    A3 signals labeled SUPPLY_ABSORPTION_SETUP or NEUTRAL.

    Requires 'phase_label' column in merged (join cf_panel that has labels).
    RESEARCH ONLY.
    """
    if "phase_label" not in merged.columns or fwd_col not in merged.columns:
        return pd.DataFrame()

    df = merged.copy()
    if tier_col in df.columns:
        df = df[df[tier_col] == 1]
    if df.empty:
        return pd.DataFrame()

    records = []
    for label in df["phase_label"].dropna().unique():
        subset = df[df["phase_label"] == label].dropna(subset=[fwd_col])
        if len(subset) < 5:
            continue
        records.append({
            "phase_label": label,
            "n_signals": len(subset),
            "avg_fwd_ret": round(subset[fwd_col].mean(), 4),
            "win_rate": round((subset[fwd_col] > 0).mean(), 3),
            "tp1_hit_rate": round(subset.get("tp1_18pct_hit_120d", pd.Series(np.nan)).mean(), 3),
        })

    return pd.DataFrame(records)


# ── Variant G: Phase 2 — Dry-Up T2 Confirmation ──────────────────────────────

def run_a3_dryup_t2_confirmation(
    merged: pd.DataFrame,
    fwd_col: str = "fwd_ret_60d",
    tier_col: str = "is_tier12",
) -> pd.DataFrame:
    """
    Test whether SUPPLY_ABSORPTION_SETUP label improves A3 T2 add-on entry outcomes.
    Compares: A3 + dry_up_near_high_with_trend_support vs A3 baseline.
    RESEARCH ONLY.
    """
    confirm_col = "dry_up_near_high_with_trend_support"
    dry_col = "dry_up_pullback_flag"

    if fwd_col not in merged.columns:
        return pd.DataFrame()

    df = merged.copy()
    if tier_col in df.columns:
        df = df[df[tier_col] == 1]
    if df.empty:
        return pd.DataFrame()

    records = []
    for group_label, mask_fn in [
        ("all_a3", lambda d: d),
        ("dry_up_pullback", lambda d: d[d[dry_col].fillna(0) == 1] if dry_col in d.columns else d.head(0)),
        ("dry_up_near_high_trend", lambda d: d[d[confirm_col].fillna(0) == 1] if confirm_col in d.columns else d.head(0)),
        ("NOT_dry_up", lambda d: d[d[dry_col].fillna(0) == 0] if dry_col in d.columns else d),
    ]:
        subset = mask_fn(df).dropna(subset=[fwd_col])
        if len(subset) < 5:
            continue
        records.append({
            "group": group_label,
            "n_signals": len(subset),
            "avg_fwd_ret": round(subset[fwd_col].mean(), 4),
            "win_rate": round((subset[fwd_col] > 0).mean(), 3),
            "tp1_hit_rate": round(subset.get("tp1_18pct_hit_120d", pd.Series(np.nan)).mean(), 3),
            "fwd_ret_std": round(subset[fwd_col].std(), 4),
        })

    return pd.DataFrame(records)


# ── Master A3 Enhancement Runner ─────────────────────────────────────────────

def run_all_a3_enhancement_tests(
    cf_panel: pd.DataFrame,
    a3_path: Path = A3_PANEL_PATH,
) -> dict[str, pd.DataFrame]:
    """Run all A3 enhancement variants and return results dict."""
    print("Loading A3 signals...")
    try:
        a3 = load_a3_signals(a3_path)
    except FileNotFoundError as e:
        print(f"  SKIP: {e}")
        return {}

    print("Joining CF scores to A3 signals...")
    merged = join_cf_to_a3(a3, cf_panel)

    if merged.empty:
        print("  WARN: No join matches — skipping A3 enhancement tests")
        return {}

    print("Running A3 baseline (Variant A)...")
    baseline = run_a3_baseline(merged)
    print(f"  Baseline: {baseline}")

    print("Running A3 ranking (Variant B)...")
    ranking = run_a3_ranking(merged)

    print("Running A3 review priority (Variant C)...")
    priority = run_a3_review_priority(merged)

    print("Running A3 soft filter (Variant D)...")
    soft_filter = run_a3_soft_filter(merged)

    print("Running A3 T2 confirmation (Variant E)...")
    t2 = run_a3_t2_confirmation(merged)

    print("Running A3 extension risk warning (Variant F)...")
    ext_risk = run_a3_extension_risk_warning(merged)

    print("Running A3 dry-up T2 confirmation (Variant G)...")
    dryup_t2 = run_a3_dryup_t2_confirmation(merged)

    return {
        "baseline": pd.DataFrame([baseline]),
        "ranking": ranking,
        "review_priority": priority,
        "soft_filter": soft_filter,
        "t2_confirmation": t2,
        "extension_risk_warning": ext_risk,
        "dryup_t2_confirmation": dryup_t2,
        "merged_sample": merged.head(100),
    }


def run_all_a3_phase2_tests(
    cf_panel: pd.DataFrame,
    a3_path: Path = A3_PANEL_PATH,
) -> dict[str, pd.DataFrame]:
    """
    Phase 2 A3 enhancement tests. Uses full CF panel (no ADV filter applied)
    to maximize universe overlap with A3's lower-liquidity stocks.
    """
    print("Loading A3 signals (Phase 2)...")
    try:
        a3 = load_a3_signals(a3_path)
    except FileNotFoundError as e:
        print(f"  SKIP: {e}")
        return {}

    print(f"  A3 universe: {a3['symbol'].nunique() if 'symbol' in a3.columns else '?'} symbols")

    # Join using full (unfiltered) CF panel
    print("Joining Phase 2 CF panel to A3 signals...")
    merged = join_cf_to_a3(a3, cf_panel)

    if merged.empty:
        print("  WARN: Still no join matches after universe fix")
        return {"join_diagnostics": _build_join_diagnostics(a3, cf_panel)}

    # Phase 2 tests: extension risk + dry-up T2
    print("Running Phase 2 A3 extension risk warning...")
    ext_risk = run_a3_extension_risk_warning(merged)

    print("Running Phase 2 A3 dry-up T2 confirmation...")
    dryup_t2 = run_a3_dryup_t2_confirmation(merged)

    # Phase 1 tests also re-run with fixed universe
    print("Running baseline and ranking with fixed universe...")
    baseline = run_a3_baseline(merged)
    ranking = run_a3_ranking(merged)

    return {
        "p2_baseline": pd.DataFrame([baseline]),
        "p2_ranking": ranking,
        "p2_extension_risk_warning": ext_risk,
        "p2_dryup_t2_confirmation": dryup_t2,
        "p2_merged_sample": merged.head(200),
        "p2_match_count": pd.DataFrame([{
            "a3_total": len(a3),
            "cf_panel_total": len(cf_panel),
            "matched": len(merged),
            "match_rate_pct": round(len(merged) / max(len(a3), 1) * 100, 1),
            "matched_symbols": merged["symbol"].nunique() if "symbol" in merged.columns else 0,
        }]),
    }


def _build_join_diagnostics(a3: pd.DataFrame, cf_panel: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic report when join still fails."""
    a3_syms = set(a3["symbol"].unique()) if "symbol" in a3.columns else set()
    cf_syms = set(cf_panel["symbol"].unique()) if "symbol" in cf_panel.columns else set()
    overlap = a3_syms & cf_syms

    a3_dates = (a3["date"].min(), a3["date"].max()) if "date" in a3.columns else (None, None)
    cf_dates = (cf_panel["date"].min(), cf_panel["date"].max()) if "date" in cf_panel.columns else (None, None)

    return pd.DataFrame([{
        "a3_symbols": len(a3_syms),
        "cf_symbols": len(cf_syms),
        "symbol_overlap": len(overlap),
        "a3_date_min": a3_dates[0],
        "a3_date_max": a3_dates[1],
        "cf_date_min": cf_dates[0],
        "cf_date_max": cf_dates[1],
        "sample_a3_syms": str(sorted(a3_syms)[:10]),
        "sample_cf_syms": str(sorted(cf_syms)[:10]),
    }])
