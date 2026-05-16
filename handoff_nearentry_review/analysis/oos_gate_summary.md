# OOS Gate Summary

Generated: 2026-05-14 | Optimization epoch: 2012-2026 | Universe: ex_VIN3 / full

> **Caveat:** Parameters were selected on the full 2012-2026 sample. Subperiod analysis is a STABILITY check, not a pure walk-forward OOS test. The 2023-2026 subperiod is the most relevant near-term regime signal.

## Survival Criteria

- OOS capture (2023-2026 delta / full-sample delta) >= 50%
- Positive Sharpe delta in >= 2 of 3 subperiods
- maxDD in 2023-2026 must not deteriorate vs baseline by > 10pp
- Verdict: **PASS** = meets all criteria, **PASS_DD_WARN** = passes but DD flag, **FRAGILE** = partial, **FAIL** = fails, **NEUTRAL** = delta too small to judge


## PRIMARY Candidates (B_cloud20_100)


### PRIMARY Subperiod Performance

| candidate_id | label | period | cagr | sharpe | max_dd | mar | n_trades | hit_rate | avg_trade | avg_hold_bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | baseline | 2012-2017 | 14.1% | 1.457 | -9.3% | 1.520 | 3778 | 72.7% | 7.69% | 140 |
| A1 | baseline | 2018-2022 | 12.5% | 1.379 | -24.8% | 0.503 | 4638 | 68.8% | 4.17% | 144 |
| A1 | baseline | 2023-2026 | 8.3% | 0.661 | -28.2% | 0.295 | 4477 | 68.3% | 6.15% | 131 |
| A1 | baseline | full_sample | 12.1% | 1.157 | -30.0% | 0.404 | 12893 | 69.8% | 5.89% | 138 |
| A2 | ranking_upg | 2012-2017 | 14.6% | 1.501 | -8.6% | 1.689 | 3778 | 72.7% | 7.69% | 140 |
| A2 | ranking_upg | 2018-2022 | 20.8% | 1.950 | -12.4% | 1.667 | 4638 | 68.8% | 4.17% | 144 |
| A2 | ranking_upg | 2023-2026 | 5.8% | 0.538 | -31.1% | 0.187 | 4477 | 68.3% | 6.15% | 131 |
| A2 | ranking_upg | full_sample | 14.5% | 1.381 | -32.1% | 0.454 | 12893 | 69.8% | 5.89% | 138 |
| A3 | exit_upg | 2012-2017 | 16.5% | 1.466 | -10.4% | 1.592 | 3778 | 70.2% | 8.64% | 151 |
| A3 | exit_upg | 2018-2022 | 10.8% | 0.997 | -24.8% | 0.433 | 4638 | 66.4% | 4.90% | 154 |
| A3 | exit_upg | 2023-2026 | 13.2% | 1.031 | -15.8% | 0.838 | 4477 | 65.6% | 6.66% | 140 |
| A3 | exit_upg | full_sample | 13.6% | 1.182 | -26.5% | 0.513 | 12893 | 67.2% | 6.61% | 148 |
| A4 | combined | 2012-2017 | 17.8% | 1.644 | -9.7% | 1.833 | 3778 | 70.2% | 8.64% | 151 |
| A4 | combined | 2018-2022 | 19.3% | 1.725 | -14.0% | 1.374 | 4638 | 66.4% | 4.90% | 154 |
| A4 | combined | 2023-2026 | 5.0% | 0.469 | -21.6% | 0.234 | 4477 | 65.6% | 6.66% | 140 |
| A4 | combined | full_sample | 15.1% | 1.352 | -26.8% | 0.562 | 12893 | 67.2% | 6.61% | 148 |
| A5 | exit_15_20 | 2012-2017 | 16.3% | 1.632 | -9.9% | 1.640 | 3778 | 72.8% | 6.84% | 135 |
| A5 | exit_15_20 | 2018-2022 | 17.5% | 1.555 | -15.3% | 1.144 | 4638 | 68.9% | 3.69% | 139 |
| A5 | exit_15_20 | 2023-2026 | 8.9% | 0.711 | -22.5% | 0.394 | 4477 | 68.4% | 6.06% | 126 |
| A5 | exit_15_20 | full_sample | 14.9% | 1.321 | -33.8% | 0.440 | 12893 | 69.9% | 5.44% | 134 |

### PRIMARY — OOS Gate Verdicts

| ID | Label | Sharpe delta (full) | Sharpe delta (OOS) | OOS capture | Periods improved | DD in OOS | Verdict | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | baseline | (baseline) | (baseline) | — | — | — | — | — |
| A2 | ranking_upg | +0.224 | -0.122 | -55% | 2/3 | -2.9% | **FAIL** | OOS reversal (-0.122) |
| A3 | exit_upg | +0.025 | +0.370 | 1504% | 2/3 | +12.4% | **PASS** | OOS capture 1504%, wins 2/3 periods |
| A4 | combined | +0.195 | -0.192 | -99% | 2/3 | +6.6% | **FAIL** | OOS reversal (-0.192) |
| A5 | exit_15_20 | +0.164 | +0.050 | 30% | 3/3 | +5.7% | **FRAGILE** | OOS capture 30%, wins 3/3 periods |

## SHADOW Candidates (B_cloud21_55)


### SHADOW Subperiod Performance

| candidate_id | label | period | cagr | sharpe | max_dd | mar | n_trades | hit_rate | avg_trade | avg_hold_bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | baseline | 2012-2017 | 6.6% | 0.690 | -21.4% | 0.309 | 5014 | 72.1% | 6.60% | 141 |
| S1 | baseline | 2018-2022 | 15.0% | 1.572 | -19.0% | 0.789 | 6483 | 65.7% | 2.15% | 149 |
| S1 | baseline | 2023-2026 | 6.3% | 0.446 | -33.7% | 0.187 | 5626 | 68.6% | 6.67% | 130 |
| S1 | baseline | full_sample | 9.4% | 0.825 | -34.6% | 0.272 | 17123 | 68.5% | 4.94% | 140 |
| S2 | opt_exvin3 | 2012-2017 | 9.4% | 1.034 | -15.5% | 0.605 | 5014 | 69.4% | 8.73% | 161 |
| S2 | opt_exvin3 | 2018-2022 | 16.8% | 1.630 | -12.4% | 1.358 | 6483 | 62.6% | 3.56% | 168 |
| S2 | opt_exvin3 | 2023-2026 | 7.3% | 0.512 | -21.5% | 0.341 | 5626 | 65.6% | 7.35% | 147 |
| S2 | opt_exvin3 | full_sample | 11.5% | 1.003 | -27.4% | 0.419 | 17123 | 65.6% | 6.32% | 159 |
| S3 | opt_full | 2012-2017 | 10.4% | 1.114 | -15.5% | 0.667 | 5057 | 69.2% | 8.69% | 162 |
| S3 | opt_full | 2018-2022 | 16.5% | 1.647 | -12.4% | 1.333 | 6556 | 62.4% | 3.47% | 169 |
| S3 | opt_full | 2023-2026 | 7.8% | 0.537 | -21.5% | 0.361 | 5694 | 65.5% | 7.57% | 147 |
| S3 | opt_full | full_sample | 11.9% | 1.037 | -27.4% | 0.434 | 17307 | 65.4% | 6.34% | 159 |

### SHADOW — OOS Gate Verdicts

| ID | Label | Sharpe delta (full) | Sharpe delta (OOS) | OOS capture | Periods improved | DD in OOS | Verdict | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | baseline | (baseline) | (baseline) | — | — | — | — | — |
| S2 | opt_exvin3 | +0.178 | +0.067 | 38% | 3/3 | +12.2% | **FRAGILE** | OOS capture 38%, wins 3/3 periods |
| S3 | opt_full | +0.213 | +0.092 | 43% | 3/3 | +12.2% | **FRAGILE** | OOS capture 43%, wins 3/3 periods |

---

## Decision Summary

**A. Best PRIMARY candidate after OOS gate:**

  A3 (exit upgrade only: ema_dist + 18%/2.5) — only exit upgrade survives; ranking upgrade rejected.

**B. Best SHADOW candidate after OOS gate:**

  S3 (mom20 + 18%/3.5 + FULL) — FRAGILE but wins 3/3 periods with strong DD improvement. Advances to Step 3 CONDITIONALLY with active monitoring.

**C. Ranking upgrade (ema_dist_mom60) survives?** FAIL

**D. Exit upgrade (18%/2.5) survives?** PASS

**E. Combined upgrade (A4) survives?** FAIL

**F. A5 (15%/2.0) rejected?** YES — reject 15%/2.0 per decision rule

**G. Shadow full universe?** CONDITIONAL — S3 (full) advances under monitoring; fall back to ex_vin3 if live diverges


**Which config should advance to Step 3 sizing overlays?**

  PRIMARY: A3 — ema_dist + tp=18% / trail=2.5 + ex_vin3
  SHADOW: per above


**H. Should paper-trade spec be updated now?**

  NO — OOS gate only confirms survival, not superiority in live execution. Paper-trade spec should only be updated after Step 3 (sizing) confirms that the new config also survives the sizing overlay tests AND after a paper-trade dry-run period.


---

*End of OOS Gate Summary*
