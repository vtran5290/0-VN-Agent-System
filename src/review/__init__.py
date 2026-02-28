"""
Trade Postmortem Layer — review real executed trades, diagnostics, masters review, lessons learned.
No change to risk/regime/allocation/signal logic.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECISION_DIR = REPO / "data" / "decision"
RAW_DIR = REPO / "data" / "raw"
TRADE_HISTORY_MD = RAW_DIR / "trade_history_open_positions.md"
POSITIONS_DIGEST_MD = RAW_DIR / "current_positions_digest.md"
