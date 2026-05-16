# Breadth Rule Patch Notes

Date: 2026-05-16

## What Changed

The original Phase33 docs used breadth as a hard T1 entry block. This was WRONG based on backtest evidence.

### Original (wrong) language in phase33 docs:
- `phase33_paper_trade_rules.md` line 11: "A3 breadth ≥ 40% (breadth_zone = normal)" as entry condition #4
- `FINAL_DAILY_RUNBOOK.md` line 21: "35–40%: caution (T1 only, no T2)" — implied T1 was blocked elsewhere
- `FINAL_DAILY_RUNBOOK.md` line 25: "< 35%: defense (no new entries, block T2)"
- `FINAL_DECISION_MEMO_CLEAN.md` line 103: "No new live entries unless manually overridden" for defense
- `FINAL_DECISION_MEMO_CLEAN.md` line 136: "A3 breadth gate | 40% caution, 35% hard stop"

### Root cause of error:
The wrong wording was written before backtests showed that hard breadth gates HURT MAR:
- hard_40: MAR 0.416 → 0.344 (blocked 1125 winners vs 616 losers)
- hard_35: MAR 0.416 → 0.166 (catastrophic)

### Correct rule (evidence-based):
- Breadth is T2 risk control only. T1 is always allowed when VNINDEX is bull.
- Defense zone (<35%) adds operator review requirement but does NOT auto-block T1.
- Only VNINDEX bear regime (EMA20 < EMA100) is a hard T1 block.

## Files Updated

| Original File | Updated File | Key Change |
|--------------|-------------|------------|
| BREADTH_RULE_FINAL.md | UPDATED_BREADTH_RULE_FINAL.md | T1/T2 permission columns added |
| phase33_paper_trade_rules.md | UPDATED_phase33_paper_trade_rules.md | Breadth removed from entry conditions |
| FINAL_DAILY_RUNBOOK.md | UPDATED_FINAL_DAILY_RUNBOOK.md | Defense zone: T1 allowed with review |
| FINAL_DECISION_MEMO_CLEAN.md | UPDATED_FINAL_DECISION_MEMO_CLEAN.md | Breadth gate row corrected |
| phase33_daily_scan_sample.csv | phase34_daily_scan_sample.csv | NO_NEW_ENTRY_BREADTH → NEW_T1_MANUAL_REVIEW_BREADTH |

## Scan Logic Change

Old `_final_action()` logic:
```python
if breadth_zone == "defense":
    return "NO_NEW_ENTRY_BREADTH"  # WRONG — hard block
```

New `_final_action()` logic:
```python
if not regime_bull:
    return "SKIP_VNINDEX_BEAR"     # Only hard block
if liq_rec == "skip":
    return "SKIP_LIQUIDITY"
if a3_active:
    if breadth_zone == "defense":
        return "NEW_T1_MANUAL_REVIEW_BREADTH"  # Review, not block
    return "NEW_T1"
```

## New Scan Fields Added in Phase34

- `breadth_t1_permission` (bool): True unless VNINDEX bear
- `breadth_t2_permission` (bool): False when breadth_zone = defense or caution, True otherwise
- `final_action_reason` (str): Human-readable explanation
- `strategy_classification` (str): A3_PRODUCTION | PTS_SHADOW | S3_RESEARCH_ONLY | WATCH_ONLY | SKIP
- `pb_trigger_price` (float): Entry price × 0.96 (T2 trigger level)
- `tp1_price` (float): Entry price × 1.18
- `trail_price` (float): Estimated trail stop from current peak
