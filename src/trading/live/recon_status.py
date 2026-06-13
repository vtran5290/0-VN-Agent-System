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


def _recon_asof_date(persisted: Dict[str, Any]) -> Optional[str]:
    raw = persisted.get("asof_date")
    if raw is None:
        return None
    return str(raw)[:10]


def _stale_recon_status(recon_date: Optional[str], cycle_asof_date: str) -> Dict[str, Any]:
    cycle = cycle_asof_date[:10]
    return {
        "BLOCK_NEW_ORDERS": True,
        "has_issues": True,
        "status": "STALE",
        "asof_date": recon_date,
        "reason": (
            f"Recon file is stale (recon={recon_date}, cycle={cycle}) — "
            "run reconciliation for today before executing"
        ),
    }


def reconciliation_extra_for_mode(
    config: LiveTradingConfig,
    mode: str,
    persisted: Optional[Dict[str, Any]],
    *,
    cycle_asof_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Build reconciliation dict passed to risk/execute. Never inject fake clean status."""
    if persisted is not None:
        if (
            cycle_asof_date is not None
            and mode in ("live_manual", "live_auto")
        ):
            recon_date = _recon_asof_date(persisted)
            if recon_date != cycle_asof_date[:10]:
                return _stale_recon_status(recon_date, cycle_asof_date)
        return persisted
    if mode in ("live_manual", "live_auto"):
        return {
            "BLOCK_NEW_ORDERS": True,
            "has_issues": True,
            "status": "MISSING",
        }
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
