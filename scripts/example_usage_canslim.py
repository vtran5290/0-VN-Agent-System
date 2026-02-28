"""
example_usage_canslim.py
========================
Demo cách dùng CANSLIM engine — không cần FireAnt token để test logic rules.
"""
import os
import sys

# Thêm src vào sys.path để import được package canslim
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from canslim.rules import CanslimInputs, canslim_pre_buy_check, canslim_position_management


def main() -> None:
    # ============================================================
    # Test 1: Pre-buy check — cổ phiếu tốt trong uptrend
    # ============================================================
    print("=" * 60)
    print("TEST 1: Strong candidate in confirmed uptrend")
    print("=" * 60)

    inputs_good = CanslimInputs(
        q_eps_yoy=0.45,          # +45% -> ELITE
        q_sales_yoy=0.30,        # +30% -> pass
        sales_accel=True,
        rs_rating=88,            # > 80 -> pass
        price=52_000,            # VND
        pivot=50_000,
        breakout_volume_ratio=1.8,  # 1.8x avg -> good
        market_status="confirmed_uptrend",
        leader_stock=True,
    )

    result = canslim_pre_buy_check(inputs_good)
    print(f"Allow buy: {result['allow_buy']}")
    print(f"Size:      {result['size_suggestion']}")
    print(f"EPS tier:  {result['eps_tier']}")
    print(f"Buy zone:  {result['buy_zone']}")
    print(f"Reasons:   {result['reasons']}")

    # ============================================================
    # Test 2: Pre-buy check — bị reject vì chase + market xấu
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 2: Chase entry + market in correction")
    print("=" * 60)

    inputs_bad = CanslimInputs(
        q_eps_yoy=0.35,
        q_sales_yoy=0.28,
        rs_rating=82,
        price=56_000,     # 12% trên pivot -> CHASE_FORBIDDEN
        pivot=50_000,
        breakout_volume_ratio=1.2,   # volume yếu
        market_status="correction",
    )

    result2 = canslim_pre_buy_check(inputs_bad)
    print(f"Allow buy: {result2['allow_buy']}")
    print(f"Size:      {result2['size_suggestion']}")
    print(f"Reasons:   {result2['reasons']}")

    # ============================================================
    # Test 3: Position management — stop bị hit
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 3: Position management — hard stop hit")
    print("=" * 60)

    pos_stop = CanslimInputs(
        entry_price=50_000,
        gain_from_entry=-0.085,   # -8.5% -> hard stop
        drawdown_from_entry=-0.085,
        weeks_since_entry=1.5,
        market_status="correction",
    )

    pos_result = canslim_position_management(pos_stop)
    print(f"Action: {pos_result['action']}")
    print(f"Reason: {pos_result['reason']}")

    # ============================================================
    # Test 4: Position management — fast run exception
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 4: Fast run +22% in 2 weeks -> HOLD (don't sell early)")
    print("=" * 60)

    pos_fast = CanslimInputs(
        entry_price=50_000,
        gain_from_entry=0.22,      # +22%
        drawdown_from_entry=0.22,
        weeks_since_entry=2.0,     # chỉ 2 tuần -> fast run exception
        market_status="confirmed_uptrend",
        leader_stock=True,
    )

    pos_result2 = canslim_position_management(pos_fast)
    print(f"Action: {pos_result2['action']}  (expected: hold)")
    print(f"Reason: {pos_result2['reason']}")

    # ============================================================
    # Test 5: EPS min_pass (18-20%) nhưng RS cao + sales accel
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 5: EPS borderline (19%) but RS=91 + sales accel -> allow with warning")
    print("=" * 60)

    inputs_borderline = CanslimInputs(
        q_eps_yoy=0.19,          # MIN_PASS (18-25%)
        q_sales_yoy=0.20,        # <25% nhưng...
        sales_accel=True,        # ...accelerating -> pass sales
        rs_rating=91,
        price=51_500,
        pivot=50_000,
        breakout_volume_ratio=2.1,
        market_status="confirmed_uptrend",
    )

    result5 = canslim_pre_buy_check(inputs_borderline)
    print(f"Allow buy: {result5['allow_buy']}")
    print(f"EPS tier:  {result5['eps_tier']}  (note: min_pass = caution)")
    print(f"Reasons:   {result5['reasons']}")

    print("\n✅ CANSLIM rules tests completed.")


if __name__ == "__main__":
    main()

