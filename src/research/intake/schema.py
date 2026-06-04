"""Research intake index schema and allowed enum values."""

from __future__ import annotations

INDEX_COLUMNS: tuple[str, ...] = (
    "source_id",
    "file_name",
    "source_type",
    "ticker",
    "sector",
    "source_date",
    "broker_or_source",
    "report_title",
    "extraction_date",
    "confidence",
    "thesis_impact",
    "watchlist_action",
    "key_catalyst",
    "key_risk",
    "linked_card_path",
    "status",
)

SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "equity_research",
        "agm_note",
        "management_meeting",
        "earnings_note",
        "sector_report",
        "macro_strategy",
        "fund_factsheet",
        "other",
    }
)

STATUSES: frozenset[str] = frozenset(
    {
        "RAW_EXTRACTED",
        "CARD_CREATED",
        "REVIEWED",
        "WATCHLIST_UPDATED",
        "ARCHIVED",
    }
)

THESIS_IMPACTS: frozenset[str] = frozenset(
    {
        "IMPROVED",
        "UNCHANGED",
        "WEAKENED",
        "MIXED",
        "UNKNOWN",
    }
)

WATCHLIST_ACTIONS: frozenset[str] = frozenset(
    {
        "UPGRADE",
        "MAINTAIN",
        "DOWNGRADE",
        "REMOVE",
        "ADD_TO_WATCH",
        "NO_ACTION",
    }
)

SAFETY_PHRASE = (
    "Research is thesis/watchlist context only and does not set or override final_action."
)

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = REPO_ROOT / "data" / "research" / "intake" / "index" / "research_index.csv"
