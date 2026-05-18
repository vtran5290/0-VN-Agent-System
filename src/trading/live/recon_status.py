"""Load persisted reconciliation status for workflow gating."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.trading.config import LiveTradingConfig


def load_reconciliation_status(config: LiveTradingConfig) -> Optional[Dict[str, Any]]:
    path = config.reconciliation_status_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"BLOCK_NEW_ORDERS": True, "has_issues": True, "status": "CORRUPT"}


def reconciliation_extra_for_mode(
    config: LiveTradingConfig,
    mode: str,
    persisted: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build reconciliation dict passed to risk/execute. Never inject fake clean status."""
    if persisted is not None:
        return persisted
    if config.allow_missing_reconciliation or mode == "paper":
        return {
            "BLOCK_NEW_ORDERS": False,
            "has_issues": False,
            "status": "MISSING",
        }
    return {
        "BLOCK_NEW_ORDERS": True,
        "has_issues": True,
        "status": "MISSING",
    }
