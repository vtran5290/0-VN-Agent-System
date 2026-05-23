from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import (
    FRAGILE_REGIME_LABEL,
    TIER1_MAX_RISK,
    TIER1_MIN_MONEY_FLOW,
    TIER1_MIN_SCORE,
    TIER2_MIN_SCORE,
    TIER2_MIN_SCORE_FRAGILE,
    TIER2_PCTL_FLOOR,
    TIER2_PCTL_MAX_RISK,
    TIER2_PCTL_MIN_MONEY,
    TIER2_PCTL_MIN_SCORE,
    TIER3_CONSENSUS_MIN_MONEY,
    TIER3_CONSENSUS_MIN_SCORE,
    TIER3_MIN_SCORE,
    TIER3_MIN_SCORE_FRAGILE,
    TIER3_PCTL_FLOOR,
    TIER3_PCTL_MAX_RISK,
    TIER3_PCTL_MIN_SCORE,
    WEIGHT_CONTEXT,
    WEIGHT_MONEY_FLOW,
    WEIGHT_PRICE_STRUCTURE,
    WEIGHT_RISK_PENALTY,
)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _scale(val: Optional[float], lo: float, hi: float, invert: bool = False) -> float:
    if val is None or not np.isfinite(val):
        return 0.5
    if hi == lo:
        t = 0.5
    else:
        t = _clip01((float(val) - lo) / (hi - lo))
    return 1.0 - t if invert else t


def _group_score(parts: List[float]) -> float:
    return 100.0 * float(np.mean(parts)) if parts else 50.0


def _score_cmf_group(m: Dict[str, Any], reasons: List[str]) -> float:
    cmf_d = m.get("cmf20_daily")
    cmf_w = m.get("cmf20_weekly")
    parts = [
        _scale(cmf_d, -0.15, 0.25),
        _scale(cmf_w, -0.15, 0.25),
        _scale(m.get("cmf20_daily_slope_10"), -0.02, 0.02),
        _scale(m.get("cmf20_weekly_slope_8"), -0.02, 0.02),
    ]
    if cmf_d is not None and cmf_d > 0.05:
        reasons.append("CMF daily positive")
    if cmf_w is not None and cmf_w > 0.05:
        reasons.append("CMF weekly positive")
    if m.get("cmf_flow_conflict"):
        parts.append(0.3)
        reasons.append("CMF daily/weekly conflict")
    return _group_score(parts)


def _score_obv_pvt_group(m: Dict[str, Any], reasons: List[str]) -> float:
    parts = [
        _scale(m.get("obv_slope_20"), -0.01, 0.03),
        _scale(m.get("obv_slope_50"), -0.005, 0.02),
        _scale(m.get("obv_vs_ma20"), -0.1, 0.15),
        _scale(m.get("pvt_slope_20"), -0.01, 0.03),
        _scale(m.get("pvt_slope_50"), -0.005, 0.02),
    ]
    if m.get("obv_vs_ma20") is not None and m["obv_vs_ma20"] > 0:
        reasons.append("OBV above MA20")
    return _group_score(parts)


def _score_adl_group(m: Dict[str, Any], reasons: List[str]) -> float:
    parts = [_scale(m.get("adl_slope_20"), -0.01, 0.03)]
    if m.get("adl_price_divergence_bearish"):
        parts.append(0.2)
        reasons.append("ADL bearish divergence vs price")
    else:
        parts.append(0.78)
    return _group_score(parts)


def _score_participation_group(m: Dict[str, Any], reasons: List[str]) -> float:
    ud = m.get("up_down_volume_ratio_20")
    parts = [_scale(ud, 0.8, 1.8)]
    if ud is not None and ud >= 1.1:
        reasons.append("Up-volume dominates (20d)")
    up_hv = m.get("hv_up_days_20") or 0
    dn_hv = m.get("hv_down_days_20") or 0
    hv_ratio = up_hv / max(dn_hv, 1)
    parts.append(_scale(hv_ratio, 0.5, 2.5))
    if up_hv > dn_hv:
        reasons.append("More HV up-days than down-days")
    tac = m.get("turnover_accel_ratio_5d50d")
    parts.append(_scale(tac, -0.15, 0.35))
    if tac is not None and tac > 0.1:
        reasons.append("Turnover acceleration vs 50d baseline")
    return _group_score(parts)


def score_money_flow(m: Dict[str, Any]) -> Tuple[float, List[str], Dict[str, float]]:
    """Grouped sub-factors (de-correlated blocks), then equal-weight across groups."""
    reasons: List[str] = []
    groups = {
        "cmf": _score_cmf_group(m, reasons),
        "obv_pvt": _score_obv_pvt_group(m, reasons),
        "adl": _score_adl_group(m, reasons),
        "participation": _score_participation_group(m, reasons),
    }
    score = float(np.mean(list(groups.values())))
    return score, reasons, groups


def score_price_structure(p: Dict[str, Any]) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    parts: List[float] = []

    parts.append(_scale(p.get("rs_vs_vnindex_20"), -0.05, 0.12))
    parts.append(_scale(p.get("rs_vs_vnindex_60"), -0.08, 0.20))
    parts.append(_scale(p.get("rs_line_slope_20"), -0.03, 0.08))
    if p.get("rs_vs_vnindex_20") is not None and p["rs_vs_vnindex_20"] > 0:
        reasons.append("RS vs VNINDEX 20d positive")

    if p.get("holds_ma50"):
        parts.append(0.85)
        reasons.append("Holds MA50")
    elif p.get("holds_ma20"):
        parts.append(0.7)
        reasons.append("Holds MA20")
    else:
        parts.append(0.35)

    if p.get("volatility_contraction_flag"):
        parts.append(0.9)
        reasons.append("Volatility contraction + supportive CMF")
    else:
        parts.append(0.55)

    if p.get("pullback_quality_flag"):
        parts.append(0.9)
        reasons.append("Shallow pullback on declining volume")
    else:
        parts.append(0.5)

    parts.append(_scale(p.get("close_strength_10d"), 0.45, 0.75))
    score = 100.0 * float(np.mean(parts))
    return score, reasons


def score_risk_penalty(
    money: Dict[str, Any],
    price: Dict[str, Any],
    *,
    vingroup_distortion: bool,
    illiquid: bool,
    one_bar_spike: bool,
) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    pen = 0.0

    ext = price.get("extension_pct_above_ma20")
    if ext is not None:
        if ext > 25:
            pen += 35
            reasons.append(f"Extended {ext:.1f}% above MA20/50")
        elif ext > 15:
            pen += 20
            reasons.append(f"Moderately extended {ext:.1f}%")

    dist = price.get("distribution_days_25")
    if dist is not None:
        if dist >= 6:
            pen += 30
            reasons.append(f"High distribution-day count ({dist}/25)")
        elif dist >= 4:
            pen += 15
            reasons.append(f"Elevated distribution days ({dist}/25)")

    dist_w = money.get("distribution_weeks_6")
    if dist_w is not None:
        if dist_w >= 4:
            pen += 22
            reasons.append(f"High weekly distribution weeks ({dist_w}/6)")
        elif dist_w >= 3:
            pen += 12
            reasons.append(f"Elevated weekly distribution weeks ({dist_w}/6)")

    if vingroup_distortion:
        pen += 22
        reasons.append("Vingroup distortion: RS extension without multi-horizon flow confirmation")

    if illiquid:
        pen += 40
        reasons.append("Fails liquidity gate")

    if money.get("cmf_flow_conflict"):
        pen += 12
        reasons.append("Inconsistent CMF daily vs weekly")

    if money.get("adl_price_divergence_bearish"):
        pen += 15
        reasons.append("ADL diverging bearishly from price")

    if one_bar_spike:
        pen += 18
        reasons.append("One-bar speculative spike risk")

    if illiquid is False and price.get("distribution_risk_flag"):
        pen += 10

    return float(min(100.0, pen)), reasons


def detect_one_bar_spike(money: Dict[str, Any], price: Dict[str, Any]) -> bool:
    rs = price.get("rs_vs_vnindex_20")
    cmf_sl = money.get("cmf20_daily_slope_10")
    if rs is None or cmf_sl is None:
        return False
    return bool(rs > 0.12 and cmf_sl < -0.005)


def composite_score(
    context_pts: float,
    money_pts: float,
    price_pts: float,
    risk_pen: float,
) -> float:
    raw = (
        WEIGHT_CONTEXT * context_pts
        + WEIGHT_MONEY_FLOW * money_pts
        + WEIGHT_PRICE_STRUCTURE * price_pts
        - WEIGHT_RISK_PENALTY * risk_pen
    )
    return float(max(0.0, min(100.0, raw)))


def _is_fragile_regime(regime_label: Optional[str]) -> bool:
    r = (regime_label or "").lower()
    return FRAGILE_REGIME_LABEL in r or ("fragile" in r and "narrow" in r)


def assign_tier(
    total: float,
    money_pts: float,
    risk_pen: float,
    *,
    liquidity_ok: bool,
    regime_label: Optional[str] = None,
    score_percentile: Optional[float] = None,
    in_consensus_core: bool = False,
) -> str:
    if not liquidity_ok:
        return "Reject"

    if (
        total >= TIER1_MIN_SCORE
        and money_pts >= TIER1_MIN_MONEY_FLOW
        and risk_pen <= TIER1_MAX_RISK
    ):
        return "Tier 1"

    fragile = _is_fragile_regime(regime_label)
    t2_floor = TIER2_MIN_SCORE_FRAGILE if fragile else TIER2_MIN_SCORE
    t3_floor = TIER3_MIN_SCORE_FRAGILE if fragile else TIER3_MIN_SCORE

    if total >= t2_floor and money_pts >= 40 and risk_pen <= 50:
        return "Tier 2"

    if fragile and score_percentile is not None:
        if (
            score_percentile >= TIER2_PCTL_FLOOR
            and total >= TIER2_PCTL_MIN_SCORE
            and money_pts >= TIER2_PCTL_MIN_MONEY
            and risk_pen <= TIER2_PCTL_MAX_RISK
        ):
            return "Tier 2"

    if total >= t3_floor:
        return "Tier 3"

    if fragile and score_percentile is not None:
        if (
            score_percentile >= TIER3_PCTL_FLOOR
            and total >= TIER3_PCTL_MIN_SCORE
            and risk_pen <= TIER3_PCTL_MAX_RISK
        ):
            return "Tier 3"

    if (
        fragile
        and in_consensus_core
        and total >= TIER3_CONSENSUS_MIN_SCORE
        and money_pts >= TIER3_CONSENSUS_MIN_MONEY
        and risk_pen <= 48
    ):
        return "Tier 3"

    return "Reject"


def build_notes(
    tier: str,
    context_reasons: List[str],
    money_reasons: List[str],
    price_reasons: List[str],
    risk_reasons: List[str],
) -> str:
    parts = [f"tier={tier}"]
    for group in (money_reasons[:3], price_reasons[:2], context_reasons[:1], risk_reasons[:2]):
        parts.extend(group)
    return "; ".join(parts)[:500]
