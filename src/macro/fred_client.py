# src/macro/fred_client.py — FRED API client with file cache and 24h TTL
"""
Do NOT hardcode API keys; use env var FRED_API_KEY.
Cache: data/cache/fred/<series_id>.json. TTL 24h unless --force.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO_ROOT / "data" / "cache" / "fred"
OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_INFO_URL = "https://api.stlouisfed.org/fred/series"
TTL_SECONDS = 24 * 3600


def _get_api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("FRED_API_KEY env var is required and must be non-empty")
    return key


def _cache_path(series_id: str, end_date: str | None = None) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{end_date}" if end_date else ""
    return CACHE_DIR / f"{series_id}{suffix}.json"


def _is_cache_valid(path: Path, ttl_sec: int = TTL_SECONDS) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < ttl_sec


class FREDClient:
    """Simple FRED client with file cache and optional force refresh."""

    def __init__(self, api_key: str | None = None, cache_ttl_sec: int = TTL_SECONDS, force: bool = False):
        self._api_key = api_key or _get_api_key()
        self._ttl = cache_ttl_sec
        self._force = force

    def get_series_observations(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch observations JSON from FRED. Uses cache unless force or expired.
        start_date/end_date: YYYY-MM-DD. If None, end_date=today, start=end-60 days.
        Cache key includes end_date so --asof is respected.
        """
        end = end_date or date.today().isoformat()
        start = start_date or (date.fromisoformat(end) - timedelta(days=60)).isoformat()
        cache_path = _cache_path(series_id, end)
        if not self._force and _is_cache_valid(cache_path, self._ttl):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "observation_start": start,
            "observation_end": end,
            "sort_order": "desc",
        }
        r = requests.get(OBSERVATIONS_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data

    def get_latest_observation(self, series_id: str, end_date: str | None = None) -> tuple[float | None, str | None]:
        """
        Return (latest_value, observation_date) or (None, None) if no valid observation.
        Uses get_series_observations (cached); first non-missing value in desc order.
        """
        end = end_date or date.today().isoformat()
        try:
            data = self.get_series_observations(series_id, end_date=end)
        except Exception:
            return None, None
        for o in data.get("observations", []):
            v = o.get("value")
            if v is None or v == ".":
                continue
            try:
                return float(v), o.get("date")
            except (TypeError, ValueError):
                continue
        return None, None

    def get_observation_n_days_ago(
        self,
        series_id: str,
        end_date: str | None = None,
        n_days: int = 90,
    ) -> tuple[float | None, str | None]:
        """Value and date of observation at ~n_days before end_date (for policy_delta_3m). Uses 130d window, separate cache key."""
        end = end_date or date.today().isoformat()
        start = (date.fromisoformat(end) - timedelta(days=130)).isoformat()
        cache_path = CACHE_DIR / f"{series_id}_{end}_3m.json"
        if not self._force and _is_cache_valid(cache_path, self._ttl):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            params = {
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
                "sort_order": "asc",
            }
            r = requests.get(OBSERVATIONS_URL, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        target = (date.fromisoformat(end) - timedelta(days=n_days)).isoformat()
        best_val, best_date = None, None
        for o in data.get("observations", []):
            d = o.get("date")
            if not d or d > target:
                continue
            v = o.get("value")
            if v is None or v == ".":
                continue
            try:
                best_val, best_date = float(v), d
            except (TypeError, ValueError):
                continue
        return best_val, best_date

    def get_series_info(self, series_id: str) -> dict[str, Any] | None:
        """Optional: fetch series metadata (units, frequency) for snapshot."""
        params = {"series_id": series_id, "api_key": self._api_key, "file_type": "json"}
        try:
            r = requests.get(SERIES_INFO_URL, params=params, timeout=10)
            r.raise_for_status()
            js = r.json()
            seriess = js.get("seriess", [])
            if seriess:
                return seriess[0]
        except Exception:
            pass
        return None
