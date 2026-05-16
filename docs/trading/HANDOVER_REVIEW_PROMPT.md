# Handover — Real-Capital Readiness + Trading Skeleton (for external AI review)

## Zip contents

- `src/trading/` — full canonical engine (skeleton + live readiness)
- `config/trading.yaml`, `config/live_trading.yaml`
- `docs/trading/` — README, LIVE_CONFIG_GUIDE, BROKER_ADAPTER_GUIDE, REAL_CAPITAL_READINESS
- `pp_backtest/live/run_live_workflow.py` — thin wrapper only
- `scripts/trading_daily_run.py`
- `tests/test_trading_*.py`, `tests/fixtures/trading/`
- `.env.example` (trading vars section)

## Verified commands

```powershell
cd "<repo_root>"
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_reconciliation.py tests/test_trading_batch_risk.py tests/test_trading_order_intent.py tests/test_trading_paper_ledger_live.py tests/test_trading_trade_intent_lock.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py -q
# Expected: 17 passed

.\.venv\Scripts\python.exe -m src.trading.cli live-workflow --mode paper --date 2026-05-16
# Expected: data_health WARN, intents_count ~10, kill_switch CLEAR
```

## Copy-paste review prompt below

---

You are reviewing **Real-Capital Readiness Hardening** added to repo `VN Agent System` on top of an existing `src/trading/` paper-first skeleton.

### Scope of this review

**In scope:** execution safety, OMS hardening, scan adapter, risk batching, reconciliation baseline, kill switch, paper ledger, CLI workflow, tests, docs.

**Out of scope:** strategy optimization, EMA/cloud logic changes, promoting PTS/S3 to production, modifying `data/paper_trade/` research ledger.

### Canonical architecture

- All logic under `src/trading/` (NOT a parallel engine in `pp_backtest/`)
- `pp_backtest/live/run_live_workflow.py` is a thin wrapper only
- Daily scan CSV (phase34) = source of truth; OMS is signal **consumer** only

### Strategy contract (must remain frozen)

- Production: **A3_DP** only (`strategy_classification == A3_PRODUCTION`)
- T1 50%, T2 only on scan `ADD_T2` (>=4% pullback already in scan)
- TP1 +18%, trail 2.5×ATR14, max hold 250 — not recomputed in OMS
- PTS: shadow only, no capital orders
- S3: research/watchlist only
- Breadth defense → `MANUAL_REVIEW`, not hard T1 block
- Sector L4: warning only
- Performance throttle: not implemented
- Macro: `pending_external_data`, not fabricated
- AFL: visual metadata only

### What was implemented

1. **Config:** `config/live_trading.yaml`, `LiveTradingConfig`, modes paper/dry_run/live_manual/live_auto (live_auto fail-closed)
2. **Data health:** `src/trading/live/data_health.py` → PASS/WARN/CRITICAL_FAIL, BLOCK_ORDER_GENERATION
3. **Paper ledger:** `data/trading/live/paper_trades.csv` (separate from `data/paper_trade/`)
4. **Order intents:** `src/trading/live/order_intent.py` reads phase34 scan, maps `final_action` → BUY_T1 / MANUAL_REVIEW / WATCH / SKIP
5. **Batch risk:** `src/trading/risk/batch_context.py` — simulated portfolio updates across proposal batch
6. **Live rules:** data health, kill switch, reconciliation, regime_bull, max_slots, max_daily_orders
7. **Trade-intent lock:** `strategy|date|symbol|side` blocks duplicate same-day intents
8. **Pre-submit re-risk:** reload state before `place_order`; `REJECTED_AT_EXECUTION`; broker capacity check
9. **Baseline reconciliation:** `snapshot-baseline` CLI; expected = baseline + OMS fills
10. **Kill switch:** `src/trading/monitoring/kill_switch.py`
11. **Daily report:** daily vs cumulative order counts; dashboard under `data/trading/live/dashboard/`
12. **Stale data:** uses `latest_panel_date` in proposal metadata when available
13. **UTC:** `src/trading/util/timeutil.py`
14. **CLI:** `live-workflow`, `data-health`, `build-intents`, `snapshot-baseline`
15. **DNSE:** still placeholder; triple gate; `NotImplementedError` after gates

### Safety defaults (verify)

- `LIVE_TRADING=false`, `DRY_RUN=true`
- No hardcoded credentials
- No broker retry loops
- Real capital: **NO-GO** per `docs/trading/REAL_CAPITAL_READINESS.md`

### Review checklist

1. Does any code recompute strategy signals (EMA/cloud) in OMS? (should be NO)
2. Can batch risk still over-approve collective exposure/cash/slots?
3. Are trade-intent lock and idempotency key both correct?
4. Does pre-submit re-risk cover all state changes after risk-review?
5. Is baseline reconciliation math correct?
6. Can live_auto or DNSE slip through to real orders?
7. Test gaps — what P0 cases are missing?
8. Production scan path — still points to sample CSV; is wiring documented?

### Deliverable format

- **FACTS** (what exists, paths)
- **GAPS** vs production-grade paper trading
- **RISKS** P0/P1/P2
- **RECOMMENDATIONS** (max 10, ordered)
- **VERDICT:** Ready for scan-driven paper / needs fixes / not ready

Do not recommend real capital or DNSE live orders until explicit future approval phase.
