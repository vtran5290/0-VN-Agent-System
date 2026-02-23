"""
Advisory-only regime suggestion from market/price signals.
Does NOT auto-apply; weekly report prints Suggested vs Current and Mismatch.
Inputs: dist composite, breadth (MA trend), optional global yield trend.
"""
from __future__ import annotations
from typing import Dict, Any, Optional

RegimeLabel = Optional[str]  # "A" | "B" | "C" | "D"


def suggest_regime_from_market(
    market: Dict[str, Any],
    global_data: Optional[Dict[str, Any]] = None,
) -> RegimeLabel:
    """
    Suggest regime from dist composite, breadth, and optional global yield trend.
    Advisory only; not used to override detect_regime().
    """
    composite = (market.get("dist_risk_composite") or "").strip()
    vn30_ok = market.get("vn30_trend_ok")
    hnx_ok = market.get("hnx_trend_ok")
    upcom_ok = market.get("upcom_trend_ok")

    # Breadth weak = both HNX and UPCOM below MA20 (when we have data)
    breadth_weak = False
    if hnx_ok is False and upcom_ok is False:
        breadth_weak = True
    elif (hnx_ok is False or upcom_ok is False) and (market.get("hnx_level") is not None or market.get("upcom_level") is not None):
        # One index weak and we have data → mixed breadth
        if hnx_ok is False and upcom_ok is False:
            breadth_weak = True

    # Global yield trend: optional; rising = tight bias
    global_tight_bias = False
    if global_data:
        # WoW change if available (from features); positive = yields up = tight
        chg = global_data.get("ust_2y_chg_wow") if isinstance(global_data.get("ust_2y_chg_wow"), (int, float)) else None
        if chg is not None and chg > 0:
            global_tight_bias = True

    # Map to suggested regime
    if composite == "High":
        if breadth_weak:
            return "C"
        return "C"  # High dist → suggest C regardless of breadth
    if composite == "Elevated":
        if breadth_weak:
            return "C"
        return "B"
    if composite == "Normal":
        if breadth_weak:
            return "B"
        if global_tight_bias:
            return "B"
        return "A"
    if composite == "Unknown":
        return None
    return None
