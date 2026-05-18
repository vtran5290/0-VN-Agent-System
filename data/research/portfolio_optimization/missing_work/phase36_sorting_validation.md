# Phase36 Sorting Validation

**Date:** 2026-05-17  
**Scan command:** `python pp_backtest/portfolio_optimization_final_steps.py --step scan`  
**Output:** `phase36_daily_scan_sample.csv` (94 rows, as_of 2026-05-15)

---

## Method

1. Loaded post-scan CSV (already sorted for operator review).
2. Re-sorted alphabetically by `symbol` to simulate pre-display order.
3. Applied `_sort_scan_for_review()` (Phase36 sort function).
4. Compared multiset counts and per-symbol fields before vs after sort.

---

## Results

| Check | Pass? |
|-------|-------|
| `final_action` count distribution unchanged | **YES** |
| `strategy_classification` count distribution unchanged | **YES** |
| Per-symbol `final_action` unchanged | **YES** |
| Per-symbol `target_T1_M` unchanged | **YES** |
| Per-symbol `a3_rank_score` unchanged | **YES** |
| Only row order may change | **YES** |

### final_action counts (unchanged by sort)

| final_action | Count |
|--------------|------:|
| WATCH_ONLY | 38 |
| TRAIL_EXIT | 32 |
| NO_T2_BREADTH | 17 |
| HOLD_T1_ONLY | 4 |
| TP1_PARTIAL | 2 |
| NEW_T1_MANUAL_REVIEW_BREADTH | 1 |
| NEW_T1 | 0 |
| ADD_T2 | 0 |
| SKIP_LIQUIDITY | 0 |
| SKIP_VNINDEX_BEAR | 0 |

### NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH (sort target)

| Symbol | final_action | a3_rank_score | phase36_operator_priority |
|--------|--------------|---------------|---------------------------|
| VPB | NEW_T1_MANUAL_REVIEW_BREADTH | 0.993 | 1 |

Only one new-entry candidate on this scan date — order change vs alpha sort is **N/A** (single row). When multiple candidates exist, sort places `NEW_T1` before `NEW_T1_MANUAL_REVIEW_BREADTH`, then `a3_rank_score` DESC.

---

## Conclusion

Phase36 sorting is **display-only**. No production fields are mutated by `_sort_scan_for_review()`.
