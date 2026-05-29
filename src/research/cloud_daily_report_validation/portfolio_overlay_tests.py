"""Portfolio overlay tests — section 5.9.

No historical portfolio state available → BLOCKED_BY_DATA.
Documents what would be needed for a real portfolio overlay test.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    _REPO,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_CURRENT_POSITIONS_PATH = _REPO / "data" / "raw" / "current_positions_derived.json"
_OUTPUT_FILE = OUTPUT_DIR / "portfolio_overlay_validation.csv"

_REQUIREMENTS_FOR_REAL_TEST = [
    "Daily position snapshots (size, cost basis, unrealized P&L) for at least 3 months",
    "Time-stamped portfolio entry/exit log matching scan final_action",
    "NAV history with daily returns attributable to individual holdings",
    "Overlay action log (TAKE_PARTIAL, REVIEW_TRAIL_EXIT, ADD_BLOCKED_BY_BREADTH) timestamps",
    "Matched scan_date → action_date → execution_price to reconstruct event study",
]


def run_portfolio_overlay_validation() -> pd.DataFrame:
    """Document portfolio overlay test status.

    All tests are BLOCKED_BY_DATA — only current position state exists,
    no historical snapshots available for event study.
    """
    rows: list[dict] = []
    base = {
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
    }

    # Check current positions file
    positions_exists = _CURRENT_POSITIONS_PATH.is_file()
    rows.append({
        **base,
        "test": "current_positions_file_check",
        "data_available": positions_exists,
        "notes": (
            f"current_positions_derived.json {'EXISTS' if positions_exists else 'MISSING'} — "
            "but contains only current state, not historical snapshots. "
            "Cannot reconstruct portfolio event study from current state alone."
        ),
    })

    overlay_actions = [
        "TAKE_PARTIAL",
        "REVIEW_TRAIL_EXIT",
        "ADD_BLOCKED_BY_BREADTH",
        "PAPER_ONLY",
    ]
    for action in overlay_actions:
        rows.append({
            **base,
            "test": f"portfolio_overlay_{action}",
            "data_available": False,
            "notes": (
                f"BLOCKED_BY_DATA: '{action}' overlay test requires historical position snapshots. "
                "No daily portfolio state history available. "
                "This test cannot be run until position logging is implemented."
            ),
        })

    # Document what is needed
    requirements_note = " | ".join(f"[{i+1}] {r}" for i, r in enumerate(_REQUIREMENTS_FOR_REAL_TEST))
    rows.append({
        **base,
        "test": "requirements_for_real_portfolio_overlay_test",
        "data_available": False,
        "notes": f"REQUIREMENTS: {requirements_note}",
    })

    return pd.DataFrame(rows)


def run_portfolio_overlay_validation_full() -> pd.DataFrame:
    """Run portfolio overlay validation, writing results to CSV."""
    result = run_portfolio_overlay_validation()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Portfolio overlay validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
