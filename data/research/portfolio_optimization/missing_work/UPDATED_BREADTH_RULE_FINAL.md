# Breadth Rule Final (Updated 2026-05-16)

Supersedes: BREADTH_RULE_FINAL.md
Change: Clarified T1/T2 permission split. Defense zone allows T1 with operator review.

---

## Test Results

| Gate | MAR | CAGR | MaxDD | 2021 | 2025 | Blocked | Avoided W | Avoided L |
|------|-----|------|-------|------|------|---------|-----------|----------|
| no_gate | 0.416 | 5.81% | -13.99% | 44.63% | 23.26% | 0 | 0 | 0 |
| hard_40 | 0.344 | 6.13% | -17.82% | 42.08% | 17.84% | 1741 | 1125 | 616 |
| hard_35 | 0.166 | 4.30% | -26.01% | 44.14% | 21.58% | 927 | 581 | 346 |
| hysteresis_35_45 | 0.236 | 5.25% | -22.19% | 43.23% | 24.39% | 1301 | 839 | 462 |

---

## Backtest Verdict — CRITICAL FINDING

**Hard breadth gates HURT MAR:**
- hard_40: MAR 0.416 → 0.344 (-0.072). Blocked 1741 trades: 1125 winners, 616 losers (ratio 1.8:1).
- hard_35: MAR 0.416 → 0.166 (-0.250). Severe.
- Hysteresis 35/45: MAR 0.416 → 0.236. Still harmful.

**Root cause:** A3 DP already uses VNINDEX regime gate (EMA20 > EMA100). Breadth <40% periods
inside a bull regime still contain tradeable setups. Hard breadth blocks remove winners faster than
losers because A3 signals already passed the regime quality filter.

**Decision: Breadth is DASHBOARD_WARNING_ONLY for T1. Controls T2 aggression only.**

---

## Operating Rules (Evidence-Based, FINAL)

| A3 breadth | Zone | breadth_t1_permission | breadth_t2_permission | final_action modifier |
|------------|------|-----------------------|----------------------|----------------------|
| ≥ 40% | Normal | True | True | NEW_T1 (normal) |
| 35–40% | Caution | True | Reduced (30–40% slot) | NEW_T1 (with caution note) |
| < 35% | Defense | True (manual review) | False | NEW_T1_MANUAL_REVIEW_BREADTH |
| VNINDEX EMA20 < EMA100 | Bear | False (hard block) | False | SKIP_VNINDEX_BEAR |

**Only the VNINDEX bear regime gate produces a hard T1 block.**

---

## T2 Hysteresis (for T2 blocking only)

- Block T2 adds when breadth drops below 35%
- Restore T2 when breadth recovers above 45%
- T1 entries: always allowed when regime gate is open (VNINDEX bull) and liquidity OK

---

## What "Manual Review" Means in Defense Zone

When breadth_zone = defense (< 35%) and signal is NEW_T1_MANUAL_REVIEW_BREADTH:

The operator must explicitly confirm before entering T1:
1. Is the VNINDEX regime still bull? (must be)
2. Is the individual signal high-quality? (cloud strong, EMA dist < 10%, liquidity OK)
3. Is sector L4 concentration below 30% of portfolio?

If all 3 yes → operator can enter T1 at reduced size or normal size (judgment call).
If any no → skip.

This is not an automated block. It is an operator review flag.

---

## Scan Fields Added (Phase34)

- `breadth_t1_permission`: True/False
- `breadth_t2_permission`: True/False
- `final_action`: expanded enum (see phase34_daily_scan_schema.csv)
- `final_action_reason`: human-readable explanation string
