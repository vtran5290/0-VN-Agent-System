# ChatGPT Review Prompt — P0 Hardening + Auto-Trading (attach zip)

Copy everything below the line. Attach **vn_auto_trading_p0_review.zip**.

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System** after the **P0 hardening patch**. The zip contains `src/trading/`, configs, docs, tests, and thin wrapper.

## Verdict context (do not change without explicit approval)

- **Real capital: NO-GO**
- **DNSE live: NO-GO** (`NotImplementedError` even if gates pass)
- **live_auto: NO-GO** (fail-closed)
- Target: **limited scan-driven paper testing** only

## Read first in zip

1. `docs/trading/AUTO_TRADING_DESIGN_SUMMARY.md`
2. `docs/trading/README.md`
3. `docs/trading/REAL_CAPITAL_READINESS.md`
4. `docs/trading/LIVE_CONFIG_GUIDE.md`

## Architecture (non-negotiable)

- **Single engine:** `src/trading/` only. `pp_backtest/live/run_live_workflow.py` = thin wrapper.
- **Signal SSOT:** Daily scan CSV (`final_action`, sizing, exit prices). OMS is **adapter only** — no EMA/cloud/breadth/ATR recompute.
- **Execution ledger:** `data/trading/live/` — NOT `data/paper_trade/` (research/legacy).
- **No LLM** in trade path.

## Frozen strategy contract

| Rule | Detail |
|------|--------|
| Production | A3_DP / A3_PRODUCTION only |
| Entries | T1 50%; T2 only on scan `ADD_T2` |
| Exits | TP1 +18%, trail 2.5×ATR14, max hold 250 — from scan columns only |
| PTS | Shadow only, off |
| S3 | Research + paper-shadow only; separate ledger; no DNSE; no A3 P&L mix |
| A3+S3 dual-active | A3 production intent wins (not S3 shadow swallow) |
| Breadth | `NEW_T1_MANUAL_REVIEW_BREADTH` → MANUAL_REVIEW, not hard T1 block |
| Sector L4 | Warning only |
| Phase36 | `a3_rank_score` = operator sort only; cannot create/block/size orders |
| AFL | Visual only |
| Performance throttle | Rejected |
| Macro | `pending_external_data`, not fabricated |

## P0 patch — what was implemented (verify in code)

### 1. Scan resolver (`src/trading/live/scan_resolver.py`)

Priority: CLI `--scan-path` > `PHASE36_DAILY_SCAN_PATH` > config > latest `phase36*.csv` > `phase35` > `phase34`.

- Sample CSV **blocked** unless `allow_sample_scan: true`
- Stale asof vs scan dates → `BLOCK_ORDER_GENERATION`
- Metadata: `resolved_scan_path`, `scan_hash`, `is_sample`, `is_stale`

### 2. Paper mode true execution

- `mode=paper`: `PaperBroker` fills, updates `paper_trades.csv` / `paper_positions.csv` / `paper_broker_state.json`
- `mode=dry_run`: audit only, **no** ledger mutation
- Kill switch / dirty recon / pre-submit re-risk block fills

### 3. SELL exit intents (`order_intent.py`)

| final_action | OMS action |
|--------------|------------|
| TP1_PARTIAL | SELL_TP1 (50% of position or scan qty) |
| TRAIL_EXIT | SELL_EXIT |
| MAX_HOLD_EXIT | SELL_EXIT |

- No position → `SKIP_NO_POSITION` / `RECON_REQUIRED`, not fabricated SELL
- Prices from scan: `tp1_price`, `trail_price`, else `close_kVND`

### 4. Reconciliation gating

- Loads `data/trading/live/reconciliation_status.json` before risk/execute
- **No** fake `recon_pre = {"BLOCK_NEW_ORDERS": False}`
- Dirty recon blocks new orders when `require_reconciliation_clean=true`

### 5. Daily run lock (`run_lock.py`)

- `run_locks/{date}_{mode}.lock`
- `run_manifests/run_{date}_{mode}.json`
- Duplicate run aborts; `--force` only when safe (no open SUBMITTED/PARTIAL)

### 6. Batch trade-intent lock

- Key: `strategy|date|symbol|side`
- Duplicate in same batch → BLOCK (`duplicate_trade_intent_batch`)
- Preserves `intent_sequence` order (no alphabetical sort)

### 7. Pre-submit fix

- `check_trade_intent_blocked(..., exclude_idempotency_key=current)` — no self-block
- Audit: `pre_submit_duplicate_trade_intent_rejected`

### 8. CLI

```powershell
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <path> [--force]
python -m src.trading.cli build-intents --asof YYYY-MM-DD --scan-path <path>
```

- `propose` warns: PlaceholderStrategy test path only

## Pipeline (`live-workflow`)

1. Run lock acquire
2. Scan resolve
3. Data health
4. Order intents from scan
5. Proposals (preserve intent order)
6. Batch risk (with recon + kill switch context)
7. Execute (paper / dry_run)
8. Reconciliation + dashboard + manifest complete

## Tests (run if you have venv)

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_reconciliation.py tests/test_trading_batch_risk.py tests/test_trading_order_intent.py tests/test_trading_paper_ledger_live.py tests/test_trading_trade_intent_lock.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py tests/test_trading_p0_hardening.py -q
# Expected: 34 passed
```

## Your deliverables

### 1. FACTS
What exists, paths, data flow, safety defaults after P0.

### 2. P0 VERIFICATION
For each P0 item above: PASS / PARTIAL / FAIL with file:line evidence.

### 3. GAPS
Remaining vs production-grade scan-driven paper (ordered).

### 4. RISKS
P0 / P1 / P2 with concrete failure scenarios.

### 5. RECOMMENDATIONS (max 12, ordered)
Include designs for:
- Automated phase36 CSV wiring post daily scan
- MANUAL_REVIEW approve/reject workflow
- Paper P&L reconciliation vs scan exit columns
- Idempotent operator runbook

### 6. OPTIMIZATION ROADMAP
Paper MVP → Paper hardened → Pre-live (still NO-GO real capital).

### 7. VERDICT
*Ready for limited scan-driven paper* | *Needs P0 fixes* | *Not ready*

**Do NOT** recommend real capital, DNSE live, or `live_auto` until explicit future approval.
