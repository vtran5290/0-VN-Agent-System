from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


VIETNAM_LIQUIDITY_FIELDS: List[str] = [
    "omo_net",
    "interbank_on",
    "credit_growth_yoy",
    "fx_usd_vnd",
]


@dataclass(frozen=True)
class VietnamFieldProvenance:
    """
    Field-level provenance for weekly macro inputs.

    Note: weekly report template currently consumes only vietnam.{field} values.
    Provisional provenance is stored in manual_inputs.json for traceability and for
    shadow comparison artifacts.
    """

    field: str
    chosen_source: str
    existing_source: Optional[str] = None
    sstock_source: Optional[str] = None
    series_name: Optional[str] = None
    as_of: Optional[str] = None
    fetched_at: Optional[str] = None
    verification_status: str = "unverified"  # unverified | parsed | auth_missing | request_failed | fallback_used | fallback_failed
    confidence: Optional[float] = None
    delta_vs_existing: Optional[float] = None
    article_date: Optional[str] = None
    value_date: Optional[str] = None
    source_detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "chosen_source": self.chosen_source,
            "existing_source": self.existing_source,
            "sstock_source": self.sstock_source,
            "series_name": self.series_name,
            "as_of": self.as_of,
            "fetched_at": self.fetched_at,
            "verification_status": self.verification_status,
            "confidence": self.confidence,
            "delta_vs_existing": self.delta_vs_existing,
            "article_date": self.article_date,
            "value_date": self.value_date,
            "source_detail": self.source_detail,
        }


@dataclass(frozen=True)
class VietnamLiquidityFacts:
    values: Dict[str, Any]
    meta: Dict[str, VietnamFieldProvenance]
    errors: List[str]

    def to_manual_inputs_vietnam(self) -> Dict[str, Any]:
        # Keep backward compatible: only return the values mapping.
        return dict(self.values)

