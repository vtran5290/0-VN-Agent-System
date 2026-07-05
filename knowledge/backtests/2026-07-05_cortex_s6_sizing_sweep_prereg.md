# Pre-Registration — S6 Kelly Sizing Sweep
# Cross-sectional quarter-Kelly vs half-Kelly sizing on S1-filtered A3_RS universe

**Date filed:** 2026-07-05
**Status:** LOCKED — gates pre-committed before any harness run
**Test type:** Portfolio Amendment / Sizing Protocol (not a signal filter test)
**Belief involved:** S6 (SOURCED — knowledge.md)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md
**Pre-check:** EXPRESSIBLE (2026-07-05 Cursor — cortex_xdisc_s6_kelly_precheck.py)
  - Pre-cap quarter-Kelly fraction below 5% cap: 25.0% (PASS gate ≥15%)
  - Post-cap CV: 0.345 (PASS gate >0.10)
  - Quarter-Kelly decile range: 0.0324 (decile 9) to 0.1005 (decile 5)
  - CONFIRMED: meaningful cross-sectional sizing variance exists; S3-wall degenerate risk ruled out

---

## What this test measures

**Control arm:** flat 5% sizing on S1-filtered A3_RS signals → OOS MAR 1.7844 (S1 standalone, 2026-07-05)
**Treatment arms:** cross-sectional Kelly-derived sizing on the same signal pool, same universe

This is PURELY a sizing test. Signal selection is FROZEN (S1 within_15pct filter, same as S1 calibration).
No change to entry/exit logic, holding period, stop rules, or signal generation.
A3_RS + S1 filter = same candidate pool as S1 calibration. Only HOW MUCH changes.

**Why the baseline changed (2026-07-05):**
Prior S6 framing referenced A3_RS raw OOS MAR 0.8386 as baseline.
S1 is now CALIBRATED (OOS MAR 1.7844) and is the best-performing signal filter.
S6 sizing must be measured against S1-filtered MAR — running Kelly sizing on a weaker
signal pool (raw A3_RS) would make the sizing test meaningless. The correct question is:
"does Kelly sizing improve over flat 5% sizing ON THE BEST CURRENT SIGNAL?"

---

## Baseline (control arm — FROZEN)

| Metric | S1 standalone, flat 5% sizing |
|--------|-------------------------------|
| Full MAR | 1.4435 |
| OOS MAR | 1.7844 |
| OOS MaxDD | −8.17% |
| OOS CAGR | 14.57% |
| N_OOS (full) | 1732 |
| N_OOS sub-A (2020-2022) | 612 (MAR 5.276) |
| N_OOS sub-B (2023-2026) | 1120 (MAR 0.546 — recency weakening, monitor) |
| Avg position size | 5.0% (flat, all signals equal) |

Signal pool: A3_RS signals passing S1 (price_close / hi_52w ≥ 0.85) in OOS window.
IS/OOS split: identical to S1 calibration run — use SAME date boundaries, same universe.
Realism conventions: same as S1 (ADV-adjusted, 40bps RT, min_hold=3, P1 execution, T+2).

---

## Kelly sizing methodology (LOCKED — no tuning post-run)

**Step 1: Compute RS decile rank on signal bar**
For each A3_RS signal day passing S1, assign a decile rank (1=lowest RS, 10=highest RS)
based on the signal stock's RS score relative to all other A3_RS candidates on that day.
Decile rank is computed from prior-window RS scores (no look-ahead):
  `decile = pd.qcut(rs_scores, q=10, labels=False) + 1` on the IS-period RS distribution

**Step 2: Map decile → Kelly fraction (pre-computed from pre-check)**
The pre-check (`cortex_xdisc_s6_kelly_precheck.py`) already derived Kelly fractions
from MI between RS decile and forward return distribution on the OOS period.
**USE THESE FIXED FRACTIONS** — do not re-derive from OOS data (look-ahead).
For C1 (quarter-Kelly) and C2 (half-Kelly), apply the following rules:

| Decile | Pre-check quarter-Kelly f* | C1 (quarter-Kelly, cap 10%) | C2 (half-Kelly, cap 10%) |
|--------|---------------------------|------------------------------|---------------------------|
| 10 (top) | TBD (read from pre-check output) | min(f*, 0.10) | min(2×f*, 0.10) |
| 9 | 0.0324 | 3.24% | 6.48% |
| 8 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 7 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 6 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 5 | 0.1005 | 10.0% (capped) | 10.0% (capped — 2×0.1005=0.201>cap) |
| 4 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 3 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 2 | TBD | min(f*, 0.10) | min(2×f*, 0.10) |
| 1 (bot) | TBD | min(f*, 0.10) | min(2×f*, 0.10) |

NOTE: read the full decile table from `data/research/cortex_xdisc/s6_kelly_precheck.json`
before building the harness. The pre-check computed all 10 deciles; the table above shows only
the two deciles that appeared in the knowledge.md evidence summary.

**Step 3: Apply sizing and cap**
Position size for each signal = Kelly fraction for that signal's decile, capped at max cap.
Portfolio normalization: if total intended size > 100%, scale all positions proportionally.
(In practice, the concurrent-holding count and ADV constraints make this unlikely to bind;
include the normalization guard regardless.)

**HARD RULE**: this sizing is applied to the SAME signal pool as S1 flat-5% baseline.
Do NOT apply additional signal filters in this test. S1 filter is active; no additional
S2, S3, or other filters. The sizing change must be isolated.

---

## Candidates (k = 2)

| ID | Sizing rule | Position cap | Expected mechanism |
|----|-------------|-------------|-------------------|
| C1_qkelly | quarter-Kelly per pre-check fractions | 10% max | Modest overweight of high-RS signals; 25% of positions sub-5% (down-weighted low-RS) |
| C2_hkelly | half-Kelly per pre-check fractions (×2) | 10% max | Stronger down-weight of low-RS (decile 9: 6.48% vs 5% flat); top deciles all capped at 10% |

k = 2 → k-adjustment for G1a: base 0.050 + log2(2) × 0.010 = +0.060

---

## Gates (LOCKED — do not adjust post-run)

**G1a (relative non-degradation + improvement bar):**
Best candidate OOS MAR ≥ baseline OOS MAR + k-adjustment
= 1.7844 + 0.060 = **1.8444**
(At least one of C1/C2 must beat flat S1 baseline by ≥0.060 OOS MAR units)

**G1b (absolute floor):**
Best candidate OOS MAR ≥ **0.516**
(Standard floor; sizing should not destroy the signal edge entirely)

**G2 (MaxDD constraint):**
Best candidate OOS MaxDD ≤ baseline OOS MaxDD × 1.15
= −8.17% × 1.15 = ≤ **−9.40%** (i.e., drawdown must not worsen by more than 15%)
Rationale: Kelly sizing should NOT increase drawdown. 15% slack for simulation variance.
If MaxDD worsens beyond this: candidate fails G2 regardless of MAR performance.
(Note: quarter-Kelly is expected to IMPROVE MaxDD vs flat; half-Kelly may be neutral)

**G3 (sizing variance — sanity check):**
Confirm post-cap CV in harness ≥ 0.10 (matches pre-check expectation)
If post-cap CV < 0.05: the position cap has eliminated all variance → sizing test degenerate
(Degenerate → VN-SUBSUMED, not INVALIDATED)

**N_OOS constraint:**
N_OOS must equal S1 baseline N_OOS (1732 full, 612 sub-A, 1120 sub-B) within ±1%.
Sizing does NOT change signal count — any deviation is a harness bug, not a real result.
If N_OOS deviates by >1%: stop, report harness error, do not compute MAR.

**Sub-window gates:** N checks only (not gate criteria — diagnostic only).
Report sub-A and sub-B OOS MAR for both candidates. Key diagnostic:
M3 check: does Kelly sizing improve sub-B MAR above 0.546 (S1 sub-B flat baseline)?
If C1 or C2 sub-B MAR > 0.600: positive indicator that Kelly sizing partially addresses S1's
recency weakness (would be evidence for ADDITIVE classification).

**Neg-OOS-cap:** guaranteed PASS by construction (S1-filtered signals are bull-regime only).

**Standing guardrail:** if both baseline and best candidate OOS MAR are negative (impossible
given baseline is 1.7844) → the baseline is stale; stop and re-read S1 calibration before proceeding.

---

## Verdict mapping

**BEST PASS: C1 or C2 passes G1a AND G1b AND G2:**
→ S6 status: TESTED (sizing benefit confirmed in OOS)
→ Apply winning sizing rule to A3_RS+S1 production signals
→ Update knowledge.md S6 evidence: add OOS MAR, MaxDD, G1a/G1b/G2 gate verdicts
→ Classification: if best candidate OOS MAR ≥ baseline + 0.100: ADDITIVE
                  if ≥ baseline + 0.060 but < + 0.100: NEUTRAL-PLUS (marginal improvement; monitor next cycle)
→ Winning candidate becomes the recommended sizing rule (can be applied in paper mode; config: pa007-style enabled:false gate)

**NEUTRAL: best candidate passes G1b but fails G1a (MAR improvement < 0.060):**
→ S6 status: TESTED (not inactive — SOURCED beliefs can be TESTED even without CALIBRATED verdict)
→ Kelly sizing does not materially improve over flat 5% for this signal/universe combination
→ Retain flat 5% sizing; file result in knowledge.md S6 evidence
→ Do NOT re-run on same data. Revisit if universe expands or S1 sub-B recency problem worsens.
→ Classification: NEUTRAL — no operational change

**DEGRADING: best candidate fails G2 (MaxDD worsens beyond −9.40%):**
→ Sizing change hurts risk profile; reject regardless of MAR improvement
→ S6 status: TESTED (PARKED — Kelly sizing harmful to drawdown in VN context)
→ Preserve flat 5% sizing; log mechanism failure (Kelly over-weights high-RS stocks that also have high VIN volatility)
→ No re-run without new pre-registration

**DEGENERATE (post-cap CV < 0.05 OR N_OOS deviates > 1%):**
→ Harness issue — do not produce verdict; fix and re-run
→ Not a test result

---

## Attribution slices required (alongside gate verdicts)

1. **Year attribution**: OOS MAR by year (2019-2025) for C1, C2, and flat-5% baseline — does Kelly improve consistency?
2. **Decile attribution**: MAR by RS decile for Kelly vs flat — which deciles benefit most from re-weighting?
3. **Position-size distribution**: histogram of actual position sizes for C1 and C2 in OOS (confirm cap doesn't flatten everything)
4. **Sub-window table**: sub-A and sub-B MAR + MaxDD for all three arms
5. **Top-10 overweight stocks**: which stocks received the highest Kelly weights (>8%) — check for VIN distortion (C3)

---

## Files to create (Cursor)

| File | Description |
|------|-------------|
| `pp_backtest/cortex_s6_sizing_sweep.py` | Main harness — applies Kelly sizing, computes OOS MAR for C1 and C2 |
| `data/research/cortex_s6/s6_sizing_sweep_report.md` | Full results with gate verdicts, attribution slices |
| `data/research/cortex_s6/s6_sizing_sweep_meta.json` | Machine-readable gate verdicts + key metrics |

**Read before writing harness:**
- `data/research/cortex_xdisc/s6_kelly_precheck.json` — full 10-decile Kelly fraction table
- `data/research/cortex_book2/s1_52wkhi_report.md` — S1 harness reference for OOS date split + universe
- `knowledge.md` § Calibrated — S1 entry for exact baseline MAR values (confirm 1.7844 OOS before proceeding)

---

## Hard rules

- Do NOT change S1 signal selection. within_15pct threshold LOCKED.
- Do NOT tune Kelly fractions after seeing OOS data. Use pre-check fractions.
- Do NOT run PA-007, PA-008, S2, or any other overlay in this test. Isolated sizing test only.
- If N_OOS deviates >1% from S1 baseline (1732): STOP — this is a harness bug, not a result.
- If post-cap CV < 0.05: DEGENERATE — do not compute gates. Fix harness (likely cap is too low or decile assignment broken).
- Do NOT write knowledge.md until Claude CLI reviews the report. Write the report; Claude decides TESTED vs other verdict.

---

## Expansion gate implication

**Mechanism gate status after this test:**
- ≥10 SOURCED: ✓ (16 as of v15)
- ≥3 new CALIBRATED: S1 ✓, S2 ✓ standalone; need 1 more (S6 TESTED does NOT satisfy this — TESTED ≠ CALIBRATED)
  Note: S6 reaching TESTED is progress but not gate-closing. Gate closes on the THIRD full CALIBRATED belief.
  S6 can reach CALIBRATED if it passes this test AND survives a second OOS cycle — that's a later review.
- Falsification pathway fired ≥1: ✗ (0/1; S1+S2 DEGRADING-REJECT is interaction-level, not belief-level)

This test does not close the mechanism gate regardless of verdict. It advances S6 from SOURCED → TESTED
and refines the operational sizing protocol. Gate progress is separate from operational value.

---

## References

- S6 belief: knowledge.md § Sourced Beliefs, S6 entry (SOURCED, pre-check EXPRESSIBLE)
- Pre-check: `data/research/cortex_xdisc/s6_kelly_precheck.json` + `cortex_xdisc_s6_kelly_precheck.py`
- S1 calibration: knowledge.md § Calibrated Beliefs, S1 entry (baseline = 1.7844 OOS MAR)
- Pre-reg authority: memory_log.md 2026-07-05 ~20:30 entry ("Next: Write S6 sizing-sweep pre-registration")
- Gate design: verification-harness.md § VN Agent System → promotion gate design
- Baseline update rationale: S1+S2 DEGRADING-REJECT 2026-07-05 (prior baseline A3_RS raw 0.8386 superseded)
