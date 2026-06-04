# CF Annotation Implementation Report

**Date:** 2026-05-30
**Status:** COMPLETE — annotation patch implemented, tested, and validated

---

## Objective

Implement Phase 3 Capital Footprint labels as non-binding, read-only operator annotations
in the daily Phase36 scan output. No production columns may be altered; annotation is
opt-in via config flag (default off).

---

## FACTS

### Files Created or Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/trading/research/capital_footprint/annotation.py` | Created | Annotation engine (operator notes, merge, JSON/MD builders) |
| `config/trading.yaml` | Modified | Added `research.cf_annotation_enabled: false` flag |
| `scripts/reporting/daily_scan_report.py` | Modified | Three surgical edits — guard, md section, JSON field |
| `tests/research/test_cf_annotation.py` | Created | 53-test smoke suite |
| `data/research/capital_footprint/sample_daily_scan_before.json` | Created | Baseline before/after reference |
| `data/research/capital_footprint/sample_daily_scan_after.json` | Created | Annotation-enabled reference |

### Annotation Logic (from Phase 3 decision memo)

| Condition | cf_annotation_active | cf_operator_note |
|-----------|---------------------|-----------------|
| SUPPLY_ABSORPTION_SETUP + BULL_BROAD regime | 1 | ✓ Dry-up setup in BULL_BROAD — constructive watchlist setup |
| SUPPLY_ABSORPTION_SETUP + other regime | 1 | ✗ Dry-up outside BULL_BROAD — weak/avoid as entry signal |
| EXTENSION_DISTRIBUTION_RISK + event_age ≥ 5 | 1 | ⚠ Extended 5+ bars — do not add / review distribution risk |
| EXTENSION_DISTRIBUTION_RISK + event_age < 5 | 0 | Extension started — observe only (no edge at T=0) |
| FAILED_BREAKOUT | 0 | Research-only: possible bounce/reclaim — verify manually before acting |
| BREAKOUT_CONFIRMED | 0 | Research-only: breakout confirmed — not yet production-ready |
| BREAKOUT_FOLLOW_THROUGH_PENDING | 0 | Research-only: breakout pending volume confirm — not yet production-ready |
| NEUTRAL / not in CF panel | 0 | (no annotation) |

### Test Suite Results

53/53 tests pass. Test classes:

| Class | Tests | What It Verifies |
|-------|-------|-----------------|
| `TestOperatorNote` | 9 | All annotation branches, NEUTRAL, missing phase label |
| `TestBuildCfAnnotationForDate` | 4 | Date slice, empty date, regime column fallback |
| `TestAnnotateScanDfPreservesProduction` | 9 | final_action, a3_rank_score, all original columns unchanged |
| `TestAnnotateScanDfCfColsDrop` | 3 | Pre-existing cf_* cols dropped before re-join |
| `TestVerifyProductionColumnsIntact` | 8 | AssertionError on any protected-column mutation |
| `TestIsCfAnnotationEnabled` | 5 | Flag read/default/missing YAML/invalid YAML/import-error |
| `TestBuildCfAnnotationSection` | 7 | Missing cols, empty active, active table, passive table |
| `TestWriteDailyScanReportFlagOff` | 8 | Report writer: flag off → no cf_* columns; flag on → cf_annotation in JSON; final_action counts identical |

### Sample Output Validation

Ran `write_daily_scan_report()` with `cf_annotation_enabled: true` against real panel data.

**Before (flag off):**
```
final_action_counts: {TRAIL_EXIT: 45, WATCH_ONLY: 42, NO_T2_BREADTH: 11, HOLD_T1_ONLY: 4, NEW_T1_MANUAL_REVIEW_BREADTH: 2, TP1_PARTIAL: 2}
"cf_annotation": absent
```

**After (flag on):**
```
final_action_counts: {TRAIL_EXIT: 45, WATCH_ONLY: 42, NO_T2_BREADTH: 11, HOLD_T1_ONLY: 4, NEW_T1_MANUAL_REVIEW_BREADTH: 2, TP1_PARTIAL: 2}
cf_annotation.enabled: true
cf_annotation.n_cf_symbols: 106
cf_annotation.n_active: 18
```

**final_action counts IDENTICAL.** Hard constraint verified.

---

## ASSUMPTIONS

- `breadth_regime_bucket` is the correct column name in the live CF panel (verified in classifier output).
- `parents[4]` from `annotation.py` resolves to repo root `D:\V\0. VN Agent System` — verified during implementation.
- CF panel build (~25-30s) is acceptable latency for operator review; daily scan is not real-time.
- Symbols not in CF panel (adv50 < 100mn VND) silently get NaN cf_* columns — operator is aware CF covers only ~366 liquid symbols vs 1,562 scanned.

---

## RISKS

| Risk | Severity | Mitigation |
|------|----------|-----------|
| CF panel build failure breaks daily scan | Low | try/except wrapper; annotation failure is logged and skipped; report continues normally |
| breadth_regime_bucket column name changes | Low | `annotation.py` uses `next()` fallback across 3 possible names |
| Flag accidentally enabled in production | Low | Default is `false`; requires explicit config edit; section comment in trading.yaml explains consequence |
| CF panel build adds 25-30s to scan runtime | Medium | Acceptable for daily operator review; not on real-time order path |
| 4-week observation period not started | Medium — noted | See next steps |

---

## Hard Constraints — Verified Intact

- `final_action`: unchanged (smoke tested on real panel)
- `a3_rank_score`: unchanged (tested in `TestAnnotateScanDfPreservesProduction`)
- OMS payload: untouched (annotation path never calls OMS functions)
- DNSE routing: untouched
- Position sizing: untouched
- `_verify_production_columns_intact()` raises `AssertionError` immediately if any protected column is altered

---

## What Was NOT Changed

- A3 signal logic, scoring, ranking
- OMS order generation
- DNSE routing
- Any existing column in the scan output when flag is off
- Any column values when flag is on — only cf_* columns are appended

---

## Open Issues

1. **4-week observation period not started.** Phase 3 decision memo requires 4 weeks of operator monitoring before any CF label is promoted beyond research-only. Start: enable flag in config, monitor weekly.
2. **BREAKOUT_CONFIRMED and BREAKOUT_PENDING are research-only** with no forward-return edge proven in production. Do not promote to active annotation without 4 weeks of live observation.
3. **CF coverage is 366 symbols vs 1,562 A3-scanned.** ~76% of A3 scan symbols get NaN cf_* annotation. This is expected and documented.

---

## Next Steps

| Priority | Action | Owner |
|----------|--------|-------|
| P0 | Enable `cf_annotation_enabled: true` in config to begin 4-week observation | Operator |
| P1 | Review `cf_annotation.n_active` and `active_annotations` in daily scan weekly | Operator |
| P2 | After 4 weeks: assess whether SA+BULL_BROAD annotations match market intuition | Operator → ChatGPT review |
| P3 | After 4 weeks: decide whether to promote any label from research-only to active | Operator → ChatGPT IC |

---

## Next Decision Required

**Enable the flag to start observation?**

Command to enable:
```yaml
# config/trading.yaml
research:
  cf_annotation_enabled: true
```

Then run the daily scan script normally. The CF annotation section will appear at the bottom of `daily_scan.md` and the `cf_annotation` block will appear in `daily_scan.json`.

---

*Implementation: Claude Code, 2026-05-30*
*Phase 3 source: `capital_footprint_phase3_decision_memo.md`*
*Runner: `scripts/research/run_capital_footprint_phase3_backtest.py`*
