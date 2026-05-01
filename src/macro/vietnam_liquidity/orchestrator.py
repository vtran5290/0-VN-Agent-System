from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional, Tuple

from .adapter import merge_vietnam_liquidity
from .models import VIETNAM_LIQUIDITY_FIELDS, VietnamFieldProvenance, VietnamLiquidityFacts
from .providers.sbv_provider import fetch_vietnam_liquidity_sbv
from .providers.sstock_provider import fetch_vietnam_liquidity_sstock


def _relative_delta(a: float, b: float) -> Optional[float]:
    if a == 0:
        return None
    return abs(a - b) / abs(a)


def _near_match(field: str, existing: Any, sstock: Any) -> bool:
    if existing is None or sstock is None:
        return False
    try:
        if field == "fx_usd_vnd":
            return abs(int(round(float(existing))) - int(round(float(sstock)))) <= 1
        # Other fields: allow 1% relative delta or absolute small tolerance.
        a = float(existing)
        b = float(sstock)
        if a == 0:
            return abs(b) <= 0.001
        return _relative_delta(a, b) is not None and _relative_delta(a, b) <= 0.01
    except Exception:
        return False


def compare_vietnam_liquidity(
    *,
    asof: str,
    existing: VietnamLiquidityFacts,
    sstock: VietnamLiquidityFacts,
    chosen: VietnamLiquidityFacts,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"asof": asof, "items": []}

    for field in VIETNAM_LIQUIDITY_FIELDS:
        ev = existing.values.get(field)
        sv = sstock.values.get(field)
        cv = chosen.values.get(field)
        # chosen source comes from chosen meta if available
        chosen_src = chosen.meta.get(field).chosen_source if field in chosen.meta else None

        if ev is None and sv is None:
            status = "missing"
        elif ev is None and sv is not None:
            status = "missing_existing"
        elif ev is not None and sv is None:
            status = "missing_sstock"
        elif cv is None:
            status = "mismatch"
        elif ev == sv:
            status = "match"
        elif _near_match(field, ev, sv) and (cv == ev or cv == sv):
            status = "near_match"
        else:
            status = "mismatch"

        out["items"].append(
            {
                "field": field,
                "existing_value": ev,
                "sstock_value": sv,
                "chosen_value": cv,
                "chosen_source": chosen_src,
                "existing_as_of": asof,
                "sstock_as_of": asof,
                "status": status,
                "delta_abs": None
                if (ev is None or sv is None)
                else abs(float(ev) - float(sv)),
            }
        )

    return out


def get_vietnam_liquidity_with_provider(
    *,
    asof: str,
    provider_mode: str,
    enable_sstock: bool,
) -> Tuple[VietnamLiquidityFacts, Dict[str, Any]]:
    """
    Returns:
      - chosen: VietnamLiquidityFacts (merged facts + per-field provenance)
      - compare: comparison dict (empty unless enable_sstock)
    provider_mode:
      - existing: chosen==sbv (even if None)
      - sstock: chosen==sstock (even if None)
      - auto: chosen == sbv if present else sstock
      - shadow: chosen == sbv if present else sstock (but caller should write artifacts)
    """
    existing = fetch_vietnam_liquidity_sbv(asof=asof)

    if not enable_sstock:
        chosen = merge_vietnam_liquidity(
            existing=existing.values,
            sstock={},
            provider_mode=provider_mode,
            existing_source_name="sbv",
            sstock_source_name="sstock",
            existing_meta={f: existing.meta.get(f) for f in VIETNAM_LIQUIDITY_FIELDS if f in existing.meta},
            sstock_meta={},
        )
        return chosen, {}

    sstock = fetch_vietnam_liquidity_sstock(asof=asof)

    chosen = merge_vietnam_liquidity(
        existing=existing.values,
        sstock=sstock.values,
        provider_mode=provider_mode,
        existing_source_name="sbv",
        sstock_source_name="sstock",
        existing_meta={f: existing.meta.get(f) for f in VIETNAM_LIQUIDITY_FIELDS if f in existing.meta},
        sstock_meta={f: sstock.meta.get(f) for f in VIETNAM_LIQUIDITY_FIELDS if f in sstock.meta},
    )

    compare = compare_vietnam_liquidity(
        asof=asof,
        existing=existing,
        sstock=sstock,
        chosen=chosen,
    )
    return chosen, compare


__all__ = ["get_vietnam_liquidity_with_provider", "compare_vietnam_liquidity"]

