# B_cloud Research Program — Closure Note

**Date:** 2026-07-08
**Program pre-reg:** `2026-07-07_bcloud_research_program_prereg.md`
**Terminal state:** CLOSED-NEGATIVE
**Reason:** Phase 2→3 advisory gate fired (+0.012 delta, needed +0.300); no remaining authorized phase reachable within authorized search space (S1/S2 filters + RS-proxy ranking modes)

---

## Per-Phase Results

| Phase | Method | Baseline OOS MAR | Best Result | Delta | Gate | Verdict |
|---|---|---|---|---|---|---|
| Phase 1 | S1/S2 filter overlays (8 candidates) | 0.4698 | 0.4859 (S2_1.3×) | +0.016 | G1a: 0.5357 | RESEARCH-NEGATIVE |
| Phase 2 | RS-proxy ranking modes (4/5 tested, 1 ERROR) | 0.4698 | 0.4816 (ema_dist) | +0.012 | Advisory: baseline + 0.300 | RESEARCH-NEGATIVE |
| Phase 3 | RS ranking + filter combined | — | — | — | NOT ENTERED (advisory gate blocked) | — |

## Structural Diagnosis (confirmed by both phases)

The MAR gap between B_cloud (0.4698) and the target (2.5447) is architectural:
- **FIFO ranking** is quality-agnostic — filters subtract quantity without adding quality concentration
- **partial_tp exit** (TP1=+15%, trail 2.5×ATR) clips large winners — compresses the return distribution regardless of entry quality ranking
- Selection-side levers (filters, ranking modes) are additive on FIFO but multiplicative on quality-ranked pools (A3_RS). The ceiling for this class of lever on B_cloud's architecture is estimated ~1.0–1.8 MAR.

## Untested Lever — Exit Mode

Per council verdict (2026-07-08_BcloudDirection_Council.md — Opus REDIRECT):
The exit mode (partial_tp → fixed-hold) is the mechanistically motivated untested lever. This program's authorized search space explicitly excluded exit mode changes (§2 OUT-OF-SCOPE). Testing this lever requires a **new program pre-reg**.

This program does NOT rule out B_cloud reaching target via exit-mode change. The correct closure statement is:

> "B_cloud S1/S2 filter overlays and RS-proxy ranking modes are exhausted (CLOSED-NEGATIVE). Exit-mode lever identified but not yet tested. Testing requires new program pre-reg (exit-mode class only)."

## Asset Disposition

| Asset | Disposition |
|---|---|
| B_cloud PRIMARY (paper mode) | **CONTINUES** — paper monitoring under kill criterion pre-reg (`2026-07-07_bcloud_kill_criterion_prereg.md`) |
| Phase 1 harness (`cortex_book2_bcloud_s_filters.py`) | PARKED — research artifact, RESEARCH_ONLY_NOT_PRODUCTION |
| Phase 2 harness (`cortex_book2_bcloud_ranking.py`) | PARKED — research artifact, RESEARCH_ONLY_NOT_PRODUCTION |
| S2 evidence tracker (`s2_evidence_tracker.json`) | Step 0 recorded as RESEARCH-NEGATIVE; no production implication |
| Program pre-reg | CLOSED-NEGATIVE — this closure note is the terminal artifact |

## Operator Acknowledgment Required

Per `verification-harness.md` → Research Program Pre-Registration: closure as CLOSED-NEGATIVE requires operator acknowledgment. Closure is applying the framework, not changing it — no council required.

**Pending operator decision:**
- [ ] Authorize exit-mode program pre-reg (new program, exit-mode class only, 1 decisive test)
- [ ] OR: Explicitly deprioritize B_cloud exit-mode testing ("exit lever identified but deprioritized")

`RESEARCH_ONLY_NOT_PRODUCTION`
