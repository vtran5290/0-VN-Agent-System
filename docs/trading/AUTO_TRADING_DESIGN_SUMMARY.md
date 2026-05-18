# Auto-Trading Infrastructure — Design Summary

**Repo:** VN Agent System | **Maturity:** Paper-first + real-capital readiness (NO-GO live) | **Engine:** `src/trading/` only

## Architecture

```
Research scan CSV (SSOT) → live/data_health → live/order_intent → OrderProposal
  → batch risk → OMS execute → reconciliation → kill switch / dashboard
```

- **NOT in OMS:** EMA/cloud recompute, strategy optimization, LLM decisions
- **Ledgers:** research `data/paper_trade/` (unchanged) | execution paper `data/trading/live/`
- **Brokers:** PaperBroker (default) | DNSEBroker (placeholder, NotImplementedError)

## Frozen strategy (adapter only)

A3_DP production only | T1 50% / T2 on ADD_T2 | exits from scan | PTS shadow off | S3 research-only | breadth → MANUAL_REVIEW | Sector L4 warning | no perf throttle | macro pending | AFL visual

## Key modules

| Module | Role |
|--------|------|
| `live/workflow.py` | Orchestrates full live-workflow |
| `live/order_intent.py` | Scan CSV → intents (ACTION_MAP on final_action) |
| `live/data_health.py` | Panel/scan integrity → PASS/WARN/CRITICAL_FAIL |
| `live/paper_ledger.py` | Execution paper trades CSV |
| `risk/engine.py` + `rules.py` + `live_rules.py` | PASS / MANUAL_REVIEW / BLOCK |
| `risk/batch_context.py` | Simulated NAV/cash/slots across batch |
| `oms/order_manager.py` | State machine, trade-intent lock, pre-submit re-risk |
| `reconciliation/` | Baseline + OMS vs broker |
| `monitoring/kill_switch.py` | Blocks on critical failures |

## Two CLI paths

1. **Production:** `live-workflow --mode paper` (scan-driven)
2. **Legacy:** `propose` uses PlaceholderStrategy (test only — not production)

## Config

- `config/trading.yaml` — risk defaults
- `config/live_trading.yaml` — modes, flags, `scan_csv_path` (currently sample CSV)

## Paper accounts usability (done)

- Named accounts: 30M pilot + 5B reference + 10B scale + 20B liquidity stress + S3 shadow
- Account sizing policies (`scan_size_strict`, `cap_to_account_limits`, `cap_to_liquidity`)
- Manual review row_hash stale guard | Traffic light dashboard | `run-all` CLI
- S3 date filter + strict `s3_no_real_order_flag` | Path guard vs `data/paper_trade/`

## P0.1 hardening (done)

- Exact A3_PRODUCTION gate | SELL risk path | MANUAL_REVIEW queue | TP1 partial P&L
- build-intents production-safe | S3 shadow under live/s3_shadow/

## P0 hardening (done)

- Scan resolver (`live/scan_resolver.py`)
- Paper mode true fills + execution ledger
- SELL exit intents from scan
- Reconciliation gating from persisted status
- Run lock + manifest
- Batch + pre-submit trade-intent fixes

## Remaining gaps

- Wire automated daily phase36 CSV output (not only resolver latest-file)
- MANUAL_REVIEW approve/reject workflow
- Slippage, partial fills, VN holiday calendar
- DNSE integration behind same interface

## Tests

19× `tests/test_trading_*.py` — run all before any change. Paper-live ready: `paper-accounts run-all`.
