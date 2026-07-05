# Pre-Registration — Interaction Test: Sector Cap + Inverse-Vol Sizing (Tier 2b)

**Date filed:** 2026-07-03
**Status:** RUN COMPLETE — 2026-07-03 (`sprint2d_interaction_sectorcap_volsizing.py`)
**Council approval:** Pending — filed to enable immediate execution if promotion evidence clears
**Preceded by:**
- Sprint 2B-C1 vol-sizing → CONDITIONAL-ADVANCE (confirmation-only)
- Sprint 2c sector cap 35% → CONDITIONAL-ADVANCE
- Promotion evidence pack (`data/research/portfolio_optimization/promotion_evidence/`)

## Purpose

Test whether sector cap (35%) and inverse-vol sizing are **additive** when layered
on the operational stack, or whether vol-sizing's de-weighting of high-vol names
(many of which are high-concentration) causes the sector cap to rarely bind.

**This is a COMBINED interaction test — not a new candidate design.** No parameter
tuning. Kelly explicitly rejected.

## Frozen baseline

A3 + D4 (iPower) + D3 sector tilt **1.25/0.75** (operational — NOT 1.35/0.65),
P1 honest exit (`build_a3_honest_trades` / `d3_size_neighbor.py` wiring),
capital-based accounting.

Reference numbers (pre-run, from prior sprints):
- Full-sample MAR **0.532**, MaxDD **-14.26%**
- Primary OOS (last 12mo): baseline MAR **-0.891**
- Confirmation OOS (prior 12mo, mechanical): baseline MAR **+0.537** (positive)

## Combined candidate spec (fixed)

Layer **both** mechanisms on the operational baseline:

1. **Inverse-vol sizing** (Sprint 2B-C1 spec): 20d realized vol, 15% floor,
   `weight_i = (1/vol_i)/sum(1/vol_j)*n` per entry-date cohort, on top of D3 tilt.
2. **Sector hard cap** (Sprint 2c spec): no sector > **35% of NAV** at entry;
   skip/clip to next-highest RS when breached.

Order of application: D3 tilt mult → inverse-vol mult → sector cap at capital sim entry.

## Windows (pre-committed — do not change post-run)

| Window | Rule | Expected dates (as of 2026-07-03 data) |
|--------|------|----------------------------------------|
| Full sample | All equity | 2012–2026 |
| Primary OOS | `slice_equity_last_months(eq, 12)` | ~2025-07 to 2026-07 |
| Confirmation OOS | `slice_equity_prior_months(eq, 12, 12)` | ~2024-07 to 2025-07 |

## Pre-registered gates

Per `verification-harness.md` promotion gate design. Thresholds **fixed before run**.

### Full-sample

| Gate | Criterion |
|------|-----------|
| G1b | Combined full-sample MAR ≥ **0.532** |
| G4 | Frozen-A3 entry stream identical to baseline |

### Primary OOS window

| Gate | Criterion |
|------|-----------|
| G1a | Combined OOS MAR ≥ baseline OOS MAR + **0.10** (≥ **-0.791**) |
| G_neg | If both baseline and combined OOS MAR negative → max verdict **CONDITIONAL-ADVANCE** |

### Confirmation OOS window

| Gate | Criterion |
|------|-----------|
| G1a_confirm | Combined OOS MAR ≥ baseline OOS MAR + **0.10** on confirmation window |
| G_confirm_pos | If baseline OOS MAR **positive** on confirmation window: combined must not degrade by > **0.05** MAR vs baseline |

### Mechanism / additivity checks (report-only, inform verdict)

| Check | Criterion | Concern |
|-------|-----------|---------|
| M1 | Sector cap fire count in **combined** vs **sector-cap-only** (standalone ~10 on primary OOS) | If combined fires near-zero, flag **non-additivity** |
| M2 | Report uncapped sector max on both windows for combined vs standalone sector cap | Magnitude auditable |
| M3 | Vol-sizing standalone vs combined full-sample MAR delta | Interaction effect size |

## Verdict rules

- **ADVANCE:** All G1a + G1b + G4 pass on **both** windows where applicable, AND negative-window guardrail not binding on both, AND M1 does not show near-zero cap binding without explanation.
- **CONDITIONAL-ADVANCE:** Gates pass but negative-window guardrail applies on primary OOS, OR M1 shows cap rarely binds (document why).
- **KILL:** Any core gate fails on full-sample or primary OOS.

## Fail gate

Any G1b or primary G1a fail → **KILL** combined stack for this quarter. No parameter iteration.

## Next step after result

- ADVANCE → route to Trigger #5 dual-judge for operational promotion of combined layer
- CONDITIONAL-ADVANCE → hold; council decides if confirmation-window strength sufficient
- KILL → retain sector cap and vol-sizing as separate research items only

## Verify (when approved to run)

`python pp_backtest/sprint2d_interaction_sectorcap_volsizing.py` — **run complete**; see `data/research/portfolio_optimization/sprint2d_interaction/interaction_report.md`
