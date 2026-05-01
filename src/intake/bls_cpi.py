"""
Official BLS CPI-U (seasonally adjusted) YoY from public API v2.
Series: CUUR0000SA0 — CPI-U All Items, U.S. city average, seasonally adjusted.

No API key required for single-series requests (rate limits apply).
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def _parse_year_month(period: str, year: str) -> Optional[str]:
    """BLS period is M01..M12 + year string -> YYYY-MM."""
    if not period or not year:
        return None
    if not period.startswith("M") or len(period) != 3:
        return None
    try:
        m = int(period[1:])
        y = int(year)
        return f"{y:04d}-{m:02d}"
    except ValueError:
        return None


def fetch_cpi_u_yoy_official(
    *,
    end_year: Optional[int] = None,
    series_id: str = "CUUR0000SA0",
    timeout: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Return latest YoY % for CPI-U SA from BLS, with reference month of the *index* (not release date).

    fetch_status:
      - ok
      - request_failed
      - insufficient_history
    """
    ey = end_year or date.today().year
    sy = ey - 2
    payload = {"seriesid": [series_id], "startyear": str(sy), "endyear": str(ey)}
    try:
        r = requests.post(
            BLS_URL,
            data=json.dumps(payload),
            headers={"Content-type": "application/json"},
            timeout=timeout,
        )
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        logger.warning("BLS CPI request failed: %s", e)
        return {
            "cpi_yoy": None,
            "cpi_reference_month": None,
            "cpi_index_value": None,
            "cpi_prior_year_index_value": None,
            "source_name": "BLS",
            "source_series": series_id,
            "fetch_status": "request_failed",
            "release_date": None,
            "value_date": None,
        }

    try:
        series_list = js.get("Results", {}).get("series", [])
        if not series_list:
            return None
        obs: List[Tuple[str, float]] = []
        for s in series_list:
            for row in s.get("data", []):
                ym = _parse_year_month(row.get("period", ""), row.get("year", ""))
                if ym is None:
                    continue
                try:
                    v = float(row["value"])
                except (KeyError, TypeError, ValueError):
                    continue
                obs.append((ym, v))
        obs.sort(key=lambda x: x[0], reverse=True)
        if len(obs) < 13:
            return {
                "cpi_yoy": None,
                "cpi_reference_month": obs[0][0] if obs else None,
                "fetch_status": "insufficient_history",
                "source_name": "BLS",
                "source_series": series_id,
            }
        cur_ym, cur_v = obs[0]
        cy, cm = cur_ym.split("-")
        target_prior = f"{int(cy) - 1}-{cm}"
        yoy_v = None
        for ym, v in obs:
            if ym == target_prior:
                yoy_v = v
                break
        if yoy_v is None or yoy_v == 0:
            return {
                "cpi_yoy": None,
                "cpi_reference_month": cur_ym,
                "cpi_index_value": cur_v,
                "fetch_status": "insufficient_history",
                "source_name": "BLS",
                "source_series": series_id,
            }
        yoy_pct = round((cur_v / yoy_v - 1.0) * 100.0, 2)
        return {
            "cpi_yoy": yoy_pct,
            "cpi_reference_month": cur_ym,
            "cpi_index_value": cur_v,
            "cpi_prior_year_index_value": yoy_v,
            "source_name": "BLS",
            "source_series": series_id,
            "source_type": "official_release",
            "fetch_status": "ok",
            "release_date": None,
            "value_date": cur_ym,
        }
    except Exception as e:
        logger.warning("BLS CPI parse failed: %s", e)
        return None
