# Pre-Registration — S6 Kelly Sizing Sweep
# Does cross-sectional Kelly weighting improve OOS MAR vs flat 5%?

**Date filed:** 2026-07-05
**Status:** PENDING RUN — gates locked
**Test type:** Step 2-4 Lane A (PROPAGATION_PROTOCOL.md)
**Belief ID:** S6 — Kelly/entropy sizing
**Source:** Stone, Information Theory (2015) Ch.6-8; Kelly criterion
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md

---

## Recap: what the pre-check confirmed

Empirical pre-check 2026-07-05 (Cursor — cortex_xdisc_s6_kelly_precheck.py):
- Total OOS signal instances: 4889
- Quarter-Kelly distribution by RS decile: 3.24% (decile 9) → 10.05% (decile 5)
- Fraction below 5% slot cap: 25.0% (PASS ≥15%)
- Post-cap CV: 0.345 (PASS >0.10)
- VERDICT: EXPRESSIBLE — sufficient variance for the sizing test to be non-degenerate

---

## Baseline

**Baseline system = S1-filtered signals (within_15pct, min_prox=0.85)**
- Flat 5% sizing on S1-filtered signals
- OOS MAR: 1.7844
- Full MAR: 1.4435
- N_OOS: 1732
- OOS MaxDD: −8.17%

Rationale: S1 is the strongest standalone CALIBRATED filter. Testing Kelly sizing improvement
on top of S1 (not raw A3_RS) is the correct next step — Kelly sizing interacts with signal
quality, so testing on a higher-quality signal pool gives cleaner evidence.

Alternative baseline (raw A3_RS + flat 5%):
- OOS MAR: 0.8386
- Will be reported as a secondary comparison only.

---

## Candidate implementations (k = 3 sweep)

All three share the same sizing approach: cross-sectional quarter-Kelly allocation based on
the signal day's RS decile rank. The three candidates vary in how the Kelly fraction is
computed and capped:

| Label | Sizing rule | Cap |
|-------|-------------|-----|
| K1 | Quarter-Kelly from RS decile lookup (pre-computed table) | 5% floor / 15% ceiling |
| K2 | Quarter-Kelly from RS decile, proportional rescaling (normalize to same gross exposure as flat) | 5% floor / 10% ceiling |
| K3 | Half-Kelly from RS decile lookup | 5% floor / 15% ceiling |

k=3 candidates → log2(3) = 1.585 → G1a margin adjustment: base 0.050 × (1 + 1.585/3) ≈ 0.077

**G1a (relative, k=3): combined OOS MAR ≥ S1-baseline OOS MAR + 0.077**
= 1.7844 + 0.077 = **1.8614**

**G1b (absolute floor): combined OOS MAR ≥ 0.516** (same absolute floor as prior tests)

**G_full (no-regression gate): combined Full MAR ≥ S1 Full MAR − 0.050**
= 1.4435 − 0.050 = **1.3935**

**N_OOS minimum:** ≥ 30 full (same universe as S1; sizing doesn't change which signals fire)
Sub-window checks: ≥ 12 each (N unchanged — sizing is applied post-selection)

**Neg-OOS-cap:** both baseline and candidate OOS MAR must be positive.

---

## Verdict mapping (pre-commit)

**If any candidate OOS MAR ≥ G1a (1.8614) AND ≥ G1b (0.516) AND G_full PASS:**
→ CALIBRATED (FULL) for Kelly sizing
→ Selected candidate is the default sizing rule for S1-filtered signals in production
→ Report which k variant won; use that threshold going forward
→ Update knowledge.md S6 entry: SOURCED → CALIBRATED (FULL)
→ Expansion gate: CALIBRATED count → 3/3 new (S1 + S2 + S6) ✓ — gate satisfied

**If all candidates fail G1a but any passes G1b (0.516 ≤ MAR < 1.8614):**
→ INCONCLUSIVE-HOLD: Kelly sizing does not improve over flat S1
→ Status: S6 remains SOURCED
→ Action: continue with flat 5% sizing; do not re-run on same data; await fresh OOS year
→ Note: "S6 Kelly sizing: INCONCLUSIVE-HOLD 2026-07-05 — no improvement over flat on S1-filtered signals"

**If any candidate OOS MAR < G1b (0.516) OR Full MAR < G_full (1.3935):**
→ DEGRADING: Kelly sizing actively harms S1-filtered performance
→ Status: S6 remains SOURCED; flag DEGRADING on attempted implementation
→ Action: revert to flat 5%; do not implement variable sizing without council review

---

## Expected output files

| File | Description |
|------|-------------|
| `data/research/cortex_xdisc/s6_kelly_sizing_report.md` | Full report with gate verdicts |
| `data/research/cortex_xdisc/s6_kelly_sizing_meta.json` | Machine-readable metrics |

---

## Realism conventions (same as S1/S2 standalones)
- 40bps RT cost (applied to actual position size, not flat 5%)
- min_hold = 3 days
- P1 honest execution (T+2 settlement, floor/ceiling locks, ADV caps)
- ADV cap: total day's sizing cannot exceed ADV limit regardless of Kelly
- S1 filter applied first; sizing applied only to S1-passing signals
- RS decile computed at signal bar close; entry at T+1 open (no look-ahead)
- Quarter-Kelly cap: min position 5% (prevent over-dilution of weak signals), max 15% (prevent over-concentration)

---

## Mechanism checks (required post-run)

| Check | Measure | Concern |
|-------|---------|---------|
| M1 High-decile contribution | OOS MAR split by RS decile quintile | If all gain from top decile only → fragile; concentrated risk |
| M2 Sizing vs flat difference | CAGR/MaxDD delta vs flat-5% S1 | If CAGR improves but MaxDD worsens → partial improvement |
| M3 Sub-B check | Sub-B MAR of winning candidate vs S1 sub-B (0.546) | Does variable sizing fix recency weakness? |
| M4 Cap utilization | % of positions at floor (5%) vs ceiling (15%) | Heavy floor-hitting → sizing mechanism not engaging |

---

## Why S1-filtered baseline (not raw A3_RS)

Testing Kelly sizing on A3_RS raw signals would conflate two improvements:
(1) S1 filter selects better signals
(2) Kelly sizing allocates better within signals

Testing on S1-filtered signals isolates (2) only — the cleaner experiment.
Both baselines are reported for reference; the primary gate is against S1-filtered.

---

## Expansion gate note

If S6 CALIBRATED: expansion gate reaches 3/3 new CALIBRATED (S1 + S2 + S6).
Combined with 10+ SOURCED ✓, 1 recalibration cycle ✓: gate is fully unlocked EXCEPT
for sessions (1/10 — this cannot be fast-tracked) and INVALIDATED (0/1 — structural).
INVALIDATED criterion remains the binding constraint even after S6.
