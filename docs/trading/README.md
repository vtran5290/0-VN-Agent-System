# Vietnam Auto-Trading (Paper-First)

Production skeleton for deterministic signal → risk → execution → reconciliation.  
**No real DNSE orders in v1.** Default: `LIVE_TRADING=false`, `DRY_RUN=true`.

## Architecture

Canonical engine: `src/trading/` (see also `src/trading/live/` for production readiness).

- `src/trading/brokers/` — `BaseBroker`, `PaperBroker`, `DNSEBroker` (placeholder)
- `src/trading/live/` — data health, scan→intents, paper ledger, workflow
- `src/trading/risk/` — batch-aware risk (PASS / MANUAL_REVIEW / BLOCK)
- `src/trading/oms/` — trade-intent lock, pre-submit re-risk
- `src/trading/reconciliation/` — baseline + live recon
- `src/trading/monitoring/` — kill switch, daily vs cumulative counts

**Strategy contract (frozen):** A3_DP only; daily scan = source of truth; PTS shadow OFF; S3 research-only; breadth = manual review not hard T1 block; Sector L4 warning only; no performance throttle; macro pending; AFL visual only.

Research ledger (`data/paper_trade/`) is **unchanged**. Execution paper ledger: `data/trading/live/`.

See [`REAL_CAPITAL_READINESS.md`](REAL_CAPITAL_READINESS.md) — **NO-GO** for real capital.

## Setup

```powershell
cd "c:\Users\LOLII\Documents\V\0. VN Agent System"
copy .env.example .env
# Edit .env: keep LIVE_TRADING=false, DRY_RUN=true for safe mode
```

Risk defaults: [`config/trading.yaml`](../../config/trading.yaml)

## Daily workflow

### 1) Daily scan (existing)

```powershell
.\daily_three_strategy_scan_run.cmd
```

Produces `data/paper_trade/reports/scan_YYYY-MM-DD.md` (human workflow).

### 2) Generate order proposals

```powershell
python -m src.trading.cli propose --asof 2026-05-16
```

Output: `data/trading/order_proposals/order_proposals_2026-05-16.json`

Optional integration test symbol:

```powershell
$env:TRADING_PLACEHOLDER_SYMBOL = "FPT"
python -m src.trading.cli propose --asof 2026-05-16
```

### 3) Risk review

```powershell
python -m src.trading.cli risk-review --asof 2026-05-16
```

Writes per-order state under `data/trading/orders/` and audit log `data/trading/audit/order_events.jsonl`.

### 4) Paper execution

Safe default (no broker call):

```powershell
python -m src.trading.cli execute --asof 2026-05-16 --broker paper
```

To simulate paper fills:

```powershell
$env:LIVE_TRADING = "true"
$env:DRY_RUN = "false"
$env:BROKER = "paper"
python -m src.trading.cli execute --asof 2026-05-16
```

### 5) Reconciliation

```powershell
python -m src.trading.cli reconcile --asof 2026-05-16
```

Output: `data/trading/reconciliation/recon_2026-05-16.json`

### Daily report

```powershell
python -m src.trading.cli report --asof 2026-05-16
```

Output: `data/trading/reports/daily_report_2026-05-16.md`

### All-in-one (dry pipeline)

```powershell
python scripts/trading_daily_run.py 2026-05-16
# or
python -m src.trading.cli run-daily --asof 2026-05-16
```

## Safety gates (DNSE live — future)

Real DNSE `place_order` requires **all**:

- `LIVE_TRADING=true`
- `DRY_RUN=false`
- `CONFIRM_LIVE_BROKER=DNSE`
- `BROKER=dnse`
- `TRADING_MAX_ORDER_VALUE_VND` configured

v1 raises `NotImplementedError` even when gates pass.

## Tests

```powershell
pytest tests/test_trading_*.py -q
```

## Phase 2 (not implemented)

- `signals/scan_adapter.py` — read `scan_watchlists_last.json` → proposals
- DNSE via `vnstock.connector.dnse.Trade`
- Slippage from `src/backtest/execution.py`
