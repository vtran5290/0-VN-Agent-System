# Pre-Registration — Cross-Discipline S6: Stone — Kelly/Entropy Sizing
# Lane A (pending expressibility confirmation) | STATUS: UNCERTAIN-PENDING-EMPIRICAL

**Date filed:** 2026-07-05
**Status:** UNCERTAIN-PENDING-EMPIRICAL — degeneracy pre-check incomplete; pre-check gates LOCKED (see §Distributional Pre-Check Gates); sizing-sweep gates NOT YET WRITTEN
**Belief:** S6 — "Signal edge is quantifiable as mutual information between signal state and forward return; Kelly-derived sizing from that entropy should outperform flat sizing on OOS MAR"
**Source:** Stone, Information Theory: A Tutorial Introduction (2015), Ch.6–8 (Shannon entropy, mutual information, Kelly criterion)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md — belief S6
**Session context:** 2026-07-05 propagation session log — Decision 005
**Advisors:** Opus (artifact seat) + Fable (framework seat) — 2026-07-05

---

## Background: S3 Interaction Flag

S3 (Minervini risk_pct sizing) was classified VN-SUBSUMED because: all three risk_pct candidates (1.25%, 1.75%, 2.50%) produced identical position weights — the 1/20 slot cap bound before the IV could differentiate. S3 was degenerate by algebra: a uniform scalar multiplied against a hard cap collapses to the cap for the entire population.

S6's IV is structurally different: Kelly fractions are per-signal (derived from each signal's mutual information), not uniform. The slot cap can only censor the UPPER tail of the per-signal Kelly distribution. IF the distribution has meaningful mass BELOW 5%, those signals receive smaller-than-flat positions — creating cross-sectional variance the slot cap cannot suppress.

BUT: if A3_RS is already a high-selectivity filter, even its "weakest" signals may carry Kelly fractions well above 5%, making the entire distribution censored to flat — same degeneracy as S3.

This is an empirical question, not a logical one. The appropriate action is a distributional diagnostic, not a full sizing sweep.

---

## Degeneracy Pre-Check — Distributional (Opus verdict, 2026-07-05)

### EXPRESSIBILITY: UNCERTAIN-PENDING-EMPIRICAL

A priori reasoning cannot settle this case. The distributional check below is required.

### (b) Claim fidelity: Two-part structure

The S6 claim decomposes into:
- **(a) MI quantifies signal edge:** An object-level claim about information content. True or false independent of any sizing constraint.
- **(b) Kelly-from-MI sizing beats flat sizing on OOS MAR:** An operational claim conditioned on the current constraint stack (1/20 slot cap + ADV caps).

These are SEPARATELY STATUSED. Degeneracy in (b) does NOT refute (a). If (b) is VN-SUBSUMED:
- Claim (b) → VN-SUBSUMED (same constraint family as S3)
- Claim (a) → retained as SOURCED/Lane B advisory: MI as an edge-quantification and signal-ranking framework, usable even if it cannot drive sizing

**Lane fork pre-committed:**
- Pre-check returns EXPRESSIBLE → proceed to Lane A sizing sweep (write sizing-sweep gates at that time)
- Pre-check returns VN-SUBSUMED → reclassify Lane A→Lane B; (a) retained as advisory; park (b) per DEGENERACY RULE; add retest trigger (constraint-free sub-universe or regime where Kelly fractions can vary below 1/20)
- Pre-check borderline (5–15% mass below cap) → Lane B default; operator may authorize scoped mini-sweep

### (c) VN-transfer: PASSES (4/4)
1. Mathematical framework — no VN-specific exclusion. PASSES.
2. HOSE mechanics — sizing formula, not instrument-specific. PASSES.
3. Testable against VN Agent data — existing A3_RS signal set (no new generation needed). PASSES.
4. Full ADV-qualified universe — applicable. PASSES.

---

## Distributional Pre-Check — Gates (PRE-REGISTERED AND LOCKED)

**⚠️ These thresholds must NOT be modified after the distribution is computed. They were set before computation. Modifying post-hoc is selection bias.**

### What to compute

On the existing A3_RS historical signal set (2020–present, OOS period — same universe as baseline):

**Step 1 — Estimate per-signal Kelly fractions** using the conditional-moment route (recommended for computational efficiency before committing to full MI estimation):
- Bin signal instances by signal strength decile (or by signal condition — proximity quartile, volume quartile, RS score quartile — whichever is available in the signal data)
- Within each bin: compute realized win-rate (p), mean win (W), mean loss (L) on the actual hold horizon
- Derive bin-level Kelly fraction: f* = (p × W − (1−p) × L) / W (simplified form; use full-Kelly first)
- Also compute quarter-Kelly (f*/4) — the realistic operating fraction

**Step 2 — Apply constraint stack**:
- Apply slot cap: capped_f = min(f*, 0.05)
- Apply ADV cap: further reduce for any symbol where ADV participation limit < capped_f × portfolio_value

**Step 3 — Measure distribution**:
- Histogram of pre-cap Kelly fractions across all signal instances
- Measure: fraction of signal instances with pre-cap Kelly < 0.05
- Measure: coefficient of variation (CV = std/mean) of post-cap weight vector

**Step 4 — Compare to flat-sizing baseline**:
- Flat sizing = 0.05 (1/20) for all signals
- Report: does post-cap weight vector differ materially from the flat 0.05 vector?

### Pre-check gates (LOCKED — pre-registered 2026-07-05)

| Gate | Threshold | Implication |
|------|-----------|-------------|
| Signal mass below 5% | ≥ 15% of signal instances have pre-cap Kelly < 5% | Necessary condition for EXPRESSIBLE |
| Post-cap weight CV | > 0.10 | The IV must actually produce cross-sectional variance in weights |
| Both gates pass | → EXPRESSIBLE → proceed to write sizing-sweep gates and Lane A harness |
| Signal mass < 5% | < 5% of instances below cap | → VN-SUBSUMED (same constraint as S3); park (b); retain (a) as Lane B |
| Borderline (5–15% mass) | 5–15% of instances below cap | → Lane B default; operator decision before mini-sweep authorized |

**Kelly fraction flavor pre-committed:** compute and report BOTH full-Kelly AND quarter-Kelly. Pre-check gate applies to QUARTER-KELLY (the realistic operating fraction). Rationale: full-Kelly is almost never deployed in practice; a pre-check that only passes on full-Kelly overestimates expressibility.

**IS/OOS discipline:** estimate the Kelly-mapping (signal bin → fraction) on the IN-SAMPLE period (2012–2019); apply and measure distribution on the OUT-OF-SAMPLE period (2020–2026). An OOS distribution that passes on the same data used to estimate the mapping would be selection bias.

**ADV cap applied:** apply BOTH caps (slot cap 1/20 AND ADV cap) before measuring residual dispersion. A signal that passes the slot-cap check but fails the ADV cap still produces a flat weight.

---

## Sizing-Sweep Gates (NOT YET WRITTEN — will be added to this file after pre-check returns EXPRESSIBLE)

Do not write these gates until the pre-check confirms EXPRESSIBLE. Writing them now against an unknown expressibility state risks the circular-baseline trap (S6 vs flat baseline where S6 positions are structurally identical to flat for all capped signals).

When written, they will follow the standard format:
- G1a: candidate OOS MAR ≥ flat-sizing baseline OOS MAR + G1a_margin_adjusted (k TBD)
- G1b: candidate OOS MAR ≥ floor
- Negative-OOS cap, N_OOS min, two pre-committed sub-windows

Note: the baseline for the sizing comparison is the FLAT SIZING (1/20) baseline for the A3_RS entry set — NOT the full D3 baseline. This is a sizing-within-same-entries comparison.

---

## Fable Framework Ruling (2026-07-05)

Fable verdict on "distributional pre-check as degeneracy gate" — should this be encoded in PROPAGATION_PROTOCOL.md?

**FRAMEWORK VERDICT: GAP (narrow) → Option C / B-plus:**
- Step 2 of PROPAGATION_PROTOCOL.md is genuinely incomplete for the UNCERTAIN case (not provably bound, not provably free)
- Resolution: add distributional pre-check to Pruning Machinery → Routine Candidates section (NOT live schema)
- Trigger to instantiate: second belief with UNCERTAIN expressibility
- Step 2 schema unchanged until second occurrence
- This session's specific thresholds (≥15%/CV>0.10) are recorded in this file and the routine-candidate entry for provenance

**Action:** PROPAGATION_PROTOCOL.md v1.1 edit proposed → protocol_amendment_proposals.md PA-003 (pending user approval).

---

## Pre-check Implementation — Cursor handoff

**Required before any pre-check computation:**
- Confirm signal data available: historical A3_RS signal instances with condition attributes (strength score or proxy) and realized hold-period returns
- Confirm ADV cap thresholds available in the sizing logic

**Cursor script pattern:**
```python
# For each signal instance in the OOS period (2020–present):
# 1. Classify by signal-strength decile (use IS-estimated bin boundaries)
# 2. Compute conditional win-rate, mean win, mean loss on IS period
# 3. Derive quarter-Kelly fraction = (p * W - q * L) / W / 4
# 4. Apply min(f*, 0.05) and ADV cap
# 5. Collect distribution: fraction of instances with pre-cap quarter-Kelly < 0.05
# 6. Compute CV of post-cap weight vector
# 7. Report against pre-check gates
```

**Output required:**
- Pre-cap Kelly fraction histogram (full-Kelly and quarter-Kelly)
- Gate results: (i) % signal mass below 5%, (ii) post-cap CV
- Verdict: EXPRESSIBLE / VN-SUBSUMED / BORDERLINE
- Write to: `knowledge_base/2026-07-05_s6_kelly_distribution_precheck.md`

---

## Scope boundary

This pre-registration governs ONLY the distributional pre-check for S6. It does not:
- Authorize a full sizing-sweep backtest (contingent on pre-check passing)
- Modify production sizing_policy.py or any live OMS code
- Change the A3_RS signal logic
- Constitute authority to use Kelly sizing in any live or paper trading system
