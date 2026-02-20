from __future__ import annotations
from typing import List, Dict, Any, Optional

def watchlist_updates(tickers: List[str], regime: Optional[str], market_flags: Dict[str, Any]) -> Dict[str, Any]:
    rf = market_flags.get("risk_flag", "Unknown")
    posture = "Neutral"
    if regime == "B":
        posture = "Selective / Leader-only"
    if rf in ("Elevated", "High"):
        posture = "Defensive / Reduce new buys"

    return {
        "posture": posture,
        "tickers": tickers,
        "notes": "MVP: no per-ticker scoring yet. Add technical/fundamental signals later."
    }
