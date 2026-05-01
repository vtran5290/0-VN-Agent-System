"""Fetch research intake from inputs/research folder."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from scripts.ingest.config import REPO
from scripts.ingest.source_registry import research_intake_path
from scripts.utils.io import read_json

WEEKLY_NOTES = REPO / "data" / "raw" / "weekly_notes.json"


def fetch_research_intake(asof: str | None = None) -> Dict[str, Any]:
    """Aggregate research intake from weekly_notes and optional inputs/research."""
    out: Dict[str, Any] = {"macro": [], "sector": [], "company": [], "policy": []}
    notes = read_json(WEEKLY_NOTES)
    if notes:
        out["macro"] = list(notes.get("intake_takeaways") or [])[:20]
        out["sector"] = list(notes.get("broker_notes") or [])[:20]
        out["company"] = list(notes.get("earnings_facts") or [])[:20]
        out["policy"] = list(notes.get("policy_facts") or [])[:20]
    path = research_intake_path()
    if path.exists():
        for f in path.glob("*"):
            if f.suffix.lower() in (".json", ".md", ".txt"):
                try:
                    raw = f.read_text(encoding="utf-8")
                    if f.suffix.lower() == ".json":
                        data = read_json(f)
                        if isinstance(data, dict) and data.get("doc_type") == "macro_report":
                            out["macro"].append({"file": f.name, "doc_type": "macro_report"})
                    else:
                        out["macro"].append({"file": f.name, "preview": raw[:200]})
                except Exception:
                    pass
    return out
