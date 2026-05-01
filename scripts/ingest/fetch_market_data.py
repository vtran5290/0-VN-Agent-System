"""Fetch market data (FireAnt / local fallback)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import REPO
from scripts.utils.io import read_json

MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"
DEBUG_SNAPSHOT = REPO / "data" / "decision" / "market_snapshot_debug.json"


def fetch_market_data(asof: str | None = None) -> Dict[str, Any]:
    """Return market levels from FireAnt debug snapshot or manual_inputs."""
    out: Dict[str, Any] = {"levels": {}, "breadth": {}, "distribution": {}}
    # Prefer debug snapshot (from last weekly run)
    if DEBUG_SNAPSHOT.exists():
        dbg = read_json(DEBUG_SNAPSHOT)
        raw = dbg.get("raw_source", {}) or {}
        mkt = raw.get("market", {}) or {}
        out["levels"] = {
            "vnindex_level": mkt.get("vnindex_level"),
            "vn30_level": mkt.get("vn30_level"),
            "distribution_days_rolling_20": mkt.get("distribution_days_rolling_20"),
            "dist_proxy_symbol": mkt.get("dist_proxy_symbol"),
        }
        out["breadth"] = {
            "vn30_trend_ok": mkt.get("vn30_trend_ok"),
            "hnx_trend_ok": mkt.get("hnx_trend_ok"),
            "upcom_trend_ok": mkt.get("upcom_trend_ok"),
        }
        return out
    manual = read_json(MANUAL_INPUTS)
    m = (manual.get("market") or {}) if manual else {}
    out["levels"] = {
        "vnindex_level": m.get("vnindex_level"),
        "vn30_level": m.get("vn30_level"),
        "distribution_days_rolling_20": m.get("distribution_days_rolling_20"),
        "dist_proxy_symbol": m.get("dist_proxy_symbol"),
    }
    out["breadth"] = {
        "vn30_trend_ok": m.get("vn30_trend_ok"),
        "hnx_trend_ok": m.get("hnx_trend_ok"),
        "upcom_trend_ok": m.get("upcom_trend_ok"),
    }
    return out
