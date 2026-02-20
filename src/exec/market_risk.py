from __future__ import annotations
from typing import Optional, Dict, Any

def market_risk_flags(market: Dict[str, Any]) -> Dict[str, Any]:
    dd = market.get("distribution_days_rolling_20")
    flag = None
    if dd is None:
        flag = "Unknown"
    elif dd >= 6:
        flag = "High"
    elif dd >= 4:
        flag = "Elevated"
    else:
        flag = "Normal"
    return {"distribution_days_rolling_20": dd, "risk_flag": flag}
