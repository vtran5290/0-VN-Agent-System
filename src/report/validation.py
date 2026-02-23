from __future__ import annotations
from typing import Dict, Any, List

CORE_FIELDS = [
    ("global", "ust_2y"),
    ("global", "ust_10y"),
    ("global", "dxy"),
    ("vietnam", "omo_net"),
    ("vietnam", "interbank_on"),
    ("vietnam", "credit_growth_yoy"),
    ("market", "distribution_days_rolling_20"),
]

def validate_core(inputs: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[str] = []
    for sec, key in CORE_FIELDS:
        val = inputs.get(sec, {}).get(key)
        if val is None:
            missing.append(f"{sec}.{key}")

    # market level = vnindex OR vn30 (proxy)
    mkt = inputs.get("market", {})
    vn = mkt.get("vnindex_level")
    vn30 = mkt.get("vn30_level") or mkt.get("vnindex_proxy_level")
    if vn is None and vn30 is None:
        missing.append("market.market_level(vnindex_or_vn30)")

    # 0 missing → High; 1–4 → Medium; ≥5 → Low (VN liquidity weekly manual is acceptable)
    if len(missing) == 0:
        confidence = "High"
    elif len(missing) <= 4:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {"confidence": confidence, "missing": missing}
