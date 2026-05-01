from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional, Tuple

from .models import VIETNAM_LIQUIDITY_FIELDS, VietnamFieldProvenance, VietnamLiquidityFacts


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat() + "Z"


def choose_field_value(
    *,
    field: str,
    existing_value: Any,
    sstock_value: Any,
    provider_mode: str,
    existing_source_name: str,
    sstock_source_name: str,
) -> Tuple[Any, VietnamFieldProvenance]:
    """
    provider_mode:
      - "existing": chosen always existing (even if None)
      - "sstock": chosen always sstock (even if None)  (experimental; prefer not to use as primary)
      - "auto": chosen existing if not None else sstock
      - "shadow": treated like auto (chosen existing if available), but provenance will be recorded
    """
    mode = (provider_mode or "existing").lower()
    existing_missing = existing_value is None
    sstock_missing = sstock_value is None

    if mode == "existing":
        chosen = existing_value
        chosen_source = existing_source_name
    elif mode == "sstock":
        chosen = sstock_value
        chosen_source = sstock_source_name
    elif mode in ("auto", "shadow"):
        if not existing_missing:
            chosen = existing_value
            chosen_source = existing_source_name
        else:
            chosen = sstock_value
            chosen_source = sstock_source_name
    else:
        chosen = existing_value
        chosen_source = existing_source_name

    verification_status = "unverified"
    if chosen is None and (existing_missing and sstock_missing):
        verification_status = "request_failed_or_missing"
    elif chosen_source == existing_source_name and existing_value is not None:
        verification_status = "parsed"
    elif chosen_source == sstock_source_name and sstock_value is not None:
        verification_status = "parsed"
    else:
        verification_status = "unverified"

    prov = VietnamFieldProvenance(
        field=field,
        chosen_source=chosen_source,
        existing_source=existing_source_name,
        sstock_source=sstock_source_name,
        verification_status=verification_status,
        fetched_at=_now_iso(),
    )
    return chosen, prov


def merge_vietnam_liquidity(
    *,
    existing: Dict[str, Any],
    sstock: Dict[str, Any],
    provider_mode: str,
    existing_source_name: str = "sbv",
    sstock_source_name: str = "sstock",
    existing_meta: Optional[Dict[str, VietnamFieldProvenance]] = None,
    sstock_meta: Optional[Dict[str, VietnamFieldProvenance]] = None,
) -> VietnamLiquidityFacts:
    existing_meta = existing_meta or {}
    sstock_meta = sstock_meta or {}

    values: Dict[str, Any] = {}
    meta: Dict[str, VietnamFieldProvenance] = {}
    errors: list[str] = []

    for field in VIETNAM_LIQUIDITY_FIELDS:
        ev = existing.get(field)
        sv = sstock.get(field)
        chosen, prov = choose_field_value(
            field=field,
            existing_value=ev,
            sstock_value=sv,
            provider_mode=provider_mode,
            existing_source_name=existing_source_name,
            sstock_source_name=sstock_source_name,
        )

        # When the field is still null, keep SBV (or other existing) diagnostic provenance — e.g. OMO primary_missing + source_detail.
        if chosen is None and field in existing_meta:
            prov = existing_meta[field]
        # Swap in enriched provenance if the chosen value came from that source and we have meta.
        elif prov.chosen_source == existing_source_name and ev is not None and field in existing_meta:
            prov = existing_meta[field]
        elif prov.chosen_source == sstock_source_name and sv is not None and field in sstock_meta:
            prov = sstock_meta[field]

        values[field] = chosen
        meta[field] = prov

    return VietnamLiquidityFacts(values=values, meta=meta, errors=errors)


__all__ = ["merge_vietnam_liquidity", "choose_field_value"]

