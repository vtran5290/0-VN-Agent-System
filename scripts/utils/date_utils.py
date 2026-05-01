"""Date helpers for report freshness and asof."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional


def parse_date(s: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD to date; return None if invalid."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def report_age_days(asof: Optional[str], today: Optional[date] = None) -> Optional[int]:
    """Days between today and asof_date."""
    d = parse_date(asof)
    if d is None:
        return None
    t = today or date.today()
    return (t - d).days


def is_date_after(a: Optional[str], b: Optional[str]) -> bool:
    """True if date a is strictly after date b (YYYY-MM-DD)."""
    da, db = parse_date(a), parse_date(b)
    if da is None or db is None:
        return False
    return da > db


def iso_now_utc() -> str:
    """Current time in ISO8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
