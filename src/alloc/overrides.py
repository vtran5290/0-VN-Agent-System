from __future__ import annotations
from typing import Dict, Any, Optional

def apply_risk_overrides(
    alloc: Dict[str, Any],
    market_flags: Dict[str, Any],
    regime: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(alloc, dict):
        return alloc
    rf = market_flags.get("risk_flag")
    out = dict(alloc)
    if rf == "High" and out.get("gross_exposure") is not None:
        g = float(out["gross_exposure"])
        # Hard switch: cap gross by regime when dist-days >= 6
        if regime == "B":
            cap = 0.40
        elif regime == "C":
            cap = 0.15
        else:
            cap = 0.35  # A/D or unknown
        new_g = min(g, cap)
        new_g = round(new_g, 2)
        out["gross_exposure_override"] = new_g
        out["cash_weight_override"] = round(1.0 - new_g, 2)
        out["override_reason"] = "DistDays>=6 → High risk → cap gross exposure"
        out["no_new_buys"] = True
    return out
