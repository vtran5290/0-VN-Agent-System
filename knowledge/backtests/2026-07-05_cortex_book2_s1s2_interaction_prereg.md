# Pre-Registration — Cortex Book 2: S1+S2 Interaction Test
# Combined 52-week proximity + breakout volume filter

**Date filed:** 2026-07-05
**Status:** PENDING RUN — gates locked, harness not yet built
**Test type:** Step 4 Interaction Test (PROPAGATION_PROTOCOL.md §Section 4)
**Beliefs involved:** S1 (within_15pct, CALIBRATED STANDALONE) + S2 (1.4×, CALIBRATED STANDALONE)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md
**Triggered by:** S2 M2 check — ~59% signal overlap with S1 within_20pct → independent deployment assumption invalid

---

## Why this test is required

S1 and S2 were independently CALIBRATED as standalone filters on the A3_RS baseline.
However, the S2 mechanism check (M2) found ~59% of S2-filtered signals also pass S1 within_20pct
proximity. Since the selected S1 threshold is even stricter (within_15pct, prox≥0.85), the two
filters have substantial overlap — applying both simultaneously will produce a materially smaller
signal pool than either alone. This interaction is NOT analytically resolvable (unlike S1's
own interaction test, which was filter-type and combined = standalone by construction). Here, two
*different* filter criteria interact with each other, and the combined effect on OOS MAR is unknown.

**The question:** does requiring BOTH near-52wk-high AND high-volume-surge produce better signal
quality than requiring EITHER filter alone?

This test must complete before S1 and S2 are used as a combined filter system in production.

---

## Baseline for this interaction test

**Baseline = S1 standalone (the stronger of the two standalone CALIBRATED filters)**

| Metric | S1 standalone (within_15pct) |
|--------|------------------------------|
| Full MAR | 1.4435 |
| OOS MAR | 1.7844 |
| OOS MaxDD | −8.17% |
| OOS CAGR | 14.57% |
| N_OOS (full) | 1732 |
| N_OOS sub-A (2020-2022) | 612 |
| N_OOS sub-B (2023-2026) | 1120 |
| S1 sub-B MAR | 0.546 (recency weakening — monitor) |

Rationale: S1 is used as baseline (not S2 or A3_RS raw) because S1 is the stronger filter
(Full MAR 1.4435 vs S2's 0.9080) and is the natural "step 1" for a combined filter question.
The combined test asks: does adding the S2 volume requirement ON TOP of S1 improve further?

Alternative interpretation (S2 as baseline, S1 added on top): produces the same combined candidate
signal pool by commutativity. Choosing S1 as baseline to frame the question correctly — we are
asking whether volume confirms what proximity already selected, not the reverse.

---

## Candidate

**Combined filter:** A3_RS signal day must satisfy BOTH:
1. S1: `price_close / hi_52w >= 0.85` (within_15pct of 52-week high, on signal bar)
2. S2: `volume / vol_50d_avg >= 1.4` (≥1.4× 50-day average volume, on signal bar)

Order of filter application: apply S1 first (proximity check), then S2 (volume check) on the
S1-passing candidates. Result is the S1 ∩ S2 signal pool.

**k = 1** (one combined candidate — no multiple-testing adjustment)
This is a binary question: does the combined filter PASS or FAIL? Not a sweep over parameter space.

---

## Gates (pre-commit — do not adjust post-run)

**G_ia (relative, primary): combined OOS MAR ≥ S1-baseline OOS MAR + 0.050**
= 1.7844 + 0.050 = **1.8344**
k=1 → no log2 adjustment. Base margin 0.050 as standard.
Interpretation: S1+S2 combined must beat S1 alone by a meaningful margin.

**G_ib (absolute floor): combined OOS MAR ≥ 0.516**
Same absolute floor as standalone tests (already conservative — well below expected combined MAR).
Acts as a safety floor only.

**G_full (no-regression gate): combined Full MAR ≥ S1 Full MAR − 0.050**
= 1.4435 − 0.050 = **1.3935**
Ensures adding S2 does not significantly harm IS-period performance. If combined Full MAR drops
below this, flag for review even if OOS gates pass.

**N_OOS (estimated — verify in run):**
- Full OOS (2020-2026): ≥ 30 (estimated ~700-900 from S1's 1732 × ~48% passing S2 vol filter)
- Sub-window A (2020-2022): ≥ 12 (estimated ~280-350)
- Sub-window B (2023-2026): ≥ 12 (estimated ~420-550)
If full OOS < 30 → VN-THIN for combined filter; both S1 and S2 remain CALIBRATED STANDALONE.

**Neg-OOS-cap:** both S1-baseline and combined candidate OOS MAR must be positive.
(Guaranteed by construction since both filters select from bull-regime signals.)

**Sub-window gates:** N checks only (same as S1 and S2 standalone tests).
Sub-window MAR is diagnostic — reported but NOT a gate criterion.

---

## Realism conventions (identical to S1 and S2 standalone)
- ADV-adjusted returns
- 40bps RT cost
- min_hold = 3 days
- P1 honest execution (T+2 settlement, floor/ceiling locks, ADV caps)
- Survivorship-checked panel
- No look-ahead: both filters applied on signal bar close; entry at next open (T+1)
- 50d vol avg: rolling mean of prior 50 volume bars EXCLUDING signal bar (same as S2 standalone)
- 52w high: rolling max of prior 252 high bars INCLUSIVE of signal bar (same as S1 standalone)

---

## Verdict mapping

**If combined OOS MAR ≥ G_ia (1.8344) AND combined OOS MAR ≥ G_ib (0.516) AND N_OOS full ≥ 30:**
→ CALIBRATED (FULL) for combined S1+S2 system
→ Update knowledge.md S1 and S2 entries: "CALIBRATED (FULL) — S1+S2 combined interaction test PASS"
→ Combined system now has operational status: deploy S1+S2 together in production filter
→ Count as satisfying S1's existing "CALIBRATED (FULL)" status note (currently already marked FULL
   because S1's own interaction test was analytical; S2's standalone is STANDALONE)
→ Update S2 entry: CALIBRATED (STANDALONE) → CALIBRATED (FULL)

**If G_ib (0.516) ≤ combined OOS MAR < G_ia (1.8344) AND N_OOS full ≥ 30:**
→ INCONCLUSIVE-HOLD: combining S1+S2 does not add value over S1 alone
→ Status remains: S1 CALIBRATED (FULL) standalone, S2 CALIBRATED (STANDALONE) standalone
→ Action: do NOT run S1+S2 combined in production; run whichever is more favorable per regime
→ Note: "S1+S2 interaction test: INCONCLUSIVE-HOLD 2026-07-05 — combined does not improve over S1 alone"
→ Do NOT re-run on same data. Await fresh OOS data (next calendar year) before re-testing.

**If combined OOS MAR < G_ib (0.516) OR combined OOS MAR < S1 baseline − 0.100 (severe regression):**
→ DEGRADING-REJECT: combining S1+S2 actively hurts S1 performance
→ Status remains: S1 CALIBRATED (FULL) standalone, S2 CALIBRATED (STANDALONE) standalone
→ Action: S1+S2 combined use FORBIDDEN; flag as DEGRADING in both belief entries
→ Council review required before any future combined-filter attempt

**If N_OOS full < 30 (VN-THIN for combined):**
→ Combined filter is too restrictive in VN — insufficient sample
→ Status remains unchanged (both STANDALONE CALIBRATED)
→ Note: "S1+S2 combined VN-THIN — ~N OOS trades insufficient. Retry when VN universe expands."
→ Consider testing S1 within_20pct + S2 1.4× (looser S1) as alternative — pre-register separately.

---

## Expected output files

| File | Description |
|------|-------------|
| `data/research/cortex_book2/s1s2_interaction_report.md` | Full backtest report with gate verdicts |
| `data/research/cortex_book2/s1s2_interaction_meta.json` | Machine-readable metrics |

---

## Mechanism checks (required if CALIBRATED verdict)

| Check | Measure | Concern |
|-------|---------|---------|
| M1 Fire count | N_OOS combined / N_OOS S1-baseline | < 5% of S1 signals remaining → near-degenerate |
| M2 Marginal contribution | OOS MAR gain from adding S2 on S1 | If < 0.010, vol filter adds noise not signal |
| M3 Sub-B | Combined sub-B MAR vs S1 sub-B (0.546) | Does volume filter fix S1's recency weakness? |
| M4 Monotonicity | Combined Full MAR vs S1 Full MAR | Regression on IS period flags overfitting |

M3 is particularly informative: if adding S2 raises sub-B MAR above G_ia → the volume filter
specifically improves S1's weakest window. This would be strong evidence for the combination.

---

## Notes and caveats

1. **59% overlap figure is approximate:** the M2 check in S2 was based on within_20pct, not
   within_15pct (our S1 threshold). The actual overlap with within_15pct is likely somewhat lower.
   The harness will compute exact N for the combined filter.

2. **Direction of causality:** volume surge may CAUSE price to reach proximity to 52wk high (not
   the other way around), so the two criteria may be partially sequential in time. If so, requiring
   both on the SAME signal day is unnecessarily strict — a volume surge 1-3 days before the
   52wk high touch might be more predictive. This is a mechanism concern, not a gate concern;
   document in report if N_OOS combined turns out VN-THIN.

3. **Interaction with S1 recency:** S1's sub-B was 0.546 (below G1a). S2's sub-B was 1.166
   (above G1a). If the combined filter's sub-B exceeds S1's — this is the key diagnostic
   (M3 above). A volume requirement may naturally filter out the lower-quality 2023-2026
   signals that caused S1's sub-B weakness.
