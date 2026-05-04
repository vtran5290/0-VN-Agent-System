# Phase 4 Research — Final Report

Run date: 2026-05-04

---

## A. FACTS

### Phase 3 Reference
| A2 baseline | 17.4% | 0.52 | -30.3% | 7.1% | 3.1% | 7.8% |
| EX09a (P3 best) | 29.3% | 0.72 | -30.7% | 19.5% | 12.9% | -7.1% |
| EX08 (backup) | 23.9% | 0.71 | -32.4% | 12.6% | 9.1% | 10.4% |

### Phase 4 Combination Results (sorted by MAR)

| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |
|-----|-------|---|------|-----|----------|--------|--------|------|
| C06 | EX09a+FT05+SZ06 | 170 | 22.0% | 0.73 | -27.3% | 12.5% | 8.5% | 2.1% |
| C02 | EX09a+SZ06 | 173 | 26.9% | 0.73 | -29.1% | 19.3% | 12.7% | -11.9% |
| C01 | EX09a_tstop20 | 173 | 29.3% | 0.72 | -30.7% | 19.5% | 12.9% | -7.1% |
| C09 | EX08_ema20 | 285 | 23.9% | 0.71 | -32.4% | 12.6% | 9.1% | 10.4% |
| C08 | EX09a+FT07+FT05+SZ06 | 154 | 20.3% | 0.68 | -27.3% | 7.3% | 4.1% | 7.4% |
| C04 | EX09a+FT05 | 170 | 21.9% | 0.65 | -30.7% | 13.4% | 9.8% | 4.8% |
| C11 | EX08+SZ06 | 285 | 19.9% | 0.64 | -29.7% | 8.6% | 5.2% | 3.9% |
| C07 | EX09a+FT07+FT05 | 154 | 20.1% | 0.62 | -30.0% | 7.3% | 4.1% | 10.5% |
| C05 | EX09a+FT07+SZ06 | 166 | 17.3% | 0.55 | -28.4% | 7.1% | 5.2% | 9.8% |
| C15 | EX03_stop10 | 130 | 18.9% | 0.55 | -27.7% | 6.1% | 2.4% | -2.6% |
| C18 | EX03+FT07+SZ06 | 128 | 15.4% | 0.54 | -25.1% | 3.5% | 2.3% | 6.0% |
| C17 | EX03+SZ06 | 130 | 15.2% | 0.53 | -23.6% | 4.6% | 1.8% | -2.6% |
| C00 | A2_baseline | 111 | 17.4% | 0.52 | -30.3% | 7.1% | 3.1% | 7.8% |
| C16 | EX03+FT07 | 128 | 16.7% | 0.52 | -29.3% | 4.9% | 2.7% | 6.2% |
| C03 | EX09a+FT07 | 166 | 16.9% | 0.48 | -32.3% | 6.9% | 5.1% | 12.8% |
| C12 | EX08+FT07+SZ06 | 240 | 14.2% | 0.45 | -31.9% | 2.8% | 0.1% | 3.7% |
| C10 | EX08+FT07 | 240 | 15.0% | 0.43 | -35.0% | 3.8% | 1.1% | 6.8% |
| C13 | EX08+FT05 | 270 | 14.5% | 0.41 | -36.5% | 7.4% | 0.7% | 2.4% |
| C14 | EX08+FT05+SZ06 | 270 | 12.3% | 0.38 | -34.0% | 4.8% | -1.8% | -2.6% |

### Phase 4 Time Stop Sensitivity (EX09a variants)

| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |
|-----|-------|---|------|-----|----------|--------|--------|------|
| T25_sz06 | tstop25+SZ06 | 155 | 26.3% | 0.86 | -31.9% | 19.1% | 15.2% | 0.2% |
| T25_base | tstop25 | 155 | 26.1% | 0.76 | -33.8% | 19.1% | 14.9% | 2.6% |
| T20_sz06 | tstop20+SZ06 | 173 | 26.9% | 0.73 | -29.1% | 19.3% | 12.7% | -11.9% |
| T20_base | tstop20 | 173 | 29.3% | 0.72 | -30.7% | 19.5% | 12.9% | -7.1% |
| T15_ft07_sz06 | tstop15+FT07+SZ06 | 187 | 17.5% | 0.68 | -22.9% | 3.6% | 1.2% | 16.3% |
| T25_ft07_sz06 | tstop25+FT07+SZ06 | 153 | 18.0% | 0.62 | -26.7% | 6.1% | 3.6% | 11.0% |
| T15_ft07 | tstop15+FT07 | 187 | 17.1% | 0.59 | -26.4% | 3.4% | 1.0% | 19.0% |
| T25_ft07 | tstop25+FT07 | 153 | 17.3% | 0.56 | -29.5% | 5.7% | 3.2% | 13.4% |
| T20_ft07_sz06 | tstop20+FT07+SZ06 | 166 | 17.3% | 0.55 | -28.4% | 7.1% | 5.2% | 9.8% |
| T15_sz06 | tstop15+SZ06 | 208 | 16.1% | 0.53 | -26.5% | 5.4% | 1.3% | 5.0% |
| T30_ft07_sz06 | tstop30+FT07+SZ06 | 146 | 15.2% | 0.50 | -26.9% | 3.5% | 1.1% | 6.9% |
| T20_ft07 | tstop20+FT07 | 166 | 16.9% | 0.48 | -32.3% | 6.9% | 5.1% | 12.8% |
| T15_base | tstop15 | 208 | 17.6% | 0.48 | -32.6% | 4.3% | 0.4% | 5.5% |
| T30_ft07 | tstop30+FT07 | 146 | 14.8% | 0.46 | -29.9% | 3.3% | 1.0% | 7.9% |
| T30_base | tstop30 | 159 | 5.7% | 0.13 | -43.8% | -3.7% | -8.9% | -0.7% |
| T30_sz06 | tstop30+SZ06 | 159 | 5.1% | 0.13 | -38.3% | -1.8% | -6.8% | -2.7% |

### SZ06b Diagnostic

| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |
|-----|-------|---|------|-----|----------|--------|--------|------|
| SZ06b_C01 | EX09a+SZ06b | 173 | 26.9% | 0.73 | -29.1% | 19.3% | 12.7% | -11.9% |
| SZ06b_C11 | EX08+SZ06b | 285 | 19.9% | 0.64 | -29.7% | 8.6% | 5.2% | 3.9% |
| SZ06b_C05 | EX09a+FT07+SZ06b | 166 | 17.3% | 0.55 | -28.4% | 7.1% | 5.2% | 9.8% |

---

## B. BEST COMBINATION

**Best arm: T25_sz06 (tstop25+SZ06) — FAIL**
- CAGR 26.3%  MAR 0.86
- Active MaxDD -31.9%
- ex-top3 CAGR 19.1%  ex-top5 15.2%
- 2024 0.2%  2025 59.1%
- Notes: active_dd -31.9% < -30%

---

## C. EX09a + SZ06 ASSESSMENT (C02)

C02 (EX09a+SZ06): **FAIL**
- CAGR 26.9%  MAR 0.73
- Active MaxDD -29.1%  (A2 baseline: -30.3%)
- ex-top3 19.3%  ex-top5 12.7%
- 2024: -11.9%
- Notes: 2024 ret -11.9% < -8%

---

## D. EX09a + FT07 ASSESSMENT (C03)

C03 (EX09a+FT07): **FAIL**
- CAGR 16.9%  MAR 0.48
- Active MaxDD -32.3%
- ex-top3 6.9%  ex-top5 5.1%
- 2024: 12.8%
- Notes: active_dd -32.3% < -30%; ex-top3 CAGR 6.9% < 10%

---

## E. EX08 BRANCH vs EX09a BRANCH

EX09a best (C01): MAR 0.72  aDD -30.7%  xT3 19.5%
EX08 best (C09):  MAR 0.71  aDD -32.4%  xT3 12.6%
EX09a+FT07+SZ06 (C05): MAR 0.55  aDD -28.4%  xT3 7.1%
EX08+FT07+SZ06 (C12):  MAR 0.45  aDD -31.9%  xT3 2.8%

INTERPRETATION: EX09a branch maintains MAR advantage vs EX08 branch.

---

## F. HARD-STOP BRANCH (EX03)

EX03 only (C15): MAR 0.55  aDD -27.7%  xT3 6.1%
EX03+FT07+SZ06 (C18): MAR 0.54  aDD -25.1%  xT3 3.5%

Hard stop (10%) reduces drawdown risk but at the cost of cutting winners.

---

## G. CONCENTRATION REVIEW

Arms with ex-top3 CAGR >= 12% (required threshold):
  C01          exT3=19.5%  exT5=12.9%  top5_pct=77.7%  top1_tick=24.2%
  T20_base     exT3=19.5%  exT5=12.9%  top5_pct=77.7%  top1_tick=24.2%
  C02          exT3=19.3%  exT5=12.7%  top5_pct=77.7%  top1_tick=24.2%
  T20_sz06     exT3=19.3%  exT5=12.7%  top5_pct=77.7%  top1_tick=24.2%
  SZ06b_C01    exT3=19.3%  exT5=12.7%  top5_pct=77.7%  top1_tick=24.2%
  T25_base     exT3=19.1%  exT5=14.9%  top5_pct=73.3%  top1_tick=27.4%
  T25_sz06     exT3=19.1%  exT5=15.2%  top5_pct=73.3%  top1_tick=27.4%
  C04          exT3=13.4%  exT5=9.8%  top5_pct=71.2%  top1_tick=19.5%
  C09          exT3=12.6%  exT5=9.1%  top5_pct=67.7%  top1_tick=18.0%
  C06          exT3=12.5%  exT5=8.5%  top5_pct=71.2%  top1_tick=19.5%

---

## H. 2024 REVIEW

EX09a's 2024 was -7.1% — the main cost of the time stop. Checking which combinations recover 2024:
  C03          2024=12.8%  MAR=0.48  xT3=6.9%
  C07          2024=10.5%  MAR=0.62  xT3=7.3%
  C09          2024=10.4%  MAR=0.71  xT3=12.6%
  C05          2024=9.8%  MAR=0.55  xT3=7.1%
  C00          2024=7.8%  MAR=0.52  xT3=7.1%
  C08          2024=7.4%  MAR=0.68  xT3=7.3%
  C10          2024=6.8%  MAR=0.43  xT3=3.8%
  C16          2024=6.2%  MAR=0.52  xT3=4.9%
  C18          2024=6.0%  MAR=0.54  xT3=3.5%
  C04          2024=4.8%  MAR=0.65  xT3=13.4%
  C11          2024=3.9%  MAR=0.64  xT3=8.6%
  C12          2024=3.7%  MAR=0.45  xT3=2.8%
  C13          2024=2.4%  MAR=0.41  xT3=7.4%
  C06          2024=2.1%  MAR=0.73  xT3=12.5%
  C15          2024=-2.6%  MAR=0.55  xT3=6.1%
  C14          2024=-2.6%  MAR=0.38  xT3=4.8%
  C17          2024=-2.6%  MAR=0.53  xT3=4.6%

---

## I. PRODUCTION / PAPER-TRADE DECISION

**1 arm(s) qualify for paper trading:**

**C06 (EX09a+FT05+SZ06) — PAPER_TRADE**
- CAGR 22.0%  MAR 0.73
- Active MaxDD -27.3%
- ex-top3 12.5%  ex-top5 8.5%
- 2024 2.1%  2025 49.8%
- Criteria met: MAR 0.73; active_dd -27.3%; ex-top3 12.5%; ex-top5 8.5%; 2024 2.1%; N=170

---

## J. TOP 3 RISKS

1. **2024 regime dependency**: EX09a's time stop is punitive in 2024 (VNINDEX down year).    Any arm that fixes 2024 may be doing so by selectively filtering out the exact period where    the time stop fires most. This is potentially an optimization artifact.    Walk-forward OOS on 2025+ is the only clean test.

2. **Concentration is asymmetric**: ex-top3 CAGR improvement from EX09a is real,    but the base CAGR of 29.3% is also inflated by winners running longer.    The 'improvement' partly reflects selection bias in the remaining portfolio.    Check: do the top trades in EX09a differ materially from A2's top trades?

3. **Short backtest period**: 2023-04/2026 = ~3.3 years, bull-recovery bias.    All CAGR / MAR numbers are inflated vs what a neutral regime would produce.    Active MaxDD of -22% to -30% may look much worse in a genuine bear market.

---

## K. NEXT RESEARCH QUESTIONS

1. **Walk-forward OOS test**: Train on 2023-2024 only, test on 2025-04/2026.    Does best Phase 4 arm maintain MAR > 0.5 OOS?

2. **2024 root-cause**: Identify exactly which positions EX09a time-stops exited in 2024    at a loss, and whether those were CA-contaminated or legitimate losers.    If they were legitimate, the time stop is doing its job. If CA-contaminated, fix data first.

3. **Combination stability**: The best combo arms (e.g. C05) use 3 overlays.    Test each overlay's marginal contribution. Is FT07 + SZ06 doing equal work,    or is one of them doing all the work?