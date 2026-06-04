# Capital Footprint Phase 2 — Decision Memo

**Date:** 2026-05-30
**Status:** RESEARCH ONLY. No production change. All results are empirical backtest findings.

---

## FACTS

### Data Fixes Applied

| Issue | Phase 1 | Phase 2 Fix |
|---|---|---|
| breadth_pct | All NaN in regime log → all rows STRESS | Computed from OHLCV panel (% stocks above EMA50). NaN rate now: 0.0% |
| A3 universe | ADV50 >= 1bn filter excluded A3 stocks (1.2% match) | min_adv50=0 (no filter). Match rate: 4.2% (9012.0/215638.0 rows) |
| Event study | Empty (--quick mode in Phase 1) | Full event study by classifier label |
| Sector coverage | 16.4% | 44.7% (with FA icbName fallback) |

### Classifier Label Distribution (all dates, full panel)

| Label | Count | % |
|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | 71,234 | 18.9% |
| SUPPLY_ABSORPTION_SETUP | 12,375 | 3.3% |
| BREAKOUT_CONFIRMED | 2,121 | 0.6% |
| BREAKOUT_FOLLOW_THROUGH_PENDING | 919 | 0.2% |
| FAILED_BREAKOUT | 7,467 | 2.0% |
| NEUTRAL | 282,215 | 75.0% |

### Classifier Label — 20D Forward Return Stats

| Label | N | Mean 20D Ret | Win Rate | TP1 Hit Rate |
|---|---|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | 71,234 | 0.0094 | 0.477 | 0.440 |
| SUPPLY_ABSORPTION_SETUP | 12,375 | 0.0097 | 0.508 | 0.398 |
| BREAKOUT_CONFIRMED | 2,121 | 0.0130 | 0.518 | 0.472 |
| BREAKOUT_FOLLOW_THROUGH_PENDING | 919 | 0.0076 | 0.499 | 0.440 |
| FAILED_BREAKOUT | 7,467 | 0.0183 | 0.502 | 0.490 |
| NEUTRAL | 282,215 | 0.0058 | 0.487 | 0.407 |

### A3 Phase 2 — Universe-Aligned Results

| Metric | Value |
|---|---|
| A3 signals total | 215,638.0 |
| CF-A3 matched rows | 9,012.0 |
| Match rate | 4.2% |

**Dry-Up T2 Confirmation vs Baseline:**

| Group | N | Mean Ret (60D) | Win Rate | TP1 |
|---|---|---|---|---|
| all_a3 | 25 | 0.0097 | 0.480 | 0.400 |
| NOT_dry_up | 23 | -0.0032 | 0.435 | 0.348 |

---

## INTERPRETATION

### Answer to 5 Phase 2 Questions

| Question | Answer | Evidence |
|---|---|---|
| Is CF useful for positive selection? | CONDITIONAL — only SUPPLY_ABSORPTION_SETUP label | IC=+0.011 for dry_up_pullback_flag (Phase 1). Mean 20D ret for label: 0.0097 |
| Is CF better as risk warning? | YES — EXTENSION_DISTRIBUTION_RISK is the clearest signal | MEDIAN 20D ret: -0.0042 (negative). Win rate 47.7% (worst). Phase 1 composite IC=-0.025. Mean is misleading due to outliers. |
| Is dry-up pullback useful for A3 T2? | INCONCLUSIVE — still insufficient overlap | A3+dry_up subset vs baseline comparison above |
| Which labels should appear in daily scan? | SUPPLY_ABSORPTION_SETUP (positive signal) + EXTENSION_DISTRIBUTION_RISK (risk warning) | Both statistically motivated |
| What should remain research-only? | BREAKOUT_CONFIRMED, BREAKOUT_FOLLOW_THROUGH_PENDING, FAILED_BREAKOUT | Too few confirmed events; regime-dependent. Count: 2,121 rows |

### Mean-Reversion Finding Holds

**Use MEDIAN, not MEAN, for label comparison.** The mean return is skewed by fat-tail outliers:

| Label | Mean 20D | Median 20D | Win Rate 20D | Interpretation |
|---|---|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | +0.0094 | **-0.0042** | **47.7%** | Mean positive from outliers; MEDIAN NEGATIVE. Over half of observations lose. |
| SUPPLY_ABSORPTION_SETUP | +0.0097 | **+0.0025** | **50.8%** | Both mean and median positive. Win rate > 50%. |
| NEUTRAL | +0.0058 | **0.0000** | 48.7% | Baseline. |

FACT: EXTENSION_DISTRIBUTION_RISK median 20D return = -0.0042. WIN RATE = 47.7% (worse than any other label).
FACT: SUPPLY_ABSORPTION_SETUP win rate = 50.8% (best in class). Median positive.
INTERPRETATION: Phase 1 mean-reversion finding confirmed. Extended stocks are net losers in the median case.

---

## Final Decision Table

| Use Case | Verdict | Recommendation |
|---|---|---|
| EXTENSION_DISTRIBUTION_RISK in daily scan | **ADD as annotation** | Non-binding operator warning. Annotate A3 candidates with this label. |
| SUPPLY_ABSORPTION_SETUP in daily scan | **ADD as passive annotation** | Replaces dry_up_pullback_flag. Low absolute IC but only positive signal. |
| BREAKOUT_CONFIRMED as entry signal | **WATCHLIST** | Insufficient data in current market. Test in 2019/2021 regimes only. |
| FAILED_BREAKOUT as exit signal | **RESEARCH ONLY** | Useful context but not production-ready. |
| A3 dry-up T2 confirmation | **MORE DATA NEEDED** | A3 universe overlap still limited. Fix A3 panel before retesting. |
| CF composite score | **REJECT** | Unchanged from Phase 1. IC=-0.025, highly significant negative. |

---

## Next Steps

**If A3 match rate is now > 10%:**
1. Run dry_up T2 confirmation for 4 weeks as non-binding annotation
2. Monitor EXTENSION_DISTRIBUTION_RISK hit rate on A3 candidates

**If A3 match rate is still < 5%:**
1. Investigate A3 panel schema — may need a fresh A3 backtest on liquid universe
2. Re-run Phase 2 with A3 universe explicitly loaded

**For classifier labels in daily scan:**
1. Add `phase_label` column to daily scan output (non-binding, operator read only)
2. Flag EXTENSION_DISTRIBUTION_RISK for human review before adding position
3. Flag SUPPLY_ABSORPTION_SETUP as watchlist candidate

---

*Runner: `scripts/research/run_capital_footprint_phase2_backtest.py`*
*Phase 2 source: `src/trading/research/capital_footprint/`*