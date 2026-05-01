# src/theme/scorer.py — Lane weights, total score, flags, tiers
from __future__ import annotations

import pandas as pd

from .schema import (
    FLAG_HIGH_LEVERAGE,
    FLAG_WEAK_INTEREST_COVER,
    FLAG_WC_TRAP,
    LANE_GRID_EPC,
    TIER1,
    TIER2,
    TIER3,
    validate_lane,
)


def weighted_score(row: pd.Series, weights: dict[str, float]) -> float:
    """Total score = sum(weight[c] * row[c]) for c in Q,R,T,V,M."""
    total = 0.0
    for c in ("Q", "R", "T", "V", "M"):
        w = weights.get(c, 0.0)
        total += w * row.get(c, 50.0)
    return total


def compute_flags(row: pd.Series, lane: str, thresholds: dict) -> list[str]:
    """Hard guards: weak_interest_cover, high_leverage, wc_trap (GRID_EPC only)."""
    flags = []
    ic = row.get("interest_coverage")
    if pd.notna(ic):
        try:
            if float(ic) < float(thresholds.get("interest_coverage_weak", 2)):
                flags.append(FLAG_WEAK_INTEREST_COVER)
        except (TypeError, ValueError):
            pass
    nd = row.get("net_debt_to_ebitda")
    if pd.notna(nd):
        try:
            if float(nd) > float(thresholds.get("net_debt_to_ebitda_high", 4)):
                flags.append(FLAG_HIGH_LEVERAGE)
        except (TypeError, ValueError):
            pass
    if lane == LANE_GRID_EPC:
        wc = row.get("working_capital_days")
        if pd.notna(wc):
            try:
                if float(wc) > float(thresholds.get("working_capital_days_trap_grid_epc", 180)):
                    flags.append(FLAG_WC_TRAP)
            except (TypeError, ValueError):
                pass
    return flags


def assign_tier(total_score: float, flags: list[str], thresholds: dict) -> str:
    """Tier1: score>=75 and no red flags. Tier2: 60..74 or (>=60 with 1 flag). Tier3: else."""
    t1 = float(thresholds.get("tier1_min_score", 75))
    t2 = float(thresholds.get("tier2_min_score", 60))
    has_red = len(flags) > 0
    if total_score >= t1 and not has_red:
        return TIER1
    if total_score >= t2:
        return TIER2
    return TIER3


def score_and_flag(
    df: pd.DataFrame,
    cfg: dict,
    lane_per_symbol: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Add total_score, lane, flags, tier. If lane_per_symbol not provided, use first lane from config for all.
    """
    lanes = cfg.get("lanes", [])
    weights_by_lane = cfg.get("weights_by_lane", {})
    thresholds = cfg.get("thresholds", {})
    if not lanes:
        lanes = ["GRID_EPC"]
    default_lane = lanes[0]
    for ln in lanes:
        validate_lane(ln)

    out = df.copy()
    total_scores = []
    out_flags = []
    out_lanes = []
    out_tiers = []
    for i, row in out.iterrows():
        sym = row.get("symbol", i)
        lane = (lane_per_symbol or {}).get(str(sym).upper(), default_lane)
        if lane not in weights_by_lane:
            lane = default_lane
        w = weights_by_lane.get(lane, weights_by_lane.get(default_lane, {"Q": 0.2, "R": 0.2, "T": 0.2, "V": 0.2, "M": 0.2}))
        sc = weighted_score(row, w)
        flags = compute_flags(row, lane, thresholds)
        tier = assign_tier(sc, flags, thresholds)
        total_scores.append(sc)
        out_flags.append("|".join(flags) if flags else "")
        out_lanes.append(lane)
        out_tiers.append(tier)
    out["total_score"] = total_scores
    out["lane"] = out_lanes
    out["flags"] = out_flags
    out["tier"] = out_tiers
    return out
