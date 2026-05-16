# Breadth Rule Final

As of: 2026-05-16

## Test Results

| Gate | MAR | CAGR | MaxDD | 2021 | 2025 | Blocked | Avoided W | Avoided L |
|------|-----|------|-------|------|------|---------|-----------|----------|
| no_gate | 0.416 | 5.81% | -13.99% | 44.63% | 23.26% | 0 | 0 | 0 |
| hard_40 | 0.344 | 6.13% | -17.82% | 42.08% | 17.84% | 1741 | 1125 | 616 |
| hard_35 | 0.166 | 4.30% | -26.01% | 44.14% | 21.58% | 927 | 581 | 346 |
| hysteresis_35_45 | 0.236 | 5.25% | -22.19% | 43.23% | 24.39% | 1301 | 839 | 462 |

## Backtest Verdict — CRITICAL FINDING

**Hard breadth gates HURT MAR in backtest:**
- hard_40: MAR 0.416 → 0.344 (-0.072). Blocked 1741 trades: 1125 winners, 616 losers.
- hard_35: MAR 0.416 → 0.166 (-0.250). Severe performance drag.
- Hysteresis 35/45: MAR 0.416 → 0.236. Still hurts.

**Root cause:** A3 DP already uses VNINDEX regime gate (EMA20 > EMA100). Breadth <40% periods
inside a bull regime still contain tradeable setups. Blocking them removes winners faster than losers.

**Recommendation: DASHBOARD_WARNING_ONLY — do NOT use as hard entry block.**

The breadth gate should be:
- Displayed in dashboard as context
- Used to increase caution on T2 sizing (reduce T2 from 50% to 30-40%)
- Not used to block T1 entries entirely

## Operating Rules (Revised — Evidence-Based)

| A3 breadth | Zone | Rule |
|------------|------|------|
| ≥ 50% | Strong bull | Normal entries, full T2 add |
| 40–50% | Normal | Normal entries, normal T2 |
| 35–40% | Caution | Allow T1. Reduce T2 to 30–40% of slot. |
| < 35% | Defense | Allow T1. Block T2 adds. Monitor closely. |
| VNINDEX bear (EMA20 < EMA100) | Bear | No new entries (regime gate handles this) |

## Hysteresis (for T2 blocking only)

- Block T2 adds when breadth drops below 35%
- Restore T2 when breadth recovers above 45%
- T1 entries: always allowed when regime gate is open and liquidity OK
