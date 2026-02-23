"""
Distribution days: O'Neil-style, aligned with AFL 04_DIST_DAY.
Expire rule (IBD): dist day drops out of count after lb sessions → rolling window Sum(is_dist, lb).
Refined: DropPct >= min, ClosePos <= max (selling into close), MinVol filter.
"""
from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Bar:
    d: str
    c: float
    v: Optional[float]

@dataclass
class BarOHLC:
    d: str
    o: float
    h: float
    l: float
    c: float
    v: Optional[float] = None

# AFL-aligned defaults
DD_LB_DEFAULT = 25        # lookback: dist day expires after 25 sessions (rolling window)
DD_LB = DD_LB_DEFAULT     # alias
DD_MIN_DROP_PCT = 0.002   # 0.20%; tune 0.003–0.005 for "meaningful" only
DD_CLOSE_MAX_POS = 0.50   # close in lower half of range (selling into close)
DD_MIN_VOL = 0.0          # set >0 to filter noise if needed

def distribution_days_rolling_lb_basic(bars: List[Bar], lb: int = DD_LB_DEFAULT) -> Optional[int]:
    """
    Basic: close down + volume up. Rolling window of lb sessions (dist day expires after lb).
    """
    need = lb + 1
    if len(bars) < need:
        return None
    window = bars[-need:]
    if any(b.v is None for b in window):
        return None
    cnt = 0
    for i in range(1, len(window)):
        if window[i].c < window[i-1].c and window[i].v is not None and window[i-1].v is not None and window[i].v > window[i-1].v:
            cnt += 1
    return cnt

def distribution_days_rolling_20(bars: List[Bar]) -> Optional[int]:
    """Backward compat: calls rolling_lb_basic with lb=25."""
    return distribution_days_rolling_lb_basic(bars, lb=DD_LB_DEFAULT)

def distribution_days_rolling_lb_refined(
    bars: List[BarOHLC],
    lb: int = DD_LB_DEFAULT,
    min_drop_pct: float = DD_MIN_DROP_PCT,
    close_max_pos: float = DD_CLOSE_MAX_POS,
    min_vol: float = DD_MIN_VOL,
) -> Optional[int]:
    """
    AFL-aligned: close down + volume up + DropPct >= min + ClosePos <= max + V >= min_vol.
    Rolling window lb (default 25): dist day expires after lb sessions. Need lb+1 bars. Index without volume -> None.
    """
    need = lb + 1
    if len(bars) < need:
        return None
    window = bars[-need:]
    if any(b.v is None for b in window):
        return None

    cnt = 0
    for i in range(1, len(window)):
        prev, cur = window[i - 1], window[i]
        if prev.v is None or cur.v is None or cur.c >= prev.c or cur.v <= prev.v:
            continue
        # DropPct
        drop_pct = (prev.c - cur.c) / prev.c if prev.c > 0 else 0.0
        if drop_pct < min_drop_pct:
            continue
        if cur.v < min_vol:
            continue
        # ClosePos: where close sits in day range (0=at low, 1=at high)
        rng = cur.h - cur.l
        close_pos = (cur.c - cur.l) / rng if rng > 0 else 0.5
        if close_pos > close_max_pos:
            continue
        cnt += 1
    return cnt

def distribution_days_rolling_20_refined(
    bars: List[BarOHLC],
    min_drop_pct: float = DD_MIN_DROP_PCT,
    close_max_pos: float = DD_CLOSE_MAX_POS,
    min_vol: float = DD_MIN_VOL,
) -> Optional[int]:
    """Backward compat: calls rolling_lb_refined with lb=DD_LB_DEFAULT (25)."""
    return distribution_days_rolling_lb_refined(bars, lb=DD_LB_DEFAULT, min_drop_pct=min_drop_pct, close_max_pos=close_max_pos, min_vol=min_vol)
