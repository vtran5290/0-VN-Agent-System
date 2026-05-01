from __future__ import annotations
from datetime import date
import os
from typing import Dict, Any
from src.intake.fred_api import latest_value, latest_observation_with_date

# Never map DTWEXBGS to `dxy` (ICE ~100). Broad dollar is a separate semantic field.
SERIES = {
    "ust_2y": "DGS2",
    "ust_10y": "DGS10",
}


def build_auto_global(asof: str | None = None) -> Dict[str, Any]:
    if asof is None:
        asof = date.today().isoformat()

    key = os.getenv("FRED_API_KEY")
    if not key:
        return {
            "asof_date": asof,
            "global": {
                "ust_2y": None,
                "ust_10y": None,
                "usd_broad_index_fred": None,
            },
            "note": "Missing FRED_API_KEY",
        }

    g: Dict[str, Any] = {}
    for k, sid in SERIES.items():
        try:
            g[k] = latest_value(sid, key, asof, days_back=45)
        except Exception:
            g[k] = None
    # Optional: same observation dates as weekly fetch_global when possible
    try:
        u2 = latest_observation_with_date("DGS2", key, asof, days_back=45)
        if u2:
            g["ust_2y_value_date"] = u2[0]
    except Exception:
        pass
    try:
        u10 = latest_observation_with_date("DGS10", key, asof, days_back=45)
        if u10:
            g["ust_10y_value_date"] = u10[0]
    except Exception:
        pass
    try:
        broad = latest_observation_with_date("DTWEXBGS", key, asof, days_back=60)
        if broad:
            g["usd_broad_index_fred"] = broad[1]
            g["usd_broad_index_fred_value_date"] = broad[0]
    except Exception:
        g["usd_broad_index_fred"] = None

    return {"asof_date": asof, "global": g}
