from __future__ import annotations
from typing import Dict, Any, List, Optional

def compute_total(item: Dict[str, Any], weights: Dict[str, float]) -> Optional[float]:
    f, t, r = item.get("fundamental"), item.get("technical"), item.get("regime_fit")
    if f is None or t is None or r is None:
        return None
    return round(f*weights["fundamental"] + t*weights["technical"] + r*weights["regime_fit"], 2)

def rank_watchlist(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    weights = payload.get("weights", {"fundamental":0.3,"technical":0.5,"regime_fit":0.2})
    scores = payload.get("scores", [])
    out = []
    for s in scores:
        s2 = dict(s)
        s2["total"] = compute_total(s2, weights)
        out.append(s2)
    out.sort(key=lambda x: (x["total"] is not None, x["total"]), reverse=True)
    return out
