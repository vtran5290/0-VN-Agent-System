"""Fetch Vietnam liquidity data (SBV / manual fallback)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import REPO
from scripts.utils.io import read_json

MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"


def fetch_vn_liquidity(asof: str | None = None) -> Dict[str, Any]:
    """Return VN liquidity facts from manual_inputs; SBV adapter stubbed."""
    out: Dict[str, Any] = {"facts": {}, "what_changed": [], "sources": []}
    manual = read_json(MANUAL_INPUTS)
    if not manual:
        return out
    v = manual.get("vietnam", {}) or {}
    out["facts"] = {
        "omo_net": v.get("omo_net"),
        "interbank_on": v.get("interbank_on"),
        "credit_growth_yoy": v.get("credit_growth_yoy"),
        "fx_usd_vnd": v.get("fx_usd_vnd"),
    }
    return out
