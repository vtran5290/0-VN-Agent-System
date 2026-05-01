from __future__ import annotations

from typing import Any, Dict

from ..models import VIETNAM_LIQUIDITY_FIELDS, VietnamFieldProvenance, VietnamLiquidityFacts


def fetch_vietnam_liquidity_sbv(asof: str | None = None) -> VietnamLiquidityFacts:
    # Reuse existing production SBV scraper (+ optional TBNN OMO fallback inside fetch).
    from scripts.fetch_vietnam_liquidity import fetch_vietnam_liquidity as _fetch

    data = _fetch(asof)
    v = (data or {}).get("vietnam") or {}
    omo_prov = (data or {}).get("_omo_provenance") or {}

    values: Dict[str, Any] = {f: v.get(f) for f in VIETNAM_LIQUIDITY_FIELDS}
    meta: Dict[str, VietnamFieldProvenance] = {}
    for f in VIETNAM_LIQUIDITY_FIELDS:
        vs = "parsed" if values[f] is not None else "request_failed_or_missing"
        article_date = None
        value_date = None
        source_detail = None
        chosen = "sbv"
        if f == "omo_net":
            if omo_prov:
                vs = str(omo_prov.get("verification_status") or vs)
                article_date = omo_prov.get("article_date")
                value_date = omo_prov.get("value_date")
                source_detail = omo_prov.get("source_detail")
                if omo_prov.get("chosen_source"):
                    chosen = str(omo_prov.get("chosen_source"))
        if f == "fx_usd_vnd" and values[f] is not None:
            source_detail = (source_detail or "SBV tỷ giá — reference/central USD/VND (not interbank spot)").strip()
        meta[f] = VietnamFieldProvenance(
            field=f,
            chosen_source=chosen,
            existing_source="sbv",
            sstock_source=None,
            series_name=None,
            as_of=asof,
            fetched_at=None,
            verification_status=vs,
            confidence=None,
            article_date=article_date,
            value_date=value_date,
            source_detail=source_detail,
        )

    return VietnamLiquidityFacts(values=values, meta=meta, errors=[])


__all__ = ["fetch_vietnam_liquidity_sbv"]

