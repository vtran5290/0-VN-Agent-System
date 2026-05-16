# Final Package Manifest

Date: 2026-05-16

---

## Production Files (use these)

| File | Classification | Purpose |
|------|---------------|---------|
| `Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` | PRODUCTION_CANDIDATE | AmiBroker A3 DP chart + scan |
| `Cloud_Strategy_S3_21_55_RESEARCH_ONLY.afl` | RESEARCH_ONLY | AmiBroker S3 chart (no capital) |
| `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Reference | Strategy classification (authoritative) |
| `UPDATED_BREADTH_RULE_FINAL.md` | Reference | Breadth rules with T1/T2 permission logic |
| `UPDATED_phase33_paper_trade_rules.md` | Reference | Paper trade entry/exit rules |
| `FINAL_DAILY_RUNBOOK_CLEAN.md` | Reference | Daily operator runbook (10 steps) |
| `FINAL_DASHBOARD_SPEC.md` | Reference | Dashboard 9-panel specification |
| `A3_DP_First_User_Guide_FINAL.md` | Reference | End-user strategy guide |
| `phase34_daily_scan_schema.csv` | Reference | 37-field scan schema |
| `phase34_daily_scan_sample.csv` | Sample output | Phase34 scan with correct final_action |
| `updated_final_candidate_classification.csv` | Reference | Strategy classification table |
| `UPDATED_FINAL_OPEN_ITEMS.md` | Reference | Done/rejected/pending/optional tracker |
| `FINAL_DEPLOYMENT_READINESS_CHECKLIST.md` | Pre-live | Checklist before real capital |

---

## Patch/Audit Files (context and evidence)

| File | Purpose |
|------|---------|
| `breadth_rule_patch_notes.md` | Explains breadth wording fix |
| `sector_l4_patch_notes.md` | Explains sector status change |
| `phase34_scan_patch_notes.md` | Phase34 scan upgrade details |
| `AFL_PARITY_NOTES.md` | AFL vs Python consistency check |
| `AFL_PARITY_SMOKE_TEST.csv` | 10-symbol parity test results |
| `FINAL_PATCH_NOTES.md` | All Phase34 changes documented |

---

## Research Evidence Files (Phase 3.1 and earlier)

| File | Content |
|------|---------|
| `phase31/PHASE31_LIQUIDITY_AUDIT.md` | 1000× ADV50 unit fix |
| `phase31_liquidity_recomputed.csv` | DP/PTS at all capacity combos |
| `s3_dp_screening_pass.csv` | S3 81-config MAR grid |
| `breadth_hysteresis_rule_test.csv` | Breadth gate backtest evidence |
| `performance_scaling_tests.csv` | Throttle rule tests (all rejected) |
| `sector_l4_stress_rule_tests.csv` | Sector cap tests |
| `regime_decomposition_market.csv` | VNINDEX regime history |
| `regime_decomposition_breadth.csv` | A3/S3 breadth history (3582 rows) |
| `playbook_corrected_liquidity_summary.csv` | 5-playbook comparison |
| `annual_component_performance.csv` | Year-by-year decomposition |
| `FINAL_DECISION_MEMO_CLEAN.md` | Original (superseded by UPDATED_ version) |
| `BREADTH_RULE_FINAL.md` | Original (superseded by UPDATED_ version) |
| `SECTOR_L4_FINAL_FINDINGS.md` | Original (superseded by UPDATED_ version) |

---

## Python Code

| File | Purpose |
|------|---------|
| `pp_backtest/portfolio_optimization_final_steps.py` | Phase34 scan, regime, breadth, sector |
| `pp_backtest/portfolio_optimization_missing_work.py` | Phase 3.1 backtest pipeline (S3, PTS) |

Key functions in `portfolio_optimization_final_steps.py`:
- `_final_action()`: Phase34 corrected logic (breadth defense → review, not block)
- `_breadth_permissions()`: Returns (breadth_t1_permission, breadth_t2_permission)
- `_strategy_classification()`: A3_PRODUCTION | S3_RESEARCH_ONLY | etc.
- `run_scan()`: Full Phase34 daily scan with 37-field output
- `run_breadth()`: Breadth hysteresis tests
- `run_sector()`: Sector L4 stress tests
- `run_scaling()`: Throttle rule tests (all rejected)

---

## Not Included (Missing Data)

| Item | Reason |
|------|--------|
| Macro regime (SBV, DXY, VND) | Data not available. See MACRO_DATA_MISSING.md. |
| Walk-forward validation (2023-2026) | Requires live execution data. Future work. |
| Live paper trade log | 3+ months required before real capital. Not started. |
