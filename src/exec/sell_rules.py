from __future__ import annotations
from typing import Dict, Any, List

def evaluate_row(r: Dict[str, Any]) -> Dict[str, Any]:
    tier = r.get("tier")
    day2 = r.get("day2_trigger", False)
    day1 = r.get("day1_trigger", False)
    below = r.get("close_below_ma", False)

    action = "HOLD"
    reason = "No violation"

    if day2:
        action = "SELL / EXIT"
        reason = "Day-2 confirmation breach"
    elif day1 or (below and tier in (1, 2, 3)):
        action = "TRIM / TIGHTEN STOP"
        reason = "Day-1 close below key MA"

    return {**r, "action": action, "reason": reason}

def evaluate(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("tickers", [])
    return [evaluate_row(r) for r in rows]
