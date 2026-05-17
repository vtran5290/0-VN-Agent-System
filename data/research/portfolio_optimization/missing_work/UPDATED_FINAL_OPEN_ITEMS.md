# Final Open Items (Updated 2026-05-16)

Supersedes: FINAL_OPEN_ITEMS.md
Changes: Sector L4 decision corrected to DASHBOARD_WARNING_ONLY. Breadth gate rejection added.

---

## A — Done

| Item | Output | Notes |
|------|--------|-------|
| Phase 3.1 liquidity unit audit (1000× bug fix) | phase31/ | ADV50 corrected, PTS/DP re-tagged |
| A3 DP vs PTS corrected capacity (1B/3B/5B/10B × 5/10/20%) | phase31_liquidity_recomputed.csv | DP wins all 12 combos |
| A3 DP confirmed as PRODUCTION_CANDIDATE | UPDATED_FINAL_DECISION_MEMO_CLEAN.md | MAR=0.416 at 5B/10% |
| PTS classified as PAPER_TRADE_SHADOW | UPDATED_FINAL_DECISION_MEMO_CLEAN.md | MAR=0.343, not default |
| S3 21/55 full corrected-liquidity pipeline (81 DP configs) | s3_dp_screening_pass.csv | Best MAR=0.190 |
| S3 PTS configs (4 variants) | s3_phase31_pts_strength_corrected.csv | Best MAR=0.183 |
| S3 GK overlay tests | s3_phase31_gk_overlay_corrected.csv | |
| S3 cost/liquidity sensitivity | s3_phase31_cost_liquidity_sensitivity.csv | |
| S3 classified as RESEARCH_ONLY | UPDATED_FINAL_DECISION_MEMO_CLEAN.md | MAR=0.190 < 0.30 |
| Ledger schema audit (all 6 ledgers) | step0_ledger_schema_check.csv | |
| Sector L4 taxonomy (272 symbols) | sector_l4_map_coverage.csv | 170 high / 32 medium / 71 unknown |
| Sector L4 stress rule tests | sector_l4_stress_rule_tests.csv | DASHBOARD_WARNING_ONLY |
| Sector L4 daily breadth metrics | sector_l4_daily_metrics.csv | |
| Sector L4 by year | sector_l4_by_year.csv | |
| VNINDEX regime decomposition (EMA50/100/200) | regime_decomposition_market.csv | |
| Breadth regime daily (A3/S3 universe) | regime_decomposition_breadth.csv | 3582 rows |
| Per-trade regime tags | regime_decomposition_liquidity.csv | |
| Performance throttle tests (9 rules) | performance_scaling_tests.csv | All rejected |
| Breadth hysteresis tests (4 variants) | breadth_hysteresis_rule_test.csv | Hard gate hurts MAR |
| Playbook combinations (5 playbooks) | playbook_corrected_liquidity_summary.csv | A3 DP pure wins |
| Annual decomposition (all candidates) | annual_component_performance.csv | |
| Phase32/33 daily scan (A3+S3+breadth+sector) | phase33_daily_scan_sample.csv | 94 active setups |
| Phase33 scan schema | phase33_daily_scan_schema.csv | 29 fields |
| Phase33 dashboard spec | phase33_dashboard_spec.md | 9 panels |
| Phase33 paper trade rules | phase33_paper_trade_rules.md | |
| A3 DP AFL (production) | Cloud_Strategy_A3_20_100_DP_First_FINAL.afl | With corrected liquidity title |
| S3 research-only AFL | Cloud_Strategy_S3_21_55_RESEARCH_ONLY.afl | Warning in title |
| Final decision memo (clean) | UPDATED_FINAL_DECISION_MEMO_CLEAN.md | Breadth wording corrected |
| Final candidate classification CSV | updated_final_candidate_classification.csv | |
| Breadth operating rules (evidence-based) | UPDATED_BREADTH_RULE_FINAL.md | T1/T2 permission split |
| Breadth rule patch notes | breadth_rule_patch_notes.md | Explains wording fix |
| Sector L4 final findings (updated) | UPDATED_SECTOR_L4_FINAL_FINDINGS.md | DASHBOARD_WARNING_ONLY |
| Sector L4 patch notes | sector_l4_patch_notes.md | Explains SHADOW→DASHBOARD fix |
| MACRO_DATA_MISSING.md | MACRO_DATA_MISSING.md | Lists required sources |
| Phase34 daily scan schema | phase34_daily_scan_schema.csv | 36 fields |
| Phase34 daily scan sample | phase34_daily_scan_sample.csv | Corrected final_action enum |
| Phase34 paper trade rules | UPDATED_phase33_paper_trade_rules.md | Breadth as advisory only |
| Final dashboard spec | FINAL_DASHBOARD_SPEC.md | 9 panels updated |
| AFL parity smoke test | AFL_PARITY_SMOKE_TEST.csv + AFL_PARITY_NOTES.md | |
| Final daily runbook (clean) | FINAL_DAILY_RUNBOOK_CLEAN.md | 10-step correct order |
| Final patch notes | FINAL_PATCH_NOTES.md | All changes documented |
| Final package manifest | FINAL_PACKAGE_MANIFEST.md | All deliverable files |
| Deployment readiness checklist | FINAL_DEPLOYMENT_READINESS_CHECKLIST.md | Pre-live checklist |
| **S3 upgrade research (6 tests)** | s3_exit_optimization_tests.csv + 5 others | max_hold=60 → MAR=0.377 |
| **S3 max60 classified PAPER_TRADE_SHADOW** | UPDATED_S3_DECISION_MEMO.md | Supersedes RESEARCH_ONLY |
| **S3 shadow AFL** | Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl | max_hold=60 param, PAPER_SHADOW title |
| **Phase35 daily scan schema** | phase35_daily_scan_schema.csv | 47 fields (37 base + 10 new S3 shadow) |
| **Phase35 daily scan sample** | phase35_daily_scan_sample.csv | 10 rows × 47 fields, validated clean |
| **S3 shadow paper trade ledgers** | s3_shadow_paper_trades.csv + s3_shadow_positions.csv | Headers only, paper use only |
| **Phase35 dashboard spec** | UPDATED_PHASE35_DASHBOARD_SPEC.md | Adds S3 shadow panels |
| **S3 shadow paper trade rules** | S3_SHADOW_PAPER_TRADE_RULES.md | Hard rules + max60 enforcement |
| **Updated daily runbook (S3 shadow)** | UPDATED_FINAL_DAILY_RUNBOOK.md | Step 3b S3 shadow check |
| **Updated candidate classification CSV** | updated_final_candidate_classification.csv | S3_max60 + S3_GK5 rows added |

---

## B — Not Done Because Rejected (with reason)

| Item | Reason |
|------|--------|
| **Hard breadth gate (>40%) as T1 entry block** | Backtest shows MAR drops 0.416→0.344. Hard gate blocks 1125 winners vs 616 losers (1.8:1 ratio). A3 regime gate already filters bear markets. Breadth reclassified to T2-only advisory. |
| **Hard breadth gate (<35%) as defense block** | Same backtest evidence. MAR 0.416→0.166 (hard_35). Defense zone now generates NEW_T1_MANUAL_REVIEW_BREADTH — operator review, not automatic block. |
| **Performance throttle (trailing 3M return rules)** | All 8 throttle rules either leave MAR unchanged or reduce it. ruleA_3M_5pct: MAR 0.416→0.357. No rule improves MAR without killing bull-year returns. Rejected. |
| **Sector L4 name/exposure cap as trade filter** | max_1_per_l4: MAR drops to 0.197. max_2_per_l4: MAR 0.319. All caps hurt more than they help. DASHBOARD_WARNING_ONLY. |
| **Sector L4 stress as SHADOW_RISK_CONTROL** | Best stress rule (l4_breadth<50%) barely improves MAR 0.416→0.438 (+0.022). Not material enough to justify complexity. DASHBOARD_WARNING_ONLY. |
| **S3 as paper-trade book** | MAR=0.190 at 5B/10%. Below 0.30 threshold. S3 classified RESEARCH_ONLY/WATCHLIST_ONLY. No capital allocation. |
| **PTS as default entry mode** | After corrected liquidity MAR=0.343 vs DP=0.416. PTS strength-add captures lower-quality entries. DP wins all 12 portfolio-size/participation combos. PTS is PAPER_TRADE_SHADOW only. |

---

## C — Not Done Due to Missing Data

| Item | Missing Data | Required Source |
|------|-------------|----------------|
| Full macro regime decomposition (rates, DXY, VND) | SBV OMO, policy rate, USD/VND daily, DXY | See MACRO_DATA_MISSING.md |
| Domestic liquidity cycle tags | SBV net OMO injection/withdrawal | scripts/run_weekly_full_fetch.py or manual SBV download |
| Global risk-on/off regime | MSCI EM or S&P 500 daily return | Yahoo Finance / Stooq |
| VN market total value regime | Daily total market value traded | FireAnt or VSD data |
| Individual stock ownership data | Foreign ownership limits | VSD / SSC |

---

## D — Optional Future Research

| Item | Priority | Prerequisite | Notes |
|------|----------|-------------|-------|
| A3 DP exit optimization (TP1 level: 15%/18%/20%/25%) | Low | None | Risk: overfitting |
| ATR period sensitivity (10/14/20 bars) | Low | None | Marginal improvement expected |
| S3 with tighter universe (ex-VIN3 like A3) | Medium | None | May improve MAR above 0.25 |
| S3 with quality filter (market cap > 1T VND) | Medium | Market cap data | Remove micro-cap noise |
| PTS conditional on regime (bull breadth >60% only) | Low | Breadth data | Specific regime PTS may be useful |
| GK10 overlay performance on PTS shadow | Low | PTS ledger | Academic interest only |
| Walk-forward validation (2023-2026 out-of-sample) | High | Live data | Required before real capital |
| Live paper trade data integration | High | Live execution | 3+ months paper data before live |
| Sector L4 coverage improvement (71 unknowns) | Medium | Company research | Fill unknown sector_l4 |
| Macro data integration (SBV, DXY) | Medium | Data download | See MACRO_DATA_MISSING.md |
