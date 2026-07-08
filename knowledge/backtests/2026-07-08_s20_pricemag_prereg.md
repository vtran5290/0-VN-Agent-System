# Pre-Registration: S20 Price-Magnitude Leg — Climax-Top Exit Filter
# PA Status: PENDING (gate-zero screen required before full OOS harness)
# Class: EXIT — overlay_class = exit
# Count-only track: PARKED 2026-07-08 (N=7/10/15 all failed; over-triggered 56-97%)
# Price-magnitude leg: separate pre-reg required — BORDERLINE gate-zero 78.8%
# Date: 2026-07-08
# Source: Minervini, Think and Trade Like a Champion (2016), Ch. 9
#
# GATE-ZERO SCREEN REQUIRED before committing to full OOS harness.
# If gate-zero trigger rate < 30% or > 70% of OOS positions → reassess mechanic.
# THIS IS A PRE-REGISTRATION DOCUMENT — gate parameters locked before data seen.

---

## User sign-off (required before gate-zero screen run)
```
USER SIGN-OFF: [x] checked
Date: 2026-07-08
Signed: V
```

---

## Belief amendment statement (LOCKED)

"The largest single up-day magnitude during a position's entire holding period (measured as a multiple of ATR14 or as a raw % return vs. the holding-period average) predicts demand exhaustion when it exceeds a pre-registered threshold; selling on the next day produces better risk-adjusted MAR than A3_RS+S2@1.4× standard exit."

Key distinction from count-only (PARKED): Count-only fired on ANY day with ≥70% up-days in the window, indiscriminately. Price-magnitude requires that the LARGEST single up-day in the move exceeds a threshold — a necessary condition for Minervini's "climax run" diagnosis.

---

## Architecture context

- Base: A3_RS+S2@1.4× (OOS MAR 2.5233, MaxDD −5.57%, sub-B 1.1312)
- Exit overlay: if climax-run condition fires during a held position → exit the NEXT trading day
- overlay_class: exit
- leverage_available: NO (no re-deployment of freed position at same ADV)

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
baseline_maxdd_measured: -0.0557  # from data/research/cortex_pa009_exit_class/baseline_maxdd.json

G1a_exit: OOS MAR >= 2.5233 × 0.85 = 2.1448
G1b_exit: OOS MaxDD >= -0.0557 × 0.60 = -0.0334  (algebraic; less negative = shallower)
G1c_exit: OOS CAGR > 0%
G1d_exit sub-A: OOS sub-A MAR > 0
G1d_exit sub-B: OOS sub-B MAR > 0

trigger_rate_declared: PM-B 28.4%, PM-C 54.1%, PM-A 4.7% (gate-zero 2026-07-08)
parameter_sensitivity_required: YES if trigger_rate > 50%
two_leg_accounting_required: YES before any exit-class promotion
```

---

## Price-magnitude condition candidates (gate-zero screen)

The price-magnitude leg requires ONE of the following to fire during a held position:

| Candidate | Condition | Rationale |
|-----------|-----------|-----------|
| PM-A | max_single_day_return >= 3.0×ATR14 (on that day) | ATR-normalized; adapts to stock vol |
| PM-B | max_single_day_return >= 8% (absolute threshold) | Raw % magnitude; simpler but non-adaptive |
| PM-C | max_single_day_return >= 5×holding_period_avg_daily_return | Relative to trade's own rhythm |

Gate-zero screen: for each candidate, compute trigger rate on full A3_RS+S2@1.4× OOS signal set.
Lock thresholds before screen such that each would be expected to fire ~30-50% of positions.
Thresholds to pre-register:
- PM-A threshold: **3.0** (× ATR14 on trigger day)
- PM-B threshold: **8%** single-day return
- PM-C threshold: **5** (× holding-period avg daily return)

These values must be pre-registered (written here) BEFORE the gate-zero screen is run.
No threshold changes after gate-zero results are seen.

---

## Gate-zero verdict rules

| Trigger rate | Verdict |
|---|---|
| < 20% | Too rare — condition too strict; reassess threshold before full run |
| 20%–50% | Acceptable range — proceed to full OOS harness |
| 50%–70% | BORDERLINE — include parameter sensitivity (±1 threshold step) |
| > 70% | Over-fires — same failure mode as count-only; do not run full OOS |

If gate-zero fires in 20%-70% range → full OOS harness with exit-class dual gate.
If gate-zero > 70% for ALL candidates → S20 Lane A PARKED (count-only + price-magnitude both closed); S20 belief remains SOURCED but no further Lane A candidate registered without new council.

---

## Prior result context (count-only — do NOT conflate)

S20 count-only harness (PARKED 2026-07-08):
- N=7: OOS MAR 0.2841 (trigger 96%), N=10: 0.5349 (90%), N=15: 0.3133 (56%)
- All below G1b (1.2646 at that time — standalone baseline)
- The count-only mechanic triggered on too many ordinary up-trending positions
- Price-magnitude is a DIFFERENT, more selective condition — do not use count-only results as evidence

---

## Interaction rule

Price-magnitude leg only applies to A3_RS+S2@1.4× positions in isolation.
If both count-AND-magnitude conditions are met simultaneously → price-magnitude fires (stricter).
If only count (≥70% up-days) but not magnitude → do NOT exit (count-only is PARKED).

---

## Files to create (after user sign-off)

1. Gate-zero screen: `pp_backtest/cortex_s20_pricemag_gatezero.py`
2. Full harness (if gate-zero passes): `pp_backtest/cortex_s20_pricemag.py`

---

## References
- Count-only pre-reg: `knowledge/backtests/2026-07-07_s20/` (Cursor-written)
- S20 sourced belief: `knowledge/knowledge_ACTIVE.md` § Sourced Beliefs → S20 row
- Exit-class gate template: `D:\V\.claude\rules\verification-harness.md` § Overlay-class gate declaration
