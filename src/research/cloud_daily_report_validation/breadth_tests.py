"""T1/T2 breadth gate tests — section 5.2.

Tests whether breadth_t1_permission and breadth_t2_permission gates
are predictive of forward returns.

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

_OUTPUT_FILE = OUTPUT_DIR / "t1_t2_gate_validation.csv"


def run_t1_t2_gate_validation(
    scan_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Test T1/T2 gate conditions against forward returns.

    Compares returns when breadth_t1_permission=True vs False.

    Given ~1wk of scan data, most results will be BLOCKED_BY_DATA.
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    base_row = {
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
    }

    rows: list[dict] = []
    for gate_col in ("breadth_t1_permission", "breadth_t2_permission"):
        for h in horizons:
            row = dict(base_row)
            row["gate"] = gate_col
            row["horizon_days"] = h

            if scan_df.empty or gate_col not in scan_df.columns:
                row["n_allowed"] = 0
                row["n_blocked"] = 0
                row["mean_ret_allowed"] = None
                row["mean_ret_blocked"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = f"BLOCKED_BY_DATA: scan_df empty or missing {gate_col}"
                rows.append(row)
                continue

            allowed = scan_df[scan_df[gate_col].astype(str).str.upper().isin(["TRUE", "1", "YES"])].copy()
            blocked = scan_df[~scan_df[gate_col].astype(str).str.upper().isin(["TRUE", "1", "YES"])].copy()

            n_allowed = len(allowed)
            n_blocked = len(blocked)
            row["n_allowed"] = n_allowed
            row["n_blocked"] = n_blocked

            if n_allowed < MIN_EVENTS_FOR_STAT or n_blocked < MIN_EVENTS_FOR_STAT:
                row["mean_ret_allowed"] = None
                row["mean_ret_blocked"] = None
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = (
                    f"BLOCKED_BY_DATA: n_allowed={n_allowed}, n_blocked={n_blocked}; "
                    f"both groups need N>={MIN_EVENTS_FOR_STAT}; accumulate 3+ months of scan data"
                )
                rows.append(row)
                continue

            # Compute forward returns
            allowed_rets = compute_forward_returns(allowed, ohlcv, horizons=[h])
            blocked_rets = compute_forward_returns(blocked, ohlcv, horizons=[h])

            ret_col = f"forward_ret_{h}d"
            a_mean = (
                pd.to_numeric(allowed_rets[ret_col], errors="coerce").dropna().mean()
                if ret_col in allowed_rets.columns
                else None
            )
            b_mean = (
                pd.to_numeric(blocked_rets[ret_col], errors="coerce").dropna().mean()
                if ret_col in blocked_rets.columns
                else None
            )

            row["mean_ret_allowed"] = round(float(a_mean), 6) if a_mean is not None and pd.notna(a_mean) else None
            row["mean_ret_blocked"] = round(float(b_mean), 6) if b_mean is not None and pd.notna(b_mean) else None
            row["evidence_label"] = EvidenceLabel.INCONCLUSIVE.value
            row["notes"] = (
                f"N too small for robust test (n_allowed={n_allowed}, n_blocked={n_blocked}); "
                "labeled INCONCLUSIVE"
            )
            rows.append(row)

    return pd.DataFrame(rows)


def run_t1_t2_gate_validation_full() -> pd.DataFrame:
    """Load data and run T1/T2 gate validation, writing results to CSV."""
    scan_df = load_scan_files()
    ohlcv = load_ohlcv_panel()
    result = run_t1_t2_gate_validation(scan_df, ohlcv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("T1/T2 gate validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
