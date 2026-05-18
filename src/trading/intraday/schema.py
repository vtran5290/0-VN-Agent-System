"""Normalized intraday quote schema (preview layer only)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

SESSION_PHASES = (
    "PRE_OPEN",
    "MORNING_CONTINUOUS",
    "LUNCH_BREAK",
    "AFTERNOON_CONTINUOUS",
    "PRE_ATC",
    "ATC",
    "CLOSED",
    "UNKNOWN",
)

DATA_QUALITY_VALUES = (
    "OK",
    "STALE",
    "MISSING_PRICE",
    "MISSING_VOLUME",
    "SOURCE_UNAVAILABLE",
    "OUT_OF_SESSION",
    "PARTIAL_VOLUME_ESTIMATE",
    "LOW_CONFIDENCE",
)


@dataclass
class IntradayQuote:
    symbol: str
    exchange: str = "HOSE"
    timestamp: str = ""
    source: str = "FireAnt"
    source_latency_sec: Optional[float] = None
    last_price_kvnd: Optional[float] = None
    open_price_kvnd: Optional[float] = None
    high_price_kvnd: Optional[float] = None
    low_price_kvnd: Optional[float] = None
    cumulative_volume: Optional[float] = None
    cumulative_value_vnd: Optional[float] = None
    reference_price_kvnd: Optional[float] = None
    ceiling_price_kvnd: Optional[float] = None
    floor_price_kvnd: Optional[float] = None
    bid1_price_kvnd: Optional[float] = None
    ask1_price_kvnd: Optional[float] = None
    data_quality: str = "OK"
    is_stale: bool = False
    is_intraday: bool = True
    session_phase: str = "UNKNOWN"
    raw_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("raw_fields", None)
        return d


INTRADAY_QUOTE_COLUMNS: List[str] = [
    "symbol",
    "exchange",
    "timestamp",
    "source",
    "source_latency_sec",
    "last_price_kvnd",
    "open_price_kvnd",
    "high_price_kvnd",
    "low_price_kvnd",
    "cumulative_volume",
    "cumulative_value_vnd",
    "reference_price_kvnd",
    "ceiling_price_kvnd",
    "floor_price_kvnd",
    "bid1_price_kvnd",
    "ask1_price_kvnd",
    "data_quality",
    "is_stale",
    "is_intraday",
    "session_phase",
]
