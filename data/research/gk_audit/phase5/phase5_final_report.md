# Phase 5 Research — Final Report

Run date: 2026-05-04

---

## A. FACTS

**C06 Definition (Phase 4 winner — unchanged):**
- Entry: GK_FAST (Len=100, Mult=2.0, ATR=14, Confirm=2)
- Filter: VolExp >= 1.2 at entry
- Exit: GK_SELL OR TimeStop20 (after 20 bars, if ret <= 0%)
- Sizing: half-size when VNINDEX < EMA50
- Ranking: ADV50 descending, max 10 positions

**C06 Phase 4 results (reference):**
- CAGR 22.0%  MAR 0.73  Active MaxDD -27.3%
- ex-top3 12.5%  ex-top5 8.5%  2024 +2.1%  2025 +49.8%
- N=170  top1_ticker 19.5%

---

## B. WALK-FORWARD OOS RESULT

### Fold1_OOS (2025+) — FAIL
- N trades: 78
- CAGR: 20.3%
- MAR: 0.87
- Active MaxDD: -23.0%
- ex-top3 CAGR: -5.7%
- ex-top5 CAGR: -9.8%
- top1 ticker: 50.1%

### Fold2_OOS (2026+) — FAIL
- N trades: 27
- CAGR: 19.9%
- MAR: 0.89
- Active MaxDD: -21.5%
- ex-top3 CAGR: 0.9%
- ex-top5 CAGR: -25.0%
- top1 ticker: 76.9%

**OOS interpretation:**
- Fold 1 (2025+): FAIL — Check specific fails above
- Fold 2 (2026+): FAIL (or insufficient) — 

---

## C. MARGINAL CONTRIBUTION OF FT05 AND SZ06

| Arm | Label | N | CAGR | MAR | aDD | exT3 | exT5 | 2024 |
|-----|-------|---|------|-----|-----|------|------|------|
| M00 | EX09a_only | 173 | 29.3% | 0.72 | -30.7% | 19.5% | 12.9% | -7.1% |
| M01 | EX09a+FT05_1.2 | 170 | 21.9% | 0.65 | -30.7% | 13.4% | 9.8% | 4.8% |
| M02 | EX09a+SZ06 | 173 | 26.9% | 0.73 | -29.1% | 19.3% | 12.7% | -11.9% |
| M03 | EX09a+FT05+SZ06 | 170 | 22.0% | 0.73 | -27.3% | 12.5% | 8.5% | 2.1% |
| M04 | EX09a+FT05_1.1 | 178 | 19.0% | 0.55 | -31.1% | 12.1% | 8.2% | 6.6% |
| M05 | EX09a+FT05_1.3 | 172 | 19.3% | 0.55 | -32.4% | 8.6% | 4.5% | 6.1% |
| M06 | EX09a+FT05_1.5 | 170 | 9.9% | 0.24 | -38.6% | 0.2% | -4.2% | 1.1% |
| M07 | EX09a+SZ06b | 173 | 26.9% | 0.73 | -29.1% | 19.3% | 12.7% | -11.9% |
| M08 | EX09a+FT05+SZ06b | 170 | 22.0% | 0.73 | -27.3% | 12.5% | 8.5% | 2.1% |

**FT05 verdict**: FT05 adds value — MAR and/or DrawDown improves with filter vs without
**SZ06 verdict**: SZ06 adds value — reduces active MaxDD or improves MAR

Volume threshold sensitivity (M01=1.2, M04=1.1, M05=1.3, M06=1.5):
- M04 (1.1): CAGR 19.0%  MAR 0.55
- M01 (1.2): CAGR 21.9%  MAR 0.65
- M05 (1.3): CAGR 19.3%  MAR 0.55
- M06 (1.5): CAGR 9.9%  MAR 0.24

---

## D. TIMESTOP20 ROBUSTNESS

| Arm | bars | threshold | N | CAGR | MAR | aDD | exT3 | 2024 |
|-----|------|-----------|---|------|-----|-----|------|------|
| TS_b15_t-2 | - | - | 172 | 14.1% | 0.46 | -27.9% | n/a | 7.7% |
| TS_b15_t+0 | - | - | 202 | 14.7% | 0.43 | -32.1% | n/a | 4.3% |
| TS_b15_t+2 | - | - | 226 | 12.1% | 0.33 | -34.9% | n/a | -9.7% |
| TS_b20_t-2 | - | - | 157 | 16.8% | 0.54 | -27.7% | n/a | 6.0% |
| TS_b20_t+0 | - | - | 170 | 22.0% | 0.73 | -27.3% | n/a | 2.1% |
| TS_b20_t+2 | - | - | 188 | 19.7% | 0.52 | -34.7% | n/a | -1.1% |
| TS_b25_t-2 | - | - | 149 | 17.2% | 0.48 | -32.7% | n/a | 15.0% |
| TS_b25_t+0 | - | - | 160 | 23.5% | 0.75 | -28.3% | n/a | 20.0% |
| TS_b25_t+2 | - | - | 175 | 18.2% | 0.52 | -31.7% | n/a | 12.1% |
| TS_b30_t-2 | - | - | 142 | 13.2% | 0.37 | -31.5% | n/a | 14.1% |
| TS_b30_t+0 | - | - | 149 | 18.4% | 0.52 | -31.9% | n/a | 14.5% |
| TS_b30_t+2 | - | - | 158 | 19.0% | 0.55 | -31.5% | n/a | 14.0% |

**TimeStop robustness**: FRAGILE — not all bar windows show consistent MAR > 0.55. Check table above.

---

## E. 2024 ROOT-CAUSE ANALYSIS

EX09a 2024 return: -7.1% (Phase 3).  C06 2024 return: +2.1% (Phase 4).

- EX09a trades in 2024: 61
- Trades time-stopped in 2024: 38
- Signals FT05 blocked in 2024: 48

- Time-stopped trades that later recovered (20b): 13
- Time-stopped trades that did NOT recover: 25
- Average return of FT05-blocked trades (in EX09a): 0.7%
- 2024 trades in CA watchlist tickers: 6

**Interpretation:**
- See phase5_2024_trade_diagnosis.csv for full trade-by-trade analysis.
- See phase5_2024_blocked_trades.csv for FT05 rejections.
- See phase5_2024_time_stop_review.csv for post-exit recovery.

---

## F. AFL / PYTHON SIGNAL RECONCILIATION

Python signal trace exported for: VRE, VGI, VIC, FPT, HPG, TCH, NVL

- See phase5_signal_reconciliation.csv for full per-bar signal state.
- See phase5_afl_debug_rows.csv for rows around BUY/EXIT events.
- See phase5_signal_mismatches.md for the reconciliation checklist.

Key check: compare `gk_buy`, `gk_sell`, `tstop_would_fire`, `volexp_ok`,
`vnx_above_e50` columns against AmiBroker AFL chart for each ticker.

---

## G. CORPORATE-ACTION RISK

- CA watchlist tickers with large gaps (>=20%): 16
- CA tickers share of C06 total PnL: 41.0%

Top/bottom 20 PnL tickers: see phase5_top20_pnl_ca_check.csv.

**Risk assessment:**
- CA tickers contribute 41.0% of total PnL.
- If > 30%, CA data contamination is a material risk to the backtest.
- Recommended: obtain adjusted price data for CA tickers before live trading.

---

## H. PAPER-TRADE DECISION

**DECISION: C06 DOWNGRADED — RESEARCH ONLY**

Reason(s):
- OOS Fold1 passed: NO
- TimeStop20 robust: NO
- FT05 adds value: YES
- SZ06 adds value: YES

Next step: extend to 2018-2022 data and re-run Phase 3 before resuming paper trade.

---

## I. PAPER-TRADE OPERATING PLAN

See phase5_paper_trade_plan.md for the full operating plan.

Summary:
- Entry: GK_FAST BUY + VolExp >= 1.2 + ADV50 >= 2B
- Exit: GK_SELL or TimeStop20 (bar 20 if ret <= 0%)
- Size: Equity/10, half when VNINDEX < EMA50
- Review weekly; kill criteria defined in plan.

---

## J. TOP 3 RISKS

1. **Short OOS sample**: Fold 1 covers 2025 (1 year+), Fold 2 covers 2026 (months).
   Both are still bull-recovery period. No true bear market in the test window.
   A 2018-style -30% VNINDEX period would stress-test the system properly.

2. **FT05 data-mining risk**: VolExp threshold of 1.2 was not pre-specified;
   it was discovered as the best overlay in Phase 4. Even though it has an
   economic rationale (strong volume = institutional participation), the 1.2
   level should be treated as approximate, not precise.

3. **Corporate-action contamination**: CA-watchlist tickers have unverified
   price data. If unadjusted CA events inflate returns for VIC/VHM/VRE/VGI,
   the actual edge may be materially lower than reported.

---

## K. NEXT RESEARCH QUESTIONS

1. **Extend to 2018-2022**: if historical data available, run C06 on the
   pre-recovery period. Key check: does active MaxDD stay above -30%?

2. **Adjusted price data**: obtain CA-adjusted OHLCV for VIC/VHM/VRE/VGI/SAB.
   Re-run C06 on adjusted data. If CAGR drops > 5 ppts, the edge is partly
   CA-contaminated and must be investigated before live trading.

3. **FT05 stability across regimes**: track VolExp filter hit rate in live paper
   trading. If hit rate drops (fewer signals pass VolExp), investigate whether
   market liquidity conditions have changed since the 2023-2026 backtest period.
