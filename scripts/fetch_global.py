"""
Fetch global macro from FRED. DTWEXBGS for USD index; fallback Yahoo DXY.
Idempotent; partial data on API failure; no crash.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict

logger = logging.getLogger(__name__)

REPO_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


def _fred_series(series_id: str, api_key: str, end: str, days_back: int = 45):
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import latest_value
        return latest_value(series_id, api_key, end, days_back=days_back)
    except Exception as e:
        logger.warning("FRED %s: %s", series_id, e)
        return None


def _fred_cpi_yoy(api_key: str, end: str):
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import cpi_yoy
        return cpi_yoy(api_key, end)
    except Exception as e:
        logger.warning("FRED CPI YoY: %s", e)
        return None


def _fred_nfp(api_key: str, end: str):
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import nfp_latest
        return nfp_latest(api_key, end)
    except Exception as e:
        logger.warning("FRED NFP: %s", e)
        return None


def _dxy_yahoo_fallback(end: str) -> Any:
    try:
        import requests
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        j = r.json()
        chart = j.get("chart", {}).get("result", [{}])[0]
        meta = chart.get("meta", {})
        regular = chart.get("indicators", {}).get("quote", [{}])[0]
        closes = regular.get("close", [])
        if not closes:
            return None
        last = [c for c in closes if c is not None]
        return round(last[-1], 2) if last else None
    except Exception as e:
        logger.warning("Yahoo DXY fallback: %s", e)
        return None


def fetch_global(asof: str | None = None) -> Dict[str, Any]:
    """
    Return {"global": {"ust_2y", "ust_10y", "dxy", "cpi_yoy", "nfp"}}.
    Partial data on failure; never raise.
    """
    if asof is None:
        asof = date.today().isoformat()
    key = os.getenv("FRED_API_KEY")
    out: Dict[str, Any] = {"global": {}}
    if not key:
        logger.warning("FRED_API_KEY not set; global fields will be null")
        return out

    out["global"]["ust_2y"] = _fred_series("DGS2", key, asof)
    out["global"]["ust_10y"] = _fred_series("DGS10", key, asof)
    out["global"]["dxy"] = _fred_series("DTWEXBGS", key, asof)
    if out["global"]["dxy"] is None:
        out["global"]["dxy"] = _dxy_yahoo_fallback(asof)
    out["global"]["cpi_yoy"] = _fred_cpi_yoy(key, asof)
    out["global"]["nfp"] = _fred_nfp(key, asof)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = fetch_global()
    for k, v in r.get("global", {}).items():
        print(f"  {k}: {v}")
