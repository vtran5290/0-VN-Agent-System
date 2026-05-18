# Daily paper operator prompt (trading days 16:30)

Use this prompt when running or scheduling the daily paper-live workflow.

## Pareto cadence for solo operator

| Cadence | Accounts |
|---------|----------|
| **Weekly** | `A3_DSE_PILOT_PAPER_SMALL`, `A3_PROD_PAPER_5B` |
| **Monthly** | `A3_SCALE_PAPER_10B`, `A3_SCALE_PAPER_20B`, `S3_MAX60_SHADOW_PAPER` |

- **S3** remains shadow-only — no A3 production P&L mix.
- **10B/20B** are scale/capacity checks, not weekly workload.
- Paper accounts validate OMS readiness; they are not the destination.
- For weekly **decision support** (no orders): `.\scripts\trading\weekly_pareto_operator.ps1`

When running daily paper-live, you may limit `run-all` to pilot + 5B on non-monthly weeks (operator choice; YAML unchanged).

---

Run today's VN Agent System paper-trading workflow.

This is PAPER TRADING ONLY.

Do NOT place real DSE/DNSE orders.
Do NOT enable live_auto.
Do NOT modify data/paper_trade/.
Do NOT change strategy logic.
Do NOT recompute EMA/cloud/breadth/ATR/trail in OMS.
Daily scan CSV is the signal source of truth.
OMS consumes final_action only.

Paper accounts to run today:

1. A3_DSE_PILOT_PAPER_SMALL — 30M VND, tiny DSE pilot mimic, cap_to_account_limits
2. A3_PROD_PAPER_5B — 5B VND, A3 production reference, scan_size_strict
3. A3_SCALE_PAPER_10B — 10B VND, scale check
4. A3_SCALE_PAPER_20B — 20B VND, liquidity / capacity stress, cap_to_liquidity
5. S3_MAX60_SHADOW_PAPER — shadow only, ledger `data/trading/live/s3_shadow/`

Workflow:

1. `python pp_backtest/portfolio_optimization_final_steps.py --step scan` (writes `phase36_daily_scan_latest.csv`)
2. `python -m src.trading.cli resolve-scan --date TODAY --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv`
3. If scan **stale** (calendar date != `as_of_date`) → **STOP** (no paper run). Backfill only:
   `.\scripts\trading\daily_paper_live_full_run.ps1 -Date TODAY -UseLatestScanDate -Force`
   (`-Force` only if run lock exists from a prior incomplete run — never on scheduled task)
4. Init accounts (idempotent)
5. `python -m src.trading.cli paper-accounts run-all --date TODAY --scan-path <RESOLVED_CSV> --include-s3-shadow`
   - Use `--allow-sample` only if resolver blocks `phase36_daily_scan_sample.csv` (production filename contains "sample")
6. Summaries, compare, manual-review display (do not approve rows)
7. Confirm: `daily_operator_pack_TODAY.md`, `compare_TODAY.md`, `valid_paper_day_TODAY.json`

Or run script: `.\scripts\trading\daily_paper_live_full_run.ps1`

Deliver operator report sections A–H (see PAPER_TRADING_OPERATIONS_GUIDE.md).

Real capital: NO-GO | DSE/DNSE live: NO-GO | live_auto: NO-GO
