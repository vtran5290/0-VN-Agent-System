# Pre-Registration: S16 — Gray/Vogel Momentum Seasonality (Month-Based Entry Filter)
# Belief ID: S16
# Status: SOURCED → Lane A pre-registration
# Date: 2026-07-05
# Prepared by: Claude CLI
# Source: Gray & Vogel, Quantitative Momentum (2016), Ch.7 ("Momentum Investors Need to Know Their Seasons")
#   US evidence: January worst month (spread −1.72%); quarter-end months best (+3.10%/mo avg)
#   Mechanism: institutional window-dressing + tax-loss selling reversal
#
# VN pre-check result (2026-07-05): EXPRESSIBLE. Std monthly return = 21.03%; all 12 months N≥10.
# Pre-check file: data/research/cortex_book7/s16_seasonality_precheck.md
# Pre-check note: April only negative month (mean −3.76%, N=161 in full pool);
#                 September (70%), December (44%), October (36%) are highest.
#                 N=4889 total trades (full A3_RS pool, not S1-filtered).
#
# ADVERSE PRIOR EVIDENCE (must be logged in pre-reg):
#   A June/July seasonality size-overlay on A3 (not S1-filtered) was tested 2026-06-28.
#   Council verdict: DO NOT DEPLOY — bootstrap not significant, jackknife not robust,
#   0 overlay days triggered in live period (underpowered). Prior test used a different
#   mechanism (position-size scaling) and tested different calendar windows (June last-2-days,
#   July first-half). S16's harness uses a different mechanism (entry exclusion on IS-determined
#   bottom-2 months in S1+A3_RS pool). Prior failure is adverse base-rate evidence, not dispositive.
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor writes or runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"Excluding the 2 calendar months with the lowest mean forward MAR in the IS period (2015-2019)
from the S1+A3_RS entry signal universe — as a timing filter derived from IS data only — produces
higher OOS MAR in the remaining 10-month pool than the full S1+A3_RS baseline."

VN operationalization:
- Universe: all A3_RS+S1 OOS signal days (N≈1732 baseline)
- IS phase: for each entry calendar month (1-12), compute mean forward MAR for S1+A3_RS signals
  in that month within IS window (2015-2019). Identify bottom K=2 months by mean IS MAR.
  Lock these as "bad months" BEFORE evaluating any OOS data.
- OOS phase: exclude S1 signals whose entry date falls in the IS-identified bottom-2 months.
  Evaluate remaining pool's OOS MAR vs S1 baseline.
- K=2 is fixed in pre-reg. Cannot be changed to K=1 or K=3 after seeing OOS results.

Note: if IS-determined bad months include April (consistent with pre-check showing April as
only negative month), this is a VN-specific Tet/post-Tet seasonal effect, not the US
tax-loss January effect from Gray/Vogel. Both are admissible VN analogs of S16; the IS
determination is the arbiter, not the theory.

---

## Gate parameters (LOCKED before harness runs)

| Gate | Threshold | Rationale |
|------|-----------|-----------|
| G1a (primary) | OOS MAR ≥ 1.820 | 2.0% improvement over S1 baseline (1.7844); modest target appropriate for timing filter with ~17% signal exclusion |
| G1b (floor) | OOS MAR ≥ 0.516 | Absolute floor (G1B_FLOOR constant in common.py) |
| G2 (mechanism) | good_months_MAR > bad_months_MAR (OOS) | IS-determined bad months must also underperform in OOS; confirms seasonal persistence |
| G3 (N floor) | N_OOS ≥ 30 in remaining pool | Minimum OOS trade count; excluding ~2 months from 1732 base → expect N_OOS ≈ 1440+ easily satisfied |

**Negative-OOS cap:** if both remaining pool and baseline OOS MAR are negative, maximum status is
CONDITIONAL-ADVANCE — never full ADVANCE.

**Borderline-pass rule:** if G1a margin < 0.020 above threshold (i.e., MAR 1.820–1.840), require a
separate pre-registered confirmation test before promoting to CALIBRATED. Present to user.

---

## Sub-window validation (required)

Report OOS MAR for remaining pool separately for:
- Sub-A: 2020–2022 (IS-adjacent, trending regime)
- Sub-B: 2023–2026 (OOS-far, choppy regime)

CONTEXT: sub-B collapse has been observed across all 4 tested Lane A stock-filters (S14/S15/S17/S18).
S16 is a timing filter, not a stock filter — sub-B behavior may differ if bad months cluster
disproportionately in the 2020-2022 regime and the filter "accidentally" improves sub-B
by removing those high-variance months. Or sub-B may still collapse if the choppy regime
distributes bad months evenly. Report sub-B carefully; compare to S1 baseline sub-B (TBD from prior runs).

---

## IS phase design notes

1. IS window: same as all other harnesses — IS_WINDOW from `cortex_book1_common.py`.
2. MAR computation per month: for each calendar month M, collect all (ticker, signal_date) pairs
   in IS window where month(signal_date) == M. Compute mean forward MAR for that subset.
   "Forward MAR" = same as the outcome measure used in S1 baseline (per A3_RS trade definition).
3. Lock bottom-2 months: write IS month rankings to gates_addendum.md BEFORE loading OOS data.
4. OOS phase: apply IS-locked month exclusion; do not recompute rankings on OOS data.

---

## Harness design notes

1. **Script name:** `pp_backtest/cortex_book7_s16_seasonality_harness.py`
2. **IS gate lock step must be printed/written BEFORE OOS evaluation runs** — same discipline as S15 FIP IS threshold lock.
3. **G2 control group:** compute mean OOS MAR for signals in the excluded months (the "bad months" pool). Report alongside the "good months" pool.
4. **Month-level OOS breakdown:** optionally output mean MAR per month in OOS (diagnostic — not a gate condition).
5. **No per-signal-date split needed** (unlike S15 FIP): months are global calendar months, not per-day ranks.

---

## Output files

| File | Description |
|------|-------------|
| `knowledge/backtests/s16_harness_results.md` | Gate verdicts, IS month rankings (locked), OOS remaining pool stats, G2 mechanism check, sub-window |
| `data/research/cortex_book7/s16_seasonality_harness_meta.json` | Machine-readable results |
| `knowledge/backtests/2026-07-05_schwager_s16_seasonality_gates_addendum.md` | IS month rankings locked before OOS eval |

---

## Adverse prior evidence note (for interpretation)

The June/July A3-level seasonality backtest (2026-06-28) found no significant seasonality signal
in VN. S16's harness tests a different mechanism (entry exclusion vs. size overlay) and different
calendar windows (IS-determined vs. theory-driven June/July). The mechanism difference is genuine,
but the base rate for VN seasonality signal is already weakly negative based on prior evidence.
If this harness also fails (DEGRADING-REJECT), log as the second VN seasonality null result and
flag that S16's belief as stated is VN-INVALID for the current A3_RS+S1 deployment context.

---

## Expansion gate context

S16 ADVANCE would provide the 3rd CALIBRATED belief needed for Mechanism Gate unlock.
S16 is the last EXPRESSIBLE pre-checked Lane A candidate from the current Schwager extraction batch.
If S16 → DEGRADING-REJECT: Mechanism Gate requires finding a new CALIBRATED candidate from the
remaining SOURCED pool (S13 Graham fundamental quality is the next viable Lane A candidate —
requires degeneracy pre-check before pre-reg can be written).
