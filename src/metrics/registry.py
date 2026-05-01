"""
Machine-readable metric audit rows for weekly global macro (and extensions).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class MetricRecord(TypedDict, total=False):
    metric_key: str
    semantic_label: str
    source_name: str
    source_series_code_or_page: str
    source_type: str  # official_release | market_close | fallback | manual | derived
    units: str
    value: Any
    previous_value: Any
    value_date: str
    release_date: str
    as_of_date: str
    fetch_status: str  # ok | failed | not_due_yet | fallback_used | ...
    verification_status: str
    stale_policy: str
    notes: str


def assert_no_dtwexbgs_labeled_dxy(audit: List[Dict[str, Any]]) -> None:
    """Hard validation: FRED DTWEXBGS may only appear as usd_broad_index_fred (never as DXY)."""
    for row in audit:
        if not isinstance(row, dict):
            continue
        code = str(row.get("source_series_code_or_page") or "")
        key = str(row.get("metric_key") or "")
        if code == "DTWEXBGS" and key != "usd_broad_index_fred":
            raise ValueError(
                f"Semantic error: DTWEXBGS must only be metric_key=usd_broad_index_fred, got {key!r}"
            )


def assert_payroll_level_not_labeled_nfp_change(audit: List[Dict[str, Any]]) -> None:
    for row in audit:
        if not isinstance(row, dict):
            continue
        if row.get("metric_key") == "nonfarm_payroll_level_thousands":
            lab = str(row.get("semantic_label") or "").lower()
            if "change" in lab or "mom" in lab or "nfp" == lab:
                raise ValueError("Semantic error: payroll level labeled as change/NFP")
