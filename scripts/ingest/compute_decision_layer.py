"""Compute decision layer from allocation and alerts."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from scripts.ingest.config import REPO
from scripts.utils.io import read_json

ALLOC = REPO / "data" / "decision" / "allocation_plan.json"
ALERTS = REPO / "data" / "alerts" / "market_flags.json"


def compute_decision_layer(asof: str | None = None) -> Dict[str, Any]:
    """Build decision_layer from allocation_plan and market_flags."""
    alloc = read_json(ALLOC)
    flags = read_json(ALERTS)
    actions: List[str] = []
    risks: List[str] = []
    rules_fired: List[str] = []
    if flags.get("risk_flag"):
        rules_fired.append(flags["risk_flag"])
    if isinstance(alloc.get("allocation"), dict) and alloc["allocation"].get("no_new_buys"):
        rules_fired.append("no_new_buys")
    return {
        "top_actions": actions,
        "top_risks": risks,
        "watchlist_updates": {},
        "decision_rules_fired": rules_fired,
    }
