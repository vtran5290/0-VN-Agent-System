"""S3 radar tests — section 5.5.

S3 is paper-shadow only by design. All labels: DISPLAY_ONLY.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED, load_scan_files
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "s3_radar_validation.csv"

_S3_FIELDS = [
    "s3_active",
    "s3_cloud_bull",
    "s3_bars_since",
    "s3_signal_today",
    "s3_lead_bucket",
    "s3_fresh_lead_flag",
    "s3_shadow_action",
    "s3_no_real_order_flag",
    "gk5",
    "gk10",
    "gk_mult",
]


def run_s3_radar_validation(scan_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Check S3 radar fields and confirm paper-shadow status.

    All S3 outputs are DISPLAY_ONLY by design.
    s3_no_real_order_flag must be True for all S3 rows.
    """
    if scan_df is None:
        scan_df = load_scan_files()

    rows: list[dict] = []

    # Check that s3_no_real_order_flag is enforced
    s3_flag_ok = True
    s3_flag_note = "s3_no_real_order_flag not present in scan data"
    n_s3_rows = 0

    if not scan_df.empty and "s3_no_real_order_flag" in scan_df.columns:
        s3_subset = scan_df[scan_df.get("in_s3_universe", pd.Series([False] * len(scan_df))).astype(bool)] if "in_s3_universe" in scan_df.columns else scan_df
        n_s3_rows = len(s3_subset)
        if n_s3_rows > 0:
            # Check that flag is always True for S3 rows
            flag_vals = s3_subset["s3_no_real_order_flag"].astype(str).str.upper()
            all_true = flag_vals.isin(["TRUE", "1", "YES"]).all()
            s3_flag_ok = bool(all_true)
            s3_flag_note = (
                "s3_no_real_order_flag=True for all S3 rows — paper-shadow confirmed"
                if s3_flag_ok
                else "WARNING: s3_no_real_order_flag is not True for all S3 rows — investigate"
            )

    rows.append({
        "test": "s3_no_real_order_flag_enforcement",
        "n_s3_rows_checked": n_s3_rows,
        "flag_always_true": s3_flag_ok,
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "notes": s3_flag_note,
    })

    # Document each S3 field as DISPLAY_ONLY
    for field in _S3_FIELDS:
        present = field in scan_df.columns if not scan_df.empty else False
        rows.append({
            "test": f"s3_field_{field}",
            "n_s3_rows_checked": n_s3_rows,
            "flag_always_true": True,
            "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
            "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
            "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": (
                f"S3 field '{field}' is DISPLAY_ONLY by design (paper-shadow); "
                f"field present in scan: {present}"
            ),
        })

    return pd.DataFrame(rows)


def run_s3_radar_validation_full() -> pd.DataFrame:
    """Load data and run S3 radar validation, writing results to CSV."""
    scan_df = load_scan_files()
    result = run_s3_radar_validation(scan_df)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("S3 radar validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
