# B_cloud Research Program — Program-Level Pre-Registration

**Pre-registered:** 2026-07-07  
**Domain:** VN Agent System — B_cloud strategy research  
**Council mandate:** Fable GAP verdict (2026-07-07) — required before iterative B_cloud research loop proceeds  
**Operator override note:** This program supersedes the CONDITIONAL verdict issued 2026-07-07 (see council file `2026-07-07_BcloudDirection_Council.md`). That verdict used "CONDITIONAL/defer until A3_RS shadow reaches 20 decisions" — classified as REDIRECT-with-named-condition. Per high-stakes-triggers.md §4, operator is final tiebreaker. Operator has explicitly waived the deferral condition and authorized immediate research. This document is the governance artifact for that decision.

---

## 1. Program Goal

**Goal metric:** B_cloud PRIMARY achieves OOS MAR > **2.5447** (the A3+S2 benchmark, validated OOS 2020–2026 on A3_RS pipeline)  
**Goal interpretation:** B_cloud OOS MAR must exceed the A3+S2 CALIBRATED figure on B_cloud's own evaluation pipeline (ema_portfolio_sim, not D3 pipeline). Cross-architecture comparison with A3+S2 is directional only — the goal is a *relative ordering* (B_cloud beats the historical benchmark), not a claim that the architectures are equivalent.  
**Goal failure definition:** If no candidate within the authorized search space achieves OOS MAR ≥ 2.0 after Phase 3, the program is FAILED. B_cloud remains in kill-criterion monitoring (2026-07-07_bcloud_kill_criterion_prereg.md); research investment ends.  

---

## 2. Search Space (authorized research phases)

| Phase | Scope | Authorization |
|-------|-------|---------------|
| **Phase 1** | S1/S2 filter overlays — 8 named candidates (S1×3, S2×3, S1+S2 AND, S1+S2 OR) | **Pre-registered 2026-07-06** — already authorized, running as of 2026-07-07 |
| **Phase 2** | RS-based ranking variant (`B_cloud_RS`): port D3 sector-RS sort key into B_cloud (keep partial_tp, cloud_only, max_pos=20). Test RS ranking vs FIFO baseline. | **Authorized here** — requires its own per-run pre-reg before execution. New architecture (cross-architecture per verification-harness.md); Trigger #5 at promotion time. |
| **Phase 3** | Combined: `B_cloud_RS` + best Phase 1 filter overlay | **Authorized here** — only if Phase 2 shows RS variant achieves ≥ 0.5 MAR improvement over FIFO baseline. Requires its own per-run pre-reg. Trigger #5 at promotion. |

**Out of scope (unauthorized without new program-level pre-reg):**
- Changing exit mode from partial_tp to any other (fixed-hold, full-trail, chandelier)
- Expanding universe beyond ex_vin3 (adding VIC/VHM/VRE)
- Changing EMA parameters (20/100 is locked)
- Any write to `final_action`, OMS, or DNSE
- Any promotion without Trigger #5 dual-judge (opus + ChatGPT) + user sign-off

---

## 3. Iteration Governance

**Per-run pre-regs remain required** within each phase. This program pre-reg does not replace them — it *bounds the loop* they operate within. No run may proceed without its own per-run pre-reg specifying:
- Specific candidates and thresholds
- Baseline OOS MAR (known from prior run or locked from this pre-reg)
- G1a relative gate (baseline + 0.066 for filter overlays; recalibrate for RS variant)
- G1b advisory floor
- N_OOS thresholds
- Direction expectation

**Iteration cap:** Maximum 3 research phases (Phase 1 + Phase 2 + Phase 3). No Phase 4 without a new program pre-reg.

**Phase transition gates:**
- Phase 1 → Phase 2: Phase 1 must complete (all 8 candidates run, verdicts recorded). Phase 2 authorized regardless of Phase 1 results (FIFO → RS is the structural fix; filter results are informative but not blocking).
- Phase 2 → Phase 3: Phase 2 must show RS variant OOS MAR ≥ baseline + 0.30 on B_cloud ema_portfolio_sim pipeline (not a binding gate — advisory; prevents running Phase 3 on a failing RS ranking that degrades further with filter stacking).

---

## 4. Program Kill Criterion

The research program terminates as FAILED if:
- After Phase 3: best candidate OOS MAR < 2.0 AND both sub-windows (2020-2022, 2023-2026) are negative
- OR: after Phase 2, RS ranking degrades vs FIFO baseline (MAR gap negative), making Phase 3 pointless

Program FAIL ≠ production KILL. Production monitoring continues under `2026-07-07_bcloud_kill_criterion_prereg.md`. A research program fail means no new production candidate was found; B_cloud continues in paper monitoring mode under the production kill criterion document.

---

## 5. Pre-registered Direction Expectations

| Research question | Pre-registered expectation |
|-------------------|---------------------------|
| Do S1/S2 filters add value on B_cloud? | POSITIVE direction expected for S2 (same entry signals as A3_RS). S1 secondary. Magnitude uncertain — partial_tp exit interacts with vol filter differently than A3_RS fixed-hold. |
| Does RS ranking (vs FIFO) improve B_cloud MAR? | **STRONGLY POSITIVE expected** — RS ranking is the primary structural explanation for A3_RS MAR > B_cloud MAR. Porting RS sort key should capture a meaningful portion of the gap. Magnitude target: ≥ 0.5 MAR improvement over FIFO baseline. |
| Does Phase 3 (RS + filter) exceed Phase 2 (RS alone)? | POSITIVE but diminishing returns expected. The filter should add a smaller increment on top of RS ranking than on top of FIFO. |

---

## 6. Cross-Architecture Governance

Per verification-harness.md (cross-architecture promotion section):
- Phase 1 results are B_cloud-specific evidence only — do NOT feed into A3_RS gates
- Phase 2 (B_cloud_RS) creates a new architecture requiring its own pre-registered shadow track before production. B_cloud_RS research → Trigger #5 dual-judge → shadow paper run → graduation review (per `2026-07-05_shadow_a3rs_s1_prereg.md` pattern, adapted for B_cloud_RS)
- Incumbent disposition (replace/coexist/sunset B_cloud FIFO) must be stated in the Trigger #5 graduation review pack for any Phase 2/3 promotee — this is already a blocking precondition per verification-harness.md

---

## 7. Output Locations

| Phase | Output path |
|-------|-------------|
| Phase 1 | `data/research/cortex_book2_bcloud/bcloud_s_filters_report.md` (existing) |
| Phase 2 | `data/research/bcloud_rs/bcloud_rs_baseline_report.md` (to be created) |
| Phase 3 | `data/research/bcloud_rs/bcloud_rs_plus_filter_report.md` (to be created) |
| Program summary | `data/research/bcloud_program/bcloud_research_program_summary.md` (after each phase) |

---

## 8. Scope Summary

**IN SCOPE:**
- S1/S2 filter overlays on B_cloud PRIMARY (Phase 1)
- RS ranking variant of B_cloud PRIMARY (Phase 2)
- RS ranking + filter overlay combined (Phase 3)
- Per-run pre-regs for each Phase 2/3 run
- Research summary after each phase

**OUT OF SCOPE:**
- Exit mode changes
- Universe changes
- EMA parameter changes
- Any production integration without Trigger #5 dual-judge
- A3_RS research (separate track, separate pre-regs)

---

## 9. References

- Phase 1 per-run pre-reg: `knowledge/backtests/2026-07-06_cortex_book2_bcloud_s_filters_prereg.md`
- B_cloud kill criterion (production): `knowledge/backtests/2026-07-07_bcloud_kill_criterion_prereg.md`
- Operator override authority: `D:\V\.claude\rules\high-stakes-triggers.md` §4
- Council verdict (superseded): `00. Command Center/05_AI_Handoffs/2026-07-07_BcloudDirection_Council.md`
- Fable GAP verdict (mandated this pre-reg): `00. Command Center/05_AI_Handoffs/2026-07-07_BcloudResearch_Council.md` (written this session)
- Cross-architecture rules: `D:\V\.claude\rules\verification-harness.md`

`RESEARCH_ONLY_NOT_PRODUCTION`
