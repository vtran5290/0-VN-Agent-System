# Pre-Registration — Cortex Book 2: S2 — O'Neil Breakout Volume Filter
# Lane A (backtestable)

**Date filed:** 2026-07-04
**Status:** PENDING RUN — gates locked, harness not yet built
**Belief:** S2 — "Breakout volume must be 40%+ above 50-day average to confirm trend signal"
**Source:** O'Neil, How to Make Money in Stocks, Ch.2 (CAN-SLIM S = Supply/Demand)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md — belief S2
**Phase 1–4 audit context:** knowledge_base/2026-07-04_BookPropagation_Progress.md

---

## Why this test is "Book 2" priority

S2 is the volume companion to S1 (52-week proximity). Both are O'Neil entry filters on A3_RS.
S2 can be run in the same Cursor session as S1 (separate scripts or combined multi-filter test).
If combined in one run: pre-register S1+S2 interaction gate BEFORE combining (per Step 4 protocol).

**Run order recommendation:** run S1 standalone first; if S1 passes, run S2 standalone, then
S1+S2 interaction. This avoids testing a combined system before either filter is individually validated.

---

## Degeneracy Pre-Check (Step 2 answers — mandatory before harness spend)

### (a) Expressibility
"Which VN constraint binds first if I run this test?"

The test: binary entry filter on A3_RS signals — "enter only if current bar volume >= X×
50-day average volume." Independent variable = multiplier X (e.g., 1.2×, 1.3×, 1.4×).

Constraint check:
- Slot cap, ADV cap: Sizing constraints — do not prevent volume-based selection. IV varies.
- C1 bear suppression: Bear periods suppressed equally for baseline and candidate. Wash.
- Price bands: Affect single-bar price move, not volume calculation. Irrelevant.
- **VN volume pattern (KEY RISK — NOT a structural constraint like the slot cap):**
  The 40% threshold (1.4× average) is calibrated on US stock data. In VN's thinner market:
  (a) If VN A3_RS names frequently spike volume >= 1.2× their 50-day average on signal days
      → IV varies → EXPRESSIBLE → normal test.
  (b) If VN names almost never achieve even 1.2× average volume on signal days
      → near-zero N_OOS → VN-THIN (thin EMPIRICAL distribution, not structural constraint)
  This is different from S3's failure (structural slot-cap binding). Here the constraint is
  empirical — we don't know the answer until we run it. Testing k=3 (1.2×, 1.3×, 1.4×)
  reveals which thresholds are viable in VN.

EXPRESSIBILITY VERDICT: **LIKELY EXPRESSIBLE** — no structural binding found.
VN-THIN RISK: elevated. If ALL three thresholds yield N_OOS < 15, classify VN-THIN (not INVALIDATED,
not VN-SUBSUMED). Mitigation: test 1.2× (lower than US standard) to maximize N_OOS.

### (b) Claim fidelity
O'Neil's exact claim: volume >= 40% above 50-day average is required to CONFIRM a breakout.
The 40% figure is US-market calibrated. In VN: the equivalent "confirmation level" may be lower.

Proposed test: filter A3_RS signals by volume multiplier. Directly tests whether a volume surge
threshold improves signal quality.

Threshold calibration decision: testing 1.2×/1.3×/1.4× lets the VN data reveal the right level
rather than dogmatically importing the US-calibrated 1.4×. This is more faithful to the
underlying claim ("volume surge confirms quality") than testing only 1.4×.

**Known proxy concerns:**
- M2 overlap: VN A3_RS signals fire on RS rank momentum, itself correlated with institutional
  buying → institutional buying flow already biases the A3_RS universe toward volume-active
  names. The volume filter may be partially redundant with existing RS screening.
- VN volume microstructure noise: foreign institution block trades and day-trading flurries may
  produce volume spikes that don't correspond to genuine accumulation. This is a known risk.
  Harris (Trading and Exchanges) would help quantify this — but that source is frozen.

CLAIM FIDELITY VERDICT: **ACCEPTABLE** — with M2 overlap and microstructure noise risks
documented. These are mechanism-check findings, not grounds to reject the test design.

### (c) VN-transfer check
1. Assumes short-selling/borrow/derivatives/intraday liquidity VN lacks? → NO. Pure volume screen.
2. Survives HOSE/HNX/VSDC mechanics?
   → PARTIAL CONCERN. VN volume mechanics differ: foreign room caps can cause artificial volume
   clustering; batch auction periods may skew volume relative to US continuous-session baseline.
   The 50-day average computed on VN trading days is a valid approximation, but noise level
   is higher than US equivalent. Flag as known risk; proceed.
3. Testable against actual VN Agent data? → YES.
4. Applies to top 50-100 liquid names or smaller? → ADV-qualified universe (same as A3_RS).

VN-TRANSFER VERDICT: **PASSES 3/4 — concern on check #2 (microstructure noise).**
Proceed with flag; document in harness report.

**Pre-check conclusion: PROCEED to Lane A pre-registration with VN-THIN risk acknowledged.**

---

## Hypothesis under test

Adding a volume confirmation filter to A3_RS momentum signals improves OOS MAR versus the
A3_RS + D3 baseline, by selecting only entries where current bar volume exceeds the
50-day rolling average volume by a meaningful multiple.

Formally: does filtering A3_RS entry signals to only those where `volume >= X × vol_50d_avg`
produce a candidate system with OOS MAR meaningfully higher than the unfiltered baseline?

---

## Baseline

A3_RS + D3 sector-slot sizing system. Same entry signals. Same window: 2012-01-03 → 2026-07-03.
Same OOS split: 2020-01-01 → 2026-07-03.

**Reference baseline metrics (from 2026-07-04 Book 1 gates_addendum.md):**
- Baseline OOS MAR (2020-present): 0.8386
- Baseline full-sample MAR (2012-present): 0.5321

50-day average volume: computed on trading days only (days with volume > 0). Verify implementation
matches this definition; document any divergence as an assumption.

---

## Candidate

Same system + volume filter at k=3 thresholds. Thresholds must be set in gates_addendum
BEFORE running.

**Suggested thresholds (set in gates_addendum):** 1.2×, 1.3×, 1.4× of 50-day average volume.
Rationale: 1.4× = O'Neil's stated 40%. 1.2× and 1.3× are VN-calibrated lower bounds.
The implementer should check empirical distribution of VN volume spikes on A3_RS signal days
to confirm whether 1.2× is achievable (brief descriptive analysis before running full harness).

**k = 3** (unless one threshold is VN-THIN in preliminary check — see VN-THIN handling below).

---

## Gates (pre-commit before running — no post-hoc adjustment)

### Gate structure

**G1a (relative, primary):**
candidate OOS MAR >= baseline OOS MAR + G1a_margin_adjusted
k=3 → G1a_margin_adjusted = base_margin + 0.010 × log2(3) = base_margin + 0.016
Base margin recommendation: +0.050. G1a_margin_adjusted = 0.066.
At baseline OOS MAR 0.8386: candidate needs OOS MAR >= 0.9046.
→ Lock exact value in gates_addendum before running.

**EXCEPTION: if any threshold is VN-THIN (N_OOS < 15):**
- Exclude that threshold from the k count. Recompute k for the remaining viable thresholds.
- k=2 (1.2× and 1.3× viable, 1.4× VN-THIN): G1a_adj = 0.050 + 0.010 × log2(2) = 0.060
- k=1 (only one threshold viable): G1a_adj = 0.050 (no multiple-testing adjustment)
- Lock the effective k and threshold list in gates_addendum before running.

**G1b (absolute floor, derived from THIS window):**
Recommendation: 0.500 (same as S1 — same rationale, same baseline).
G1b_adjusted for k=3: 0.500 + 0.016 = 0.516.
→ Lock in gates_addendum.

**Negative-OOS cap:**
If both baseline OOS MAR AND candidate OOS MAR are negative → max CONDITIONAL-ADVANCE.

**N_OOS targets:**
- >= 30 raw trades in FULL primary OOS (2020-present) per viable threshold
- >= 12 per each of the two pre-committed OOS sub-windows
- Pre-commit sub-windows in gates_addendum (consistent with S1 sub-windows)

**VN-THIN rule for S2:**
If ALL three thresholds (1.2×, 1.3×, 1.4×) yield N_OOS < 15 in full primary OOS:
→ Classify S2 as VN-THIN.
→ Note in knowledge.md: "VN volume rarely exceeds 1.2× 50-day average on A3_RS signal days —
  insufficient sample to test O'Neil's claim at any tested threshold. Defer until:
  (a) universe expansion to more liquid names, or (b) lower threshold calibration study."
→ This is NOT INVALIDATED. The IV (volume threshold) may still vary if the threshold is set
  lower. A future retest with thresholds < 1.2× is legitimate — pre-register separately.

**Multiple-testing adjustment:** applied as stated above (k varies by viable threshold count).
Same adjustment applied to both G1a AND G1b per PROPAGATION_PROTOCOL.md §Section 1.

### Realism conventions (match Book 1 and S1)
- ADV-adjusted returns
- Fee = 30 bps, min_hold = 3 days
- Survivorship-checked
- No look-ahead
- 50-day average volume: rolling on trading days only (verify vs Book 1 data conventions)

---

## Verdict mapping

- Clears G1a + G1b (viable thresholds, both OOS windows): candidate CALIBRATED
  → Go to Step 4 (Interaction test vs C1–C4 baseline; if S1 already CALIBRATED, test S1+S2 combined)
  → Cite this test in knowledge.md S2 entry
  → Counts toward expansion gate: new CALIBRATED
- Fails cleanly (G1a fails, belief expressed, N_OOS >= 30): candidate INVALIDATED
  → Mark S2 INVALIDATED with evidence
  → One recalibration cycle allowed: adjust threshold calibration rationale once, re-run once
- ALL thresholds VN-THIN (N_OOS < 15 across all viable thresholds): VN-THIN
  → S2 stays SOURCED with VN-THIN annotation; defer
- Specific threshold(s) VN-THIN, others viable: test viable thresholds only under adjusted k

---

## Mechanism checks (required if CALIBRATED verdict reached)

| Check | Measure | Concern |
|-------|---------|---------|
| M1 Fire count | % of A3_RS signals that meet volume filter | < 5% → near-redundant (too few signals change) |
| M2 Signal overlap | Correlation between high-volume signal days and high RS rank | High → volume filter redundant with A3_RS momentum |
| M3 Regime sensitivity | Volume improvement in bull vs bear periods | Filter that "helps" only in suppressed-signal bear regimes has no operational value |
| VN-MICRO check | Descriptive: % of A3_RS signal days where volume >= 1.2× 50d avg | If < 20% of signal days meet even 1.2× → volume spikes are rare in VN; VN-THIN risk quantified |

---

## VN-Thin risk mitigation (run this BEFORE full harness)

Before building the full research script, run a lightweight empirical check:
"On A3_RS signal days in the VN backtest universe (2020-present), what % of signals have
volume >= 1.2×, 1.3×, 1.4× of their 50-day average?"

If < 20% of signals meet 1.2×: VN-THIN risk is HIGH. Consider:
- Lowering the threshold range to 1.0×, 1.1×, 1.2× instead (re-pre-register with these levels)
- Documenting this as a VN market microstructure finding

This empirical check takes 5 minutes. It prevents building a full harness for a degenerate test.

---

## VN-THIN Pre-Check Result (2026-07-05 empirical — LOCKED)

**Date run:** 2026-07-05
**Source data:** `data/fireant_ssot/ta_ohlcv_panel.parquet` (1,317,849 rows; 1,564 symbols; 2017-05-18–2026-07-03)
**Universe filter applied:** ADV-qualified stocks only (daily value >= 2B VND) in OOS window 2020-2026

**Empirical volume distribution on ADV-qualified stock-days (OOS 2020-2026):**

| Threshold | % of stock-days meeting threshold | Est. OOS filtered trades (from ~3,800 baseline) |
|-----------|----------------------------------|--------------------------------------------------|
| volume >= 1.2× 50d avg | 29.1% | ~1,106 |
| volume >= 1.3× 50d avg | 24.6% | ~933 |
| volume >= 1.4× 50d avg | 20.8% | ~788 |

**VN-THIN verdict: NOT TRIGGERED**
All three thresholds produce >>30 OOS trades (min requirement = 30 full OOS). Even the strictest
threshold (1.4×) retains ~788 estimated OOS filtered trades — 26× the minimum N_OOS threshold.

**k = 3 LOCKED** — no threshold adjustment required. Thresholds remain [1.2×, 1.3×, 1.4×] as pre-registered.

**G1a and G1b unchanged** (k=3 was already the pre-registered assumption):
- G1a: OOS MAR >= 0.9046 (baseline 0.8386 + adjusted margin 0.066)
- G1b: OOS MAR >= 0.516 (floor 0.500 + k-adj 0.016)

**Harness status:** `pp_backtest/cortex_book2_s2_volume.py` written 2026-07-05. Ready for Cursor run.
VN-THIN result embedded in script docstring. Gates addendum file required before Cursor runs:
`knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_gates_addendum.md`

---

## Gates addendum filename convention

`0. VN Agent System/knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_gates_addendum.md`

Write this file (with locked k, thresholds, G1a, G1b, sub-windows) BEFORE running harness code.
The VN-THIN empirical check must inform the threshold list in the addendum.

---

## Interaction gate (if S1 is CALIBRATED and S2 is CALIBRATED)

If both S1 (proximity) and S2 (volume) reach standalone CALIBRATED, pre-register the S1+S2
combined interaction test BEFORE combining them. Per PROPAGATION_PROTOCOL.md Section 2:

Combined candidate: A3_RS + D3 + S1 proximity filter + S2 volume filter
Baseline: A3_RS + D3 + S1 (the state after S1 is CALIBRATED and integrated)
G_ia: combined OOS MAR >= S1-included baseline OOS MAR − 0.020
G_ib: combined full-sample MAR >= S1-included baseline full-sample MAR − 0.010

Pre-register this interaction gate in a separate file before running the combined system.

---

## Explicit rule this test does NOT touch

Running this backtest does NOT advance the "10 real /cortex sessions" counter (currently 1/10).
CALIBRATION activity — logs to this file and knowledge.md changelog, never to session_log.md.

---

## Scope boundary

This pre-registration covers ONLY S2 (breakout volume).
Does NOT authorize:
- Extraction from PENDING_CANDIDATE_SOURCES (frozen)
- Modification of live trading code (sizing_policy.py or live signal modules)
- Changes to A3_RS signal logic
The volume filter is an ADDITIONAL research-only layer.

---

## Next step (Cursor handoff)

Build the research backtest script via Cursor handoff.
Recommended: single Cursor session for both S1 and S2 scripts (shared data loading, shared
baseline computation, separate filter implementations and reports).

Handoff file convention: include both S1 and S2 in one handoff if run together:
`00. Command Center/05_AI_Handoffs/YYYY-MM-DD_CursorHandoff_CortexBook2S1S2EntryFilterBacktest.md`

Sequence within handoff:
1. Empirical VN-THIN check for S2 (quick pass on volume distribution)
2. Write S2 gates_addendum (update k and thresholds based on VN-THIN check)
3. Run S1 harness (from S1 pre-reg)
4. Run S2 harness
5. If both CALIBRATED: write S1+S2 interaction pre-registration, then run interaction test
