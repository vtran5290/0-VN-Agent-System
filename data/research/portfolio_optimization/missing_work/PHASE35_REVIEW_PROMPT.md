# Phase35 Review Package — S3 Shadow Upgrade

Date: 2026-05-16
Reviewer: External AI

---

## What This Package Is

Phase35 integrates S3 EMA21/55 as a PAPER_TRADE_SHADOW strategy (upgraded from RESEARCH_ONLY).
The single enabling finding: setting max_hold=60 bars raises S3 MAR from -0.011 to 0.377.

---

## Key Invariants to Verify

The reviewer should confirm ALL of the following are consistently enforced across all files:

1. **S3 max_hold = 60 bars everywhere.** Any reference to max_hold=250 for S3 should be flagged as REJECTED config, not active shadow.
2. **S3 never routes to real capital / DNSE.** Any file that implies S3 generates live orders is a defect.
3. **A3 and S3 P&L are tracked separately.** No file should combine them in a single equity curve.
4. **S3 never blocks A3 T1.** The a3_s3_lead_5d field is a ranking signal only, not a gate.
5. **A3 production config is unchanged.** EMA20/100, ex-VIN3, TP1=18%, trail=2.5×ATR14, max_hold=250 — none of these should be altered.
6. **S3 GK5+max60+top100 is PARALLEL_PAPER_RESEARCH only, not shadow.** MaxDD=-28.73% is too high for shadow.

---

## Files to Review

### Classification and Decision
- `UPDATED_S3_DECISION_MEMO.md` — Full S3 upgrade decision. Hard rules table. Year-by-year stability.
- `updated_final_candidate_classification.csv` — 6 rows. S3_max60 = PAPER_TRADE_SHADOW. S3_best_dp = REJECTED.
- `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` — Master classification document. Verify S3 sections updated.
- `UPDATED_REAL_CAPITAL_READINESS.md` — A3 real capital gates unchanged. S3 shadow gates separate.

### Rules and Operations
- `S3_SHADOW_PAPER_TRADE_RULES.md` — Hard rules for S3 shadow. max_hold=60. No real capital.
- `S3_ORDER_INTENT_RULES.md` — Order routing. S3_PAPER_SHADOW never reaches broker.
- `UPDATED_FINAL_DAILY_RUNBOOK.md` — Step 3b S3 shadow daily check. A3 priority lead rule.
- `UPDATED_phase33_paper_trade_rules.md` — Phase35 final_action enum. NEW_S3_SHADOW added.
- `FINAL_DEPLOYMENT_READINESS_CHECKLIST.md` — Gate 10 updated for S3 shadow.

### Research Evidence
- `S3_EXIT_FINDINGS.md` — max_hold=60 finding. Combined variant results.
- `S3_GK_FINDINGS.md` — GK5+max60 = 0.185, worse than max60 alone.
- `S3_LEAD_A3_FINDINGS.md` — a3_s3_lead_5d +0.083 MAR delta at 5-bar window.
- `S3_BREADTH_FINDINGS.md` — Breadth filters below gate. Rejected.
- `s3_exit_optimization_tests.csv` — 26 rows. max_hold=60 at row best.
- `s3_lead_a3_analysis.csv`, `s3_gk_overlay_tests.csv`, `s3_breadth_regime_tests.csv`, `s3_liquidity_subset_tests.csv`

### Phase35 Scan
- `phase35_daily_scan_schema.csv` — 49 fields. Check all 12 new S3 shadow fields are present.
- `phase35_daily_scan_sample.csv` — 10 rows. Check S3 shadow fields populated correctly.
- `UPDATED_FINAL_OPEN_ITEMS.md` — Done list. Verify S3 upgrade tasks all present.

### Implementation
- `S3_UPGRADE_IMPLEMENTATION_NOTES.md` — Code changes needed in portfolio_optimization_final_steps.py.
- `S3_SHADOW_GATE_TESTS.md` — 10 behavioral tests. Verify they cover all hard rules.
- `Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl` — AFL. Verify Param range is [60,60] not adjustable.
- `S3_21_55_Paper_Shadow_User_Guide.md` — AFL usage guide.

### Dashboard
- `UPDATED_PHASE35_DASHBOARD_SPEC.md` — Panel 6 (S3 shadow), Panel 7 (GK5 research monitor).

### Ledger Headers
- `s3_shadow_paper_trades.csv` — Paper trade log header. Verify columns cover all tracking needs.
- `s3_shadow_positions.csv` — Open positions state header.

---

## Questions for Reviewer

1. Are there any paths where S3 shadow could accidentally be interpreted as a real order?
2. Is max_hold=60 enforced in all relevant places (AFL, scan schema, paper rules, runbook, tests)?
3. Is the a3_s3_lead_5d ranking rule clearly distinguished from a gate/block in all files?
4. Does the phase35 scan sample correctly reflect what Phase35 output should look like?
5. Are the 12 new S3 shadow fields in the schema sufficient for paper trade tracking?
6. Any inconsistency between the decision memo, paper trade rules, and runbook?
