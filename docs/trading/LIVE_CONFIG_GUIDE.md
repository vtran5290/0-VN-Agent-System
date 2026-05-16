# Live Trading Config Guide

Config files:
- [`config/trading.yaml`](../../config/trading.yaml) — skeleton defaults
- [`config/live_trading.yaml`](../../config/live_trading.yaml) — production live settings

## Modes

| Mode | Broker submit | Ledger | Notes |
|------|---------------|--------|-------|
| `paper` | No (dry log) | Yes | Internal paper ledger only |
| `dry_run` | No | Optional | May read broker; builds payload |
| `live_manual` | No (v1) | Yes | Requires `approved=true` on intents |
| `live_auto` | Disabled | — | Fail-closed unless `enable_live_auto: true` |

## Key flags

- `require_regime_bull` — blocks new T1 when VNINDEX regime not bull (from scan column)
- `require_data_health` — blocks on CRITICAL_FAIL
- `require_reconciliation_clean` — blocks when `BLOCK_NEW_ORDERS`
- `allow_same_day_same_symbol_side: false` — trade-intent lock per day/symbol/side

Override via env: `TRADING_MODE`, `LIVE_TRADING`, `DRY_RUN`.
