# Phase34 Scan Patch Notes

Date: 2026-05-16

## What Changed from Phase33

Phase34 scan adds 8 new fields to the 29-field Phase33 schema.

### New Fields

| Field | Type | Why Added |
|-------|------|-----------|
| pct_cloud_bull_s3 | float | S3 breadth separate from A3 breadth for monitoring |
| breadth_t1_permission | bool | Explicit T1 gate flag (True unless VNINDEX bear) |
| breadth_t2_permission | bool | Explicit T2 gate flag (False in defense/caution) |
| strategy_classification | str | Downstream dashboard routing |
| pb_trigger_price | float | Operators see exact T2 trigger level without calculating |
| tp1_price | float | Operators see exact TP1 target without calculating |
| trail_price | float | Operators see current trail stop without AFL |
| final_action_reason | str | Machine-generated explanation of each action |

### final_action Enum Change

Phase33 (wrong):
```
NO_NEW_ENTRY_BREADTH  ← implied hard block for breadth defense
```

Phase34 (correct):
```
NEW_T1_MANUAL_REVIEW_BREADTH  ← review flag, not auto-block
NO_T2_BREADTH                  ← T2-specific block
SKIP_VNINDEX_BEAR              ← renamed from HOLD_T1_ONLY in no-signal case
```

Full Phase34 final_action enum:
- NEW_T1
- NEW_T1_MANUAL_REVIEW_BREADTH
- WAIT_PB
- ADD_T2
- HOLD_T1_ONLY
- NO_T2_BREADTH
- SKIP_LIQUIDITY
- SKIP_VNINDEX_BEAR
- WATCH_ONLY

### Python Code Location

`pp_backtest/portfolio_optimization_final_steps.py`:
- `_final_action()`: rewritten, now returns (action, reason) tuple
- `_breadth_permissions()`: new helper
- `_strategy_classification()`: new helper
- `run_scan()`: now populates all Phase34 fields, writes to phase34_daily_scan_sample.csv

### Output Files

- `phase34_daily_scan_schema.csv` — 37-field schema
- `phase34_daily_scan_sample.csv` — primary output
- `phase33_daily_scan_sample.csv` — legacy alias (same content)
- `phase34_daily_scan_schema.csv` also written to `phase33_daily_scan_schema.csv` for legacy compatibility
