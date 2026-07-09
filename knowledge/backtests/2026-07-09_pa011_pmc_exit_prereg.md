# Pre-Registration: PA-011 — S20 Price-Magnitude Exit (PM-C, ≥5× Avg Daily Return)
# PA Status: PENDING (full OOS harness not yet run)
# Class: EXIT — overlay_class = exit
# Gate-zero: ACCEPTABLE (44.7% corrected, 2026-07-09)
# Date: 2026-07-09
# Source: Minervini, Think and Trade Like a Champion (2016), Ch. 9

---

## User sign-off (required before harness run)
```
USER SIGN-OFF: [x] checked
Date: 2026-07-09
Signed: V
```

---

## Belief amendment statement (LOCKED)

"When a held A3_RS+S2@1.4× position has a single day whose return is ≥ 5× the
holding-period average daily return (denominator capped at min 2 days), exiting the NEXT
trading day produces better risk-adjusted MAR than holding to the standard A3_RS exit."

Condition definition (LOCKED):
  holding_avg_daily = (exit_price_so_far / entry_price - 1) / max(days_held_so_far, 2)
  PM-C fires if: close_to_close_daily_return_t >= 5.0 × holding_avg_daily
  ACTION: exit at next trading day open. First trigger during hold wins.

---

## Architecture context

- Base: A3_RS+S2@1.4× (OOS MAR 2.5233, MaxDD −5.57%, CAGR 14.05%)
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
G1b_exit: OOS MaxDD >= -0.0557 × 0.60 = -0.0334
G1c_exit: OOS CAGR > 0%
G1d_exit sub-A: OOS sub-A MAR > 0
G1d_exit sub-B: OOS sub-B MAR > 0

trigger_rate_declared: 44.7% (1061/2375 — corrected denominator, 2026-07-09)
parameter_sensitivity_required: NO  (44.7% < 50% — clean ACCEPTABLE range)
two_leg_accounting_required: YES
```

---

## ⚠️ Pre-registered risk flags (must be assessed in harness output)

**Flag 1 — 2020 regime over-trigger (87.4%):**
Gate-zero year breakdown shows PM-C fires on 87.4% of 2020 entry-year positions (306/350).
Portfolio-level rate is 44.7% (ACCEPTABLE) because sub-B years are more moderate.
However 2020 is the heart of sub-A. An 87.4% trigger rate in sub-A effectively makes
PM-C a near-universal exit mechanic for that year — analogous to the count-only failure.
The sub-A MAR gate (G1d sub-A > 0) is the controlling gate for this risk.
If sub-A MAR fails: [ADVERSE-2020-REGIME] annotation, root-cause required.

**Flag 2 — Median fire day = 2:**
PM-C fires at median day 2 of the holding period (exits on day 3).
This means PM-C typically exits before the momentum move extends — the "climax run"
diagnosis may not apply when the exit is that early. An early-exit mechanic that fires
consistently on day 2-3 is more likely to cut winning positions than to avoid exhaustion.
Report: count of Leg A positions with fire_day ≤ 3 vs ≥ 10. If > 50% fire in first 3 days:
flag [EARLY-EXIT-DOMINANT] in harness report. Does not change gates, but needed for
root-cause if PARKED.

**Flag 3 — 2022 near-zero trigger (4.7%):**
PM-C fires on only 7/150 positions in 2022 (bear year). This means PM-C is effectively
inactive in bear regimes — regime-asymmetric. PA-010 (PM-B) fires 26.7% in 2022,
suggesting PM-C and PM-B are measuring different phenomena. Note in report.

---

## Expected direction

Given flags above, expected outcome is more uncertain than PM-B:
- Sub-A (2020-2022): HIGH RISK of degradation due to 2020 over-triggering. The 5× threshold
  is relative to the position's own run-rate, which means in a strong bull (2020), large
  up-days are also occurring on strong-trending stocks — exiting may cut before the main move.
- Sub-B (2023-2026): more moderate trigger rates (33-49%); outcome less predictable.
- CAGR: likely to fall (shorter average holds on firing positions).

This pre-reg does NOT require a favorable directional prior. The harness will determine
the outcome. The flags are disclosed pre-run, not post-hoc.

---

## Kill criterion

If ANY of the following → PM-C PARKED (no re-test without new pre-reg):
- G1a FAIL: OOS MAR < 2.1448
- G1b FAIL: OOS MaxDD < -0.0334
- G1c FAIL: OOS CAGR ≤ 0%
- G1d FAIL: sub-A MAR ≤ 0 OR sub-B MAR ≤ 0

[ADVERSE-REVERSAL]: if OOS MaxDD is WORSE than baseline (−5.57%) → required root-cause note.
[ADVERSE-2020-REGIME]: if sub-A MAR ≤ 0 AND 2020 trigger rate > 80% → cite flag 1 in root-cause.

---

## Scope

IN: A3_RS+S2@1.4× OOS 2020-2026, all 2375 positions
IN: PM-C condition as defined (5× corrected denominator)
OUT: PM-A, PM-B (separate pre-regs)
OUT: B_cloud, OMS, final_action, live_auto, knowledge_ACTIVE.md

---

## Files to create

1. Harness: `pp_backtest/cortex_pa011_pmc_exit.py`
   (or extend cortex_pa010_pmb_exit.py to handle both in one run)
2. Output: `data/research/cortex_pa011_pmc/pa011_oos_report.md`
3. Output: `data/research/cortex_pa011_pmc/pa011_oos_meta.json`

---

## References

- Gate-zero report: `data/research/cortex_s20_pricemag/gatezero_report.md`
- Gate-zero pre-reg: `knowledge/backtests/2026-07-08_s20_pricemag_prereg.md`
- PA-010 pre-reg (PM-B): `knowledge/backtests/2026-07-09_pa010_pmb_exit_prereg.md`
- Exit-class gate template: `D:\V\.claude\rules\verification-harness.md` § Overlay-class gate declaration

## OOS Harness Results

**Run date:** 2026-07-09
**Status:** PARKED [ADVERSE-REVERSAL]

| Gate | Threshold | Value | Result |
|------|-----------|-------|--------|
| OOS MAR | 2.1448 | 0.3082 | FAIL |
| OOS MaxDD | -0.0334 | -0.1900 | FAIL |
| OOS CAGR | 0.0000 | 0.0586 | PASS |
| sub-A MAR | 0.0000 | 2.8708 | PASS |
| sub-B MAR | 0.0000 | -0.1093 | FAIL |

- OOS MAR: 0.3082 (baseline 2.519267974704099)
- Trigger rate: 92.0%
- Median fire day: 11.0
- Root cause: Gate failure: G1a, G1b, G1d_sub_b; MaxDD -0.1900 worse than baseline -0.0557
