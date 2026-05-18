# ChatGPT Review Prompt — Paper Accounts + Usability Patch

Copy everything below the line. Attach **vn_auto_trading_paper_accounts_review.zip**.

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System** after:

1. **P0** — scan resolver, paper execution, SELL exits, recon gating, run lock
2. **P0.1** — A3_PRODUCTION gate, SELL risk path, MANUAL_REVIEW queue, TP1 P&L, S3 shadow
3. **Paper accounts** — multi-account ledgers (5B + small DSE pilot + S3 shadow)
4. **Usability patch** — account sizing, stale manual approval, S3 date filter, traffic light, run-all

The zip contains `src/trading/`, configs, docs, tests, fixtures, and thin wrapper.

## Verdict context (do not change without explicit approval)

- **Real capital: NO-GO**
- **DSE/DNSE live: NO-GO** (`NotImplementedError` even if gates pass)
- **live_auto: NO-GO** (fail-closed)
- Target: **parallel paper observation** with account-level diagnostics before DSE API

## Read first in zip

1. `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`
2. `docs/trading/AUTO_TRADING_DESIGN_SUMMARY.md`
3. `config/paper_accounts.yaml`
4. `src/trading/live/sizing_policy.py`
5. `src/trading/live/manual_review.py`

## Architecture (non-negotiable)

- **Single engine:** `src/trading/` only
- **Signal SSOT:** daily scan CSV `final_action` — OMS adapter only, no EMA/cloud/breadth/ATR recompute
- **Execution ledger:** `data/trading/live/accounts/<ID>/` and `data/trading/live/s3_shadow/`
- **NOT** `data/paper_trade/` (research/legacy; runtime guard in `path_safety.py`)
- Manual real non-DSE account: outside system

## Frozen strategy (unchanged)

A3_DP / exact `A3_PRODUCTION` for capital | T1 50% / T2 on `ADD_T2` | exits from scan | PTS off | S3 shadow only | breadth → MANUAL_REVIEW | Sector L4 warning | Phase36 rank = sort only | AFL visual | no perf throttle

## Paper accounts

| Account | NAV | Sizing policy | Ledger |
|---------|-----|---------------|--------|
| `A3_PROD_PAPER_5B` | 5B | `scan_size_strict` | `accounts/A3_PROD_PAPER_5B/` |
| `A3_DSE_PILOT_PAPER_SMALL` | 10M | `cap_to_account_limits` (min 1M) | `accounts/A3_DSE_PILOT_PAPER_SMALL/` |
| `S3_MAX60_SHADOW_PAPER` | 0 | N/A (shadow only) | `s3_shadow/` |

## Usability patch (verify)

### 1. Account-level sizing (`sizing_policy.py`, `order_intent.py`)
- `scan_size_strict`: scan value as-is; risk may reject if too large
- `cap_to_account_limits`: `execution_value_VND = min(scan, max_order, cash, ADV×participation)`; below min → `SKIP_BELOW_MIN_TRADE_VALUE`
- Intent fields: `scan_value_VND`, `execution_value_VND`, `sizing_policy`, `sizing_adjustment_reason`, `account_id`
- Does **not** change `final_action` or strategy logic
- SELL exits ignore buy sizing caps

### 2. Manual review stale guard (`manual_review.py`, `row_hash.py`)
- Queue: `manual_review_key`, `row_hash`, `scan_hash`, `approval_stale`, `previous_row_hash`
- Same key + unchanged `row_hash` → preserve approval
- Same key + changed `row_hash` → `approval_stale=true`, `approved=false` for execution
- Executable only if: approved && !rejected && !approval_stale
- Approval never bypasses risk

### 3. S3 shadow (`s3_shadow_workflow.py`, `s3_flag.py`)
- Filter scan to requested `as_of_date` only; undated scan fails closed (unless test flag)
- `s3_no_real_order_flag` must be **explicitly true** — missing/false → blocked + `s3_shadow_blocked_YYYYMMDD.csv`
- Never creates production `OrderProposal`
- A3+S3 dual-active: A3 production intent preserved; S3 shadow blocked if flag invalid

### 4. Dashboard & compare (`account_dashboard.py`)
- Traffic light: GREEN / YELLOW / RED with reasons in `latest_status.json` and daily summary
- Expanded `compare_YYYYMMDD.md`: intents, BUY/SELL counts, sizing adjustments, interpretation note
- 5B vs small differences = **account constraints**, not strategy

### 5. CLI `paper-accounts run-all` (`paper_run_all.py`)
- Runs both A3 accounts; optional `--include-s3-shadow`
- `--continue-on-error` default false
- Generates compare report

### 6. Path safety (`path_safety.py`)
- Rejects ledger paths under `data/paper_trade/`
- Config/workflow cannot write research ledger

## P0 / P0.1 (regression check)

- Scan resolver, A3_PRODUCTION gate, account-scoped run locks, SELL risk path, TP1 P&L, DNSE NotImplementedError

## CLI reference

```powershell
python -m src.trading.cli paper-accounts init --account A3_PROD_PAPER_5B
python -m src.trading.cli paper-accounts run-all --date YYYY-MM-DD --scan-path <phase36_csv>
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <csv> --account A3_DSE_PILOT_PAPER_SMALL
python -m src.trading.cli manual-review --date YYYY-MM-DD --account A3_PROD_PAPER_5B
python -m src.trading.cli s3-shadow update --date YYYY-MM-DD --scan-path <csv>
python -m src.trading.cli paper-accounts compare --date YYYY-MM-DD
```

## Tests

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_paper_ledger_live.py tests/test_trading_reconciliation.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py tests/test_trading_batch_risk.py tests/test_trading_trade_intent_lock.py tests/test_trading_order_intent.py tests/test_trading_p0_hardening.py tests/test_trading_p01_hardening.py tests/test_trading_live_workflow_e2e.py tests/test_trading_paper_accounts.py tests/test_trading_paper_usability.py -q
# Expected: 71 passed
```

## Your deliverables

1. **FACTS** — current architecture, accounts, data flow
2. **USABILITY PATCH VERIFICATION** — PASS/PARTIAL/FAIL per numbered section above with file evidence
3. **PAPER ACCOUNTS VERIFICATION** — account isolation, run locks, ledgers
4. **P0/P0.1 REGRESSION** — any breaks from account scoping or sizing?
5. **GAPS** — vs daily operator-ready observation (ordered)
6. **RISKS** — P0/P1/P2 (wrong ledger, stale approval bypass, S3 leak, small-account false negatives)
7. **RECOMMENDATIONS** (max 12, ordered)
8. **OPERATOR RUNBOOK** — is `PAPER_TRADING_OPERATIONS_GUIDE.md` sufficient for non-developer daily use?
9. **VERDICT** — *Ready for parallel paper observation* | *Needs fixes* | *Not ready*

**Do NOT** recommend real capital, DSE/DNSE live, or `live_auto` until explicit future approval.
