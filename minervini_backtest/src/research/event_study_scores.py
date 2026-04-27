"""
Separate base_quality_score (0-100) and entry_quality_score (0-100).

Weights are fixed heuristics for research ranking — not optimized claims.
"""
from __future__ import annotations

import math
from typing import Any


def _clip01(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return float(max(0.0, min(1.0, x)))


def _norm_inv_depth(depth: float, lo: float = 0.08, hi: float = 0.35) -> float:
    """Prefer mid-depth bases; penalize too shallow and too deep."""
    if not math.isfinite(depth):
        return 0.0
    mid = 0.20
    if depth < lo:
        return _clip01((depth - 0.03) / (lo - 0.03))
    if depth > hi:
        return _clip01((hi + 0.15 - depth) / 0.15)
    return _clip01(1.0 - abs(depth - mid) / (hi - lo))


def _norm_pos(pos: float, lo: float = 0.45, hi: float = 0.92) -> float:
    if not math.isfinite(pos):
        return 0.0
    return _clip01((pos - lo) / (hi - lo))


def _norm_dist(dist: float, hi: float = 0.14) -> float:
    """Smaller dist (closer to pivot) is better up to a point."""
    if not math.isfinite(dist):
        return 0.0
    if dist < 0:
        return 0.3
    return _clip01(1.0 - dist / hi)


def _norm_contraction(raw: float) -> float:
    """Higher raw = more contraction vs 20d ago."""
    if not math.isfinite(raw) or raw <= 0:
        return 0.0
    return _clip01((raw - 0.85) / 0.5)


def _norm_dryup(ratio: float) -> float:
    """Lower vol/MA ratio = drier = better."""
    if not math.isfinite(ratio) or ratio <= 0:
        return 0.0
    return _clip01(1.0 - (ratio - 0.55) / 0.75)


def _norm_tight(t: float) -> float:
    if not math.isfinite(t):
        return 0.0
    return _clip01(t)


def _norm_repair(raw: float) -> float:
    """Moderate lift vs quiet zone; penalize extreme spikes."""
    if not math.isfinite(raw) or raw <= 0:
        return 0.0
    if raw > 3.5:
        return 0.4
    return _clip01((raw - 0.85) / 1.8)


def _safe(f: dict[str, Any], k: str) -> float:
    v = f.get(k)
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return x


def base_quality_score(f: dict[str, Any]) -> float:
    """
    20 depth + 15 pos + 10 dist + 15 vol contraction + 15 dry-up + 10 tightness + 15 repair.
    """
    d = _norm_inv_depth(_safe(f, "base_depth"))
    p = _norm_pos(_safe(f, "base_pos_in_base"))
    di = _norm_dist(_safe(f, "dist_to_pivot"))
    vc = _norm_contraction(_safe(f, "volatility_contraction_raw"))
    dry = 0.5 * (_norm_dryup(_safe(f, "vol_dryup_ratio_10d")) + _norm_dryup(_safe(f, "vol_dryup_ratio_20d")))
    tight = 0.5 * (_norm_tight(_safe(f, "close_tightness_5d")) + _norm_tight(_safe(f, "close_tightness_10d")))
    rep = _norm_repair(_safe(f, "right_side_repair_raw"))
    s = 20.0 * d + 15.0 * p + 10.0 * di + 15.0 * vc + 15.0 * dry + 10.0 * tight + 15.0 * rep
    return float(max(0.0, min(100.0, s)))


def _norm_rung(rung: int, cap: int = 5) -> float:
    if rung <= 0:
        return 0.0
    return _clip01(rung / float(cap))


def _norm_vol_strength(ratio: float) -> float:
    if not math.isfinite(ratio) or ratio <= 0:
        return 0.0
    return _clip01((ratio - 0.9) / 1.2)


def _norm_close_in_range(cir: float) -> float:
    if not math.isfinite(cir):
        return 0.0
    return _clip01((cir - 0.35) / 0.55)


def _norm_br_vol(r20: float, r50: float) -> float:
    return 0.5 * (_norm_vol_strength(r20) + _norm_vol_strength(r50))


def _norm_br_close(cir: float) -> float:
    return _norm_close_in_range(cir)


def _norm_br_gap(gap: float) -> float:
    if not math.isfinite(gap):
        return 0.0
    return _clip01(gap / 0.05)


def _norm_br_ext(ext: float) -> float:
    """Prefer not too extended above MA20."""
    if not math.isfinite(ext):
        return 0.0
    if ext > 0.12:
        return 0.25
    return _clip01(1.0 - ext / 0.12)


def entry_quality_score_pp(f: dict[str, Any], pp_rung: int) -> float:
    """
    PP path: 30 rung + 20 vol + 20 close strength + 15 right half + 15 repair context.
    """
    rq = _norm_rung(pp_rung)
    vq = 0.5 * (_norm_vol_strength(_safe(f, "pp_day_vol_ratio_20")) + _norm_vol_strength(_safe(f, "pp_day_vol_ratio_50")))
    cs = _norm_close_in_range(_safe(f, "pp_day_close_in_range"))
    rh = 1.0 if f.get("in_right_half_of_base") else 0.0
    rep = _norm_repair(_safe(f, "right_side_repair_raw"))
    s = 30.0 * rq + 20.0 * vq + 20.0 * cs + 15.0 * rh + 15.0 * rep
    return float(max(0.0, min(100.0, s)))


def entry_quality_score_breakout(f: dict[str, Any]) -> float:
    """
    Breakout path: 30 vol + 25 close + 20 gap vs pivot + 15 not extended + 10 tightness.
    """
    vq = _norm_br_vol(_safe(f, "breakout_vol_ratio_20"), _safe(f, "breakout_vol_ratio_50"))
    cs = _norm_br_close(_safe(f, "breakout_close_in_range"))
    g = _norm_br_gap(_safe(f, "breakout_gap_from_pivot"))
    ex = _norm_br_ext(_safe(f, "breakout_extension_from_ma20"))
    tight = 0.5 * (_norm_tight(_safe(f, "close_tightness_5d")) + _norm_tight(_safe(f, "close_tightness_10d")))
    s = 30.0 * vq + 25.0 * cs + 20.0 * g + 15.0 * ex + 10.0 * tight
    return float(max(0.0, min(100.0, s)))
