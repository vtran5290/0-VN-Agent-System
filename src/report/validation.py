from __future__ import annotations
from typing import Dict, Any, List

CORE_FIELDS = [
    ("global", "ust_2y"),
    ("global", "ust_10y"),
    ("global", "dxy"),
    ("vietnam", "omo_net"),
    ("vietnam", "interbank_on"),
    ("vietnam", "credit_growth_yoy"),
    ("market", "vnindex_level"),
    ("market", "distribution_days_rolling_20"),
]

def validate_core(inputs: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[str] = []
    for sec, key in CORE_FIELDS:
        val = inputs.get(sec, {}).get(key)
        if val is None:
            missing.append(f"{sec}.{key}")

    if len(missing) == 0:
        confidence = "High"
    elif len(missing) <= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {"confidence": confidence, "missing": missing}
