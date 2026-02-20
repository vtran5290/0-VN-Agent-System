from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal
import yaml

RegimeLabel = Literal["A", "B", "C", "D"]

@dataclass(frozen=True)
class Probabilities:
    fed_cut_3m: Optional[float]        # 0..1
    vn_tightening_1m: Optional[float]  # 0..1
    vnindex_breakout_1m: Optional[float]  # 0..1

def load_thresholds(path: str = "config/thresholds.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def default_probabilities(regime: Optional[RegimeLabel]) -> Probabilities:
    """
    MVP rule-based probabilities if no market data.
    You will replace with real models later.
    """
    if regime is None:
        return Probabilities(None, None, None)

    # Very rough priors (MVP)
    if regime == "A":
        return Probabilities(0.55, 0.15, 0.65)
    if regime == "B":
        return Probabilities(0.40, 0.20, 0.55)
    if regime == "C":
        return Probabilities(0.25, 0.45, 0.35)
    # D
    return Probabilities(0.50, 0.35, 0.45)

def probabilities_from_features(regime: Optional[RegimeLabel], features: Dict[str, Any]) -> Probabilities:
    if regime is None:
        return Probabilities(None, None, None)

    g = features.get("global", {})
    m = features.get("market", {})
    v = features.get("vietnam", {})

    ust2 = g.get("ust_2y_chg_wow")
    dxy = g.get("dxy_chg_wow")
    dist = m.get("dist_days_chg_wow")
    on = v.get("interbank_on_chg_wow")

    # MVP heuristics
    # - If UST2 rising and DXY rising → lower breakout odds, higher tightening risk.
    breakout = 0.55 if regime == "B" else 0.5
    tighten = 0.20 if regime == "B" else 0.25
    fedcut = 0.40 if regime == "B" else 0.35

    if ust2 is not None and ust2 > 0:
        fedcut -= 0.05
        breakout -= 0.05
    if dxy is not None and dxy > 0:
        breakout -= 0.05
    if on is not None and on > 0:
        tighten += 0.05
    if dist is not None and dist > 0:
        breakout -= 0.05

    # clamp 0..1
    def clamp(x):
        return max(0.0, min(1.0, x))

    return Probabilities(clamp(fedcut), clamp(tighten), clamp(breakout))

def allocation_from_regime(regime: Optional[RegimeLabel], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    if regime is None:
        return {
            "gross_exposure": None,
            "cash_weight": None,
            "note": "Allocation unknown due to unknown regime."
        }
    bands = thresholds["allocation"]["exposure_bands"][regime]
    return {
        "gross_exposure": float(bands["gross"]),
        "cash_weight": float(bands["cash"]),
        "constraints": thresholds["risk_rules"]
    }
