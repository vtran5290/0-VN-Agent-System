from __future__ import annotations
from datetime import date, timedelta
from typing import Optional
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def latest_value(series_id: str, api_key: str, end: str, days_back: int = 30) -> Optional[float]:
    end_dt = date.fromisoformat(end)
    start_dt = end_dt - timedelta(days=days_back)
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_dt.isoformat(),
        "observation_end": end,
        "sort_order": "desc",
        "limit": 10
    }
    r = requests.get(FRED_BASE, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    obs = js.get("observations", [])
    for o in obs:
        v = o.get("value")
        if v is None:
            continue
        if v == ".":
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None
