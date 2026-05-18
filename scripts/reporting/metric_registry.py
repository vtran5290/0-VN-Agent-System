"""Metric registry — one primary home per core metric (anti-duplication SSOT)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# primary_section values control where raw numbers may appear in main report
CORE_METRICS = {
    "VNINDEX": {"category": "Market Internals", "primary_section": "market_pulse", "format": "index"},
    "VN30": {"category": "Market Internals", "primary_section": "market_pulse", "format": "index"},
    "DIST_DAYS_20": {"category": "Market Internals", "primary_section": "market_pulse", "format": "count"},
    "BREADTH": {"category": "Market Internals", "primary_section": "market_pulse", "format": "text"},
    "UST10Y": {"category": "Global", "primary_section": "global_drivers", "format": "rate"},
    "UST2Y": {"category": "Global", "primary_section": "global_drivers", "format": "rate"},
    "DXY": {"category": "Global", "primary_section": "global_drivers", "format": "level"},
    "INTERBANK_ON": {"category": "Vietnam Liquidity", "primary_section": "vn_liquidity", "format": "rate"},
    "USD_VND": {"category": "Vietnam Liquidity", "primary_section": "vn_liquidity", "format": "level"},
    "OMO_NET": {"category": "Vietnam Liquidity", "primary_section": "vn_liquidity", "format": "level"},
    "CREDIT_GROWTH": {"category": "Vietnam Liquidity", "primary_section": "vn_liquidity", "format": "pct"},
    "PCT_CLOUD_BULL_A3": {"category": "Market Internals", "primary_section": "market_internals", "format": "pct"},
    "GROSS_EXPOSURE": {"category": "Portfolio", "primary_section": "command_center", "format": "pct"},
}


def build_metric_registry(
    *,
    manual: Dict[str, Any],
    manual_prev: Dict[str, Any],
    levels: Dict[str, Any],
    scan_panel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    g = manual.get("global") or {}
    gp = manual_prev.get("global") or {}
    v = manual.get("vietnam") or {}
    vp = manual_prev.get("vietnam") or {}

    def entry(
        metric_id: str,
        display_name: str,
        current: Any,
        previous: Any = None,
        source: str = "manual_inputs",
        implication: str = "",
    ) -> Dict[str, Any]:
        meta = CORE_METRICS.get(metric_id, {})
        delta = None
        if current is not None and previous is not None:
            try:
                delta = float(current) - float(previous)
            except (TypeError, ValueError):
                delta = None
        return {
            "metric_id": metric_id,
            "display_name": display_name,
            "category": meta.get("category", "Other"),
            "primary_section": meta.get("primary_section", "appendix"),
            "importance_tier": "Core" if metric_id in CORE_METRICS else "Secondary",
            "display_format": meta.get("format", "text"),
            "current_value": current,
            "previous_value": previous,
            "delta": delta,
            "freshness_status": "Fresh" if current is not None else "Missing",
            "source": source,
            "decision_implication": implication,
        }

    metrics: List[Dict[str, Any]] = [
        entry("VNINDEX", "VNINDEX", levels.get("vnindex_level"), None, "fireant/manual", "Index trend context"),
        entry("VN30", "VN30", levels.get("vn30_level"), None, "fireant/manual", "Large-cap proxy"),
        entry("DIST_DAYS_20", "Dist days (20)", levels.get("distribution_days_rolling_20"), None, "alerts", "Distribution risk"),
        entry("UST10Y", "UST 10Y", g.get("ust_10y"), gp.get("ust_10y"), "FRED", "Global discount rate"),
        entry("UST2Y", "UST 2Y", g.get("ust_2y"), gp.get("ust_2y"), "FRED", "Front-end rates"),
        entry("DXY", "DXY", g.get("dxy"), gp.get("dxy"), "FRED/proxy", "USD pressure"),
        entry("INTERBANK_ON", "Interbank ON", v.get("interbank_on"), vp.get("interbank_on"), "SBV/manual", "VN funding cost"),
        entry("USD_VND", "USD/VND", v.get("sbv_reference_usd_vnd") or v.get("fx_usd_vnd"), vp.get("sbv_reference_usd_vnd"), "SBV", "FX pressure"),
        entry("OMO_NET", "OMO net", v.get("omo_net"), vp.get("omo_net"), "SBV", "Liquidity impulse (daily)"),
        entry("CREDIT_GROWTH", "Credit growth YoY", v.get("credit_growth_yoy"), vp.get("credit_growth_yoy"), "manual", "Credit impulse"),
    ]
    if scan_panel:
        metrics.append(
            entry(
                "PCT_CLOUD_BULL_A3",
                "% cloud bull (A3 universe)",
                scan_panel.get("pct_cloud_bull_a3"),
                None,
                "phase36 scan",
                "Cloud breadth — offensive threshold context",
            )
        )

    by_id = {m["metric_id"]: m for m in metrics}
    return {"metrics": metrics, "by_id": by_id, "core_ids": list(CORE_METRICS.keys())}


def metric_allowed_in_section(metric_id: str, section: str) -> bool:
    meta = CORE_METRICS.get(metric_id)
    if not meta:
        return True
    return meta.get("primary_section") == section
