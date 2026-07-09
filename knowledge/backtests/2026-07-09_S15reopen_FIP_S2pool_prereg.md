# Research Program Pre-Registration
# S15 Reopen — FIP Path Quality on S2 Pool (Cycle 1)
# Date: 2026-07-09
# Author: Claude CLI (Sonnet coordination seat)
# Council: Opus APPROVE (artifact) + Fable HOLDS (framework) — 2026-07-09
# Council artifact: 00. Command Center/05_AI_Handoffs/2026-07-09_S23S24S25_Council.md

---

## Operator Override Note

This program pre-registration supersedes the operator directive "recalibrate when output
is available until it finds an edge." Per Fable council (FRAMEWORK HOLDS, 2026-07-09):
unbounded iterative search loops are prohibited without a bounded pre-registration declaring
goal metric, iteration cap, and kill criterion. "Edge found" = gate pass only — never a
stopping rule for search. Re-parameterization after a gate fail = new program pre-reg event,
not a continuation of this program.

---

## Program: S15 Reopen — FIP Path Quality on S2 Pool, Cycle 1

### Background

**S15 history (DEGRADING-REJECT):** Gray/Vogel FIP quality momentum was previously tested
as a filter on the S1 (52-week high) pool. Result: OOS MAR 1.1275 < baseline 1.7844;
G2 PASS (mechanism is real in VN; it degrades when applied on S1 pool). Reopen trigger
in S15: "Regime change; fresh pre-reg."

**This reopen:** Tests FIP as tertiary sort within the A3_RS+S2 pool (not S1 pool). This
is a different application context — S2 selects volume-breakout names; FIP would sort
within that pool by path smoothness. The S1-pool-FORBIDDEN status does NOT apply to S2
pool. A fresh pre-reg on a different pool meets the S15 reopen condition.

**S23 equivalence:** The extraction file (GrayVogel_QuantitativeMomentum_extraction_2026-07-09.md)
registered this as "S23." Under this reopen framework, S23 is a label for this specific
investigation, not a new numbered SOURCED belief. S15 remains the canonical belief slot.

---

## Program Definition

| Field | Value |
|-------|-------|
| Program name | S15-reopen FIP S2-pool cycle 1 |
| Production architecture | A3_RS+S2@1.4× |
| Baseline | OOS MAR 2.4804 (S2 standalone, 2020-2026); primary system baseline 0.8386 |
| Goal | OOS MAR ≥ baseline + 0.050 = **0.8886** (entry-class G1a, k=1) |
| Overlay class | Entry-class (tertiary sort key — not exit, not sizing) |
| Phase cap | **1 phase; 1 run** — no parameter sweep |
| Search space | FIP% computed as % of weeks with positive return within 12m lookback, used as tertiary sort after a3_rank_score + S2 volume_mult. No other parameter variation authorized. |
| Kill criterion | **Regime-conditional per fable GAP verdict (2026-07-09):** G1a FAIL inside sub-B regime → status: **PARKED-[REGIME-CONFOUNDED]** (not CLOSED-NEGATIVE on mechanism). S15 hypothesis-level regime-exit trigger remains live and unconsumed — PARKED-[REGIME-CONFOUNDED] does not close the S15 lineage. G1a PASS inside sub-B regime → strong evidence (mechanism expresses despite adverse regime) → normal promotion path. Re-parameterization (different window, threshold, metric) requires a NEW program pre-reg in either outcome. |
| Terminal-state taxonomy | COMPLETED-SUCCESS (G1a PASS in any regime), **PARKED-[REGIME-CONFOUNDED]** (G1a FAIL in sub-B — mechanism still open at hypothesis level; only the S2×sub-B cell is closed), PARKED-DATA (data/run infeasible), SUPERSEDED (new pre-reg replaces). **NOTE: CLOSED-NEGATIVE on FIP mechanism is NOT a valid outcome of this run in sub-B regime.** CLOSED-NEGATIVE on FIP mechanism requires a G1a FAIL in a regime where the mechanism is not confounded (i.e., after regime exits sub-B). |

---

## Gates

### G1a — Entry-class MAR improvement (primary gate)
**Threshold:** OOS MAR ≥ **0.8886** (baseline 0.8386 + 0.050 increment, k=1)
**Window:** Same OOS 2020-2026 window as baseline
**Gate-fail consequence:** CLOSED-NEGATIVE for S2-pool FIP reopen. S15 PARKED status unchanged.

*Gate correction note (per opus council, 2026-07-09):* Earlier draft used 0.90× relative floor
(0.8386 × 0.90 = 0.7547). This was incorrect — entry-class gate is an absolute improvement
requirement (baseline + margin), not a degradation floor. The 0.90× floor is exit-class logic.

### G1b — Absolute MAR floor
**Threshold:** OOS MAR ≥ max(0.10, baseline × 0.50) = max(0.10, 0.4193) = **0.4193**
**Purpose:** Prevents ADVANCE on near-zero absolute return even if relative margin met.

### G2 — Sub-B regime check
**Threshold:** Sub-B MAR ≥ 0.50 (choppy 2023-2026 sub-period must not collapse)
**Purpose:** S15 previously showed mechanism is real (G2 PASS); confirm same here.

### G3 — S2/FIP joint evaluation (mandatory — per opus council risk flag)
**Requirement:** Results must evaluate S2+FIP jointly, not S23/FIP independently. S2 selects
for volume breakouts (discrete events); FIP prefers smooth paths. Tension is plausible —
joint evaluation determines whether the directional tension cancels or complements the FIP signal
within the A3_RS+S2 pool.
**Failure action:** If S2+FIP degrades vs S2 alone (OOS MAR < S2 standalone), halt and
document the directional tension as confirmed. Do not test additional FIP parameterizations.

---

## VN-Specific Risk Flags (must be documented in run report)

1. **VN ±7% daily price band:** Discrete events (e.g., earnings surprise) may be capped
   across multiple limit-up/limit-down days, creating artificial smoothness in the FIP% metric.
   A stock that gaps 20% up in a US-equivalent event may instead show 7%/day across 3 days —
   appearing smooth by day-count, but economically discrete. Evaluate: are the "smooth" winners
   in VN genuinely smooth, or are they band-capped discretionaries? Flag if >30% of S2 signals
   have FIP% ≥ 70% AND coincide with limit-up days.

2. **S2 pool size:** If S2 filtering reduces the pool to <20 names per month, FIP tertiary
   sort may have no discriminating power (insufficient N). Report pool size per quarter.

---

## Observational Side Task: S16 Reopen (No Gate)

Concurrent with the FIP run, conduct an observational (no intervention) analysis of A3_RS
monthly return distribution:
- Stratify A3_RS+S2 closed trade returns by calendar month of entry_date
- Compute: mean net_return, median net_return, win rate per month
- Additionally bucket by Tet-relative timing (LNY week ±2 weeks)
- Report only — no intervention without ≥10 years VN data and pre-registered minimum-sample gate
- Data source: `data/paper_trade/closed_trades.csv` (note: 2026-03-03 start = 4 months only;
  longer OOS data requires AFL output extraction — flag as [DATA-INSUFFICIENT] if <36 months)

**Reopen trigger for S16:** "New VN institutional calendar data." The observational step
constitutes collecting new VN data. If the observation shows clear January dip and/or
quarter-end lift matching US pattern, register as [OBSERVED-CONSISTENT] and proceed to
formal pre-reg with minimum-sample gate. If no pattern visible, S16 remains DEGRADING-REJECT.

---

## Regime Status Note — RESOLVED by Fable GAP Verdict (2026-07-09)

`regime_state.json` as of 2026-07-06: **regime = "B" (sub-B choppy).**

**Fable ruling (GAP, 2026-07-09, seat ID: a8b3c56fe39fea263):**

- The FORBIDDEN-as-filter clause in S15 is **pool-scoped** (S1 pool only). This S2-pool
  test is NOT blocked by the FORBIDDEN clause — it exits the pool-scoped restriction validly.

- The regime-exit trigger ("regime_state.json exits sub-B → re-run S15") is
  **hypothesis-scoped** (applies to any FIP/path-quality test on any pool), because
  regime-sensitivity is a property of the FIP mechanism, not of the pool. The "new
  investigation on different pool" argument cannot escape the regime-scoped trigger.

- **Resolution:** The S2-pool test MAY proceed in sub-B, but with regime-conditional
  terminal states (see Kill Criterion above). A G1a FAIL in sub-B = PARKED-[REGIME-CONFOUNDED],
  not CLOSED-NEGATIVE on the FIP mechanism. The regime-exit trigger remains live regardless
  of this run's outcome.

- When regime exits sub-B: the expansion gate S15 retest fires independently of this S2-pool
  run. The two investigations are parallel, not sequential.

**Source:** `00. Command Center/05_AI_Handoffs/2026-07-09_S15S16_FableGAP_Verdict.md`

---

## Implementation Notes

**What Cursor implements:**
1. AFL modification: add FIP% computation (% positive weeks in 12m lookback) as tertiary
   sort key in A3_RS+S2 scanner output. Compute per-stock before ranking.
2. Run backtest on OOS 2020-2026 with FIP% as tertiary sort, report MAR vs baseline.
3. Produce delta report: S2-only MAR vs S2+FIP MAR (same dates, same pool).
4. Python script for S16 observational: `scripts/s16_seasonality_observational.py`
   (data: AFL-exported OOS trades with entry_date; group by calendar month).

**What Claude Code verifies:**
- Delta report exists with explicit before/after comparison
- G1a, G1b, G2, G3 evaluated and documented
- VN band flag checked (G3 note above)
- S15 status in knowledge_ACTIVE.md updated to reflect outcome

**Handoff:**
This pre-reg is ready for Cursor implementation. CursorHandoff.md to be written when
/aiscollab is re-enabled (currently disabled this session).

---

## Pre-Registration Declaration

I, the operator, acknowledge that:
1. This program supersedes the open-ended "iterate until finds edge" directive
2. Gate fail = CLOSED-NEGATIVE for this specific configuration — not a retry license
3. Any change to the FIP metric, window, or pool after seeing results = new pre-reg required
4. The FIP mechanism may not transfer to VN due to ±7% band distortion — this is the test

**Operator override note (per fable pathway item 5):**
This pre-reg supersedes prior REDIRECT-equivalent framing of "iterate until edge found."
"Edge found" = G1a gate pass on first registered run. All other outcomes map to
CLOSED-NEGATIVE or PARKED per the terminal-state taxonomy above.

---

_Pre-reg written: 2026-07-09_
_Council: Opus APPROVE (S23/FIP artifact) + Fable HOLDS (framework)_
_Next action: Write CursorHandoff when /aiscollab re-enabled_
