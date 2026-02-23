from __future__ import annotations
from datetime import date
import os
from typing import Dict, Any
from src.intake.fred_api import latest_value

SERIES = {
    "ust_2y": "DGS2",
    "ust_10y": "DGS10",
    "dxy": "DTWEXBGS"
}

def build_auto_global(asof: str | None = None) -> Dict[str, Any]:
    if asof is None:
        asof = date.today().isoformat()

    key = os.getenv("FRED_API_KEY")
    if not key:
        return {"asof_date": asof, "global": {"ust_2y": None, "ust_10y": None, "dxy": None}, "note": "Missing FRED_API_KEY"}

    g = {}
    for k, sid in SERIES.items():
        try:
            g[k] = latest_value(sid, key, asof, days_back=45)
        except Exception:
            g[k] = None

    return {"asof_date": asof, "global": g}
