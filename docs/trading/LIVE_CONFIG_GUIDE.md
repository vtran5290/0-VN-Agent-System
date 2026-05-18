# Live Trading Config Guide

Config files:
- [`config/trading.yaml`](../../config/trading.yaml) — skeleton defaults
- [`config/live_trading.yaml`](../../config/live_trading.yaml) — production live settings
- [`config/paper_accounts.yaml`](../../config/paper_accounts.yaml) — named paper accounts (30M / 5B / 10B / 20B A3 + S3 shadow; NAV, slots, limits, `scan_size_basis`, ledger paths)

## Scan resolver

Priority: `--scan-path` > `PHASE36_DAILY_SCAN_PATH` > `paths.scan_csv_path` > latest `phase36*.csv` in `missing_work/`.

- `allow_sample_scan: false` — blocks filenames containing `sample` unless true.
- `allow_missing_reconciliation: true` — paper may run without prior recon file; `live_manual`/`live_auto` block if missing.

## Modes

| Mode | Broker | Fills | Ledger |
|------|--------|-------|--------|
| `paper` | PaperBroker | Yes (simulated) | `data/trading/live/accounts/<ACCOUNT_ID>/` |
| `dry_run` | No | No | unchanged |
| `live_manual` | No (v1) | No | Yes |
| `live_auto` | Disabled | — | Fail-closed |

## Key flags

- `require_regime_bull` — blocks new T1 when VNINDEX regime not bull (from scan column)
- `require_data_health` — blocks on CRITICAL_FAIL
- `require_reconciliation_clean` — blocks when `BLOCK_NEW_ORDERS`
- `allow_same_day_same_symbol_side: false` — trade-intent lock per day/symbol/side

Override via env: `TRADING_MODE`, `LIVE_TRADING`, `DRY_RUN`.
