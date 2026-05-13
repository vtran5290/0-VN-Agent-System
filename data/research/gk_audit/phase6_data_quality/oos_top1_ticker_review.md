# L40 OOS Top-1 Trade Analysis

**Trade**: Entry 2025-09-03 → Exit 2025-12-02
**Raw net return**: ~+150.5%

## 1. CA Events for L40

| Date | Gap% | Classification |
|------|-------|----------------|
| 2024-01-30 | -66.8% | CA_NEG: bonus share issue (3:1 ratio estimated) |

The CA event occurred on 2024-01-30 — **16 months BEFORE** the OOS trade entry.
The OOS trade (Sep-Dec 2025) is entered at post-CA market prices.
The trade is NOT directly contaminated by the CA event.

## 2. Price Trajectory

- 2024-01-30: price drops from 19.00 → 6.30 (CA event)
- 2024-2025: price gradually recovers from 6.30 to 35+
- 2025-08-27: volume explosion, +10% gap — start of speculative run
- 2025-09-03: C06 GK_BUY signal, entry at open 35.80
- 2025-09 to 2025-10: L40 surges from 35 → 117 (within-period peak)
- 2025-10-17: peak open 117.35, then correction to 86-98 range
- 2025-12-02: GK_SELL exit at open 90.00
- Net: 90.00 / 35.80 - 1 = +151.4%

## 3. Is the Return Legitimate?

**YES — the return is a genuine market price appreciation.**

Evidence:
- Trade entered at post-CA prices (Jan 2024 CA event is 16+ months prior)
- L40 experienced a real speculative breakout: ADV50 went from near-zero to VND 12B/day
- Price appreciation of 35 → 90 in 3 months is extreme but visible in live market data
- GK_SELL exit at 90 was well below the within-period peak of 117
- No CA event occurred during the holding period (Sep-Dec 2025)

**However, the trade represents an extreme outlier:**
- +151% in 90 calendar days
- L40 had near-zero liquidity before Aug 2025
- Even with ADV50 >= 2B filter, L40's liquidity was marginal at entry
- Single trade = 63% of OOS PnL — this is concentration, not edge

## 4. Adjusted Data Impact

GK signals on adjusted data may differ from raw:
- On raw data: the -66.8% drop in Jan 2024 creates a massive GK_SELL signal
- After recovery, the GK_BUY in Sep 2025 is 'clean' on both raw and adjusted data
- The Sep 2025 signal likely exists on adjusted data too
- The return magnitude (35 → 90) is unaffected by the prior CA adjustment

## 5. Conclusion

L40 trade is NOT data-contaminated. However, it is an extreme outlier.
The C06 OOS result is contingent on catching ONE speculative run in a micro-cap.
This is a concentration risk, not a data quality issue.

**Action required**: Re-run OOS excluding L40 to test if the system has edge WITHOUT
this single outlier. If ex-L40 OOS MAR < 0.50, the system's OOS result is illusory.
