# vn-trading-advisor — Knowledge Base
# v27 | 2026-07-08 | S2 ext COMPLETE (1.4× is optimal peak; 1.5×/1.6× CONDITIONAL-ADVANCE both G1a FAIL); S20 gate-zero BORDERLINE (78.8%); PA-008 PASS; PA-009 VIABLE
# 6 CALIBRATED / 7 SOURCED / 4 AXIOMATIC / 1 INVALIDATED / 2 VN-SUBSUMED / 1 VN-THIN / 1 TESTED / 5 DEGRADING-REJECT / 1 VN-DEGENERATE
# Source: knowledge/knowledge_v18_PENDING_WRITE.md — applied as full replacement (2026-07-06); S20 appended 2026-07-06
# Cap: 300 lines max. Archive entries >90 days old to knowledge/archive/
# SESSION START: read this file first; inject CALIBRATED + AXIOMATIC rows as active priors.

## Belief Schema
  regime_scope:     bull | bear | agnostic
  calibrated_under: {regime} @ {date} — flag [VINTAGE-CHECK] if regime_state.json differs.

Status labels:
  CALIBRATED       = survived VN workflow/backtest; strong prior
  SOURCED          = cited; not yet VN-tested
  TESTED           = checked against VN data; not yet surviving multiple cycles
  AXIOMATIC        = timeless principle; not backtestable
  INVALIDATED      = contradicted by dated VN evidence
  VN-SUBSUMED      = test channel clamped by VN constraint; parked + recoverable
  VN-THIN          = N_OOS < 15; defer until more data
  DEGRADING-REJECT = harmed combined system in interaction test; FORBIDDEN without council

DEGENERACY RULE: A degenerate test (binding constraint clamped IV) is NOT invalidation.
INVALIDATED requires: (a) IV varied, (b) result failed pre-registered gates.

---

## § Calibrated Beliefs (VN-VALIDATED — highest confidence)

| # | Claim | Status | regime_scope | calibrated_under | Evidence | Last Reviewed | Stale Trigger | Conflicts |
|---|-------|--------|--------------|-----------------|----------|---------------|---------------|-----------|
| C1 | Bear regime → suppress ALL trend signals; all sizes → 0 | CALIBRATED | agnostic | bear+bull @ 2026 | A3_RS paper runs 2026; MAR degrades to negative in bear-flagged periods | 2026-06-30 | STRATEGY — per weekly cycle | None |
| C2 | A3_RS momentum signal: MAR 0.381 locked on standalone TREND_OVERLAY | CALIBRATED | bull | bull @ 2026-06 | Backtest IS result; Phase B/C rejected; Phase D approved | 2026-06-30 | STRATEGY — per backtest cycle | Supersedes prior multi-overlay configs |
| C3 | VIC/VHM/VRE dominate size calculations in broad VN momentum screens (VIN distortion) | CALIBRATED | agnostic | agnostic @ 2026 | Observed in scan CSVs; explicit flag in resolver_rules.yml | 2026-06-30 | STRUCTURAL — quarterly | None |
| C4 | Sector classification must be verified against HOSE/HNX/FireAnt — never inferred from AI | CALIBRATED | agnostic | agnostic @ 2026 | TCX sector incident 2026 | 2026-06-30 | TIMELESS | None |
| S2 | Breakout volume surge ≥1.3× 50d avg on signal day — **PRIMARY FILTER** | CALIBRATED | agnostic | bull @ VN OOS 2020-2026 | Standalone OOS MAR 2.4804 (+196% vs baseline 0.8386), MaxDD −5.44%, sub-B MAR 1.191 (regime-agnostic). S1+S2 AND FORBIDDEN (OOS MAR 0.8728, G_ia FAIL). S1+S2 OR FORBIDDEN (OOS MAR 1.1862, sub-B 0.291). Pre-reg: 2026-07-04_cortex_book2_s2_breakout_volume_prereg.md | 2026-07-05 | STRATEGY | S1+S2 combined FORBIDDEN (AND and OR). Council review before any combined attempt. |
| S1 | 52-week high proximity (within 15%) leading indicator — **SECONDARY FILTER** | CALIBRATED | bull | bull @ VN OOS 2020-2026 | Standalone OOS MAR 1.7844 (+113% vs baseline 0.8386), MaxDD −8.17%, sub-B MAR 0.546 (recency weakening). S2 is PRIMARY (superior sub-B 1.191 vs 0.546). Pre-reg: 2026-07-04_cortex_book2_s1_52wkhi_gates_addendum.md | 2026-07-05 | STRATEGY | S1+S2 combined FORBIDDEN. Monitor sub-B decay. |

---

## § Sourced Beliefs (advisory only)

| # | Claim | Status | Evidence summary | Last Reviewed |
|---|-------|--------|-----------------|---------------|
| S4 | Darvas box breakout — wait for confirmed break | VN-THIN | PERMANENTLY PARKED: A3_RS pre-selection incompatible with Darvas tight consolidation. N_OOS=0 both windows. Retest: without A3_RS pre-filter. | 2026-07-05 |
| S5 | Cut losses before compound; no fixed rule — ongoing judgment | SOURCED | Lane B. 1/3 sessions reached. | 2026-07-02 |
| S6 | Kelly-derived sizing > flat sizing on OOS MAR | TESTED | SIZING SWEEP FAIL: quarter-Kelly OOS MAR 1.1943 < baseline 1.7844 (G1a FAIL); MaxDD −13.92% (G2 FAIL). Retain flat D3. Revisit if VN universe >200 names. | 2026-07-05 |
| S7 | Good decision can have bad outcome — evaluate reasoning ex-ante | SOURCED | Lane B. Protocol Amendment PA-001 pending. | 2026-07-05 |
| S8 | Regime persistence = reinforcing loop; reversal = limits | SOURCED | Lane B advisory. Reversal-indicator sub-component (breadth divergence, ADV decay) has Lane A pathway — needs pre-reg. | 2026-07-05 |
| S9 | 37% optimal-stopping rule for position-cutting and strategy-commitment | SOURCED | Lane B. Protocol Amendment PA-002 pending. | 2026-07-05 |
| S10 | Five-phase bubble lifecycle (displacement→boom→euphoria→distress→revulsion) | SOURCED | Lane B. VN 2007/2018/2021-22 in scope for phase-labeling. | 2026-07-05 |
| S11 | Probability-matching (bull/bear base rates) outperforms Markowitz in systematic-risk envs | SOURCED | Lane B. C1 is CALIBRATED mechanism; S11 is evolutionary theory of why C1 works. | 2026-07-05 |
| S12 | Largest single-day decline since Stage 2 advance on above-avg volume = institutional liquidation | VN-SUBSUMED | 83.5% of largest-DD-days = limit-down −7%; IV cannot express in VN ±7% band. Retest: when band widens. | 2026-07-05 |
| S13 | Graham fundamental screen (P/E≤15, P/B≤1.5) as pre-filter on A3_RS | VN-DEGENERATE | Value/momentum structural conflict; anti-correlated with A3_RS pool. EPS coverage <60%. Council: opus APPROVE-A. | 2026-07-05 |
| S20 | Climax-top exhaustion: ≥70% up-days in 7–15 day window + largest single up-day of entire move → demand exhaustion; sell aggressively | SOURCED | Lane A conditional. **Gate zero RUN 2026-07-08: BORDERLINE** — 78.8% of largest-up-days hit +7% band limit (3852/4889). Below 80% CLAMPED threshold but above 50% EXPRESSIBLE floor. **Dual-track pre-reg required:** (1) Count-only leg (≥70% up-days, band-immune) — pre-register directly; (2) Full price-magnitude claim — pre-reg with explicit acknowledgment BORDERLINE status may require re-scope. Report: knowledge/backtests/2026-07-07_s20_gate_zero.md. Source: Minervini TTLAC (2016) Ch.9 "Selling into Strength". | 2026-07-08 |

---

## § DEGRADING-REJECT (FORBIDDEN as filter on S1 pool — council required before reuse)

| # | Belief | Key Result | Reopen Trigger |
|---|--------|------------|----------------|
| S14 | Minervini MA stack | OOS MAR 0.4517 < baseline 1.7844; G2 INVERTED | Without A3_RS pre-filter |
| S15 | Gray/Vogel FIP quality momentum | OOS MAR 1.1275 < baseline; G2 PASS (mechanism real) | Regime change; fresh pre-reg |
| S16 | Gray/Vogel seasonality | Good-months OOS MAR 1.5895 < baseline; IS→OOS instability | New VN institutional calendar data |
| S17 | Cook buy-sell flow ratio (1d/5d/20d) | Best OOS MAR 1.7533 < baseline; sub-B collapse (3.946→0.098) | Sustained trending regime |
| S18 | Blake sector same-day persistence | OOS MAR 0.4615 < baseline; G2 PASS (mechanism real in VN) | Reframe as timing overlay; new pre-reg |

---

## § VN-Subsumed (parked — recoverable)

| # | Claim | Binding Constraint | Retest Trigger |
|---|-------|-------------------|----------------|
| S3 | Risk per trade 1.25–2.5% of equity; stop-loss and position size are the two levers | 1/20 slot cap + ADV limits bind before risk_pct varies | Run without slot cap |
| S12 | Largest-DD-day institutional liquidation signal | VN ±7% price band (83.5% of largest-DD-days = limit-down) | VN band widens |

---

## § Axiomatic Beliefs (timeless — not backtestable)

| # | Claim | Source | Last Reviewed |
|---|-------|--------|---------------|
| A1 | Every consistent winner defines a maximum loss threshold before entering | Schwager, Market Wizards | 2026-06-30 |
| A2 | Edge comes from discipline, patience, execution management — not signal | Schwager, Unknown Market Wizards (2024) | 2026-07-02 |
| A3 | Position sizing ~30% of success, psychology ~60%, system ~10% | Tharp, Trade Your Way to Financial Freedom | 2026-07-04 |
| A4 | Margin of safety renders unnecessary an accurate estimate of the future | Graham, The Intelligent Investor, Ch.20 | 2026-07-05 |

---

## § Invalidated Beliefs

| # | Claim | Evidence | Date |
|---|-------|----------|------|
| S19 | Buy sector leader (greatest RS), not laggard | OOS leader MAR 0.28 < laggard MAR 0.70; IS spread +0.0239 → OOS −0.07 (adversarial reversal). INVALIDATED in S1 context. Expansion gate falsification 1/1 SATISFIED. | 2026-07-05 |

---

## § Expansion Gate — SPLIT (ratified 2026-07-05)

**Mechanism Gate (2/3):**
- ≥10 SOURCED: ✓
- ≥3 CALIBRATED excl. C1/C2/C3: ✗ 2/3 — S1 ✓, S2 ✓; need 1 more
- Falsification fired: ✓ (S19 INVALIDATED)

**Usage Gate:** ≥10 qualifying paper/live decisions logged: ✗ count TBD

**REGIME-SATURATED (declared 2026-07-05):** 5 DEGRADING-REJECT across 3 families + falsification + 2 CALIBRATED.
Alternative evidence route: ✓ ALL CONDITIONS MET → harness extensions unlocked.
Retest trigger: regime_state.json exits sub-B choppy → re-run S18 (G2 PASS) + S15 (G2 PASS).

---

## § Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-07-08 | v27 | S2 extension program COMPLETE. S2@1.5×: OOS MAR 1.6201 (delta −0.909), sub-B 0.9276. S2@1.6×: OOS MAR 1.4762 (delta −1.053), sub-B 0.3742. Both CONDITIONAL-ADVANCE (G1a FAIL, G1b PASS). Monotonic trend REVERSES at 1.5× — sub-B regime collapse in choppy 2023-2026 is the mechanism (too few volume surges ≥1.5× in choppy market). **S2@1.4× is the confirmed optimal volume threshold.** Program goal (OOS MAR > 2.5447 via S2 extension) is not achievable by stricter threshold. S20 gate-zero RUN: BORDERLINE 78.8% (dual-track pre-reg required). PA-008 PASS (fill realism 2.9%, slot 0.2%). PA-009 VIABLE (75.1% reach +2R, ADV 0.18 days, slot cap 0.2%). PA-007 ATR sizing overlay structurally viable on A3_RS pending user sign-off. Reports: data/research/cortex_book2/s2_extended_report.md + knowledge/backtests/2026-07-07_s20/pa008/pa009. |
| 2026-07-08 | v26 | B_cloud exit Phase 1 COMPLETE — compression hypothesis REFUTED. partial_tp (TP1=+15% then 2.5×ATR trail) is PROTECTIVE in VN choppy regime: all 3 exit variants degraded OOS MAR vs baseline (fixed_60 −0.074; fixed_120 −0.049; trail_only −0.443). B_cloud architecture CLOSED-NEGATIVE (all search spaces: filters + ranking + exit modes exhausted). Architecture insight: TP1 clip activates ATR trail at a profit-protected point, reducing left-tail exposure — removing it keeps losers open longer. S2 threshold extension pre-registered (1.5×/1.6×, new baseline = S2@1.4× = 2.5447; see 2026-07-08_s2_extended_prereg.md). S20/PA-008/PA-009 pre-checks queued for run. |
| 2026-07-06 | v25 | S20 SOURCED added (Minervini climax-top exit). PA-008/PA-009 candidates registered. |
| 2026-07-06 | APPLIED | Applied knowledge_v18_PENDING_WRITE.md → knowledge_ACTIVE.md. Full source history preserved in knowledge_v18_PENDING_WRITE.md. |
| 2026-07-05 | v24 | S2 threshold 1.4×→1.3×; OOS MAR corrected; S1+S2 AND/OR FORBIDDEN. REGIME-SATURATED declared. |
| 2026-07-05 | v23 | S13 VN-DEGENERATE. Schwager Lane A batch CLOSED. |
| 2026-07-05 | v19-22 | S14/S15/S16/S17/S18 DEGRADING-REJECT. S12 VN-SUBSUMED. S19 INVALIDATED. |
