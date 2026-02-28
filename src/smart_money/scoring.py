from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _clamp_int(x: float, lo: int = 0, hi: int = 10) -> int:
    return int(max(lo, min(hi, round(x))))


def compute_crowding_score(
    ticker_consensus: List[Dict[str, Any]],
    sector_consensus: List[Dict[str, Any]],
    n_funds: int,
) -> Tuple[int, List[Dict[str, str]]]:
    """
    Compute single-name + sector crowding score (0–10) and flags.

    Heuristics (MVP, transparent and easy to tune):
    - Single-name crowding based on n_top10 / n_funds.
    - Sector crowding based on avg_weight across funds.
    """
    flags: List[Dict[str, str]] = []
    if n_funds <= 0:
        return 0, flags

    # Single-name crowding
    single_term = 0
    for row in ticker_consensus:
        n_top10 = row.get("n_top10")
        ticker = row.get("ticker")
        if not isinstance(n_top10, int) or not ticker:
            continue
        frac = n_top10 / n_funds if n_funds else 0.0
        if frac >= 0.70:
            single_term = max(single_term, 4)
            flags.append(
                {
                    "type": "SingleNameCrowding",
                    "detail": f"{ticker} in >=70% of funds' top10",
                }
            )
        elif frac >= 0.50:
            single_term = max(single_term, 3)
        elif frac >= 0.30:
            single_term = max(single_term, 2)

    # Sector crowding
    sector_term = 0
    for row in sector_consensus:
        sector = row.get("sector")
        avg_weight = row.get("avg_weight")
        if sector is None or avg_weight is None:
            continue
        try:
            w = float(avg_weight)
        except (TypeError, ValueError):
            continue
        if w >= 35.0:
            sector_term = max(sector_term, 4)
            flags.append(
                {
                    "type": "SectorCrowding",
                    "detail": f"{sector} avg_weight >=35%",
                }
            )
        elif w >= 30.0:
            sector_term = max(sector_term, 3)
            flags.append(
                {
                    "type": "SectorCrowding",
                    "detail": f"{sector} avg_weight >=30%",
                }
            )
        elif w >= 25.0:
            sector_term = max(sector_term, 2)

    raw_score = single_term + sector_term
    score = _clamp_int(raw_score, 0, 10)
    return score, flags


def compute_risk_on_score(median_cash: Optional[float]) -> Tuple[int, List[Dict[str, str]]]:
    """
    Compute risk-on score (0–10) based on median cash_weight.
    Lower cash => higher risk-on. Returns score and risk-related flags.
    """
    flags: List[Dict[str, str]] = []
    if median_cash is None:
        return 0, flags
    try:
        c = float(median_cash)
    except (TypeError, ValueError):
        return 0, flags

    if c <= 2.0:
        score = 5
        flags.append({"type": "MaxRiskOn", "detail": "Median cash_weight <=2%"})
    elif c <= 5.0:
        score = 4
    elif c <= 10.0:
        score = 3
    elif c <= 20.0:
        score = 1
    else:
        score = 0
    return score, flags


def compute_policy_alignment_score(
    themes: List[Dict[str, Any]],
    n_funds: int,
) -> Tuple[int, Dict[str, int]]:
    """
    Compute policy_alignment_score (0–10) and per-tag strengths.

    For each tag of interest:
    - tag_score = 10 * (n_funds_with_positive_tag / n_funds_total), clamped 0–10.
    - policy_alignment_score = average of non-zero tag_scores (or 0 if none).
    """
    if n_funds <= 0:
        return 0, {}

    tags_of_interest = {
        "Resolution79",
        "FTSEUpgrade",
        "SBVLiquidity",
        "CreditGrowth",
    }

    counts: Dict[str, int] = {t: 0 for t in tags_of_interest}
    for t in themes:
        tag = t.get("theme_tag")
        pol = t.get("polarity")
        if tag not in tags_of_interest:
            continue
        if pol == "Positive":
            counts[tag] += 1

    tag_scores: Dict[str, int] = {}
    nonzero_scores: List[int] = []
    for tag, cnt in counts.items():
        if cnt <= 0:
            tag_scores[tag] = 0
            continue
        raw = 10.0 * (cnt / n_funds)
        sc = _clamp_int(raw, 0, 10)
        tag_scores[tag] = sc
        if sc > 0:
            nonzero_scores.append(sc)

    if not nonzero_scores:
        return 0, tag_scores
    avg = sum(nonzero_scores) / len(nonzero_scores)
    total_score = _clamp_int(avg, 0, 10)
    return total_score, tag_scores


def compute_regime_bias(crowding_score: int, risk_on_score: int) -> str:
    """
    Map (crowding_score, risk_on_score) → Smart Money regime_bias label.
    """
    if risk_on_score >= 7 and crowding_score <= 6:
        return "Bullish"
    if risk_on_score >= 7 and crowding_score >= 7:
        return "Extended"
    if risk_on_score <= 3 and crowding_score >= 7:
        return "Fragile"

    # Fallback heuristic: if crowding high but risk-on mid, lean Extended; otherwise Bullish.
    if crowding_score >= 7:
        return "Extended"
    if risk_on_score <= 3:
        return "Fragile"
    return "Bullish"

