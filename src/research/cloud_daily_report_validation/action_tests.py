"""A3 Final Action Tests — section 5.1.

For each final_action class, compute forward returns if N >= 5, else BLOCKED_BY_DATA.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED, load_ohlcv_panel, load_scan_files
from .outcomes import (
    DEFAULT_HORIZONS,
    MIN_EVENTS_FOR_STAT,
    compute_forward_returns,
    label_blocked_if_small_n,
)
from .schema import (
    FINAL_ACTIONS,
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "final_action_validation.csv"


def run_action_validation(
    scan_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Validate A3 final action classes using forward return event study.

    Parameters
    ----------
    scan_df: concatenated phase36 daily scan DataFrame
    ohlcv: OHLCV panel
    horizons: forward return horizons (default [5, 10, 20, 60])

    Returns
    -------
    DataFrame with one row per (final_action, horizon) combination, with:
    - n_events: count of events for that final_action class
    - mean_forward_ret / median_forward_ret / pct_positive
    - evidence_label, dashboard_recommendation
    - signal_integrity = RECONSTRUCTED_NOT_LIVE_SCAN
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    if scan_df.empty:
        logger.warning("scan_df is empty — all action validation results will be BLOCKED_BY_DATA")
        return _empty_validation_result(FINAL_ACTIONS, horizons, "scan_df empty")

    if "final_action" not in scan_df.columns:
        logger.warning("scan_df missing 'final_action' column")
        return _empty_validation_result(FINAL_ACTIONS, horizons, "missing final_action column")

    # Filter to rows with known final_action values
    actionable = scan_df[scan_df["final_action"].isin(FINAL_ACTIONS)].copy()
    if actionable.empty:
        return _empty_validation_result(FINAL_ACTIONS, horizons, "no actionable rows in scan_df")

    # Compute forward returns for all events
    events_with_returns = compute_forward_returns(actionable, ohlcv, horizons=horizons)

    rows: list[dict] = []
    for action in FINAL_ACTIONS:
        subset = events_with_returns[events_with_returns["final_action"] == action]
        n_events = len(subset)
        for h in horizons:
            ret_col = f"forward_ret_{h}d"
            row: dict = {
                "final_action": action,
                "horizon_days": h,
                "n_events": n_events,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
            }
            if n_events < MIN_EVENTS_FOR_STAT:
                row["mean_forward_ret"] = None
                row["median_forward_ret"] = None
                row["pct_positive"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["evidence_status"] = EvidenceStatus.BLOCKED_BY_DATA.value
                row["dashboard_recommendation"] = DashboardRecommendation.NEEDS_MORE_DATA.value
                row["notes"] = (
                    f"N={n_events} < {MIN_EVENTS_FOR_STAT} required; "
                    "only ~1wk scan history available; accumulate 3+ months for meaningful study"
                )
            elif ret_col not in subset.columns or subset[ret_col].isna().all():
                row["mean_forward_ret"] = None
                row["median_forward_ret"] = None
                row["pct_positive"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["evidence_status"] = EvidenceStatus.BLOCKED_BY_DATA.value
                row["dashboard_recommendation"] = DashboardRecommendation.NEEDS_MORE_DATA.value
                row["notes"] = "All forward returns NaN — OHLCV data gap for this period"
            else:
                rets = pd.to_numeric(subset[ret_col], errors="coerce").dropna()
                row["mean_forward_ret"] = round(float(rets.mean()), 6) if len(rets) > 0 else None
                row["median_forward_ret"] = round(float(rets.median()), 6) if len(rets) > 0 else None
                row["pct_positive"] = round(float((rets > 0).mean()), 4) if len(rets) > 0 else None
                # With N>=5 but typically very small, label as INCONCLUSIVE
                row["evidence_label"] = EvidenceLabel.INCONCLUSIVE.value
                row["evidence_status"] = EvidenceStatus.NOT_BACKTESTED.value
                row["dashboard_recommendation"] = DashboardRecommendation.NEEDS_MORE_DATA.value
                row["notes"] = (
                    f"N={n_events} events — insufficient for robust evidence; "
                    "labeled INCONCLUSIVE per 1wk data limitation"
                )
            rows.append(row)

    return pd.DataFrame(rows)


def _empty_validation_result(
    actions: list[str], horizons: list[int], reason: str
) -> pd.DataFrame:
    rows = []
    for action in actions:
        for h in horizons:
            rows.append({
                "final_action": action,
                "horizon_days": h,
                "n_events": 0,
                "mean_forward_ret": None,
                "median_forward_ret": None,
                "pct_positive": None,
                "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
                "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
                "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": f"BLOCKED_BY_DATA: {reason}",
            })
    return pd.DataFrame(rows)


def run_action_validation_full() -> pd.DataFrame:
    """Load data and run full action validation, writing results to CSV.

    Returns the validation DataFrame.
    """
    logger.info("Loading scan files...")
    scan_df = load_scan_files()
    logger.info("Loading OHLCV panel...")
    ohlcv = load_ohlcv_panel()

    result = run_action_validation(scan_df, ohlcv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Action validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
