"""Exit logic tests — section 5.3.

Tests TRAIL_EXIT and TP1_PARTIAL timing and forward loss prevention.

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

_OUTPUT_FILE = OUTPUT_DIR / "exit_logic_validation.csv"

_EXIT_ACTIONS = ("TRAIL_EXIT", "TP1_PARTIAL")


def run_exit_logic_validation(
    scan_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Test exit signal forward behavior (loss prevention, risk metrics).

    For TRAIL_EXIT/TP1_PARTIAL: are returns negative if held past signal?
    With ~1wk scan data, most results will be BLOCKED_BY_DATA.
    """
    if horizons is None:
        horizons = [5, 10, 20]  # Shorter horizons relevant for exits

    rows: list[dict] = []
    for action in _EXIT_ACTIONS:
        for h in horizons:
            row: dict = {
                "exit_action": action,
                "horizon_days": h,
                "signal_integrity": LABEL_RECONSTRUCTED,
                "research_label": RESEARCH_ONLY_LABEL,
                "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
                "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
            }

            if scan_df.empty or "final_action" not in scan_df.columns:
                row["n_events"] = 0
                row["mean_ret_if_held"] = None
                row["pct_negative_if_held"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = "BLOCKED_BY_DATA: scan_df empty or missing final_action"
                rows.append(row)
                continue

            subset = scan_df[scan_df["final_action"] == action].copy()
            n_events = len(subset)
            row["n_events"] = n_events

            if n_events < MIN_EVENTS_FOR_STAT:
                row["mean_ret_if_held"] = None
                row["pct_negative_if_held"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = (
                    f"BLOCKED_BY_DATA: N={n_events} < {MIN_EVENTS_FOR_STAT}; "
                    "exit logic not tested; accumulate 3+ months of scan data"
                )
                rows.append(row)
                continue

            # Compute forward returns (what happens if you hold past exit signal)
            events_with_rets = compute_forward_returns(subset, ohlcv, horizons=[h])
            ret_col = f"forward_ret_{h}d"
            if ret_col not in events_with_rets.columns:
                row["mean_ret_if_held"] = None
                row["pct_negative_if_held"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = "Forward returns column missing"
                rows.append(row)
                continue

            rets = pd.to_numeric(events_with_rets[ret_col], errors="coerce").dropna()
            row["mean_ret_if_held"] = round(float(rets.mean()), 6) if len(rets) > 0 else None
            row["pct_negative_if_held"] = round(float((rets < 0).mean()), 4) if len(rets) > 0 else None
            row["evidence_label"] = EvidenceLabel.INCONCLUSIVE.value
            row["notes"] = f"N={n_events} — insufficient for robust test; labeled INCONCLUSIVE"
            rows.append(row)

    return pd.DataFrame(rows)


def run_exit_logic_validation_full() -> pd.DataFrame:
    """Load data and run exit logic validation, writing results to CSV."""
    scan_df = load_scan_files()
    ohlcv = load_ohlcv_panel()
    result = run_exit_logic_validation(scan_df, ohlcv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Exit logic validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
