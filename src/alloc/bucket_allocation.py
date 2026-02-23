from __future__ import annotations
from typing import Dict, Any

def split_buckets(total_alloc: Dict[str, Any], core_ok: bool) -> Dict[str, Any]:
    gross = total_alloc.get("gross_exposure_override") or total_alloc.get("gross_exposure")
    if gross is None:
        return {"core": None, "swing": None, "cash": None}

    if not core_ok:
        return {
            "core": 0.0,
            "swing": round(gross, 2),
            "cash": round(1.0 - gross, 2),
            "note": "Core disabled due to regime/risk"
        }

    # Default split when core allowed
    core = round(gross * 0.6, 2)
    swing = round(gross * 0.4, 2)

    return {
        "core": core,
        "swing": swing,
        "cash": round(1.0 - gross, 2),
        "note": "Core enabled"
    }
