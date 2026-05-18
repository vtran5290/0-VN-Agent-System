# ChatGPT Review Prompt — Auto-Trading Infrastructure

Copy everything below the line into ChatGPT. Attach **vn_auto_trading_review.zip**.

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System**. The attached zip contains the canonical engine (`src/trading/`), configs, docs, tests, and a thin workflow wrapper.

## Context

This is a **paper-first production skeleton** with **real-capital readiness hardening**. Verdict for live capital today: **NO-GO** (`docs/trading/REAL_CAPITAL_READINESS.md`). Your job is to **review and propose optimizations** — not to rewrite strategy logic or enable live DNSE.

## Design summary (read first in zip)

Open `docs/trading/AUTO_TRADING_DESIGN_SUMMARY.md` and `docs/trading/README.md`.

### Architecture (non-negotiable)

- **Single engine:** `src/trading/` only. `pp_backtest/live/run_live_workflow.py` is a thin wrapper.
- **Signal SSOT:** Daily scan CSV (`final_action`, sizing columns). OMS is **consumer/adapter only** — no EMA/cloud/breadth recompute in OMS.
- **Research ledger** `data/paper_trade/` is **out of scope** — do not merge with execution ledger `data/trading/live/`.
- **No LLM** in the trade decision path.

### Frozen strategy contract (do not change without explicit approval)

| Rule | Detail |
|------|--------|
| Production | A3_DP / A3_PRODUCTION only |
| Entries | T1 50%; T2 only on scan `ADD_T2` |
| Exits | TP1 +18%, trail 2.5×ATR14, max hold 250 — from scan, not OMS math |
| PTS | Shadow only (`allow_pts_shadow: false`) |
| S3 | Research/watchlist; shadow rows paper-only |
| Breadth | `NEW_T1_MANUAL_REVIEW_BREADTH` → MANUAL_REVIEW, not hard T1 block |
| Sector L4 | Warning metadata only |
| VIN | ex-VIN3 in config; cap-weight VNINDEX may distort 2025–2026 — prefer breadth for regime |

Phase36: `a3_rank_score` sorts operator review only — must not affect OMS routing.

### Pipeline (`live-workflow`)

1. Data health (panel parquet, scan file, ADV units, stale dates)
2. `order_intent.py` — map `final_action` → BUY_T1 / MANUAL_REVIEW / WATCH / SKIP
3. Intents → `OrderProposal`
4. Batch risk (`batch_context.py`) — simulated cash/slots across batch
5. Kill switch
6. Execute (mode: paper / dry_run / live_manual / live_auto)
7. Reconciliation (baseline + OMS fills vs broker)
8. Dashboard

### Risk model

- Base: max order value, ADV limits, position % NAV, exposure, daily new positions, no margin, duplicate orders, stale data
- Live: data health, kill switch, recon clean, regime bull, max slots/orders, PTS/S3 block, breadth manual review
- Decisions: PASS | MANUAL_REVIEW | BLOCK

### OMS hardening

- **Trade-intent lock:** `strategy|date|symbol|side` (one active intent per day)
- **Idempotency key:** includes price + qty
- **Pre-submit re-risk** before `place_order`
- **DNSE:** triple env gate + `NotImplementedError` even if gates pass

### Known gaps (prioritize your recommendations here)

1. `scan_csv_path` still points to **sample CSV** — not wired to live phase36 scan output
2. Legacy `propose` CLI uses **PlaceholderStrategy** — confuses production path
3. **Exit orders** (TP1_PARTIAL, TRAIL_EXIT, MAX_HOLD_EXIT) are WATCH-only — no SELL intent path
4. No slippage model, partial fills, or VN holiday calendar in OMS
5. MANUAL_REVIEW has no explicit approve/reject operator workflow
6. No idempotent daily-run lock (double workflow risk)
7. DNSE not integrated (placeholder only)

## What to run (if you have repo + venv)

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_reconciliation.py tests/test_trading_batch_risk.py tests/test_trading_order_intent.py tests/test_trading_paper_ledger_live.py tests/test_trading_trade_intent_lock.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py -q

.\.venv\Scripts\python.exe -m src.trading.cli live-workflow --mode paper --date 2026-05-16
```

## Your deliverables

### 1. FACTS
What exists, key paths, data flow, safety defaults.

### 2. ARCHITECTURE REVIEW
- Coupling / SSOT violations
- Race conditions (double run, batch vs execute)
- Whether batch risk + intent lock + pre-submit re-risk are sufficient at ~5B VND paper scale

### 3. GAPS
Ordered vs production-grade **scan-driven paper trading**.

### 4. RISKS
P0 / P1 / P2 with concrete failure scenarios.

### 5. RECOMMENDATIONS (max 15, ordered)
For each: what to change, which file/module, estimated effort (S/M/L), and whether it touches frozen strategy (must flag).

Include specific designs for:
- Wiring scan CSV from daily scan output (phase36)
- SELL exit intent path from scan columns
- Unifying CLI entry points
- MANUAL_REVIEW operator workflow
- Daily orchestration idempotency

### 6. OPTIMIZATION ROADMAP
3 phases: **Paper MVP** → **Paper hardened** → **Pre-live** (still NO-GO real capital until gates in REAL_CAPITAL_READINESS.md pass).

### 7. VERDICT
One of: *Ready for scan-driven paper with wiring fixes* | *Needs P0 fixes first* | *Not ready*

**Do NOT** recommend real capital, DNSE live orders, or `live_auto` until a separate explicit approval phase.
