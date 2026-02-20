from __future__ import annotations
from typing import Dict, Any

def apply_risk_overrides(alloc: Dict[str, Any], market_flags: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(alloc, dict):
        return alloc
    rf = market_flags.get("risk_flag")
    out = dict(alloc)
    if rf == "High" and out.get("gross_exposure") is not None:
        g = float(out["gross_exposure"])
        new_g = max(0.0, round(g - 0.10, 2))
        out["gross_exposure_override"] = new_g
        out["cash_weight_override"] = round(1.0 - new_g, 2)
        out["override_reason"] = "Market risk High (distribution days) → de-risk one notch"
    return out
