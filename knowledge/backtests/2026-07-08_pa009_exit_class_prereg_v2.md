# PA-009 2R Partial Exit — Exit-Class Pre-Registration v2

**Date:** 2026-07-08
**Harness:** pp_backtest/cortex_pa009_exit_class.py (to be created by Cursor)
**Baseline:** A3_RS+S2@1.4x OOS MAR = 2.5292 (recomputed 2026-07-08)
**Status:** REDIRECT/RETEST — prior CONDITIONAL-ADVANCE label rescinded by council 2026-07-08
**Council authority:** Opus REDIRECT + Fable GAP + ChatGPT APPROVE (slug: 2026-07-08-1800_VNAgent_ExitOverlayCouncil)
**overlay_class: exit**
**RESEARCH_ONLY_NOT_PRODUCTION**

---

## Overlay-class declaration (required per verification-harness.md § Overlay-class gate declaration)

```
overlay_class:             exit
leverage_available:        NO
  rationale:               VN retail paper pipeline; sizing bounded by ADV constraints;
                           no declared mechanism to re-deploy freed drawdown budget at same ADV.
                           MAR-only gate is therefore invalid — dual gate applies.
baseline_maxdd_measured:   [●] — must be measured by Cursor on same A3_RS+S2@1.4x OOS 2020-2026
                           window BEFORE gate thresholds are confirmed. Blocking precondition.
trigger_rate_declared:     74.8% (measured in screening run, 2026-07-08, 1776/2375 OOS trades)
                           This is a STRUCTURAL MECHANIC CHANGE (>50% trigger rate).
parameter_sensitivity_required: YES (trigger rate > 50% AND single parameter tested)
two_leg_accounting_required:    YES — exact split-position sim required; blended approximation
                           used in v1 screening run is for screening only, not promotion.
```

---

## Claim

When a held A3_RS+S2@1.4x position's high[i] >= entry_price + 4×ATR14 (= 2R where R = 2.0×ATR14), exit half the position on that bar. The remaining half runs to the original A3_RS exit signal.

---

## Gate values (all pre-specified — Cursor fills [●] before run starts)

```
baseline_oos_mar:           2.5292
baseline_oos_maxdd:         [●] — measure on A3_RS+S2@1.4x OOS 2020-2026 before setting thresholds
baseline_oos_cagr:          [●] — measure on same window

G1a_exit:   OOS MAR    >= baseline_oos_mar   × 0.85  = [●] (= 2.5292 × 0.85)
G1b_exit:   OOS MaxDD  <= baseline_oos_maxdd × 0.60  = [●] (= baseline_maxdd × 0.60)
G1c_exit:   OOS CAGR   > 0%
G1d_exit_a: sub-A MAR  > 0
G1d_exit_b: sub-B MAR  > 0

Kill criterion:
  If OOS MAR < baseline × 0.50: PARKED (catastrophic MAR decay)
  If OOS MaxDD > baseline_maxdd: PARKED (exit overlay worsened drawdown — structurally broken)
  If sub-B MAR < 0: PARKED (destroys choppy regime)
```

---

## Parameter sensitivity (required — trigger rate > 50%)

Test the following parameter variants on the SAME OOS window. All must be run before promotion:

| Candidate | 2R factor | ATR stop | Description |
|-----------|-----------|----------|-------------|
| pa009_v2_2r_base | 2.0 | 2.0×ATR14 | Base case (same as v1 screening) |
| pa009_v2_1r5 | 1.5 | 2.0×ATR14 | Tighter partial exit threshold |
| pa009_v2_2r5 | 2.5 | 2.0×ATR14 | Looser partial exit threshold |

All three run against same baseline pool. Promotion requires base case to pass G1a/G1b AND the result must not be a single-point spike (±1 variant results must be within 0.3 MAR of base case).

---

## Two-leg accounting (required — replace blended approximation)

v1 used: `net_return = 0.5 * return_at_2R + 0.5 * original_return` (blended proxy)

v2 must use: exact split-position simulation
- Leg A: half weight, exit on 2R trigger day, exit price = min(target_2r, close[i]) (intraday conservative fill)
- Leg B: half weight, runs to original exit date, exit price = original exit price
- Each leg contributes independently to the capital simulation as a separate position

The capital simulator must handle two separate PreparedTrade objects from the same entry event. Confirm the sim does not deduplicate or collapse same-day same-symbol entries before proceeding.

---

## Scope

IN SCOPE:
- A3_RS+S2@1.4x OOS trades with 2R partial exit applied (exit-class overlay)
- Three parameter variants (1.5×, 2.0×, 2.5× 2R factor)
- Exact two-leg position accounting
- Parameter sensitivity table
- Baseline MaxDD measurement on same OOS window

OUT OF SCOPE:
- Any change to entry logic or S2 filter
- Combining 2R partial exit with ATR trailing stop on remaining leg (separate PA)
- S1+S2 stacking (FORBIDDEN)
- B_cloud cross-architecture (FORBIDDEN)
- Any OMS path, final_action, live_auto, or cloud reports
- Retroactive credit from v1 screening run

---

## Gate status precedence

This v2 pre-reg supersedes the v1 gate (2026-07-08_pa009_exit_prereg.md). The v1 screening result (OOS MAR 1.8779, MaxDD 5.57%) is SCREENING EVIDENCE ONLY — not a promotion verdict. First application of the exit-class dual gate to PA-009 = Trigger #5-class event per verification-harness.md (unproven rule) — requires dual-judge (opus + ChatGPT) after the run.

---

## Baseline measurement instruction (Cursor blocking precondition)

Before writing final gate threshold values, Cursor must run and record:
```python
# Measure baseline A3_RS+S2@1.4x OOS MaxDD and CAGR
# Same pipeline as cortex_exit_overlays.py Step 1
# Output to: data/research/cortex_pa009_exit_class/baseline_maxdd.json
{
  "baseline_oos_mar": 2.5292,
  "baseline_oos_maxdd": [measured value],
  "baseline_oos_cagr": [measured value],
  "window": "2020-2026",
  "measured_date": "YYYY-MM-DD"
}
```
Then compute G1b_exit = baseline_oos_maxdd × 0.60 and record in pre-reg v2 amendment.
