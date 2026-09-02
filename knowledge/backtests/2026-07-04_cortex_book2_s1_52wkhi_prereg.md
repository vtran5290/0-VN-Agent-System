# Pre-Registration — Cortex Book 2: S1 — O'Neil 52-Week High Proximity Filter
# Lane A (backtestable)

**Date filed:** 2026-07-04
**Status:** PENDING RUN — gates locked, harness not yet built
**Belief:** S1 — "52-week high proximity is a leading indicator, not lagging — most traders invert this"
**Source:** O'Neil, How to Make Money in Stocks, Ch.2 (CAN-SLIM N = New highs)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md — belief S1
**Phase 1–4 audit context:** knowledge_base/2026-07-04_BookPropagation_Progress.md

---

## Why this test is "Book 2" priority

Per Fable council (2026-07-04): "Do not pick a new book yet. The first task for 'Book 2' should be:
run the degeneracy pre-check on S1 (O'Neil 52-week high proximity) — it's already SOURCED, likely
expressible, and uses the existing A3_RS harness. If clean: pre-register and run."

S1 is a pure entry filter: it changes WHICH signals fire (selection), not how they're sized.
This means it avoids S3's failure mode — the slot-cap binding doesn't apply to selection constraints.

---

## Degeneracy Pre-Check (Step 2 answers — mandatory before harness spend)

### (a) Expressibility
"Which VN constraint binds first if I run this test?"

The test: binary entry filter on A3_RS signals — "enter only if price is within X% of its
52-week high." Independent variable = proximity threshold X (e.g., 15%, 20%, 25%).

Constraint check:
- Slot cap (1/20): Sizing constraint, not selection. Does not prevent IV from varying.
- ADV cap: Sizing constraint. Does not prevent IV from varying.
- C1 bear suppression: Suppresses all signals in bear periods — but equally for baseline and
  candidate. Bear periods become a wash in the relative comparison (G1a = relative gate).
  The IV (which signals are selected by the proximity filter) varies freely in non-bear periods.
- VN price bands (±7%): Affect single-bar move size but NOT the 52-week rolling lookback
  calculation. Bands do not constrain the proximity screen.

EXPRESSIBILITY VERDICT: **EXPRESSIBLE** — no binding constraint prevents the proximity
threshold IV from varying. The filter will reduce signal count, but that is expected
signal-quality behavior, not degeneracy.

### (b) Claim fidelity
O'Neil's exact claim: "One of the greatest paradoxes of the stock market is that what seems
too high and risky to the majority of investors usually goes higher, and what seems low and
cheap usually goes lower." Operationally: buy breakouts from sound bases when the stock is
ALREADY making new highs (near 52-week high), not when it has pulled back.

Proposed test: OOS MAR improvement of A3_RS + D3 system when filtered by proximity to
52-week high. Entry fires only when A3_RS signal triggers AND price is within X% of 52W high.

Does this test the claim? YES, with nuance:
- The claim is that proximity-proximate stocks have better forward returns than non-proximate.
- The test isolates this in A3_RS context: does proximity screen separate better-performing
  A3_RS signals from worse-performing ones?
- This is an incremental test (proximity over RS momentum), not a standalone proximity test.
  That is faithful to how O'Neil intends it — the full CAN-SLIM system is the combination.

**Known proxy concern (M2 risk):** A3_RS already filters for relative strength (momentum).
Proximity to 52-week high is likely correlated with high RS rank — the filter may be partially
redundant with existing momentum screening. This won't make the test unfair, but may reduce
the magnitude of incremental improvement. The M2 mechanism check must be run.

CLAIM FIDELITY VERDICT: **ACCEPTABLE** — with M2 overlap risk flagged for mechanism checks.

### (c) VN-transfer check
1. Assumes short-selling/borrow/derivatives/deep intraday liquidity VN lacks? → NO. Pure price screen.
2. Survives HOSE/HNX/VSDC mechanics (price bands, settlement, foreign room, lot size)?
   → YES. 52-week high is a rolling price lookback — not affected by foreign room caps,
   daily price bands, or settlement cycle.
3. Testable against actual VN Agent data (OOS lift, ADV/liquidity, sector/year attribution)?
   → YES. VN Agent's daily price data supports 52-week rolling lookbacks.
4. Applies to top 50-100 liquid names only, or smaller names too?
   → Full ADV-qualified universe. No restriction.

VN-TRANSFER VERDICT: **PASSES all 4 checks.**

**Pre-check conclusion: PROCEED to Lane A pre-registration.**

---

## Degeneracy Pre-Check — Empirical Confirmation (2026-07-05)

**Date run:** 2026-07-05
**Source data:** `data/fireant_ssot/ta_ohlcv_panel.parquet` (1,317,849 rows; 1,564 symbols; 2017-05-18–2026-07-03)
**Universe filter:** ADV-qualified stocks (daily value >= 2B VND) in OOS window 2020-2026

The degeneracy pre-check in §(a) above concluded EXPRESSIBLE on logical grounds (no binding
constraint prevents the IV from varying). This section records the empirical confirmation:
that the three threshold levels produce meaningfully DIFFERENT trade selections (not degenerate).

**Empirical proximity distribution on OOS signal-day close prices (2020-2026):**

| Threshold (min_prox) | Interpretation | % of OOS stock-days passing | Est. OOS filtered trades |
|---------------------|----------------|----------------------------|--------------------------|
| >= 0.85 (within 15% of 52W high) | Strictest | 36.0% | ~1,368 |
| >= 0.80 (within 20% of 52W high) | Medium | 47.5% | ~1,805 |
| >= 0.75 (within 25% of 52W high) | Broadest | 57.6% | ~2,189 |

**Degeneracy verdict: CLEAN**
- Three thresholds produce distinctly different subsets (~36% / ~47.5% / ~57.6% pass-rates)
- Spread between strictest and broadest: ~21 percentage points — the IV clearly varies
- All thresholds produce >> 30 OOS trades (min N_OOS = 30)
- The test is not degenerate: the filter suppresses a meaningful, varying fraction of signals

**k = 3 confirmed** — thresholds [0.85, 0.80, 0.75] (i.e., within 15%, 20%, 25%) as pre-registered.

**G1a and G1b locked:**
- G1a: OOS MAR >= 0.9046 (baseline 0.8386 + adjusted margin 0.066)
- G1b: OOS MAR >= 0.516 (floor 0.500 + k-adj 0.016)

**Harness status:** `pp_backtest/cortex_book2_s1_52wkhi.py` written 2026-07-05. Ready for Cursor run.
Gates addendum required before Cursor runs:
`knowledge/backtests/2026-07-04_cortex_book2_s1_52wkhi_gates_addendum.md`

---

## Hypothesis under test

Adding a 52-week high proximity filter to A3_RS momentum signals improves OOS MAR versus
the A3_RS + D3 baseline, measured over the same window and entry stream.

Formally: does filtering A3_RS entry signals to only those where `price >= (52W_high × (1 − X%))`
produce a candidate system with OOS MAR meaningfully higher than the unfiltered baseline?

---

## Baseline

A3_RS + D3 sector-slot sizing system. Same entry signals as current production stack.
Same window: 2012-01-03 → 2026-07-03 (or true data start date — verify; do not assume).
Same OOS split: 2020-01-01 → 2026-07-03 (primary gates).

**Reference baseline metrics (from 2026-07-04 Book 1 gates_addendum.md):**
- Baseline OOS MAR (2020-present): 0.8386
- Baseline full-sample MAR (2012-present): 0.5321

These are D3 slot sizing baseline metrics from the same data window and entry stream.
Use these as reference points. Lock actual baseline value in the gates_addendum before running.

---

## Candidate

Same system + 52-week proximity filter at k=3 thresholds. Thresholds must be set before running
(in the gates_addendum below) — do NOT choose thresholds after seeing results.

**Suggested thresholds (set in gates_addendum):** 15%, 20%, 25% of 52-week high
(i.e., entry allowed when price >= 52W_high × 0.85, × 0.80, × 0.75 respectively).
These are starting points — the implementer should verify VN distribution and adjust in the
gates_addendum, stating the rationale.

**k = 3** — three separate, clearly-labeled sub-candidates.

---

## Gates (pre-commit before running — no post-hoc adjustment)

The gates_addendum (separate file, same naming convention as Book 1) must be written and
locked BEFORE any harness execution. This file sets the framework; the addendum sets the numbers.

### Gate structure

**G1a (relative, primary):**
candidate OOS MAR >= baseline OOS MAR + G1a_margin_adjusted
k=3 → G1a_margin_adjusted = base_margin + 0.010 × log2(3) = base_margin + 0.016

**Base margin recommendation:** +0.050 (same rationale as Book 1 — meaningful filter effect,
not noise; a proximity-only selection change on a frozen entry stream should not pass on noise).
G1a_margin_adjusted = 0.050 + 0.016 = 0.066.
At baseline OOS MAR 0.8386: candidate needs OOS MAR >= 0.9046.
**→ Lock exact value in gates_addendum. Do not adjust post-run.**

**G1b (absolute floor, derived from THIS window):**
candidate OOS MAR >= G1b_floor
Derivation: baseline OOS MAR is 0.8386. A floor of 0.500 requires the proximity-filtered
system to deliver meaningful real-world performance (not just relatively beating a baseline
that may itself be positive by luck). 0.500 is set lower than the baseline to permit some
degradation vs baseline while still requiring economically meaningful output.
**Recommendation: G1b_floor = 0.500. Lock in gates_addendum.**

**Negative-OOS cap:**
If both baseline OOS MAR AND candidate OOS MAR are negative → max status CONDITIONAL-ADVANCE.
(Not applicable if baseline is 0.8386, but required per protocol.)

**N_OOS targets:**
- >= 30 raw trades in FULL primary OOS (2020-present)
- >= 12 raw trades in EACH of the two pre-committed OOS sub-windows
Pre-commit the two sub-windows in the gates_addendum (e.g., 2020-2022 and 2023-present).
If proximity filter reduces N_OOS below 30 full OOS: VN-THIN result, not INVALIDATED.

**Multiple-testing adjustment:**
k=3 → G1a_margin = base + 0.010 × log2(3) = base + 0.016 (applied to both G1a AND G1b per protocol).
G1b_adjusted = 0.500 + 0.016 = 0.516. Lock in gates_addendum.

### Realism conventions (match Book 1)
- ADV-adjusted returns
- Fee = 30 bps, min_hold = 3 days
- Survivorship-checked
- No look-ahead

---

## Verdict mapping

- Clears G1a + G1b (both OOS sub-windows pass): candidate CALIBRATED
  → Go to Step 4 (Interaction test vs C1–C4 baseline)
  → Cite this test as evidence in knowledge.md S1 entry (window, OOS MAR values, date)
  → Counts toward expansion gate: 0 → 1 new CALIBRATED
- Fails cleanly (G1a fails, belief expressed, N_OOS >= 30): candidate INVALIDATED
  → Mark S1 INVALIDATED in knowledge.md with evidence
  → Counts toward expansion gate: 0 → 1 INVALIDATED
  → One recalibration cycle allowed: revise test spec once, re-run once, accept result
- N_OOS < 30 in FULL primary OOS: VN-THIN
  → S1 stays SOURCED; flag VN-THIN in Evidence field; defer until more OOS data
- N_OOS < 30 AND proximity filter clamped by a structural constraint: VN-SUBSUMED
  → Name constraint; add retest trigger; park

---

## Mechanism checks (required in every interaction report, after CALIBRATED verdict)

| Check | Measure | Concern |
|-------|---------|---------|
| M1 Fire count | How often does proximity filter change a signal vs unfiltered? | < 5% → near-redundant |
| M2 Signal overlap | % of S1-filtered signals that also ranked high on A3_RS RS score at entry | High overlap → proximity is already captured by RS momentum |
| M3 Regime sensitivity | Improvement in bull vs bear periods (note: C1 suppresses bear — test in bull windows only) | Proximity that "helps" only when C1 already suppresses → no operational value |

---

## Gates addendum filename convention

`0. VN Agent System/knowledge/backtests/2026-07-04_cortex_book2_s1_52wkhi_gates_addendum.md`

Write this file first, before running any harness code.

---

## Explicit rule this test does NOT touch

Running this backtest, regardless of outcome, does NOT advance the "10 real /cortex sessions"
counter (currently 1/10). This is CALIBRATION activity — it logs to this file and to knowledge.md's
changelog, never to session_log.md.

---

## Scope boundary

This pre-registration covers ONLY S1 (52-week high proximity).
It does not constitute authorization to:
- Extract new beliefs from PENDING_CANDIDATE_SOURCES (frozen)
- Modify live trading code (sizing_policy.py or live signal modules)
- Change the A3_RS signal logic
The proximity filter is an ADDITIONAL research-only layer, not a modification of existing production code.

---

## Next step (Cursor handoff)

Building the research backtest script is new code development — not live-trading-logic modification.
Route to Cursor handoff per the Claude/Cursor work division.
Handoff file convention: `00. Command Center/05_AI_Handoffs/YYYY-MM-DD_CursorHandoff_CortexBook2S1ProximityBacktest.md`

Include in handoff:
1. This pre-registration file as the spec
2. Instruction to write gates_addendum BEFORE running (lock G1a, G1b, sub-windows, thresholds)
3. Reference the Book 1 harness pattern (cortex_book1_sizing scripts) for script structure
4. Report format: OOS MAR per candidate, N_OOS per candidate, G1a/G1b verdict per candidate
5. Mechanism checks M1/M2/M3 in report
