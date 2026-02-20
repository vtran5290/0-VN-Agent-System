from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Dict

RegimeLabel = Literal["A", "B", "C", "D"]

@dataclass(frozen=True)
class LiquiditySignals:
    global_liquidity: Literal["easing", "tight", "unknown"]
    vn_liquidity: Literal["easing", "tight", "unknown"]

def detect_regime(signals: LiquiditySignals) -> Optional[RegimeLabel]:
    """
    Returns A/B/C/D if both sides known, else None.
    """
    if signals.global_liquidity == "unknown" or signals.vn_liquidity == "unknown":
        return None

    mapping: Dict[tuple[str, str], RegimeLabel] = {
        ("easing", "easing"): "A",
        ("tight", "easing"): "B",
        ("tight", "tight"): "C",
        ("easing", "tight"): "D",
    }
    return mapping.get((signals.global_liquidity, signals.vn_liquidity))

def explain_regime(regime: Optional[RegimeLabel]) -> str:
    if regime is None:
        return "Regime: Unknown (insufficient inputs for global/vn liquidity)."
    return f"Regime: STATE {regime}"
