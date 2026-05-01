"""Fetch global macro data (FRED / manual fallback)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import DATA_RAW, REPO
from scripts.utils.io import read_json

MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"


def fetch_global_macro(asof: str | None = None) -> Dict[str, Any]:
    """
    Return global macro facts. Uses manual_inputs.json; FRED adapter stubbed.
    """
    out: Dict[str, Any] = {"facts": {}, "what_changed": [], "sources": []}
    manual = read_json(MANUAL_INPUTS)
    if not manual:
        return out
    g = manual.get("global", {}) or {}
    out["facts"] = {
        "ust_2y": g.get("ust_2y"),
        "ust_10y": g.get("ust_10y"),
        "dxy": g.get("dxy"),
        "cpi_yoy": g.get("cpi_yoy"),
        "nfp": g.get("nfp"),
    }
    # Optional: call FRED if API key set (stub)
    fred_key = os.environ.get("FRED_API_KEY")
    if fred_key:
        # TODO: integrate scripts/fetch_global.py or FRED client
        pass
    return out
