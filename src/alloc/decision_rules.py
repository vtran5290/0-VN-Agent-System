from __future__ import annotations
from typing import Dict, Any, List, Optional

def top_actions(regime: Optional[str], market_flags: Dict[str, Any], alloc: Dict[str, Any]) -> List[str]:
    risk_flag = market_flags.get("risk_flag", "Unknown")

    if regime is None:
        actions = [
            "Fill core inputs (8 numbers) to remove regime uncertainty before increasing exposure.",
            "Keep gross exposure conservative; prioritize capital preservation.",
            "Set alerts for distribution-day cluster and key MA violations."
        ]
        if risk_flag == "High":
            actions[0] = "Reduce gross by 1 notch (distribution days High — force reduce)."
        if risk_flag in ("Elevated", "High"):
            actions[1] = "No new buys unless confirmed pocket pivot / reclaim."
        return actions

    if regime == "B":
        actions = [
            f"Maintain mid exposure per band (gross={alloc.get('gross_exposure')}, cash={alloc.get('cash_weight')}).",
            "Favor leaders with earnings clarity; avoid adding to laggards/high-beta breakouts without confirmation.",
            "Scale exposure only if breakout attempts succeed AND distribution-day risk is not rising."
        ]
        if risk_flag == "High":
            actions[0] = "Reduce gross by 1 notch (distribution days High — force reduce)."
        if risk_flag in ("Elevated", "High"):
            actions[1] = "No new buys unless confirmed pocket pivot / reclaim; trim weak names."
        return actions

    if regime == "A":
        actions = [
            f"Increase exposure selectively (gross={alloc.get('gross_exposure')}); add on constructive pullbacks to leaders.",
            "Rotate toward liquidity-sensitive sectors when breadth improves.",
            "Keep stops disciplined; avoid chasing extended moves."
        ]
        if risk_flag == "High":
            actions[0] = "Reduce gross by 1 notch (distribution days High — force reduce)."
        if risk_flag in ("Elevated", "High"):
            actions[1] = "No new buys unless confirmed pocket pivot / reclaim."
        return actions

    if regime == "C":
        actions = [
            f"Reduce risk aggressively (gross={alloc.get('gross_exposure')}, cash={alloc.get('cash_weight')}).",
            "Hold only highest-quality leaders; cut laggards quickly.",
            "De-risk if distribution days cluster or key supports break."
        ]
        if risk_flag == "High":
            actions[0] = "Reduce gross by 1 notch (distribution days High — force reduce)."
        if risk_flag in ("Elevated", "High"):
            actions[1] = "No new buys unless confirmed pocket pivot / reclaim."
        return actions

    # D
    actions = [
        f"Stay cautious (gross={alloc.get('gross_exposure')}, cash={alloc.get('cash_weight')}).",
        "Prefer defensives/earnings certainty; avoid crowded high-beta.",
        "Watch FX and policy tightening signals for further de-risking."
    ]
    if risk_flag == "High":
        actions[0] = "Reduce gross by 1 notch (distribution days High — force reduce)."
    if risk_flag in ("Elevated", "High"):
        actions[1] = "No new buys unless confirmed pocket pivot / reclaim."
    return actions

def top_risks(regime: Optional[str], market_flags: Dict[str, Any]) -> List[str]:
    rf = market_flags.get("risk_flag", "Unknown")
    base = [
        "Data gaps → narrative bias (probabilities become unreliable).",
        "Sudden liquidity shock (global or VN) causing gap-down risk.",
        "Earnings revisions risk in high-beta names."
    ]
    if rf in ("Elevated", "High"):
        base[1] = f"Market fragility elevated (distribution days risk={rf}) → higher failure rate of breakouts."
    if regime == "B":
        base.insert(0, "Regime B mismatch: global tight can override VN easing quickly (external shock sensitivity).")
    return base[:3]
