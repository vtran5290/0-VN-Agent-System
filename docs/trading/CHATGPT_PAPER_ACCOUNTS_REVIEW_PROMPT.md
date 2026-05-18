# ChatGPT Review Prompt — Paper Accounts Patch (P0 + P0.1 + Paper Accounts)

Copy everything below the line. Attach **vn_auto_trading_paper_accounts_review.zip**.

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System** after:

1. **P0** hardening (scan resolver, paper execution, SELL exits, recon gating, run lock)
2. **P0.1** hardening (A3_PRODUCTION gate, SELL risk path, MANUAL_REVIEW queue, TP1 P&L, S3 shadow)
3. **Paper accounts patch** — multi-account paper trading for observation before DSE API

The zip contains `src/trading/`, configs, docs, tests, fixtures, and thin wrapper.

## Verdict context (do not change without explicit approval)

- **Real capital: NO-GO**
- **DSE/DNSE live: NO-GO** (`NotImplementedError` even if gates pass)
- **live_auto: NO-GO** (fail-closed)
- Target: **named paper accounts operational** for parallel observation (5B reference + small DSE pilot mimic + S3 shadow)

## Read first in zip

1. `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`
2. `docs/trading/AUTO_TRADING_DESIGN_SUMMARY.md`
3. `docs/trading/REAL_CAPITAL_READINESS.md`
4. `docs/trading/LIVE_CONFIG_GUIDE.md`
5. `config/paper_accounts.yaml`

## Architecture (non-negotiable)

- **Single engine:** `src/trading/` only. `pp_backtest/live/run_live_workflow.py` = thin wrapper.
- **Signal SSOT:** Daily scan CSV (`final_action`, sizing, exit prices). OMS is **adapter only** — no EMA/cloud/breadth/ATR recompute.
- **Execution ledger:** `data/trading/live/accounts/<ACCOUNT_ID>/` and `data/trading/live/s3_shadow/` — **NOT** `data/paper_trade/` (research/legacy).
- **Manual real account** (non-DSE): outside system — do not connect.
- **No LLM** in trade path.

## Frozen strategy contract (unchanged by paper patch)

| Rule | Detail |
|------|--------|
| Production | A3_DP / **exact** `A3_PRODUCTION` classification for capital intents |
| Entries | T1 50%; T2 only on scan `ADD_T2` |
| Exits | TP1 +18%, trail 2.5×ATR14, max hold 250 — from scan columns only |
| PTS | Shadow only, off |
| S3 | Paper-shadow only; `data/trading/live/s3_shadow/`; no DNSE; no A3 P&L mix; separate CLI |
| A3+S3 dual-active | A3 production intent wins; S3 via `s3-shadow update` only |
| Breadth | `NEW_T1_MANUAL_REVIEW_BREADTH` → MANUAL_REVIEW, not hard T1 block |
| Sector L4 | Warning only |
| Phase36 | `a3_rank_score` = operator sort only |
| AFL | Visual only |
| Performance throttle | Rejected |
| Macro | `pending_external_data`, not fabricated |

## Paper accounts patch (verify)

### Config & loader
1. `config/paper_accounts.yaml` — three enabled accounts + optional `BROKER_DRYRUN_MIRROR` placeholder
2. `src/trading/live/paper_accounts.py` — `PaperAccountConfig`, load/list/init, `build_live_config_for_account()`
3. Default account: `A3_PROD_PAPER_5B` when `--account` omitted

### Named accounts

| Account ID | Type | Starting NAV | Key limits | Ledger |
|------------|------|--------------|------------|--------|
| `A3_PROD_PAPER_5B` | a3_production | 5B VND | 20 slots, max_order 500M | `data/trading/live/accounts/A3_PROD_PAPER_5B/` |
| `A3_DSE_PILOT_PAPER_SMALL` | a3_production_small | 10M VND | 3 slots, 1 new pos/day, 2 orders/day, max_order 3M | `data/trading/live/accounts/A3_DSE_PILOT_PAPER_SMALL/` |
| `S3_MAX60_SHADOW_PAPER` | s3_shadow | 0 | no real orders | `data/trading/live/s3_shadow/` |

### Account-scoped paths (`config.py` + workflow)
4. `LiveTradingConfig.account_root` scopes: trades, positions, broker state, orders, proposals, intents, manual review, run locks/manifests, dashboard
5. Run lock key: `{date}_{mode}_{account_id}` — different accounts same day do **not** block each other
6. Same account duplicate run blocked unless `--force`

### Preflight fixes (must still work)
7. `paper_ledger.close_trade()` — no undefined `pnl`; NaN-safe quantity in close
8. SELL_EXIT / SELL_TP1 realized P&L on paper ledger
9. Deterministic `order_intent_id` (`make_order_intent_id` in `order_intent.py`) for stable manual-review keys

### CLI
```powershell
python -m src.trading.cli paper-accounts list|init|summary|compare
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <csv> --account A3_PROD_PAPER_5B
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <csv> --account A3_DSE_PILOT_PAPER_SMALL
python -m src.trading.cli resolve-scan --date YYYY-MM-DD
python -m src.trading.cli manual-review --date YYYY-MM-DD --account <ID>
python -m src.trading.cli apply-manual-review --date YYYY-MM-DD --account <ID>
python -m src.trading.cli s3-shadow update --date YYYY-MM-DD --scan-path <csv>
python -m src.trading.cli s3-shadow summary
```

### S3 separation
10. `S3_MAX60_SHADOW_PAPER` rejected on `live-workflow` (must use `s3-shadow`)
11. S3 shadow never creates production `OrderProposal`; requires `s3_no_real_order_flag=true`
12. S3 removed from A3 workflow path (no A3 cash/P&L contamination)

### Risk (account overrides only — no signal change)
13. Account config merges: `portfolio_size_vnd`, `max_slots`, `max_daily_new_positions`, `max_daily_orders`, `max_order_value_vnd`, `adv_participation`
14. Small account should reject/size-down more than 5B on same scan
15. SELL exits not blocked by BUY sizing caps (`sell_rules.py` unchanged in intent)

### Dashboard
16. Per-account `dashboard/daily_summary_YYYYMMDD.md`, `latest_status.json`, positions/trades exports
17. `data/trading/live/accounts/compare_YYYYMMDD.md` for 5B vs small pilot

## P0 + P0.1 (still verify)

- Scan resolver, sample block, phase36 priority
- Exact A3_PRODUCTION gate
- MANUAL_REVIEW queue account-scoped
- Reconciliation gating from persisted status
- DNSE `place_order` → NotImplementedError

## Pipeline (`live-workflow` per account)

Run lock (account-scoped) → scan resolve → data health → intents → manual review queue → proposals → batch risk → execute (paper) → recon → account dashboard → manifest

## Tests (if venv available)

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_paper_ledger_live.py tests/test_trading_reconciliation.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py tests/test_trading_batch_risk.py tests/test_trading_trade_intent_lock.py tests/test_trading_order_intent.py tests/test_trading_p0_hardening.py tests/test_trading_p01_hardening.py tests/test_trading_live_workflow_e2e.py tests/test_trading_paper_accounts.py -q
# Expected: 57 passed
```

## Your deliverables

### 1. FACTS
What exists after paper-accounts patch: paths, accounts, data flow, CLI surface.

### 2. PAPER ACCOUNTS VERIFICATION
For each numbered item in "Paper accounts patch (verify)": PASS / PARTIAL / FAIL with file evidence.

### 3. P0 / P0.1 REGRESSION
Any regressions from account scoping? Cross-account leakage risks?

### 4. GAPS
Remaining vs daily operator-ready paper tracking (ordered).

### 5. RISKS
P0 / P1 / P2 — incl. wrong account ledger, manual review cross-approval, S3→production leak.

### 6. RECOMMENDATIONS (max 12, ordered)
Incl. phase36 auto-wiring, slippage model, compare-report metrics, DSE sandbox readiness checklist.

### 7. OPERATOR RUNBOOK GAPS
What's missing in `PAPER_TRADING_OPERATIONS_GUIDE.md` for a non-developer?

### 8. VERDICT
*Ready for parallel paper account observation* | *Needs fixes* | *Not ready*

**Do NOT** recommend real capital, DSE/DNSE live, or `live_auto` until explicit future approval.
