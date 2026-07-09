# Pre-Registration: PA-010 — S20 Price-Magnitude Exit (PM-B, ≥8% Single-Day)
# PA Status: PENDING (full OOS harness not yet run)
# Class: EXIT — overlay_class = exit
# Gate-zero: PROCEED (28.4%, 2026-07-09)
# Date: 2026-07-09
# Source: Minervini, Think and Trade Like a Champion (2016), Ch. 9 — "climax run" exit rule

---

## User sign-off (required before harness run)
```
USER SIGN-OFF: [x] checked
Date: 2026-07-09
Signed: V
```

---

## Belief amendment statement (LOCKED)

"When a held A3_RS+S2@1.4× position has a single day with a close-to-close return ≥ 8%
during its holding period, exiting the NEXT trading day produces better risk-adjusted MAR
than holding to the standard A3_RS exit signal — measured by dual exit-class gate
(G1a MAR floor + G1b MaxDD improvement)."

Key distinction from count-only (PARKED) and PA-008/PA-009:
- Count-only tracked frequency of up-days within a window → over-fired (56-97%)
- PA-008 (50d-MA) used lagging trend exit → over-fired (78.5%), adverse reversal
- PA-009 (trailing ATR stop) used proportional stop → over-fired (74.8%), adverse reversal
- PM-B fires only on a SINGLE extreme day (≥8%) — much more selective (28.4%)
  These are rare climax events, not trend descriptions.

---

## Architecture context

- Base: A3_RS+S2@1.4× (the production signal stack)
- Exit overlay: if any holding-period day has daily return ≥ 8% → exit at NEXT trading day open
- overlay_class: exit
- leverage_available: NO

---

## Overlay-class requirements (per verification-harness.md)

```yaml
overlay_class: exit
baseline_configuration: A3_RS+S2@1.4x
leverage_available: NO
baseline_oos_mar: 2.5233
baseline_oos_maxdd: -0.0557
baseline_oos_cagr: 0.1405
baseline_sub_a_mar: 4.4083
baseline_sub_b_mar: 1.1312
baseline_maxdd_measured: -0.0557

G1a_exit: OOS MAR >= 2.5233 × 0.85 = 2.1448
G1b_exit: OOS MaxDD >= -0.0557 × 0.60 = -0.0334  (algebraic; less negative = shallower)
G1c_exit: OOS CAGR > 0%
G1d_exit sub-A: OOS sub-A MAR > 0
G1d_exit sub-B: OOS sub-B MAR > 0

trigger_rate_declared: 28.4% (675/2375 OOS positions — from gate-zero 2026-07-09)
parameter_sensitivity_required: NO  (28.4% is in 20%-50% clean PROCEED range)
two_leg_accounting_required: YES (before any exit-class promotion)
```

---

## Condition definition (locked)

**PM-B trigger condition:**
- During a held A3_RS+S2@1.4× position, on ANY day from entry+1 through exit-1:
  daily_return = (close_t / close_{t-1}) − 1
  If daily_return >= 0.08 → PM-B fires
- ACTION: exit at next trading day OPEN
- If PM-B never fires during the holding period → position exits at original A3_RS exit date/price

**Important constraints:**
- The 8% threshold is the LOCKED pre-registered value. Do not adjust after seeing results.
- PM-B fires at most once per position (first trigger wins).
- Intraday high is NOT used — only close-to-close daily return.
- VN ±7% price band note: some positions may have 7% ceiling days; these will NOT reach 8%.
  Positions where baseline stock hit ceiling daily but did not trigger PM-B are correctly excluded.
  This is intentional — PM-B requires a TRUE ≥8% close-to-close, not a band-constrained close.

---

## Expected direction

**Hypothesis:** After a climax up-day (≥8%), VN momentum stocks typically mean-revert or stall
in the near term as sellers who held through the move take profit. Early exit captures the
climax gain and avoids the subsequent reversion.

Expected changes vs baseline:
- OOS MAR: improvement (early exit captures extreme up-day; avoids post-climax reversion loss)
- OOS MaxDD: neutral to improvement (shorter hold on winning positions; no effect on losers)
- CAGR: neutral to slight reduction (shorter avg hold on winning positions)
- Sub-B (2023-2026): uncertain — VN market dynamics may differ vs sub-A (2020-2022 bull)

**Direction expectation must hold for ADVANCE:** MAR must improve relative to baseline, not
just "lose less." If MAR degrades, this is an adverse exit mechanic regardless of MaxDD.

---

## Kill criterion

If ANY of the following → PM-B PARKED immediately (no re-test with different threshold without
a new pre-registration):
- G1a FAIL: OOS MAR < 2.1448
- G1b FAIL: OOS MaxDD < -0.0334 (deeper drawdown than baseline × 60% floor)
- G1c FAIL: OOS CAGR ≤ 0%
- G1d FAIL: sub-A MAR ≤ 0 OR sub-B MAR ≤ 0

If ALL gates pass: PM-B status → CONDITIONAL-ADVANCE pending:
- two_leg_accounting verification (exact split-position simulation)
- Opus judgment gate (Trigger #5 class — first exit-overlay promotion in this category)
- Dual-judge: opus + ChatGPT independent verdicts
- User sign-off

[ADVERSE-REVERSAL] annotation: if ALL sensitivity variants (if any are run) show MaxDD
WORSE than baseline, annotate PARKED status as [ADVERSE-REVERSAL] and require root-cause note.
(No sensitivity required at this trigger rate — clause applies if sensitivity is run voluntarily.)

---

## Two-leg accounting specification

Leg A: positions where PM-B fires — these exit early at PM-B trigger +1 day open
Leg B: positions where PM-B does not fire — these exit at original A3_RS exit

Required before any promotion:
- Exact per-position net_return recalculation for Leg A (PM-B exit price replaces original)
- Leg B positions: original exit unchanged
- Combined MAR/MaxDD must be computed from merged Leg A + Leg B return series
- Blended/approximated returns are acceptable for gate screening; exact two-leg simulation required for promotion

---

## Scope

IN SCOPE:
- A3_RS+S2@1.4× OOS signal set (2020-2026), all 2375 positions
- PM-B condition as defined above (≥8% single-day close-to-close return)
- Dual exit-class gate check (G1a + G1b + G1c + G1d)

OUT OF SCOPE:
- B_cloud cross-architecture (FORBIDDEN without separate pre-reg)
- S1+S2 stacking (FORBIDDEN)
- OMS / final_action path (RESEARCH_ONLY)
- Any live_auto or production changes

---

## Files to create

1. Harness: `pp_backtest/cortex_pa010_pmb_exit.py`
2. Output report: `data/research/cortex_pa010_pmb/pa010_oos_report.md`
3. Output JSON: `data/research/cortex_pa010_pmb/pa010_oos_meta.json`
4. Baseline re-check: `data/research/cortex_pa010_pmb/baseline_repro.json`

---

## References

- Gate-zero results: `knowledge/backtests/s20_pricemag_gatezero_results.md`
- Gate-zero pre-reg (thresholds): `knowledge/backtests/2026-07-08_s20_pricemag_prereg.md`
- PA-008 pre-reg (prior exit attempt, 50d-MA): `knowledge/backtests/2026-07-08_pa008_exit_class_prereg_v2.md`
- PA-009 pre-reg (prior exit attempt, trailing): `knowledge/backtests/2026-07-08_pa009_exit_class_prereg_v2.md`
- Exit-class gate template: `D:\V\.claude\rules\verification-harness.md` § Overlay-class gate declaration
- Baseline values: `data/research/cortex_pa007_s2base/baseline_config.json`

## OOS Harness Results

**Run date:** 2026-07-09
**Status:** PARKED [ADVERSE-REVERSAL]

| Gate | Threshold | Value | Result |
|------|-----------|-------|--------|
| OOS MAR | 2.1448 | 0.6236 | FAIL |
| OOS MaxDD | -0.0334 | -0.1493 | FAIL |
| OOS CAGR | 0.0000 | 0.0931 | PASS |
| sub-A MAR | 0.0000 | 1.0940 | PASS |
| sub-B MAR | 0.0000 | 0.4620 | PASS |

- OOS MAR: 0.6236 (baseline 2.519267974704099)
- Trigger rate: 28.3%
- Median fire day: 33.0
- Root cause: Gate failure: G1a, G1b; MaxDD -0.1493 worse than baseline -0.0557
