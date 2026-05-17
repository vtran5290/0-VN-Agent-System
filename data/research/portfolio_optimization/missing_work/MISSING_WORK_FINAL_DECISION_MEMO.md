# Missing Work Final Decision Memo

As of: 2026-05-16

## Executive Summary

This memo classifies all strategy candidates after completing:
- Phase 3.1 Liquidity Unit Audit (resolved 1000× bug, corrected ADV50)
- S3 21/55 corrected-liquidity research (Step 1)
- Annual decomposition, playbook combinations, Phase32 daily scan

**Primary conclusion:** A3 DP-first is the only PRODUCTION_CANDIDATE.
S3 is a shadow/paper-trade book. PTS is aggressive/shadow mode only.

## Candidate Classifications

| Candidate | Classification | MAR (5B/10%) | Role |
|-----------|---------------|--------------|------|
| A3_pos15_baseline | **PAPER_TRADE_SHADOW** | 0.380 | Baseline reference; superseded by DP-first |
| DP_A3_pb_only | **PRODUCTION_CANDIDATE** | 0.416 | Primary live candidate — A3 DP-first |
| PTS_A3_pb4w30_str6w10 | **PAPER_TRADE_SHADOW** | 0.343 | Shadow/aggressive mode — A3 PTS |
| S3_best_dp | **RESEARCH_ONLY** | 0.190 | S3 shadow book — EMA21/55 DP-first |

## Detailed Notes

### A3_pos15_baseline
- **Classification:** PAPER_TRADE_SHADOW
- **MAR @ 5B/10%:** 0.380
- **Role:** Baseline reference; superseded by DP-first
- **Notes:** Full-position only, no pullback. Used as benchmark.

### DP_A3_pb_only
- **Classification:** PRODUCTION_CANDIDATE
- **MAR @ 5B/10%:** 0.416
- **Role:** Primary live candidate — A3 DP-first
- **Notes:** MAR=0.416 at 5B/10% after corrected liquidity. DP-first mode: T1=50% at entry, T2 on pullback.

### PTS_A3_pb4w30_str6w10
- **Classification:** PAPER_TRADE_SHADOW
- **MAR @ 5B/10%:** 0.343
- **Role:** Shadow/aggressive mode — A3 PTS
- **Notes:** MAR dropped from 0.72 to 0.343 after corrected liquidity. Shadow only.

### S3_best_dp
- **Classification:** RESEARCH_ONLY
- **MAR @ 5B/10%:** 0.190
- **Role:** S3 shadow book — EMA21/55 DP-first
- **Notes:** Classification pending Step 1 results. Target: MAR > 0.30 for PAPER_TRADE_PRIMARY.

## Production Deployment Plan

### Phase 1 (Live — real capital)
- **A3 DP-first**: MAR=0.416 @ 5B/10% ADV
  - Entry: EMA20/100 cloud breakout, ex-VIN3 universe
  - T1=50% at entry, T2=50% on ≥4% pullback within 30 bars
  - Exit: TP1 +18%, trail 2.5×ATR, max 250 bars
  - GK10 size boost: 1.25×
  - Max positions: 20
  - Breadth gate: A3 breadth > 40%

### Phase 2 (Paper trade)
- **S3 best DP**: Shadow paper book
  - Best config: S3_dp_d3_w20_fast_ema_t160
  - MAR @ 5B/10%: 0.190
  - Entry: EMA21/55 cloud breakout, full universe
  - Same exit as S3 baseline: TP1 +18%, trail 3.5×ATR

### Phase 3 (Shadow aggressive — conditional)
- **PTS_A3**: Only when MAR recovers > 0.35 after 6+ months live data

## Liquidity Rules (Post Phase 3.1)

- ADV50 formula: `panel['value'].rolling(50).fillna(close × volume × 1000)`
- T1 position cap: `min(T1_target, adv50_VND × participation)`
- Recommendation: full_T1 / partial_T1 / skip / no_adv_data
- All equity sims: use `_build_equity_adv_capped_v2` from phase31

## Outputs Generated

- `missing_work/annual_component_performance.csv`
- `missing_work/breadth_hysteresis_rule_test.csv`
- `missing_work/final_candidate_classification.csv`
- `missing_work/performance_breadth_scaling_tests.csv`
- `missing_work/performance_scaling_tests.csv`
- `missing_work/phase32_daily_scan_sample.csv`
- `missing_work/phase32_daily_scan_schema.csv`
- `missing_work/phase33_daily_scan_sample.csv`
- `missing_work/phase33_daily_scan_schema.csv`
- `missing_work/phase34_daily_scan_sample.csv`
- `missing_work/phase34_daily_scan_schema.csv`
- `missing_work/playbook_by_year.csv`
- `missing_work/playbook_corrected_liquidity_summary.csv`
- `missing_work/regime_component_performance.csv`
- `missing_work/regime_decomposition_breadth.csv`
- `missing_work/regime_decomposition_liquidity.csv`
- `missing_work/regime_decomposition_market.csv`
- `missing_work/s3_best_dp_trade_ledger.csv`
- `missing_work/s3_dp_screening_pass.csv`
- `missing_work/s3_phase31_baseline_corrected.csv`
- `missing_work/s3_phase31_cost_liquidity_sensitivity.csv`
- `missing_work/s3_phase31_gk_overlay_corrected.csv`
- `missing_work/s3_phase31_pts_strength_corrected.csv`
- `missing_work/sector_l4_by_year.csv`
- `missing_work/sector_l4_daily_metrics.csv`
- `missing_work/sector_l4_map_coverage.csv`
- `missing_work/sector_l4_stress_rule_tests.csv`
- `missing_work/step0_ledger_schema_check.csv`
- `missing_work/step3_cost_liquidity_sensitivity.csv`
- `missing_work/updated_final_candidate_classification.csv`
- `missing_work/A3_DP_First_User_Guide_FINAL.md`
- `missing_work/BREADTH_RULE_FINAL.md`
- `missing_work/breadth_rule_patch_notes.md`
- `missing_work/FINAL_DAILY_RUNBOOK.md`
- `missing_work/FINAL_DECISION_MEMO_CLEAN.md`
- `missing_work/FINAL_OPEN_ITEMS.md`
- `missing_work/MACRO_DATA_MISSING.md`
- `missing_work/MISSING_WORK_FINAL_DECISION_MEMO.md`
- `missing_work/PERFORMANCE_SCALING_FINAL_FINDINGS.md`
- `missing_work/phase32_dashboard_spec.md`
- `missing_work/phase32_paper_trade_rules.md`
- `missing_work/phase33_dashboard_spec.md`
- `missing_work/phase33_paper_trade_rules.md`
- `missing_work/PLAYBOOK_TOP_FINDINGS.md`
- `missing_work/REGIME_MACRO_FINAL_FINDINGS.md`
- `missing_work/S3_PHASE31_TOP_FINDINGS.md`
- `missing_work/SECTOR_L4_FINAL_FINDINGS.md`
- `missing_work/sector_l4_patch_notes.md`
- `missing_work/step0_liquidity_audit.md`
- `missing_work/UPDATED_BREADTH_RULE_FINAL.md`
- `missing_work/UPDATED_FINAL_DAILY_RUNBOOK.md`
- `missing_work/UPDATED_FINAL_DECISION_MEMO_CLEAN.md`
- `missing_work/UPDATED_FINAL_OPEN_ITEMS.md`
- `missing_work/UPDATED_phase33_paper_trade_rules.md`
- `missing_work/UPDATED_SECTOR_L4_FINAL_FINDINGS.md`
