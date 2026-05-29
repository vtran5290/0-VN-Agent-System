"""Schema constants and enumerations for cloud daily report validation framework.

RESEARCH_ONLY_NOT_PRODUCTION — all outputs are for research purposes only.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Safety label — must appear in every output
# ──────────────────────────────────────────────────────────────────────────────
RESEARCH_ONLY_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"

# ──────────────────────────────────────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────────────────────────────────────

class EvidenceStatus(str, Enum):
    """Status of existing evidence for a dashboard output."""
    VALIDATED = "VALIDATED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    REJECTED_BY_PRIOR_TEST = "REJECTED_BY_PRIOR_TEST"
    NOT_BACKTESTED = "NOT_BACKTESTED"
    DISPLAY_ONLY = "DISPLAY_ONLY"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    BLOCKED_BY_DATA = "BLOCKED_BY_DATA"
    UNKNOWN = "UNKNOWN"


class EvidenceLabel(str, Enum):
    """Evidence quality label assigned after review."""
    STATISTICALLY_SUPPORTED = "STATISTICALLY_SUPPORTED"
    DIRECTIONALLY_SUPPORTED = "DIRECTIONALLY_SUPPORTED"
    INCONCLUSIVE_DIRECTIONAL_ONLY = "INCONCLUSIVE_DIRECTIONAL_ONLY"
    RISK_CONTROL_SUPPORTED = "RISK_CONTROL_SUPPORTED"
    WORKFLOW_ONLY = "WORKFLOW_ONLY"
    DISPLAY_ONLY = "DISPLAY_ONLY"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED_BY_DATA = "BLOCKED_BY_DATA"
    ALREADY_VALIDATED = "ALREADY_VALIDATED"


class DashboardRecommendation(str, Enum):
    """Recommended action for each dashboard output."""
    KEEP_AS_ALPHA_SIGNAL = "KEEP_AS_ALPHA_SIGNAL"
    KEEP_AS_RISK_CONTROL = "KEEP_AS_RISK_CONTROL"
    KEEP_AS_WORKFLOW_CONTROL = "KEEP_AS_WORKFLOW_CONTROL"
    KEEP_AS_DISPLAY_ONLY = "KEEP_AS_DISPLAY_ONLY"
    DOWNGRADE_LABEL = "DOWNGRADE_LABEL"
    REMOVE_FROM_MAIN_DASHBOARD = "REMOVE_FROM_MAIN_DASHBOARD"
    MOVE_TO_APPENDIX = "MOVE_TO_APPENDIX"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


# ──────────────────────────────────────────────────────────────────────────────
# Final action constants
# ──────────────────────────────────────────────────────────────────────────────
FINAL_ACTIONS: list[str] = [
    "NEW_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH",
    "ADD_T2",
    "NO_T2_BREADTH",
    "WAIT_PB",
    "TRAIL_EXIT",
    "TP1_PARTIAL",
    "HOLD_T1",
    "WATCH_ONLY",
]

# ──────────────────────────────────────────────────────────────────────────────
# Path constants (relative to repo root resolved at runtime)
# ──────────────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent.parent.parent  # D:\V\0. VN Agent System

SCAN_DIR: Path = _REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
OHLCV_PATH: Path = _REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
OUTPUT_DIR: Path = _REPO / "data" / "research" / "cloud_daily_report_validation"
ARCHIVE_DIR: Path = OUTPUT_DIR / "archive"
REPORTS_DIR: Path = _REPO / "reports" / "research" / "cloud_daily_report_validation"
REVIEW_PACKAGES_DIR: Path = _REPO / "outputs" / "review_packages"

# Allowed sets for validation
EVIDENCE_STATUS_VALUES: set[str] = {e.value for e in EvidenceStatus}
EVIDENCE_LABEL_VALUES: set[str] = {e.value for e in EvidenceLabel}
DASHBOARD_RECOMMENDATION_VALUES: set[str] = {e.value for e in DashboardRecommendation}
