from __future__ import annotations
from datetime import date, timedelta
from typing import Optional, List, Tuple
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def get_observations(
    series_id: str, api_key: str, end: str, days_back: int = 400, limit: int = 20
) -> List[Tuple[str, float]]:
    """Return list of (date_str, value) sorted desc (newest first)."""
    end_dt = date.fromisoformat(end)
    start_dt = end_dt - timedelta(days=days_back)
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_dt.isoformat(),
        "observation_end": end,
        "sort_order": "desc",
        "limit": limit,
    }
    r = requests.get(FRED_BASE, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    out: List[Tuple[str, float]] = []
    for o in js.get("observations", []):
        v = o.get("value")
        if v is None or v == ".":
            continue
        try:
            out.append((o.get("date", ""), float(v)))
        except (TypeError, ValueError):
            continue
    return out


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


def cpi_yoy(api_key: str, end: str) -> Optional[float]:
    """CPIAUCSL: (CPI_t / CPI_t-12 - 1) * 100. Needs 13+ monthly obs."""
    obs = get_observations("CPIAUCSL", api_key, end, days_back=400, limit=14)
    if len(obs) < 13:
        return None
    c_t = obs[0][1]
    c_t12 = obs[12][1]
    if not c_t or not c_t12:
        return None
    return round((c_t / c_t12 - 1.0) * 100.0, 2)


def nfp_latest(api_key: str, end: str) -> Optional[float]:
    """PAYEMS: latest level (thousands). Optional: monthly change = level - prev_level."""
    obs = get_observations("PAYEMS", api_key, end, days_back=400, limit=3)
    if not obs:
        return None
    return obs[0][1]
