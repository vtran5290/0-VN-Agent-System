"""
rules.py
========
CANSLIM decision layer — O'Neil-aligned, VN-adapted.
Tất cả logic đều deterministic và auditable cho backtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EpsTier(str, Enum):
    FAIL = "fail"
    MIN_PASS = "min_pass"       # 18–<25%
    PREFERRED = "preferred"     # 25–<40%
    ELITE = "elite"             # >=40%


class BuyZone(str, Enum):
    BEFORE_PIVOT = "before_pivot"
    IDEAL = "ideal"             # 0–5%
    LATE = "late"               # 5–10%
    CHASE_FORBIDDEN = "chase"   # >10%


class Action(str, Enum):
    HOLD = "hold"
    TRIM = "trim"
    SELL = "sell"
    NO_BUY = "no_buy"
    BUY_OK = "buy_ok"


@dataclass(frozen=True)
class CanslimInputs:
    # Fundamentals
    q_eps_yoy: Optional[float] = None
    q_sales_yoy: Optional[float] = None
    sales_accel: Optional[bool] = None
    margin_yoy: Optional[float] = None
    # Leadership
    rs_rating: Optional[int] = None
    # Trade context
    price: Optional[float] = None
    pivot: Optional[float] = None
    breakout_volume_ratio: Optional[float] = None   # today_vol / avg20d_vol
    # Position context
    entry_price: Optional[float] = None
    days_since_entry: Optional[int] = None
    weeks_since_entry: Optional[float] = None
    max_gain_since_entry: Optional[float] = None
    gain_from_entry: Optional[float] = None
    drawdown_from_entry: Optional[float] = None
    # Market
    market_status: Optional[str] = None
    leader_stock: Optional[bool] = None


# ---------------------------------------------------------------------------
# Module functions
# ---------------------------------------------------------------------------

def score_eps_yoy(q_eps_yoy: Optional[float]) -> Optional[EpsTier]:
    if q_eps_yoy is None:
        return None
    if q_eps_yoy < 0.18:
        return EpsTier.FAIL
    if q_eps_yoy < 0.25:
        return EpsTier.MIN_PASS
    if q_eps_yoy < 0.40:
        return EpsTier.PREFERRED
    return EpsTier.ELITE


def pass_sales(q_sales_yoy: Optional[float], sales_accel: Optional[bool]) -> Optional[bool]:
    """Pass nếu sales >=25% HOẶC đang accelerating (theo sách O'Neil)."""
    if q_sales_yoy is None and sales_accel is None:
        return None
    if q_sales_yoy is not None and q_sales_yoy >= 0.25:
        return True
    if sales_accel is True:
        return True
    return False


def margin_guardrail(
    q_eps_yoy: Optional[float],
    q_sales_yoy: Optional[float],
    margin_yoy: Optional[float] = None,
) -> Optional[bool]:
    """Flag khi sales tăng mạnh nhưng EPS không theo — dấu hiệu margin compression."""
    if q_eps_yoy is None or q_sales_yoy is None:
        return None
    if q_sales_yoy >= 0.20 and q_eps_yoy <= 0.05:
        return False
    if margin_yoy is not None and margin_yoy < -0.02:
        return False
    return True


def pass_rs(rs_rating: Optional[int], min_rs: int = 80) -> Optional[bool]:
    """RS >= 80: investigate; winners trung bình ~87 theo O'Neil."""
    if rs_rating is None:
        return None
    return rs_rating >= min_rs


def classify_buy_zone(price: Optional[float], pivot: Optional[float]) -> Optional[BuyZone]:
    if price is None or pivot is None or pivot <= 0:
        return None
    pct = (price - pivot) / pivot
    if pct < 0:
        return BuyZone.BEFORE_PIVOT
    if pct <= 0.05:
        return BuyZone.IDEAL
    if pct <= 0.10:
        return BuyZone.LATE
    return BuyZone.CHASE_FORBIDDEN


def check_breakout_volume(
    breakout_volume_ratio: Optional[float],
    min_ratio: float = 1.4,  # VN: 1.4x avg = minimum; ideally 1.7-2x
) -> Optional[bool]:
    """
    VN-specific: breakout volume phải đủ cao.
    US: O'Neil dùng +40-50%; VN dùng median 20d nên 1.4x đã tương đương.
    """
    if breakout_volume_ratio is None:
        return None
    return breakout_volume_ratio >= min_ratio


def hard_stop_7_8(drawdown_from_entry: Optional[float]) -> Optional[bool]:
    """True = phải cắt lỗ ngay (drawdown >= 8%)."""
    if drawdown_from_entry is None:
        return None
    return drawdown_from_entry <= -0.08


def should_take_profit(
    gain_from_entry: Optional[float],
    weeks_since_entry: Optional[float],
    market_status: Optional[str],
    leader_stock: Optional[bool],
    fast_run_weeks: float = 3.0,
    min_hold_weeks: float = 8.0,
) -> Optional[Action]:
    """
    Profit-taking logic O'Neil:
    - Fast run: +20% trong <= 3 tuần -> hold ít nhất 8 tuần
    - Normal: +20-25% -> trim tùy context
    - >25% -> trim (hoặc trail stop nếu leader + uptrend)
    """
    if gain_from_entry is None or weeks_since_entry is None:
        return None

    # Exception: fast run power leader
    if gain_from_entry >= 0.20 and weeks_since_entry <= fast_run_weeks:
        if weeks_since_entry < min_hold_weeks:
            return Action.HOLD

    # >25%: trim
    if gain_from_entry >= 0.25:
        if market_status == "confirmed_uptrend" and leader_stock is True:
            return Action.HOLD  # trail stop thay vì bán ngay
        return Action.TRIM

    # 20-25%: tùy market + leader
    if gain_from_entry >= 0.20:
        if market_status != "confirmed_uptrend":
            return Action.TRIM
        if leader_stock is True:
            return Action.HOLD
        return Action.TRIM

    return Action.HOLD


# ---------------------------------------------------------------------------
# Composite decision functions
# ---------------------------------------------------------------------------

def canslim_pre_buy_check(x: CanslimInputs, rs_min: int = 80, strict: bool = False) -> dict:
    """
    Tổng hợp tất cả điều kiện trước khi mua.

    Args:
        rs_min: RS threshold (default 80). Test với 70 để so sánh "early vs late entry".
        strict: nếu True, thiếu RS / volume / sales được coi là fail (đúng kiểu O'Neil).
    """
    eps_tier = score_eps_yoy(x.q_eps_yoy)
    sales_ok = pass_sales(x.q_sales_yoy, x.sales_accel)
    margin_ok = margin_guardrail(x.q_eps_yoy, x.q_sales_yoy, x.margin_yoy)
    rs_ok = pass_rs(x.rs_rating, min_rs=rs_min)
    buy_zone = classify_buy_zone(x.price, x.pivot)
    vol_ok = check_breakout_volume(x.breakout_volume_ratio)

    reasons: list[str] = []

    # M: hard filter đầu tiên — no new buys in correction/downtrend
    if x.market_status not in (None, "confirmed_uptrend", "uptrend_under_pressure"):
        reasons.append(f"MARKET={x.market_status}")

    # Strict missing-data flags (O'Neil style)
    if strict:
        if x.rs_rating is None:
            reasons.append("RS_MISSING")
        if x.breakout_volume_ratio is None:
            reasons.append("VOL_MISSING")
        if x.q_sales_yoy is None and x.sales_accel is None:
            reasons.append("SALES_MISSING")

    # C: EPS
    if x.q_eps_yoy is None:
        reasons.append("C_MISSING")
    elif eps_tier == EpsTier.FAIL:
        reasons.append("C_FAIL: EPS <18% YoY")
    elif eps_tier == EpsTier.MIN_PASS:
        reasons.append("C_MIN_PASS: EPS 18-25% (borderline)")

    # Sales
    if sales_ok is False:
        reasons.append("SALES_FAIL: <25% YoY và không accelerating")

    # Margin guardrail
    if margin_ok is False:
        reasons.append("MARGIN_FAIL: sales up nhưng EPS flat/down")

    # RS
    if rs_ok is False:
        reasons.append(f"RS_BELOW_MIN: RS={x.rs_rating} <{rs_min}")

    # Buy zone
    if buy_zone == BuyZone.CHASE_FORBIDDEN:
        reasons.append("ZONE_CHASE: >10% past pivot")
    elif buy_zone == BuyZone.LATE:
        reasons.append("ZONE_LATE: 5-10% past pivot (half size)")

    # Volume
    if vol_ok is False:
        ratio = f"{x.breakout_volume_ratio:.1f}x" if x.breakout_volume_ratio else "N/A"
        reasons.append(f"VOL_WEAK: {ratio} avg (cần >=1.4x)")

    # Core allow/deny logic
    market_ok = x.market_status in (None, "confirmed_uptrend", "uptrend_under_pressure")

    # Strict mode: missing RS/volume/sales được coi là fail
    if strict:
        leadership_ok = (rs_ok is True)
        volume_ok_flag = (vol_ok is True)
        sales_gate_ok = (sales_ok is True)
    else:
        leadership_ok = (rs_ok is None or rs_ok is True)
        volume_ok_flag = (vol_ok is None or vol_ok is True)
        sales_gate_ok = (sales_ok is None or sales_ok is True)

    c_ok = (
        x.q_eps_yoy is not None and
        eps_tier != EpsTier.FAIL and
        sales_gate_ok and
        (margin_ok is None or margin_ok is True)
    )

    zone_ok = buy_zone not in (BuyZone.CHASE_FORBIDDEN,) if buy_zone else True

    allow_buy = market_ok and c_ok and leadership_ok and zone_ok and volume_ok_flag

    # Position size suggestion
    if allow_buy and buy_zone == BuyZone.LATE:
        size_suggestion = "half_size"
    elif allow_buy:
        size_suggestion = "full_size"
    else:
        size_suggestion = "no_buy"

    return {
        "allow_buy": allow_buy,
        "size_suggestion": size_suggestion,
        "eps_tier": eps_tier.value if eps_tier else "C_MISSING",
        "sales_ok": sales_ok,
        "margin_ok": margin_ok,
        "rs_ok": rs_ok,
        "buy_zone": buy_zone.value if buy_zone else None,
        "volume_ok": vol_ok,
        "market_status": x.market_status,
        "reasons": reasons,
    }


def canslim_position_management(x: CanslimInputs) -> dict:
    """
    Post-entry: stop + profit management.
    Stop luôn được check trước profit-taking.
    """
    # Hard stop first (bất kể điều kiện khác)
    if hard_stop_7_8(x.drawdown_from_entry):
        return {
            "action": Action.SELL.value,
            "reason": "hard_stop_7_8%",
            "gain": x.drawdown_from_entry,
        }

    profit_action = should_take_profit(
        gain_from_entry=x.gain_from_entry,
        weeks_since_entry=x.weeks_since_entry,
        market_status=x.market_status,
        leader_stock=x.leader_stock,
    )

    return {
        "action": profit_action.value if profit_action else Action.HOLD.value,
        "reason": "profit_module",
        "gain": x.gain_from_entry,
        "weeks": x.weeks_since_entry,
    }

