from __future__ import annotations
from typing import Optional, Dict, Any

def risk_flag_from_dist(dist20: int | None) -> str:
    if dist20 is None:
        return "Unknown"
    if dist20 >= 6:
        return "High"
    if dist20 >= 4:
        return "Elevated"
    return "Normal"

def market_risk_flags(market: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer composite risk (multi-proxy); fallback to single dist20
    composite = market.get("dist_risk_composite")
    dd = market.get("distribution_days_rolling_20")
    if composite in ("High", "Elevated", "Normal", "Unknown"):
        flag = composite
    else:
        flag = risk_flag_from_dist(dd)
    force_reduce_gross = flag == "High"
    return {
        "distribution_days_rolling_20": dd,
        "distribution_days": market.get("distribution_days"),
        "dist_risk_composite": composite,
        "dist_proxy_symbol": market.get("dist_proxy_symbol"),
        "risk_flag": flag,
        "force_reduce_gross": force_reduce_gross,
    }
