from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MarketStatus(str, Enum):
    DOWNTREND = "downtrend"
    RALLY_ATTEMPT = "rally_attempt"
    CONFIRMED_UPTREND = "confirmed_uptrend"
    UPTREND_UNDER_PRESSURE = "uptrend_under_pressure"
    CORRECTION = "correction"


@dataclass(frozen=True)
class RegimeConfig:
    index_symbol: str = "VN30"
    n_low: int = 15
    dd_window: int = 20
    dd_drop_thresh: float = -0.002  # -0.2%
    ftd_min_pct: float = 0.02  # +2%
    ftd_day_min: int = 3
    ftd_day_max: int = 7
    ftd_max_day: int = 12
    ftd_invalidation_days: int = 10
    ftd_close_break: float = -0.07  # -7%
    dd_under_pressure_min: int = 4
    dd_under_pressure_max: int = 5
    dd_correction_min: int = 6
    ma50_break_volume_confirm: bool = True
    day1_requires_upday: bool = True
    m_consec_below_ma50: int = 3


@dataclass
class RegimeState:
    market_status: MarketStatus = MarketStatus.DOWNTREND

    rally_attempt_active: bool = False
    rally_day_count: int = 0
    rally_start_date: Optional[str] = None
    day1_low: Optional[float] = None
    attempt_id: int = 0

    ftd_detected: bool = False
    ftd_date: Optional[str] = None
    ftd_late: bool = False
    ftd_valid: bool = False
    ftd_low: Optional[float] = None
    ftd_close: Optional[float] = None
    ftd_attempt_id: Optional[int] = None

    distribution_count_20d: int = 0
    dd_flag_today: bool = False
    ftd_flag_today: bool = False
    ma50_break_flag: bool = False

    close_vs_ma50_pct: Optional[float] = None
    close_vs_ftd_close_pct: Optional[float] = None


def defensive_state(status: MarketStatus) -> bool:
    return status in {MarketStatus.CORRECTION, MarketStatus.DOWNTREND}

