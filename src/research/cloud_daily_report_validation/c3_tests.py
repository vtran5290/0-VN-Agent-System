"""RS C3 validation — section 5.8.

C3 IC is near zero in OOS 2024+ per existing documentation.
All outputs labeled CONTEXT_ONLY / DISPLAY_ONLY.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "c3_validation.csv"

# Known finding from prior analysis
_C3_KNOWN_FINDING = (
    "C3 IC near zero in OOS 2024+ per prior analysis; "
    "Review-ranking only per memory/docs. "
    "C3 should be treated as CONTEXT_ONLY, not alpha signal."
)


def run_c3_validation() -> pd.DataFrame:
    """Return C3 validation summary based on prior documented findings.

    No new backtest is run here — the finding is from existing documentation
    and memory (IC near zero in OOS 2024+).

    All rows labeled CONTEXT_ONLY / DISPLAY_ONLY.
    """
    rows = [
        {
            "test": "C3_rating_OOS_IC",
            "test_description": "OOS Information Coefficient for C3 rating in 2024+",
            "n_events": None,
            "ic_value": None,
            "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
            "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
            "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": _C3_KNOWN_FINDING,
            "source": "prior OOS IC analysis (documented in memory/project notes)",
        },
        {
            "test": "EXTREME_RS_flag",
            "test_description": "EXTREME_RS flag predictiveness",
            "n_events": None,
            "ic_value": None,
            "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
            "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
            "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": "IC near zero in OOS 2024+; context-only per prior analysis",
            "source": "prior OOS IC analysis",
        },
        {
            "test": "C3_as_review_ranking_tool",
            "test_description": "C3 used as review/ranking display only (not alpha)",
            "n_events": None,
            "ic_value": None,
            "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
            "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
            "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": (
                "ALREADY_VALIDATED as CONTEXT_ONLY: C3 is confirmed review-ranking only "
                "per REVIEW_RANKING_ONLY lens deployment. No new backtest needed."
            ),
            "source": "RS C3 review-ranking-only integration (project memory)",
        },
    ]
    return pd.DataFrame(rows)


def run_c3_validation_full() -> pd.DataFrame:
    """Run C3 validation, writing results to CSV."""
    result = run_c3_validation()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("C3 validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
