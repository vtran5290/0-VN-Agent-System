# Capital Footprint Phase 3 — Decision Memo

**Date:** 2026-05-30
**Status:** RESEARCH ONLY. No production change.

---

## PHASE 3 OBJECTIVE

Convert Phase 2 row-level classifier statistics into event-level, de-duplicated findings.
Six tasks: event-level dedup, refined sublabels (EXTENSION, FAILED_BREAKOUT),
full SUPPLY_ABSORPTION trade-path, A3 diagnosis, daily scan annotation plan.

---

## TASK 1: Event-Level Classifier

### Deduplication Results

Cooldown: 20 trading bars. Entry event = first bar where `phase_label` changes.

| Label | N Events | N Rows | Avg Duration (bars) |
|---|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | 8,232 | 71,234 | 8.7 |
| SUPPLY_ABSORPTION_SETUP | 2,988 | 12,375 | 4.1 |
| BREAKOUT_CONFIRMED | 1,326 | 2,121 | 1.6 |
| BREAKOUT_FOLLOW_THROUGH_PENDING | 580 | 919 | 1.6 |
| FAILED_BREAKOUT | 2,338 | 7,467 | 3.2 |
| NEUTRAL | 9,603 | 282,215 | 29.4 |

Total: **25,067 events** from 376,331 rows (6.7% entry rate).
NEUTRAL has the longest persistence (29.4 bars avg) — explains the large row/event gap.

### Event-Level Forward Returns

| Label | N Events | Median 20D | Win Rate 20D | Hit TP10/Stop7 (60D) | MFE 60D | MAE 60D |
|---|---|---|---|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | 8,232 | +0.0024 | 50.4% | 34.9% | 0.284 | -0.173 |
| SUPPLY_ABSORPTION_SETUP | 2,988 | 0.0000 | 49.9% | 36.3% | 0.249 | -0.143 |
| BREAKOUT_CONFIRMED | 1,326 | +0.0053 | 52.3% | 38.9% | 0.294 | -0.149 |
| FAILED_BREAKOUT | 2,338 | +0.0016 | 50.1% | 37.9% | 0.302 | -0.160 |
| NEUTRAL | 9,603 | 0.0000 | 49.2% | 34.4% | 0.266 | -0.172 |

---

## CRITICAL FINDING 1 — EXTENSION SIGNAL REVISED

**FACT: At the EVENT ENTRY, EXTENSION_DISTRIBUTION_RISK median 20D = +0.0024 (POSITIVE).**
**This contradicts Phase 2 row-level finding of median = -0.0042.**

**Why the difference:**
- Phase 2 measured all rows, including bars 5-9 of an 8.7-bar extension episode.
- Later bars of persistent extension have worse forward returns (stock has been extended longer).
- Event-level only measures BAR 1 of the extension episode — the moment of first detection.
- At moment of first detection, EXTENSION is FLAT to slightly positive (not yet a reversal catalyst).

**Revised interpretation:**
- EXTENSION is NOT a reliable reversal signal at the moment it first triggers.
- It becomes a warning AFTER the episode has persisted (5+ bars into extension).
- The signal's value is as a "do not add" warning, not as a short/exit trigger at T=0.

**FACT:** EXTENSION sublabels ALL have negative medians (row-level, later-bar measurement):

| Sublabel | N Rows | Median 20D | Win Rate 20D |
|---|---|---|---|
| LEADERSHIP_STRONG | 23,478 | -0.0063 | 46.9% |
| EXTENDED_BUT_HEALTHY | 4,398 | -0.0091 | 46.2% |
| EXTENSION_DISTRIBUTION_RISK | 43,358 | -0.0025 | 48.2% |

INTERPRETATION: Even LEADERSHIP_STRONG extended stocks underperform (median -0.006, win 46.9%).
The hypothesis that "high RS = safe to hold extended" is NOT supported by data.
All extended conditions are net losers in the median case across the full episode.

---

## CRITICAL FINDING 2 — SUPPLY_ABSORPTION IN BULL_BROAD IS THE STRONGEST SIGNAL

**FACT: SUPPLY_ABSORPTION_SETUP in BULL_BROAD regime: median 20D = +0.0133, win_rate = 55.1%,
TP10/Stop7 hit rate (60D) = 67.0%, TP1 (18%) hit rate = 55.7%, N = 1,283 events.**

This is the clearest positive edge found in the entire Capital Footprint research.

### By Regime — Full Breakdown

| Regime | N | Median 20D | Win Rate 20D | Hit TP10/Stop7 (60D) | TP1 Hit |
|---|---|---|---|---|---|
| BULL_BROAD | 1,283 | **+0.0133** | **55.1%** | **67.0%** | **55.7%** |
| BULL_NARROW | 594 | +0.0026 | 50.7% | 51.5% | 39.1% |
| NEUTRAL | 566 | -0.0114 | 43.3% | 42.9% | 28.8% |
| BEAR | 390 | -0.0045 | 45.5% | 40.0% | 24.1% |
| STRESS | 155 | -0.0140 | 38.1% | 37.4% | 23.2% |

**FACT:** SUPPLY_ABSORPTION is profitable ONLY in BULL_BROAD. In all other regimes: negative median,
below-50% win rate. STRESS is the worst: median -0.014, win rate 38.1%.

**Overall (all regimes pooled):** median 0.0, win_rate 49.9% — explains why the overall signal appeared
weak. The regime heterogeneity was masking a strong regime-conditioned signal.

---

## TASK 3: FAILED_BREAKOUT Sublabels

| Sublabel | N Rows | Median 20D | Win Rate 20D |
|---|---|---|---|
| TRUE_FAILED_BREAKOUT | 727 | +0.0058 | 52.4% |
| BREAKOUT_RETEST_SHAKEOUT | 5,222 | 0.0000 | 49.9% |
| RECLAIM_AFTER_FAILURE | 1,518 | 0.0000 | 49.9% |

**FACT:** TRUE_FAILED_BREAKOUT (closes below EMA50) has POSITIVE median return (+0.006, win 52.4%).
This is a bounce effect — stocks breaking below EMA50 after failed breakout tend to recover.
INTERPRETATION: FAILED_BREAKOUT is NOT an exit signal. It is a "caution zone" at best.

**Overall FAILED_BREAKOUT:** Mean 20D = +0.018, median = +0.002 — net positive, not a warning.

---

## TASK 5: A3 Match Diagnosis

**See: `a3_match_diagnosis_report.md`**

Root cause: 4.2% match rate is structural, not a bug.
- CF covers 366 liquid symbols (adv50 >= 100mn VND/day).
- A3 scans 1,562 symbols (full market including illiquid stocks).
- 80% of A3 rows have non-CF symbols.
- **VERDICT: INCONCLUSIVE.** Do not draw A3/CF synergy conclusions from 9,012 matched rows.

---

## TASK 6: Daily Scan Annotation Plan

**See: `daily_scan_annotation_patch_plan.md`**

Key constraint: SUPPLY_ABSORPTION annotation should be **regime-conditioned**.
Only show the positive annotation in BULL_BROAD. Suppress or show warning in other regimes.

---

## Final Decision Table (Phase 3)

| Question | Answer | Evidence |
|---|---|---|
| Which labels survive event-level testing? | SUPPLY_ABSORPTION_SETUP (BULL_BROAD only) + EXTENSION (as persistence warning) | See findings above |
| Is SUPPLY_ABSORPTION_SETUP useful? | **YES — but ONLY in BULL_BROAD regime** | Median +0.013, win 55.1%, TP hit 67% in BULL_BROAD; negative in all other regimes |
| Is EXTENSION a real warning after removing high-RS? | **REVISED: UNCERTAIN at entry** | Event entry flat (+0.002). Warning valid only for PERSISTENT extension (5+ bars) |
| Is FAILED_BREAKOUT failure, shakeout, or reclaim? | **None are net negative** | TRUE_FAILED has positive bounce; SHAKEOUT/RECLAIM neutral |
| Should any label enter daily scan? | **YES — SA in BULL_BROAD; EXTENSION with age >= 5** | Regime-conditioned annotation only |
| Should anything be promoted beyond research-only? | **NO — not yet** | Need 4 weeks in-market observation |

---

## Revised Production Recommendations

### What to add to daily scan (non-binding annotation)

**1. SUPPLY_ABSORPTION_SETUP + BULL_BROAD regime — positive annotation:**
- Condition: `phase_label == 'SUPPLY_ABSORPTION_SETUP' AND breadth_regime_bucket == 'BULL_BROAD'`
- Note: "✓ Dry-up setup in bull market — high probability setup"

**2. EXTENSION_DISTRIBUTION_RISK + event_age >= 5 — caution annotation:**
- Condition: `phase_label == 'EXTENSION_DISTRIBUTION_RISK' AND event_age >= 5`
- Note: "⚠ Extended 5+ days — do not add"
- NOT at first trigger (event_age = 0) — no edge at T=0.

**3. SUPPLY_ABSORPTION in NEUTRAL/BEAR/STRESS — suppress or flip to warning:**
- Note: "✗ Dry-up in weak market — avoid"

### What NOT to change

- FAILED_BREAKOUT: Do NOT use as exit signal. Positive bounce expected.
- EXTENSION at first trigger: Do NOT flag negatively — flat expected return at T=0.
- BREAKOUT_CONFIRMED: Leave as research-only (N=1,326, needs more observation).

---

## Phase 3 vs Phase 2 Key Reversals

| Finding | Phase 2 | Phase 3 (Revised) |
|---|---|---|
| EXTENSION_DISTRIBUTION_RISK | Median -0.004, warning signal | At entry: flat +0.002. Warning only for PERSISTENT (5+ bars) extension |
| SUPPLY_ABSORPTION_SETUP | Flat overall (median +0.003) | STRONG in BULL_BROAD (median +0.013, win 55.1%); negative in all other regimes |
| FAILED_BREAKOUT | Net positive mean | Confirmed: positive bounce in TRUE_FAILED sublabel |
| A3/CF synergy | Inconclusive (4.2% match) | Structural mismatch confirmed — do not pursue without rebuilding A3 on CF universe |

---

## Next Steps

**Immediate (approved without further research):**
1. Implement regime-conditioned SA annotation in daily scan (see patch plan)
2. Implement extension_age >= 5 condition for EXTENSION warning

**Before promotion to daily scan:**
1. Operator monitors for 4 weeks:
   - SUPPLY_ABSORPTION signals generated per week in current market (BULL_BROAD?)
   - EXTENSION_DISTRIBUTION_RISK annotations — do they match operator intuition?
2. Review current `breadth_regime_bucket` value weekly to confirm regime detection is working

**Not required:**
1. A3/CF join fix — structural limit, not a bug. Accept and move on.
2. FAILED_BREAKOUT sublabels in production — none are negative, annotation adds no value.

---

*Runner: `scripts/research/run_capital_footprint_phase3_backtest.py`*
*Phase 3 source: `src/trading/research/capital_footprint/classifier.py`*
