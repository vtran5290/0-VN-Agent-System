"""Vietnam session phase and calendar helpers for intraday preview."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

DEFAULT_TZ = "Asia/Ho_Chi_Minh"


def _parse_hm(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))


def load_session_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, time]:
    cfg = cfg or {}
    sessions = cfg.get("sessions") or {}
    return {
        "pre_open": _parse_hm(sessions.get("pre_open", "08:45")),
        "morning_open": _parse_hm(sessions.get("morning_open", "09:00")),
        "morning_close": _parse_hm(sessions.get("morning_close", "11:30")),
        "afternoon_open": _parse_hm(sessions.get("afternoon_open", "13:00")),
        "afternoon_close": _parse_hm(sessions.get("afternoon_close", "14:45")),
        "pre_atc": _parse_hm(sessions.get("pre_atc", "14:30")),
        "atc_start": _parse_hm(sessions.get("atc_start", "14:45")),
        "market_close": _parse_hm(sessions.get("market_close", "15:00")),
    }


def detect_session_phase(
    ts: datetime,
    *,
    tz_name: str = DEFAULT_TZ,
    session_cfg: Optional[Dict[str, time]] = None,
) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo(tz_name))
    else:
        ts = ts.astimezone(ZoneInfo(tz_name))
    if ts.weekday() >= 5:
        return "CLOSED"
    t = ts.time()
    s = session_cfg or load_session_config()
    if t < s["pre_open"]:
        return "CLOSED"
    if t < s["morning_open"]:
        return "PRE_OPEN"
    if t <= s["morning_close"]:
        return "MORNING_CONTINUOUS"
    if t < s["afternoon_open"]:
        return "LUNCH_BREAK"
    if t < s["pre_atc"]:
        return "AFTERNOON_CONTINUOUS"
    if t < s["atc_start"]:
        return "PRE_ATC"
    if t < s["market_close"]:
        return "ATC"
    return "CLOSED"


def elapsed_tradable_fraction(
    ts: datetime,
    *,
    tz_name: str = DEFAULT_TZ,
    session_cfg: Optional[Dict[str, time]] = None,
) -> Tuple[float, str]:
    """Fraction of regular session elapsed (excludes lunch). Returns (fraction, session_phase)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo(tz_name))
    else:
        ts = ts.astimezone(ZoneInfo(tz_name))
    phase = detect_session_phase(ts, tz_name=tz_name, session_cfg=session_cfg)
    s = session_cfg or load_session_config()
    morning_min = (
        (datetime.combine(ts.date(), s["morning_close"]) - datetime.combine(ts.date(), s["morning_open"]))
    ).seconds / 60
    afternoon_min = (
        (datetime.combine(ts.date(), s["afternoon_close"]) - datetime.combine(ts.date(), s["afternoon_open"]))
    ).seconds / 60
    total = morning_min + afternoon_min
    if total <= 0:
        return 0.0, phase
    t = ts.time()
    if t <= s["morning_open"]:
        elapsed = 0.0
    elif t <= s["morning_close"]:
        elapsed = (datetime.combine(ts.date(), t) - datetime.combine(ts.date(), s["morning_open"])).seconds / 60
    elif t < s["afternoon_open"]:
        elapsed = morning_min
    elif t <= s["afternoon_close"]:
        elapsed = morning_min + (
            datetime.combine(ts.date(), t) - datetime.combine(ts.date(), s["afternoon_open"])
        ).seconds / 60
    else:
        elapsed = total
    return min(1.0, max(0.0, elapsed / total)), phase


def minutes_to_close(ts: datetime, *, tz_name: str = DEFAULT_TZ, session_cfg: Optional[Dict[str, time]] = None) -> Optional[int]:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo(tz_name))
    else:
        ts = ts.astimezone(ZoneInfo(tz_name))
    s = session_cfg or load_session_config()
    phase = detect_session_phase(ts, tz_name=tz_name, session_cfg=s)
    if phase in ("CLOSED", "LUNCH_BREAK", "UNKNOWN"):
        return None
    close_t = s["afternoon_close"] if phase in ("AFTERNOON_CONTINUOUS", "PRE_ATC", "ATC") else s["morning_close"]
    delta = datetime.combine(ts.date(), close_t) - datetime.combine(ts.date(), ts.time())
    return max(0, int(delta.total_seconds() // 60))


def minutes_to_lunch_break(ts: datetime, *, tz_name: str = DEFAULT_TZ, session_cfg: Optional[Dict[str, time]] = None) -> Optional[int]:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo(tz_name))
    else:
        ts = ts.astimezone(ZoneInfo(tz_name))
    s = session_cfg or load_session_config()
    if detect_session_phase(ts, tz_name=tz_name, session_cfg=s) != "MORNING_CONTINUOUS":
        return None
    delta = datetime.combine(ts.date(), s["morning_close"]) - datetime.combine(ts.date(), ts.time())
    return max(0, int(delta.total_seconds() // 60))


def now_hcm() -> datetime:
    return datetime.now(ZoneInfo(DEFAULT_TZ))
