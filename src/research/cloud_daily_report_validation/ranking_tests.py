"""A3 rank score predictiveness tests — section 5.4.

Tests whether a3_rank_score bins predict forward return ordering.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED, load_ohlcv_panel, load_scan_files
from .outcomes import DEFAULT_HORIZONS, MIN_EVENTS_FOR_STAT, compute_forward_returns
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "ranking_validation.csv"

# Rank bins (by a3_rank_score percentile)
_N_BINS = 5


def run_ranking_validation(
    scan_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Test whether a3_rank_score bins predict forward return ordering.

    With ~1wk of scan data, all results will be BLOCKED_BY_DATA.
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    rows: list[dict] = []

    if scan_df.empty or "a3_rank_score" not in scan_df.columns:
        for h in horizons:
            rows.append({
                "rank_bin": "all",
                "horizon_days": h,
                "n_events": 0,
                "mean_forward_ret": None,
                "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
                "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
                "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": "BLOCKED_BY_DATA: scan_df empty or missing a3_rank_score",
            })
        return pd.DataFrame(rows)

    # Filter to rows where a3_rank_score is numeric
    ranked = scan_df.dropna(subset=["a3_rank_score"]).copy()
    ranked["a3_rank_score"] = pd.to_numeric(ranked["a3_rank_score"], errors="coerce")
    ranked = ranked.dropna(subset=["a3_rank_score"])

    n_total = len(ranked)
    if n_total < MIN_EVENTS_FOR_STAT * _N_BINS:
        # Not enough data for meaningful bin analysis
        for h in horizons:
            rows.append({
                "rank_bin": "all",
                "horizon_days": h,
                "n_events": n_total,
                "mean_forward_ret": None,
                "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
                "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
                "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": (
                    f"BLOCKED_BY_DATA: N={n_total} insufficient for {_N_BINS}-bin rank test; "
                    f"need N>={MIN_EVENTS_FOR_STAT * _N_BINS}; "
                    "accumulate 3+ months of scan data"
                ),
            })
        return pd.DataFrame(rows)

    # Assign bins
    ranked["rank_bin"] = pd.qcut(
        ranked["a3_rank_score"], q=_N_BINS, labels=[f"Q{i+1}" for i in range(_N_BINS)], duplicates="drop"
    )

    events_with_rets = compute_forward_returns(ranked, ohlcv, horizons=horizons)

    for bin_label, grp in events_with_rets.groupby("rank_bin", observed=True):
        for h in horizons:
            ret_col = f"forward_ret_{h}d"
            n_bin = len(grp)
            row: dict = {
                "rank_bin": str(bin_label),
                "horizon_days": h,
                "n_events": n_bin,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
                "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
                "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
            }
            if n_bin < MIN_EVENTS_FOR_STAT or ret_col not in grp.columns:
                row["mean_forward_ret"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = f"BLOCKED_BY_DATA: N={n_bin} in bin {bin_label}"
            else:
                rets = pd.to_numeric(grp[ret_col], errors="coerce").dropna()
                row["mean_forward_ret"] = round(float(rets.mean()), 6) if len(rets) > 0 else None
                row["evidence_label"] = EvidenceLabel.INCONCLUSIVE.value
                row["notes"] = f"N={n_bin} — insufficient for robust rank predictiveness test"
            rows.append(row)

    return pd.DataFrame(rows)


def run_ranking_validation_full() -> pd.DataFrame:
    """Load data and run ranking validation, writing results to CSV."""
    scan_df = load_scan_files()
    ohlcv = load_ohlcv_panel()
    result = run_ranking_validation(scan_df, ohlcv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Ranking validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
