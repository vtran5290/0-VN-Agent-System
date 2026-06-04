# Distribution Risk v1.3 Panel Freshness Guard Runbook

Goal: ensure `v13_research.breadth_status` is correct and visible when the stock-level FireAnt panel lags the index date.

## Required sequence (research-only; does not affect `final_action` / OMS / sizing)

1. Refresh stock-level FireAnt OHLCV / TA panel:

```powershell
.\.venv\Scripts\python.exe scripts/update_ohlcv_panel_incremental.py --end <as_of_date>
```

2. Re-run Distribution Risk Lens v1.3 research outputs (also refreshes v1.2 base lens):

```powershell
.\.venv\Scripts\python.exe scripts/research/run_distribution_risk_v13.py --start 2012-01-01 --as-of <as_of_date>
```

## Read-only staleness behavior

After the v1.3 run, `data/research/market_risk/distribution_risk_latest.json` will contain (under `v13_research`):

- `breadth_status = OK` when `breadth_lag_sessions = 0`
- `breadth_status = STALE_BREADTH_NEEDS_REFRESH` when `breadth_lag_sessions > 2`

The production/report markdown is allowed to show this as **read-only metadata**. It must not include v1.3 probability surface forecasts or interaction lift tables.

## Pipeline wiring

The daily/weekly EOD decision-support scripts now apply the same best-effort refresh sequence:

- `scripts/trading\eod_market_context_refresh.ps1`
- `scripts/trading\weekly_pareto_operator.ps1`
- `scripts/trading\daily_eod_operator.ps1` (legacy alias)

The FireAnt panel refresh is **best-effort** (report generation continues if refresh fails). Staleness is still surfaced via metadata after the v1.3 run.

