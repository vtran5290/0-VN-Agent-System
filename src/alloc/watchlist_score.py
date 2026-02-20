from __future__ import annotations
from typing import Dict, Any, List

def score_watchlist(tickers: List[str], regime: str | None) -> List[Dict[str, Any]]:
    """
    MVP: placeholder scoring.
    Later: replace with fundamentals + technical signals.
    """
    out = []
    for t in tickers:
        out.append({
            "ticker": t,
            "fundamental_score": None,
            "technical_score": None,
            "regime_fit": regime,
            "total_score": None
        })
    return out
