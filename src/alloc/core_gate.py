from __future__ import annotations
from typing import Optional, Dict, Any

def core_allowed(regime: Optional[str], market_flags: Dict[str, Any]) -> bool:
    if regime is None:
        return False
    if regime in ("A", "B") and market_flags.get("risk_flag") != "High":
        return True
    return False
