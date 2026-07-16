# Opus Anti-COI Review Queue

Items in this file are staged belief candidates that need independent Opus review before promotion.
Anti-COI rule: belief generated and reviewed must be in different sessions/models.

## Pending Review

### P1 — Regime coverage > elapsed time
- Source: NEW_BELIEF_CANDIDATES_2026-07-13.md
- Staged: 2026-07-13
- Falsification: [see source file]
- Action needed: Opus session to independently evaluate and either APPROVE → CALIBRATED or REJECT

### P2 — Failure loop must close for learning
- Source: NEW_BELIEF_CANDIDATES_2026-07-13.md
- Staged: 2026-07-13
- Falsification: [see source file]
- Action needed: Opus session to independently evaluate and either APPROVE → CALIBRATED or REJECT

---

## BATCH 2: VN Agent Macro Beliefs — 2026-07-15
Source: VN_AGENT_MACRO_BELIEFS_20260715.md
Submitted by: Fable (2026-07-15 session)
Anti-COI status: SOURCED — awaits Opus independent review before CALIBRATED promotion

### M1 — FTSE EM Upgrade as Bull Override Catalyst
- Source: VN_AGENT_MACRO_BELIEFS_20260715.md
- Staged: 2026-07-15
- Lane: A
- Key scrutiny: passive flow magnitude ($5–6B) verification; analog quality (Saudi/Kuwait vs VN); exception protocol design
- Action needed: Opus review → APPROVE or REDIRECT → operator sign-off before any weekly_notes update

### M2 — Vietnam Bond Yield 5% Systemic Stress Veto
- Source: VN_AGENT_MACRO_BELIEFS_20260715.md
- Staged: 2026-07-15
- Lane: A
- Key scrutiny: pull historical VGB data; confirm 2022 crossing was leading not lagging; single-observation caveat
- Action needed: Opus review → APPROVE with SINGLE-OBSERVATION caveat or REDIRECT for more data

### M3 — Commodity Selectivity (LNG/Crude/Coal)
- Source: VN_AGENT_MACRO_BELIEFS_20260715.md
- Staged: 2026-07-15
- Lane: B
- Key scrutiny: verify spot prices independently; assess whether belief vs inline weekly note is appropriate
- Action needed: Opus review → APPROVE or downgrade to weekly-note-only

### M4 — FTSE Narrow Bull Risk for Breadth C1
- Source: VN_AGENT_MACRO_BELIEFS_20260715.md
- Staged: 2026-07-15
- Lane: B
- Key scrutiny: belief vs protocol note decision; sub-claim (a) verifiability; forward-only test design
- Action needed: Opus review → APPROVE as belief, REDIRECT to weekly_notes/template.md, or REQUEST-REDESIGN

### M5 — Crude Normalization / SBV Rate Cut Timing
- Source: VN_AGENT_MACRO_BELIEFS_20260715.md
- Staged: 2026-07-15
- Lane: B
- Key scrutiny: Q4 2026 timing vs SBV current signals; 2023 analog quality; IEA re-escalation tail risk
- Action needed: Opus review → APPROVE or revise timing estimate

INSTRUCTION FOR OPUS: Review each belief independently. Approve each to CALIBRATED or flag for rejection with specific reason. LLM-only promotion to CALIBRATED is protocol-prohibited — you are the anti-COI gate here.

---

## BATCH 3: Constitution Amendment H — Learning Companion Protocol — 2026-07-16
Source: `D:\V\00. Command Center\05_AI_Handoffs\AMENDMENT_H_PROPOSAL_20260716.md`
Submitted by: V (V-ACTION-19, 2026-07-16). Queued by Claude CLI.
Proposer: Fable (Cowork session, architecture advisor seat)

⚠️ **ARTIFACT CLASS DIFFERS FROM BATCHES 1–2.** This is a **Constitution amendment**, not a staged belief.
Do **not** apply the APPROVE→CALIBRATED path. Required output is a **FRAMEWORK VERDICT** per
CONSTITUTION.md Article VI §6.2 step 3. Amendment H introduces no propositional beliefs.

### H1 — Article XI (NEW): Learning Companion Protocol
- Proposal: `AMENDMENT_H_PROPOSAL_20260716.md`
- Staged: 2026-07-16
- Sonnet review: PASS on file (proposal § "Sonnet review") — no conflicts detected
- Type: Addition (new article; no existing article modified). If ratified → Constitution v1.0.8.

**Substance:** mandates a Teaching Layer on substantive outputs (§11.2.1); question-depth-based
teaching level calibration 1–4 (§11.2.2); a mandatory LEARNING_DIGEST per session (§11.3); a
`§Learning Companion` section in the canonical brain (§11.4); an anti-COI carve-out for Teaching
Layers (§11.5); seed domain levels (§11.6).

**Key scrutiny for Opus:**
1. **§11.5 anti-COI carve-out is the load-bearing clause.** It exempts Teaching Layers from
   Generator-Reviewer Separation. Section 4.1 is **unamendable** under Article VI §6.3. Does the
   carve-out narrow an unamendable provision by redefining what counts as a belief? The proposal
   argues the carve-out is narrow (only *new claims* inside a Teaching Layer trigger propagation).
   Test that boundary — "explanation" vs "claim" is agent-adjudicated at write time, with no gate.
2. **Generator-reviewer status of the proposal itself.** Fable proposed Amendment H, wrote the
   first LEARNING_DIGEST under it, self-assessed V's seed levels (§11.6), and authored the staged
   brain update. This Opus seat is the only independent review in the chain. Do not anchor on the
   Sonnet PASS — it was produced in the same lineage.
3. **§11.6 seed levels are a Fable assessment of V**, entering the canonical brain as fact with no
   independent basis. Is a self-generated calibration of the operator an appropriate brain entry,
   or should seeds be operator-declared?
4. **§11.2.1 obligation scope** — "≥10 lines or involving a non-obvious decision" binds *every*
   agent on *every* substantive output, including Haiku extraction workers. Is the Teaching Layer
   coherent at the Haiku tier, or does it force judgment onto a tier explicitly barred from it
   (advisor-routing.md: haiku "No judgment")?
5. **Hypertrophy check.** Boris principle: framework hypertrophy is the named primary failure mode
   of this workspace. Amendment H adds a mandatory per-session artifact plus a per-output
   obligation. Is the LEARNING_DIGEST pipeline's dependency on the Sonnet weekly health pass
   (flagged as a gap in the digest's own §6) a live prerequisite rather than a downstream detail?

- Action needed: Opus FRAMEWORK VERDICT (HOLDS | GAP | CONFLICT) + REASONING + RULE IMPLICATION.
  Write verdict into the "Opus FRAMEWORK VERDICT" block of `AMENDMENT_H_PROPOSAL_20260716.md`.
  → then V countersign (Article VI §6.2 step 4) → then ratification + downstream effects (step 5).

**BLOCKED ON THIS VERDICT (do not execute before it lands):**
| Held action | Target | Gate |
|---|---|---|
| V-ACTION-20 — brain update v29→v30 (§Learning Companion) | `D:\V\.claude\brains\vn-trading-advisor\knowledge.md` | Staged file states: *"V applies after Amendment H is approved"* |
| V-ACTION-21 — CLAUDE.md rule (root + domain) | root + `0. VN Agent System\.claude\CLAUDE.md` | Amendment H "Downstream effects" table; Article VI §6.2 step 5 |

INSTRUCTION FOR OPUS (Batch 3): This is a framework question, not a belief promotion. Judge the
framework. Do not anchor on the Sonnet PASS or on Fable's rationale — both originate in the
proposing lineage. Output FRAMEWORK VERDICT format only.

_Batch 3 queued 2026-07-16 by Claude CLI per V-ACTION-19. Countersign after verdict._
