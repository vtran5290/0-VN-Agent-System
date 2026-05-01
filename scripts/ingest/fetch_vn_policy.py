"""Fetch Vietnam policy events (manual / file fallback)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from scripts.ingest.config import REPO
from scripts.utils.io import read_json

WEEKLY_NOTES = REPO / "data" / "raw" / "weekly_notes.json"


def fetch_vn_policy(asof: str | None = None) -> Dict[str, Any]:
    """Return policy events from weekly_notes; official adapter stubbed."""
    out: Dict[str, Any] = {"events": [], "transmission_map": [], "sources": []}
    notes = read_json(WEEKLY_NOTES)
    if not notes:
        return out
    policy = notes.get("policy_facts") or notes.get("policy_events") or []
    if isinstance(policy, list):
        out["events"] = [e if isinstance(e, dict) else {"title": str(e)} for e in policy]
    return out
