# ChatGPT Review Prompt — P0 + P0.1 Auto-Trading (attach zip)

Copy everything below the line. Attach **vn_auto_trading_p01_review.zip**.

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System** after **P0** and **P0.1** hardening patches. The zip contains `src/trading/`, configs, docs, tests, and thin wrapper.

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
| Production | A3_DP / **exact** `A3_PRODUCTION` classification for capital intents |
| Entries | T1 50%; T2 only on scan `ADD_T2` |
| Exits | TP1 +18%, trail 2.5×ATR14, max hold 250 — from scan columns only |
| PTS | Shadow only, off |
| S3 | Research + paper-shadow only; `data/trading/live/s3_shadow/`; no DNSE; no A3 P&L mix |
| A3+S3 dual-active | A3 production intent wins |
| Breadth | `NEW_T1_MANUAL_REVIEW_BREADTH` → MANUAL_REVIEW, not hard T1 block |
| Sector L4 | Warning only |
| Phase36 | `a3_rank_score` = operator sort only |
| AFL | Visual only |
| Performance throttle | Rejected |
| Macro | `pending_external_data`, not fabricated |

## P0 patch (verify)

1. Scan resolver (`scan_resolver.py`) — CLI > env > config > latest phase36/35/34; sample blocked unless `allow_sample_scan`
2. Paper mode true fills → `paper_trades.csv`, `paper_positions.csv`, `paper_broker_state.json`
3. Dry-run — no ledger mutation
4. SELL exit intents from `final_action` only
5. Reconciliation gating from `reconciliation_status.json` (no fake clean placeholder)
6. Daily run lock + manifest
7. Batch + pre-submit trade-intent fixes
8. Intent order preserved (`intent_sequence`)

## P0.1 patch (verify)

1. **Exact A3_PRODUCTION gate** (`order_intent.py`) — capital intents only if `strategy_classification == "A3_PRODUCTION"`; else `SKIP_NON_PRODUCTION_CLASSIFICATION`
2. **SELL risk path** (`risk/sell_rules.py`, `risk/engine.py`) — SELL not blocked by BUY max_order_value / ADV / slots / new-position caps
3. **build-intents production-safe** — sample requires `--allow-sample --test-mode`
4. **MANUAL_REVIEW queue** (`manual_review.py`) — `manual_review_queue_YYYYMMDD.csv`; unapproved rows not executable
5. **TP1 partial P&L** (`paper_ledger.py`) — `realized_pnl` delta on partial sells
6. **E2E workflow test** (`test_trading_live_workflow_e2e.py`)
7. **S3 shadow ledger** (`s3_shadow_paper_ledger.py`) — `data/trading/live/s3_shadow/` only
8. **Zero-volume data health** (`data_health.py`)

## Pipeline (`live-workflow`)

Run lock → scan resolve → data health → intents → manual review queue → proposals → batch risk → execute (paper/dry_run) → recon → dashboard → manifest

## CLI

```powershell
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <path> [--force]
python -m src.trading.cli build-intents --asof YYYY-MM-DD --scan-path <path>
python -m src.trading.cli manual-review --date YYYY-MM-DD
python -m src.trading.cli apply-manual-review --date YYYY-MM-DD
```

## Tests (if venv available)

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_reconciliation.py tests/test_trading_batch_risk.py tests/test_trading_order_intent.py tests/test_trading_paper_ledger_live.py tests/test_trading_trade_intent_lock.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py tests/test_trading_p0_hardening.py tests/test_trading_p01_hardening.py tests/test_trading_live_workflow_e2e.py -q
# Expected: 44 passed
```

## Your deliverables

### 1. FACTS
What exists after P0 + P0.1, paths, data flow.

### 2. P0 / P0.1 VERIFICATION
For each item above: PASS / PARTIAL / FAIL with file evidence.

### 3. GAPS
Remaining vs production-grade scan-driven paper (ordered).

### 4. RISKS
P0 / P1 / P2 with concrete failure scenarios.

### 5. RECOMMENDATIONS (max 12, ordered)
Incl. phase36 CSV auto-wiring, operator runbook, paper P&L validation vs scan exits.

### 6. OPTIMIZATION ROADMAP
Paper MVP → Paper hardened → Pre-live (still NO-GO real capital).

### 7. VERDICT
*Ready for limited scan-driven paper* | *Needs fixes* | *Not ready*

**Do NOT** recommend real capital, DNSE live, or `live_auto` until explicit future approval.
