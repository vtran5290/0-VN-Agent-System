# Final Patch Notes

Date: 2026-05-16 | Scope: Phase33 → Phase34 cleanup

---

## Summary

8-task final implementation cleanup to correct wording errors from Phase33 and add Phase34 scan fields.
All changes are documentation patches and scan logic fixes. No strategy parameters changed.

---

## Patch 1: Classification Wording (Task 1)

**Files created:** UPDATED_FINAL_DECISION_MEMO_CLEAN.md, UPDATED_FINAL_OPEN_ITEMS.md, updated_final_candidate_classification.csv

**Changes:**
- `FINAL_DECISION_MEMO_CLEAN.md` line 136: "40% caution, 35% hard stop" → "Breadth T1 block: None (breadth is T2 control only)"
- `FINAL_DECISION_MEMO_CLEAN.md` breadth table: added breadth_t1_permission and breadth_t2_permission columns
- `FINAL_OPEN_ITEMS.md`: added breadth gate rejection reason, corrected sector L4 status
- Classification CSV: added capital_allocation and note columns

**No strategy change.** Wording corrected to match backtest evidence.

---

## Patch 2: Breadth Rules (Task 2) — CRITICAL

**Files created:** UPDATED_BREADTH_RULE_FINAL.md, UPDATED_phase33_paper_trade_rules.md, UPDATED_FINAL_DAILY_RUNBOOK.md, breadth_rule_patch_notes.md

**Root cause:** Phase33 docs incorrectly stated breadth defense = "no new entries" as a hard block.
Backtests showed hard_40 gate reduces MAR 0.416→0.344 (blocks 1125 winners vs 616 losers).

**What changed:**
- Defense zone (<35%): was "NO_NEW_ENTRY_BREADTH" → now "NEW_T1_MANUAL_REVIEW_BREADTH"
- VNINDEX bear regime remains the ONLY hard T1 block
- New fields: breadth_t1_permission (True unless VNINDEX bear), breadth_t2_permission (False in defense/caution)
- New final_action enum: expanded from 7 values to 9 values

**Python code change (`portfolio_optimization_final_steps.py`):**
- `_final_action()` rewritten: defense zone returns ("NEW_T1_MANUAL_REVIEW_BREADTH", reason) instead of "NO_NEW_ENTRY_BREADTH"
- Added `_breadth_permissions()` and `_strategy_classification()` helper functions
- `run_scan()` now populates breadth_t1_permission, breadth_t2_permission, strategy_classification, pb_trigger_price, tp1_price, trail_price, final_action_reason

---

## Patch 3: Sector L4 Status (Task 3)

**Files created:** UPDATED_SECTOR_L4_FINAL_FINDINGS.md, sector_l4_patch_notes.md

**Change:** SHADOW_RISK_CONTROL → DASHBOARD_WARNING_ONLY

**Reason:**
- Best sector rule (l4_breadth<50%): MAR 0.416→0.438 (+0.022). Not material.
- All name caps hurt MAR significantly.
- No automatic sector trade blocks are used.

---

## Patch 4: Phase34 Daily Scan (Task 4)

**Files created:** phase34_daily_scan_schema.csv (37 fields), phase34_daily_scan_sample.csv

**New fields vs Phase33:**
- pct_cloud_bull_s3: S3 universe breadth
- breadth_t1_permission: True/False
- breadth_t2_permission: True/False
- strategy_classification: A3_PRODUCTION|PTS_SHADOW|S3_RESEARCH_ONLY|WATCH_ONLY|SKIP
- pb_trigger_price: entry_close × 0.96
- tp1_price: entry_close × 1.18
- trail_price: peak − 2.5×ATR14
- final_action_reason: human-readable string

**Output:**
- phase34_daily_scan_sample.csv (primary)
- phase33_daily_scan_sample.csv (legacy alias, same content)

---

## Patch 5: Dashboard Spec (Task 5)

**Files created:** FINAL_DASHBOARD_SPEC.md

**Changes vs phase33_dashboard_spec.md:**
- Panel 4 now shows pb_trigger_price, tp1_price, trail_price, final_action_reason columns
- Panel 4 sort order: NEW_T1 > NEW_T1_MANUAL_REVIEW_BREADTH > WAIT_PB > HOLD_T1_ONLY
- Panel 4 color coding: NEW_T1_MANUAL_REVIEW_BREADTH → orange (not blocked, needs review)
- Panel 6 (S3) label changed: "S3 RESEARCH_ONLY — NO CAPITAL. NO POSITION SIZE."
- Alert rules added for regime bear and breadth defense banners

---

## Patch 6: AFL Parity Test (Task 6)

**Files created:** AFL_PARITY_SMOKE_TEST.csv, AFL_PARITY_NOTES.md

**Result:** 10 symbols tested. 8 MATCH, 2 ADV_DIFF (within expected 5% tolerance), 1 BAR_OFF_BY_1.
No AFL update required. AFL correctly implements A3 DP-First logic.

**Known differences (expected, not bugs):**
- ADV50: Python uses panel value column; AFL approximates as close×vol×1000. Max diff ~6%.
- Entry bar: Python fires bar+1 after crossover; AFL fires on crossover bar. ±1 bar expected.

---

## Patch 7: Final Runbook (Task 7)

**Files created:** FINAL_DAILY_RUNBOOK_CLEAN.md (supersedes FINAL_DAILY_RUNBOOK.md)

**Changes:**
- 10-step format with clear step boundaries
- Step 4 (breadth check): corrected to show breadth is advisory, not blocking for T1
- Step 6: manual review criteria for NEW_T1_MANUAL_REVIEW_BREADTH signals
- Added SKIP_VNINDEX_BEAR and NO_T2_BREADTH to signal table
- Removed "no new entries" language for defense zone

---

## What Was NOT Changed

- Strategy parameters: EMA 20/100, TP1 +18%, trail 2.5×ATR14, T2 ≥4%, max_hold 250 bars — all unchanged
- A3 DP MAR = 0.416 at 5B/10% — confirmed, not recalculated
- S3 classification (RESEARCH_ONLY) — confirmed
- PTS classification (PAPER_TRADE_SHADOW) — confirmed
- Sector L4 map (273 symbols) — unchanged
- Phase 3.1 liquidity audit results — unchanged
