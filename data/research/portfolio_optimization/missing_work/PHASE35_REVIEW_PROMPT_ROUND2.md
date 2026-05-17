# Phase35 Review Package — Round 2

Date: 2026-05-16
Context: 9 patches applied after Round 1 NEEDS_REVISION verdict.

---

## What Changed Since Round 1

| Patch | Problem | Fix |
|-------|---------|-----|
| 1+2 | CSV sample had 6 malformed rows (extra blank → field shift). Docs claimed 49 fields. | Regenerated via Python csv.writer. All rows = 47 fields. Docs corrected to 47. |
| 3 | "T2 Reduced" wording in 3 docs (Decision Memo, Runbook, Dashboard) | Replaced with "T2 blocked" everywhere |
| 4 | S3_LEAD_A3_FINDINGS.md cited 30-bar delta (+0.061), not selected 5-bar rule (+0.083) | Findings file rewritten. 5-bar is selected. 30-bar is diagnostic only. |
| 5 | S3_GK5_max60_top100 MAR=0.449 had no supporting CSV | Downgraded to FUTURE_RETEST_REQUIRED. MAR asterisked. Evidence notes added. |
| 6 | Implementation notes implied code complete. Code changes still pending. | Renamed to HANDOFF/SPEC ONLY. Pending code items explicitly listed. |
| 7 | Gate tests expanded from 10 to 20, now covering all S3 enum values + mode override + P&L separation + schema integrity |
| 8 | Validation script | `phase35_csv_validation.py` added. Runs clean. |

---

## Package Strategy Confirmed Unchanged

- A3 DP-first: PRODUCTION_CANDIDATE, MAR=0.416, unchanged
- PTS: PAPER_TRADE_SHADOW, default OFF
- S3_max60: PAPER_TRADE_SHADOW, MAR=0.377, max_hold=60, paper-only
- S3_best_dp (max_hold=250): REJECTED / RESEARCH_ONLY
- S3_GK5_max60_top100: FUTURE_RETEST_REQUIRED (downgraded, MAR unverified)

---

## Round 2 Checks

### Check 1 — CSV Parses Correctly

Run: `.venv\Scripts\python.exe data\research\portfolio_optimization\missing_work\phase35_csv_validation.py`

Expected: ALL CHECKS PASSED

Verify manually:
- `phase35_daily_scan_schema.csv`: count rows (exclude header) = 47
- `phase35_daily_scan_sample.csv`: every data row = 47 fields
- S3 rows (ABB, BIC, BIG, BMP, BSR, CII): final_action column is NOT blank
- `strategy_classification` for S3 rows = S3_PAPER_SHADOW (not blank/shifted)

---

### Check 2 — Field Count Consistent Everywhere (47)

Files to verify:
- `phase35_daily_scan_schema.csv`: 47 data rows
- `phase35_daily_scan_sample.csv`: header = 47 fields
- `UPDATED_FINAL_DAILY_RUNBOOK.md`: says "47 fields" (not 49)
- `UPDATED_FINAL_OPEN_ITEMS.md`: says "47 fields (37 + 10 new S3 shadow)"
- `S3_UPGRADE_IMPLEMENTATION_NOTES.md`: says "47 fields" in files table
- `S3_SHADOW_GATE_TESTS.md`: Test 16 says "exactly 47 fields"
- `field_count_consistency_check.md`: authoritative reference

---

### Check 3 — Breadth Caution = T2 Blocked Everywhere

Search for "Reduced" in all .md files in missing_work/ — should find ZERO instances
in operational tables (patch notes only).

Files to verify clean:
- `UPDATED_FINAL_DECISION_MEMO_CLEAN.md`: caution row says "T2 blocked"
- `UPDATED_FINAL_DAILY_RUNBOOK.md`: caution row says "T2 blocked"
- `UPDATED_PHASE35_DASHBOARD_SPEC.md`: alert says "T2 BLOCKED"

---

### Check 4 — S3 Lead = 5-Bar Rule, Ranking Only

Verify `S3_LEAD_A3_FINDINGS.md`:
- Verdict section leads with "5-BAR WINDOW SELECTED"
- Delta cited = +0.083 (not +0.061)
- 30-bar explicitly labeled "diagnostic only"
- Rule block says "does NOT block A3" / "does NOT force A3 entry" / "does NOT route S3 capital"

---

### Check 5 — S3_GK5_max60_top100 Evidence or Classification

Verify `updated_final_candidate_classification.csv`:
- S3_GK5_max60_top100 row has classification = FUTURE_RETEST_REQUIRED
- MAR column has asterisk (0.449*)
- Note column says "unverified"

Verify `S3_GK_FINDINGS.md`:
- Section "S3_GK5_max60_top100 — STATUS: FUTURE_RETEST_REQUIRED" present
- No claim that MAR=0.449 is canonical

---

### Check 6 — Implementation Status Honest

Verify `S3_UPGRADE_IMPLEMENTATION_NOTES.md`:
- Top section says "HANDOFF / SPEC PACKAGE ONLY"
- Section titled "Pending Code Changes" (not "Needed")
- Open Items table present with priority column
- No claim that scan code was updated

---

### Check 7 — S3 No-Live-Order Containment

Verify `S3_SHADOW_GATE_TESTS.md`:
- Tests 5-10 explicitly name each S3 final_action value
- Test 10 covers live_manual/live_auto override scenario
- All 20 tests present across 4 sections (A-D)

Verify `S3_ORDER_INTENT_RULES.md`:
- Code snippet shows `if strategy_classification in ("S3_PAPER_SHADOW", ...)`: return
- S3_PAPER_SHADOW maps to PAPER_S3_SHADOW_INTENT_ONLY
- No path where S3 reaches DNSE

---

## Files in This Package (36 files)

### Core Decision Documents
- `PHASE35_REVIEW_PROMPT_ROUND2.md` — this file
- `UPDATED_S3_DECISION_MEMO.md` — S3 upgrade decision (hard rules, year-by-year)
- `updated_final_candidate_classification.csv` — 6 rows (S3_GK5 = FUTURE_RETEST_REQUIRED)
- `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` — master classification doc
- `UPDATED_REAL_CAPITAL_READINESS.md` — gate status

### Rules and Operations
- `S3_SHADOW_PAPER_TRADE_RULES.md`
- `S3_ORDER_INTENT_RULES.md`
- `UPDATED_FINAL_DAILY_RUNBOOK.md`
- `UPDATED_phase33_paper_trade_rules.md`
- `FINAL_DEPLOYMENT_READINESS_CHECKLIST.md`

### Research Evidence
- `S3_EXIT_FINDINGS.md` + `s3_exit_optimization_tests.csv`
- `S3_LEAD_A3_FINDINGS.md` (updated Round 2) + `s3_lead_a3_analysis.csv`
- `S3_GK_FINDINGS.md` (updated Round 2) + `s3_gk_overlay_tests.csv`
- `S3_BREADTH_FINDINGS.md` + `s3_breadth_regime_tests.csv`
- `s3_liquidity_subset_tests.csv`

### Phase35 Schema and Sample
- `phase35_daily_scan_schema.csv` — 47 fields
- `phase35_daily_scan_sample.csv` — 10 rows × 47 fields (validated)
- `phase35_csv_validation.py` — validation script

### Implementation Spec
- `S3_UPGRADE_IMPLEMENTATION_NOTES.md` — HANDOFF/SPEC, code changes pending
- `S3_SHADOW_GATE_TESTS.md` — 20 behavioral tests

### Dashboard and AFL
- `UPDATED_PHASE35_DASHBOARD_SPEC.md`
- `Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl`
- `S3_21_55_Paper_Shadow_User_Guide.md`

### Ledger Headers
- `data/trading/live/s3_shadow_paper_trades.csv`
- `data/trading/live/s3_shadow_positions.csv`

### Patch Notes (Round 2)
- `PHASE35_CSV_PATCH_NOTES.md`
- `breadth_wording_patch_notes.md`
- `s3_lead_window_patch_notes.md`
- `s3_gk5_top100_evidence_notes.md`
- `implementation_status_patch_notes.md`
- `s3_containment_patch_notes.md`
- `field_count_consistency_check.md`
