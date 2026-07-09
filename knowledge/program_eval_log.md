# Program Evaluation Log — VN Agent System

**Purpose:** Track decisions about the RESEARCH PROCESS (not strategy decisions).
This is the meta-layer: did our research methodology produce useful, non-overfit results?

Distinct from `research_backlog.md` (strategy candidates) and `protocol_amendment_proposals.md` (rule changes).
This log answers: "Was the way we decided to research this thing a good design?"

Inspired by: auto-research principle — the research organization itself is a config that can be optimized.
Per Boris Principle: every AI error or process success updates a rule, not just a re-prompt.

---

## How to use

After each research phase closes (APPROVE / REJECT / PARKED), append an entry here.
Rate the PROCESS quality, not the outcome quality (Duke principle: separate decision quality from P&L).

Entry format:
```
## YYYY-MM-DD — [Program/Phase slug]

**Process design:** [what research approach was chosen — parameter bounds, baseline, regime splits, iteration count]
**Why that design:** [what reasoning led to this scope/methodology]
**Outcome:** [what result was produced]
**Process quality rating:** SOLID | ACCEPTABLE | WEAK
  SOLID = clear hypothesis, pre-registered gates, verifiable metric, regime-conditioned, kill criterion declared
  ACCEPTABLE = gates present but scope was wide or kill criterion fuzzy
  WEAK = post-hoc gate design, unbounded search, or gates calibrated on the result window
**What the design got right:** [specific]
**What the design got wrong or missed:** [specific]
**Rule implication:** [should this change how we scope future programs? If yes, cite target file.]
```

---

## Entries

### 2026-07-09 — S2 Vol-Filter Advisory Program (PA-003 through PA-008 family)

**Process design:** Pre-registered gates for each S2 variant; separate IS/OOS windows; regime-conditional sub-gates (sub-B floor); advisory-only constraint enforced throughout. Kill criterion: advisory status stays unless OOS MAR > baseline + 0.050 margin AND sub-B MAR > 0.

**Why that design:** S2 is an overlay, not a base signal. Advisory-only constraint prevents contaminating OMS while research runs. Pre-registered gates prevent p-hacking. Sub-B floor prevents "loses less" counting as proof.

**Outcome:** S2 advisory — still ADVISORY ONLY as of 2026-07-09. Evidence tracker active. Gate has not fired for full promotion.

**Process quality rating:** SOLID
- Pre-registration consistent throughout
- Regime-conditioned evaluation (sub-A, sub-B, combined)
- Kill criterion pre-declared
- Advisory-only quarantine maintained

**What the design got right:**
- Separating advisory layer from OMS was correct — prevented premature routing
- Sub-regime gates prevented a misleading full-period result
- Evidence tracker (`s2_evidence_tracker.json`) provides machine-readable cumulative state

**What the design got wrong or missed:**
- Gate calibration window vs promotion target window mismatch was discovered mid-program (gate-flaw, corrected per verification-harness.md)
- No explicit "max program duration" pre-registered — risk of indefinite advisory drift
- Kill criterion for "indefinitely stays advisory" was implicit, not explicit

**Rule implication:** Add `max_duration_weeks` field to any advisory-overlay pre-reg. Explicit end-state: promote, kill, or force a decision after N weeks. → Candidate for verification-harness.md exit-class gate section.

---

### 2026-07-09 — S15/S16 Council Session (Sizing/Exit overlay research)

**Process design:** Dual-judge council (opus + fable) for each promotion candidate. Pre-registered gates per verification-harness.md § Overlay-class gate. Phase-transition gates pre-declared with fire-consequences.

**Why that design:** Second occurrence of exit-class overlay → formalized gate template required per 2nd-occurrence rule.

**Outcome:** PA-009 CLOSED-NEGATIVE (exit-overlay ADVERSE-REVERSAL). Council unanimous 3/3.

**Process quality rating:** SOLID
- All three judges independent
- Pre-registered gates with declared fire-consequences
- ADVERSE-REVERSAL annotation correctly applied
- Root-cause note required before slot re-registration

**What the design got right:**
- Independent verdict protocol prevented anchoring
- Declaring fire-consequences in advance made CLOSED-NEGATIVE unambiguous
- PARKED-[REGIME-CONFOUNDED] vs CLOSED-NEGATIVE distinction cleanly applied

**What the design got wrong or missed:**
- Two-leg accounting requirement (exit-class pre-reg field) was added after the session as a gap, not before — suggests the gate template was not yet fully stable when first applied

**Rule implication:** Overlay-class gate template should require two-leg accounting BEFORE first run, not as a gap discovered during. Already captured in verification-harness.md 2026-07-08 entry. No new rule needed. CONFIRMED HOLDS.

---

## Running observations

**Pattern so far (2 entries):**
- Pre-registration is consistently the strongest predictor of SOLID process ratings
- The weakest point in every program is "max duration" / explicit end-state — programs drift into indefinite advisory without an explicit termination trigger
- Council independence protocol consistently rates as the highest-quality design decision

**Suggested next process improvement:**
- Add `max_duration_weeks` to all backlog items that are advisory-only or long-running
- Consider a quarterly "process audit" that asks: which programs closed cleanly vs. which are still open after >12 weeks without a gate firing?

---

## Meta-program evaluation (quarterly)

Each quarter, review this log and ask:
1. What fraction of programs were SOLID process design? (Target: >70%)
2. What is the most common WEAK process pattern? (Use to update verification-harness.md)
3. Did any WEAK-rated program produce better results than a SOLID-rated program? (Duke principle: process quality ≠ outcome quality, but track the correlation)
4. Is the research backlog getting longer or shorter? (If longer: queue mechanics may need a P3-expiry rule)
