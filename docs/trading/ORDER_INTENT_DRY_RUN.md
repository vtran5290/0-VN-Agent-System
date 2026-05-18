# Order-Intent Dry Run

**Stage 1 bridge.** Human review only. **This command does not send broker orders.**

## What it does

- Reads **positions SSOT:** `data/raw/current_positions_derived.json`
- Reads **signal SSOT:** `phase36_daily_scan_latest.csv` (`final_action` on `A3_PRODUCTION` rows only)
- Writes preview CSV: `data/trading/order_intent/order_intent_YYYY-MM-DD.csv`
- **`order_sent` must always be `NO`**
- **`manual_approval_required` defaults to `YES`**
- Does **not** replace manual judgment yet
- Does **not** activate live trading
- Does **not** use S3/intraday for production action
- Does **not** recompute EMA/cloud/ATR/trail/breadth
- Does **not** use `a3_rank_score` for action

**OMS consumes final_action only** in the production paper/live adapter (`build-intents`). This dry-run path is a **separate, broker-free** preview for the solo operator.

## Command

```powershell
python -m src.trading.cli generate-order-intent `
  --date YYYY-MM-DD `
  --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv `
  --positions-path data/raw/current_positions_derived.json `
  --output data/trading/order_intent/order_intent_YYYY-MM-DD.csv
```

Or via weekly wrapper:

```powershell
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD
```

## Date safety (operator)

- Output column **`date`** = **effective_scan_date** (panel date used for `final_action`).
- **`notes`** always includes `requested_date=YYYY-MM-DD` and `effective_scan_date=YYYY-MM-DD`.
- Placeholder years (e.g. `2099-01-01` from test fixtures) are **excluded** from production runs.
- If requested date has no scan rows, the latest scan date **on or before** requested is used.
- If gap > **7 days** (default), generation **fail-closed** unless `--allow-test-sample`.
- Production output files must **never** contain `date=2099-*` without a `test`/`sample` filename.
- Use `--allow-test-sample` only for unit tests and fixture scans.
- After generation, `weekly_pareto_operator.ps1` runs `validate-order-intent` (Python SSOT — not PowerShell `Select-String -SimpleMatch`, which does not treat `^` as regex).

## Outside-A3 holdings

| `holding_classification` | Meaning |
|------------------------|---------|
| `A3_PRODUCTION_MATCHED` | Scan match; `final_action` mapped to `suggested_action` |
| `DISCRETIONARY_OUTSIDE_A3` | No `A3_PRODUCTION` row — **no OMS action** |

Review template: `templates/outside_a3_holding_review_template.md`  
Labels: `DISCRETIONARY_OUTSIDE_A3`, `LEGACY_POSITION`, `WATCHLIST_ONLY`, `RESEARCH_SHADOW`

## Output columns

| Column | Description |
|--------|-------------|
| `date` | Effective scan panel date (not placeholder) |
| `ticker` | Holding symbol |
| `current_position_qty` | Lots from positions JSON |
| `current_position_value` | Estimated from entry × qty if no market value |
| `phase36_final_action` | From scan row |
| `suggested_action` | Mapped from `final_action` only |
| `suggested_size_value` | Blank (placeholder) |
| `reason` | Mapping / fail-closed reason |
| `risk_flag` | e.g. `OUTSIDE_A3_OR_NO_SCAN_MATCH` |
| `holding_classification` | `A3_PRODUCTION_MATCHED` or `DISCRETIONARY_OUTSIDE_A3` |
| `manual_approval_required` | Always `YES` |
| `order_sent` | Always `NO` |
| `notes` | `requested_date=` + `effective_scan_date=` + context |

## Suggested action mapping

| `final_action` | `suggested_action` |
|----------------|-------------------|
| `TRAIL_EXIT`, `MAX_HOLD_EXIT`, `TP1_PARTIAL` | `REVIEW_EXIT` |
| `NEW_T1` | `REVIEW_BUY_T1` |
| `NEW_T1_MANUAL_REVIEW_BREADTH` | `MANUAL_REVIEW_BREADTH` |
| `ADD_T2` | `REVIEW_ADD_T2` |
| `HOLD_T1_ONLY`, `NO_T2_BREADTH`, `WAIT_PB`, `WATCH_ONLY` | `HOLD_REVIEW` |
| `SKIP_LIQUIDITY`, `SKIP_VNINDEX_BEAR` | `NO_ACTION_FAIL_CLOSED` |
| missing / unknown | `NO_ACTION_FAIL_CLOSED` |
| no A3_PRODUCTION scan row | `NO_ACTION_FAIL_CLOSED` + `OUTSIDE_A3_OR_NO_SCAN_MATCH` |

## Fail-closed

| Condition | Behavior |
|-----------|----------|
| Missing scan file | Exit 1 — no CSV |
| Missing positions file | Exit 1 |
| Empty scan | Exit 1 |
| Missing `final_action` on matched row | Row flagged; exit code 2 if any flags |
| No scan match for holding | `OUTSIDE_A3_OR_NO_SCAN_MATCH` + `DISCRETIONARY_OUTSIDE_A3` |
| Placeholder-only scan dates | Exit 1 (production) |
| Stale scan > max-stale-days | Exit 1 (production) |

## What this is NOT

- Not `build-intents` (paper OMS adapter with ledger/sizing)
- Not `live-workflow` / `paper-accounts run-all`
- Not broker submission
- Not DNSE/DSE live

**Order-intent dry run sends no orders.** **Real capital remains NO-GO.**
