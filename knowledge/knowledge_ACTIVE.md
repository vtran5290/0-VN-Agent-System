# vn-trading-advisor — Knowledge Base
# v33 | 2026-07-08 | S21 TESTED: Zone (4-7% ED) sweet spot in S2 tier. ed_score sort INVERTED — reverted to a3_rank_score.
# 6 CALIBRATED / 8 SOURCED / 4 AXIOMATIC / 1 INVALIDATED / 2 VN-SUBSUMED / 1 VN-THIN / 2 TESTED / 5 DEGRADING-REJECT / 1 VN-DEGENERATE
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
| S21 | Within S2 tier (vol_mult ≥1.3×), Zone (4–7% above EMA cloud) is the sweet spot; Near (0–4%) is the worst band | TESTED | N=1621 pure S2 OOS 2020-2026. Near: mean 8.82%, median −3.33%, win 45.2%. Zone: mean 32.83%, median +3.48%, win 53.5%. Extended (7%+): mean 20.22%, median −2.28%, win 46.7%. Zone > Near in 6/7 years. ed_score sorts Near first (highest score = closest to cloud) = INVERTED. ed_score removed as secondary T1 sort key; a3_rank_score restored. Future: pre-register Zone-targeting secondary score separately. | 2026-07-08 |
| S7 | Good decision can have bad outcome — evaluate reasoning ex-ante | SOURCED | Lane B. Protocol Amendment PA-001 pending. | 2026-07-05 |
| S8 | Regime persistence = reinforcing loop; reversal = limits | SOURCED | Lane B advisory. Reversal-indicator sub-component (breadth divergence, ADV decay) has Lane A pathway — needs pre-reg. | 2026-07-05 |
| S9 | 37% optimal-stopping rule for position-cutting and strategy-commitment | SOURCED | Lane B. Protocol Amendment PA-002 pending. | 2026-07-05 |
| S10 | Five-phase bubble lifecycle (displacement→boom→euphoria→distress→revulsion) | SOURCED | Lane B. VN 2007/2018/2021-22 in scope for phase-labeling. | 2026-07-05 |
| S11 | Probability-matching (bull/bear base rates) outperforms Markowitz in systematic-risk envs | SOURCED | Lane B. C1 is CALIBRATED mechanism; S11 is evolutionary theory of why C1 works. | 2026-07-05 |
| S12 | Largest single-day decline since Stage 2 advance on above-avg volume = institutional liquidation | VN-SUBSUMED | 83.5% of largest-DD-days = limit-down −7%; IV cannot express in VN ±7% band. Retest: when band widens. | 2026-07-05 |
| S13 | Graham fundamental screen (P/E≤15, P/B≤1.5) as pre-filter on A3_RS | VN-DEGENERATE | Value/momentum structural conflict; anti-correlated with A3_RS pool. EPS coverage <60%. Council: opus APPROVE-A. | 2026-07-05 |
| S20 | Climax-top exhaustion: ≥70% up-days in 7–15 day window + largest single up-day of entire move → demand exhaustion; sell aggressively | SOURCED | Lane A **count-only PARKED** (2026-07-08). Count-only harness: N=7: 0.2841, N=10: 0.5349, N=15: 0.3133 — ALL below G1b (1.2646), kill criterion fired. Over-triggers (96%/90%/56% of OOS positions), cuts winners indiscriminately. Sub-B near-zero. **Price-magnitude leg still pending** (separate pre-reg required; BORDERLINE gate-zero 78.8%). Source: Minervini TTLAC (2016) Ch.9. | 2026-07-08 |
| PA-009 | 2R partial exit: exit half position when high[i] >= entry + 4×ATR14; run remaining half to original A3_RS exit | SOURCED | **CLOSED-NEGATIVE** (2026-07-08, Option A). Fails G1a_exit under **both** v1 blended (MAR 1.88) and v2 two-leg (MAR 0.12–0.43) vs floor 2.1448. [ADVERSE-REVERSAL]: all variants MaxDD worse than baseline. v2 magnitude partly slot-confounded (two PreparedTrade/slot + MIN_POS leg-drop) — logged, not blocking closure. Scope: 2R partial-exit 1.5×–2.5× R on A3_RS+S2@1.4x. Pre-reg: 2026-07-08_pa009_exit_class_prereg_v2.md | 2026-07-08 |
| PA-008 | 50d-MA breakeven-confirmed stop exit on A3_RS+S2@1.4× | SOURCED | **CLOSED-NEGATIVE [ADVERSE-REVERSAL]** (2026-07-08, Option A). Harness **waived**. v1 screening: MAR 0.3178, MaxDD −27.13%, sub-B −0.056, trigger 78.5%. Fails exit-class gates without re-run. Scope: MA=50 stop on A3_RS+S2@1.4x. Pre-reg: 2026-07-08_pa008_exit_class_prereg_v2.md | 2026-07-08 |
| PA-007 | ATR-inverse sizing overlay on A3_RS+S2@1.4×: pos_size = min(1/20, k/ATR_10d) | SOURCED | **PARKED — SIZING G5 FAIL** (2026-07-08). v2 re-test on correct S2@1.4× base: C1_atr20_s2 OOS MAR 2.3296, C2_atr10_s2 OOS MAR 2.3081 — G1a/G1b/G2/G3 all PASS but G5 2021 high-vol capture = 25.5–25.8% vs 85% floor (hard fail, 60pp gap). Mechanism: ATR sizing reduces position size for high-ATR stocks; VN 2021 bull concentrates P&L in exactly those high-ATR names → right-tail winner destruction. Mean-based [ATR-UNDERSIZING-RISK] flag (ratio 1.033) MISSED right-tail effect — flag structurally deficient. **N=2 confirmation:** S6 Kelly (standalone G1a FAIL 1.1943 vs 1.7844) + PA-007 v2 (G5 FAIL). Scope-of-invalidation: all inverse-vol sizing on A3_RS+S2. Non-inverse-vol sizing (conviction/momentum-scaled) is UNTESTED. Council: `2026-07-08-2300_PA007_BaselineMismatch_Council.md`. Pre-reg: `2026-07-08_pa007_atrsizing_s2base_prereg.md`. ChatGPT verdict PENDING. | 2026-07-08 |

---

## § DEGRADING-REJECT (FORBIDDEN as filter on S1 pool — council required before reuse)

| # | Belief | Key Result | Reopen Trigger |
|---|--------|------------|----------------|
| S14 | Minervini MA stack | OOS MAR 0.4517 < baseline 1.7844; G2 INVERTED | Without A3_RS pre-filter |
| S15 | Gray/Vogel FIP quality momentum | OOS MAR 1.1275 < baseline; G2 PASS (mechanism real) | Regime change; fresh pre-reg |
| S16 | Gray/Vogel seasonality | Good-months OOS MAR 1.5895 < baseline; IS→OOS instability | New VN institutional calendar data |
| S17 | Cook buy-sell flow ratio (1d/5d/20d) | Best OOS MAR 1.7533 < baseline; sub-B collapse (3.946→0.098) | Sustained trending regime |
| S18 | Blake sector same-day persistence | OOS MAR 0.4615 < baseline; G2 PASS (mechanism real in VN). **A3_RS reframe also PARKED 2026-07-08:** k=0.75: 0.6995 / k=1.00: 1.2590 — both below G1b (1.2646). k=1.00 borderline by 0.0056. Passes 25-32% of trades; reduces N_OOS below concentration threshold (equity-curve MaxDD amplification). Strong sub-B (2.8-4.6) but overall OOS dragged. | No further reframes without council |

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
| 2026-07-08 | v33 | **S21 TESTED (Zone sweet spot).** Live backtest N=1621 pure S2 OOS 2020-2026: Zone (4–7% ED) dominates (mean 32.83%, win 53.5%); Near (0–4%) is worst band (mean 8.82%, median −3.33%). ed_score as T1 secondary sort REVERTED — sorting by ed_score DESC puts Near band first (inverted). a3_rank_score restored as secondary. Zone-targeting secondary score deferred pending pre-reg. Source: combo_or_trades.csv + ta_ohlcv_panel.parquet. |
| 2026-07-08 | v32 | **PA-007 v2 PARKED.** ATR-sizing on A3_RS+S2@1.4× base: both candidates fail G5 2021 high-vol capture (25.5–25.8% vs 85%). Passes G1a/G1b/G2/G3. Root cause: inverse-vol sizing destroys right-tail P&L in VN momentum regime (2021 high-ATR = high-return). N=2 confirms scope: all inverse-vol sizing on A3_RS+S2 PARKED. [ATR-UNDERSIZING-RISK] mean-flag confirmed structurally deficient — fable framework fix required. Non-inverse-vol sizing untested. ChatGPT dual-judge (Trigger #5) pending. Review pack: 05_AI_Handoffs/2026-07-08-2300_ReviewPack_PA007v2_Parked.md |
| 2026-07-08 | v31 | **Option A executed (user).** PA-009 CLOSED-NEGATIVE confirmed with framework amendment: closure rationale = fails G1a under v1+v2; v2 magnitude slot-confounded (logged). PA-008 CLOSED-NEGATIVE [ADVERSE-REVERSAL] — exit-class harness waived (v1 MAR 0.32, MaxDD −27%). Both slots archived. No cortex_pa008_exit_class.py. Council: high council artifact + framework seats 2026-07-08. Decision: 05_AI_Handoffs/2026-07-08_VNAgent_OptionA_ExitOverlayClosure_DecisionReceived.md |
| 2026-07-08 | v30 | PA-009 exit-class v2 council complete. Opus APPROVE (CLOSED-NEGATIVE): all 3 variants fail G1a+G1b+G1d decisively; MAR 0.12–0.43 vs floor 2.1448; MaxDD worsened 2–4× [ADVERSE-REVERSAL]; sub-B negative; two-leg dedup confirmed; v1-to-v2 discrepancy economically coherent. Fable HOLDS: exit-class framework worked as designed; caught the exact failure mode (risk-transformation candidate produced opposite). Minor doc addition: [ADVERSE-REVERSAL] annotation needed in verification-harness.md exit-class section. PA-009 → CLOSED-NEGATIVE (scope: 2R partial-exit 1.5×–2.5× R-multiple on A3_RS+S2@1.4x). Trigger #5 ChatGPT verdict pending. Council: 2026-07-08-2100_PA009_ExitClass_Council.md |
| 2026-07-08 | v29 | Council called (user request). Opus REDIRECT on PA-009: gate-objective mismatch, CONDITIONAL-ADVANCE unsupported (fails G1a/baseline/goal on MAR; advanced on unregistered risk-adjusted rationale). Fable GAP: framework lacks overlay-class taxonomy; MAR-only valid only if leverage re-deployable (not in VN retail paper). Fix prospective only. PA-009 → PARKED-PENDING-FRAMEWORK-FIX. Proposed: (1) formalize overlay-class template in verification-harness.md; (2) re-pre-reg PA-009 under exit-class dual gate. Review pack written for ChatGPT /aiscollab decision. Council files: 05_AI_Handoffs/2026-07-08-1800_VNAgent_ExitOverlayCouncil_{Opus,Fable}Verdict.md |
| 2026-07-08 | v28 | Exit overlay batch COMPLETE. **PA-009 (2R partial exit): REDIRECT→PARKED-PENDING-FRAMEWORK-FIX** — OOS MAR 1.8779 (G1b PASS, G1a FAIL), sub-A 2.9677, sub-B 2.8900, MaxDD 5.57%. Council verdict 2026-07-08: Opus REDIRECT (gate-objective mismatch — MAR gate invalid for risk-reduction candidate), Fable GAP (framework lacks overlay-class taxonomy; MAR-only defensible only if leverage available, which it isn't). CONDITIONAL-ADVANCE label rescinded. Eligible for fresh re-test under new exit-class gate once overlay-class template formalized in verification-harness.md. ChatGPT aiscollab decision pending. **PA-008 (50d-MA stop): PARKED** — OOS MAR 0.3178, sub-B −0.0562 (kill criterion #2 fired: sub-B < 0; stop hurts choppy regime). **S20 count-only: PARKED** — all three windows below G1b (N=7: 0.284, N=10: 0.535, N=15: 0.313). Over-fires in uptrends (cuts 56-97% of winners). Price-magnitude leg still pending. **S18 A3_RS reframe: PARKED** — k=0.75: 0.6995, k=1.00: 1.2590 (0.0056 below G1b); sub-B strong (2.89-4.59) but concentration kills combined OOS MAR. Reports: data/research/cortex_exit_overlays/ + data/research/cortex_s18_timing_a3rs/. |
| 2026-07-08 | v27 | S2 extension program COMPLETE. S2@1.5×: OOS MAR 1.6201 (delta −0.909), sub-B 0.9276. S2@1.6×: OOS MAR 1.4762 (delta −1.053), sub-B 0.3742. Both CONDITIONAL-ADVANCE (G1a FAIL, G1b PASS). Monotonic trend REVERSES at 1.5× — sub-B regime collapse in choppy 2023-2026 is the mechanism (too few volume surges ≥1.5× in choppy market). **S2@1.4× is the confirmed optimal volume threshold.** Program goal (OOS MAR > 2.5447 via S2 extension) is not achievable by stricter threshold. S20 gate-zero RUN: BORDERLINE 78.8% (dual-track pre-reg required). PA-008 PASS (fill realism 2.9%, slot 0.2%). PA-009 VIABLE (75.1% reach +2R, ADV 0.18 days, slot cap 0.2%). PA-007 ATR sizing overlay structurally viable on A3_RS pending user sign-off. Reports: data/research/cortex_book2/s2_extended_report.md + knowledge/backtests/2026-07-07_s20/pa008/pa009. |
| 2026-07-08 | v26 | B_cloud exit Phase 1 COMPLETE — compression hypothesis REFUTED. partial_tp (TP1=+15% then 2.5×ATR trail) is PROTECTIVE in VN choppy regime: all 3 exit variants degraded OOS MAR vs baseline (fixed_60 −0.074; fixed_120 −0.049; trail_only −0.443). B_cloud architecture CLOSED-NEGATIVE (all search spaces: filters + ranking + exit modes exhausted). Architecture insight: TP1 clip activates ATR trail at a profit-protected point, reducing left-tail exposure — removing it keeps losers open longer. S2 threshold extension pre-registered (1.5×/1.6×, new baseline = S2@1.4× = 2.5447; see 2026-07-08_s2_extended_prereg.md). S20/PA-008/PA-009 pre-checks queued for run. |
| 2026-07-06 | v25 | S20 SOURCED added (Minervini climax-top exit). PA-008/PA-009 candidates registered. |
| 2026-07-06 | APPLIED | Applied knowledge_v18_PENDING_WRITE.md → knowledge_ACTIVE.md. Full source history preserved in knowledge_v18_PENDING_WRITE.md. |
| 2026-07-05 | v24 | S2 threshold 1.4×→1.3×; OOS MAR corrected; S1+S2 AND/OR FORBIDDEN. REGIME-SATURATED declared. |
| 2026-07-05 | v23 | S13 VN-DEGENERATE. Schwager Lane A batch CLOSED. |
| 2026-07-05 | v19-22 | S14/S15/S16/S17/S18 DEGRADING-REJECT. S12 VN-SUBSUMED. S19 INVALIDATED. |
