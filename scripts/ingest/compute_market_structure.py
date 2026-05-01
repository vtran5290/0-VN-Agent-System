"""Compute market structure (levels, breadth, distribution) from raw inputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import REPO
from scripts.ingest.fetch_market_data import fetch_market_data
from scripts.utils.io import read_json

ALERTS = REPO / "data" / "alerts" / "market_flags.json"


def compute_market_structure(asof: str | None = None) -> Dict[str, Any]:
    """Build market_structure section from market data and alerts."""
    mkt = fetch_market_data(asof)
    flags = read_json(ALERTS)
    levels = mkt.get("levels", {}) or {}
    breadth = mkt.get("breadth", {}) or {}
    dist = {
        "dist_risk_composite": flags.get("risk_flag"),
        "distribution_days_rolling_20": levels.get("distribution_days_rolling_20"),
        "dist_proxy_symbol": levels.get("dist_proxy_symbol"),
    }
    return {
        "levels": levels,
        "breadth": breadth,
        "distribution": dist,
        "breakout_health": {},
        "what_changed": [],
    }
