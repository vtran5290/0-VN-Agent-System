"""
Stock DNA Research Module — Schema, constants, and safety definitions.
RESEARCH ONLY. Does not modify production A3 logic.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

# ── Safety label ──────────────────────────────────────────────────────────────

RESEARCH_ONLY_LABEL = "STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE"

# ── Integration status label (exact ChatGPT-approved wording) ─────────────────

INTEGRATION_STATUS_LABEL = (
    "STOCK_DNA_RESEARCH_ANNOTATION_ONLY — "
    "production-ready for research annotation only, not trading execution"
)

# ── Feature flag (default OFF — must be explicitly enabled) ───────────────────

import os as _os
STOCK_DNA_ANNOTATION_ENABLED: bool = (
    _os.environ.get("STOCK_DNA_ANNOTATION_ENABLED", "false").lower() == "true"
)

# ── Candidate lines (council-approved v2 set — SMA50 added 2026-06-06) ───────
# v1: ema20, ema50, sma100, sma150
# v2: adds sma50 (fills gap between ema50 and sma100; targets mid-cycle pullbacks)
# SMA200 deferred — only add if sma50 results show long end is unaddressed.

CANDIDATE_LINES: dict[str, tuple[str, int]] = {
    "ema20":  ("ema", 20),
    "ema50":  ("ema", 50),
    "sma50":  ("sma", 50),   # council addition 2026-06-06
    "sma100": ("sma", 100),
    "sma150": ("sma", 150),
}

# ── Touch tolerances ──────────────────────────────────────────────────────────

TOLERANCE_PCT: dict[str, float] = {
    "1pct": 0.01,
    "2pct": 0.02,
}

TOLERANCE_ATR: dict[str, float] = {
    "0.5atr": 0.5,
    "1.0atr": 1.0,
}

# ── Confidence thresholds (council requirement) ───────────────────────────────

MIN_TOUCH_FOR_MEDIUM: int = 20
MIN_TOUCH_FOR_HIGH: int = 40
MIN_BARS_REQUIRED: int = 252
MIN_ADV20_VND: float = 5e9   # 5bn VND

# ── OOS holdout ───────────────────────────────────────────────────────────────

OOS_HOLDOUT_MONTHS: int = 12

# ── VIN / VPL handling (per VIN_EMA_CLOUD_BASELINE.md) ───────────────────────

VPL_MIN_BARS: int = 252
DISTORTION_FLAG_SYMBOLS: frozenset[str] = frozenset({"VIN"})

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")
SSOT_DIR = DATA_DIR / "fireant_ssot"
DNA_DIR = DATA_DIR / "research" / "stock_dna"
REVIEW_DIR = Path("review_outputs")

# Production paths — research outputs MUST NOT overlap with these
_PRODUCTION_PATHS = frozenset({
    str(DATA_DIR / "decision"),
    str(DATA_DIR / "scan"),
    str(DATA_DIR / "state"),
    str(DATA_DIR / "paper_trade"),
})


def assert_output_path_safe(path: "Path | str") -> None:
    """
    Raise ValueError if path overlaps with any production directory.

    Resolves the path if possible (handles relative paths and symlinks).
    Compares path parts to block both exact matches and subdirectory matches.
    Also blocks paths containing known production segment names, regardless of
    leading prefix (handles both resolved absolute and passed relative paths).
    """
    import os

    p_obj = Path(path)
    # Try to resolve; fall back to absolute if path doesn't exist yet
    try:
        p_resolved = p_obj.resolve()
    except Exception:
        p_resolved = p_obj.absolute()

    p_str = str(p_resolved)
    p_parts = p_resolved.parts

    # Check by path parts (robust to relative vs absolute and trailing slashes)
    for prod in _PRODUCTION_PATHS:
        prod_obj = Path(prod)
        prod_parts = prod_obj.parts
        # Block if prod_parts are a prefix of p_parts
        if len(prod_parts) <= len(p_parts) and p_parts[:len(prod_parts)] == prod_parts:
            raise ValueError(
                f"[Stock DNA] Output path '{p_str}' overlaps with production directory '{prod}'. "
                "Research outputs must go under data/research/stock_dna/ or review_outputs/ only."
            )

    # Also block by segment name (catches cases where path parts comparison misses due to casing/OS)
    _blocked_segments = {"decision", "scan", "state", "paper_trade"}
    for part in p_parts:
        if part.lower() in _blocked_segments:
            raise ValueError(
                f"[Stock DNA] Output path '{p_str}' overlaps with production directory '{part}'. "
                "Research outputs must go under data/research/stock_dna/ or review_outputs/ only."
            )


# ── Enums ─────────────────────────────────────────────────────────────────────

class DNAConfidence(str, Enum):
    NONE   = "NONE"
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class StockPhase(str, Enum):
    MARKUP              = "MARKUP"
    PULLBACK_IN_UPTREND = "PULLBACK_IN_UPTREND"
    DECLINE             = "DECLINE"
    BASE_OR_CHOP        = "BASE_OR_CHOP"


class BreadthRegime(str, Enum):
    BULL_BROAD  = "BULL_BROAD"
    BULL_NARROW = "BULL_NARROW"
    NEUTRAL     = "NEUTRAL"
    BEAR        = "BEAR"
    STRESS      = "STRESS"


class DNAProductionStatus(str, Enum):
    REJECT                  = "REJECT"
    WATCHLIST_ONLY          = "WATCHLIST_ONLY"
    RESEARCH_ANNOTATION_ONLY = "RESEARCH_ANNOTATION_ONLY"
    PAPER_SHADOW_CANDIDATE  = "PAPER_SHADOW_CANDIDATE"


# ── Annotation column names (research only — never written to production paths) ─

COL_DNA_T2_NOTE       = "stock_dna_t2_note"
COL_DNA_T2_LINE       = "stock_dna_t2_line"
COL_DNA_T2_CONFIDENCE = "stock_dna_t2_confidence"
COL_DNA_T2_ACTIVE     = "stock_dna_t2_active"
COL_DNA_DANGER_NOTE   = "stock_dna_danger_line_note"
COL_DNA_DANGER_LINE   = "stock_dna_danger_line"
COL_DNA_DANGER_ACTIVE = "stock_dna_danger_active"
COL_DNA_CONTEXT_SCORE = "stock_dna_context_score"

DNA_ANNOTATION_COLS = [
    COL_DNA_T2_NOTE, COL_DNA_T2_LINE, COL_DNA_T2_CONFIDENCE, COL_DNA_T2_ACTIVE,
    COL_DNA_DANGER_NOTE, COL_DNA_DANGER_LINE, COL_DNA_DANGER_ACTIVE,
    COL_DNA_CONTEXT_SCORE,
]

# Production columns that must never be modified by any research module
PROTECTED_PRODUCTION_COLS = frozenset({
    "final_action", "a3_rank_score", "symbol", "as_of_date",
    "close", "open", "high", "low", "volume", "value",
})
