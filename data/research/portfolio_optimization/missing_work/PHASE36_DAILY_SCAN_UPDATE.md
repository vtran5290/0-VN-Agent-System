# Phase36 Daily Scan Update

**Decision:** CONDITIONAL_NO_CHANGE  
**Date:** 2026-05-17

## What changed (operator layer only)

- Same production rows and `final_action` rules as Phase35.
- Added Phase36 ranking / context fields for dashboard and CSV sort order.
- Same-day A3 `NEW_T1` / `NEW_T1_MANUAL_REVIEW_BREADTH` rows sort by `a3_rank_score` DESC (display only).
- Operator report: `phase36_daily_operator_report.md`

## What did NOT change

- A3 production logic, T1/T2 sizing, exits (trail 2.5×ATR14), breadth gates, VNINDEX bear block.
- OMS: still consumes `final_action` only.
- S3: still paper-shadow only; no live/DNSE orders; does not gate A3.

## Outputs

| File | Role |
|------|------|
| `phase36_daily_scan_sample.csv` | Primary |
| `phase35_daily_scan_sample.csv` | Alias |
| `phase34_daily_scan_sample.csv` | Alias |
| `phase36_daily_scan_schema.csv` | Field dictionary |

## Command

```powershell
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```
