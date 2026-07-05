# Cortex Book #1 — Gate Thresholds Addendum (set before run)

**Date filed:** 2026-07-04
**Parent pre-reg:** `2026-07-04_cortex_book1_sizingrule_prereg.md`
**Set by:** Cursor (implementation session)
**Status:** LOCKED — thresholds fixed before any backtest execution

## Verified data window

| Field | Value |
|-------|-------|
| Requested start | 2012-01-01 |
| Actual panel min date | **2012-01-03** (first trading bar in `load_panel()`) |
| Data end | 2026-07-03 |
| Full backtest window | **2012-01-03 → 2026-07-03** (no post-hoc narrowing) |

## OOS evaluation window (primary gates)

The parent pre-reg requires OOS MAR but does not specify an OOS split. This addendum locks the repo-standard split used in `p3_rs_isoos_validation.py`:

| Window | Range | Role |
|--------|-------|------|
| IS (sanity only) | 2013-01-01 → 2019-12-31 | Reported; not a promotion gate |
| **OOS (primary gates)** | **2020-01-01 → data end** | G1a / G1b / negative-OOS cap |
| Diagnostic | Last 12 calendar months | Sprint 2B comparability; reported only |

**Reasoning:** Sprint 2B uses a 12-month OOS for near-term promotion tests. This test validates a multi-decade belief (2012-present); the 2020+ OOS split is the established repo convention for stability checks and avoids a single recent-year artifact dominating gate scores. The 12-month slice is reported as a secondary diagnostic per handoff format convention, not used for G1a/G1b.

## Stop-price rule (fixed across all candidates)

**Production P1 honest initial stop:** `stop_price = entry_price − 2.0 × ATR14` at entry bar (from `p0_realism_p1_winner.py` / `phase_exit_sweep_core.P1_WINNER`).

Fixed-fractional weight at entry:

`target_w = risk_pct × entry_price / (entry_price − stop_price)`

capped by existing slot (`1/20 × GK × total_frac`) and ADV participation limits in the capital simulator.

## G1a — relative margin (primary)

| Parameter | Value |
|-----------|-------|
| **G1a margin** | **+0.050 absolute MAR** |
| Rule | `candidate OOS MAR ≥ baseline OOS MAR + 0.050` |

**Reasoning:** Opus explicitly warned against reusing Sprint-style ~0.002 hairline margins that sit inside backtest noise. A +0.050 absolute MAR margin requires a material improvement (~10% of the ~0.53 full-sample baseline MAR reference) rather than a rounding artifact. Sizing-only changes on a frozen entry stream should not pass on noise alone.

## G1b — absolute floor

| Parameter | Value |
|-----------|-------|
| **G1b floor** | **0.400 absolute OOS MAR** |
| Rule | `candidate OOS MAR ≥ 0.400` (independent of baseline) |

**Reasoning:** Derived from **this window's scale only** — full-sample operational baseline MAR is ~0.53 over 2012-present (Sprint 2B replication). The OOS span (2020+) covers COVID, 2022 bear, and recent chop; an absolute floor of 0.40 requires the candidate to deliver economically meaningful risk-adjusted returns in that regime without importing Sprint 2B's fixed 0.532 gate (which was calibrated for a different hypothesis and promotion path).

## Negative-OOS cap

Per parent pre-reg: if **both** baseline OOS MAR **and** candidate OOS MAR are negative → max verdict **CONDITIONAL-ADVANCE** (never full ADVANCE).

## Candidate risk_pct values (fixed)

1.25%, 1.75%, 2.5% — three separate sub-candidates, not blended.
