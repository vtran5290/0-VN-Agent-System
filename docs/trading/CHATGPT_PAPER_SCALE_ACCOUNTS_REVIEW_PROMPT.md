# ChatGPT Review Prompt — Paper Scale Accounts (10B / 20B)

Copy everything below the line. Attach **`vn_auto_trading_paper_scale_review.zip`** (repo root).

---

You are a senior quant systems architect reviewing the **Vietnam auto-trading infrastructure** in repo **VN Agent System** after the **paper scale-accounts patch**:

- Adds **`A3_SCALE_PAPER_10B`** (10B VND) and **`A3_SCALE_PAPER_20B`** (20B VND) for NAV / liquidity capacity observation
- Extends **`paper-accounts run-all`** to run **4 A3 paper accounts** (+ optional S3 shadow)
- Adds **`cap_to_liquidity`** sizing policy (20B stress account)
- Expands **compare report** and **daily summaries** with cash drag, liquidity cap hits, scale interpretation

**This is infrastructure only.** Do not treat as strategy change, production promotion, or real-capital readiness.

## Verdict context (do not change without explicit approval)

- **Real capital: NO-GO**
- **DSE/DNSE live: NO-GO** (`NotImplementedError` / triple gate)
- **live_auto: NO-GO** (fail-closed)
- **S3:** paper-shadow only; never production / DSE / DNSE
- **Target:** 5-account daily paper observation (4 A3 + optional S3 shadow)

## Read first in zip

1. `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`
2. `config/paper_accounts.yaml`
3. `src/trading/live/paper_accounts.py` — `A3_PAPER_RUN_ORDER`, account types
4. `src/trading/live/sizing_policy.py` — `cap_to_liquidity`
5. `src/trading/live/paper_run_all.py`
6. `src/trading/live/account_dashboard.py` — compare + daily summary
7. `tests/test_trading_paper_scale_accounts.py`

## Architecture (non-negotiable)

- **Single engine:** `src/trading/` only (`pp_backtest/live/run_live_workflow.py` = thin wrapper)
- **Signal SSOT:** daily scan CSV `final_action` — OMS consumes adapter output only; **no** EMA/cloud/breadth/ATR/trail recompute in OMS
- **Execution ledger:** `data/trading/live/accounts/<ACCOUNT_ID>/` and `data/trading/live/s3_shadow/`
- **NOT** `data/paper_trade/` (research/legacy; `path_safety.py` blocks writes)
- Manual real non-DSE account: outside system

## Frozen strategy (unchanged)

| Rule | Value |
|------|--------|
| Production strategy | **A3_DP** only |
| Capital gate | `strategy_classification == A3_PRODUCTION` (exact) |
| T1 / T2 | 50% / 50% on scan `ADD_T2` |
| Exits | From scan columns only (TP1 +18%, trail 2.5×ATR14, max hold 250) |
| Breadth | `MANUAL_REVIEW`, not hard T1 block |
| Sector L4 | Warning only |
| Phase36 rank | Operator sort only |
| PTS | Not promoted |
| S3 EMA21/55 max_hold=250 | Rejected / research |
| S3 max_hold=60 | Shadow only |
| Performance throttle | Rejected |
| Macro missing | `pending_external_data` |
| AFL | Visual only |

## Paper accounts (daily observation set)

| Account | NAV | Role | Sizing | Max order |
|---------|-----|------|--------|-----------|
| `A3_DSE_PILOT_PAPER_SMALL` | 30M | Future DSE tiny pilot mimic | `cap_to_account_limits` | 5M |
| `A3_PROD_PAPER_5B` | 5B | A3 production reference | `scan_size_strict` | 500M |
| `A3_SCALE_PAPER_10B` | 10B | Medium-scale capacity check | `scan_size_strict` | 800M |
| `A3_SCALE_PAPER_20B` | 20B | Large NAV / liquidity stress | `cap_to_liquidity` | 1.2B |
| `S3_MAX60_SHADOW_PAPER` | 0 | Radar / shadow only | N/A | — |

**Hard interpretation rule:** Differences across 30M / 5B / 10B / 20B = **account sizing & liquidity capacity**, **not** strategy logic. 10B/20B are **not** new strategies.

## Scale patch — verify

### 1. Config (`config/paper_accounts.yaml`)
- Both scale accounts `enabled: true`, `strategy: A3_DP`, `allow_s3: false`, `allow_pts: false`
- Ledger roots under `data/trading/live/accounts/` (not `data/paper_trade/`)
- 10B: `type: a3_production_scale`, `scan_size_strict`
- 20B: `type: a3_production_scale_stress`, `cap_to_liquidity`, higher `min_trade_value_VND`

### 2. Account types (`paper_accounts.py`)
- `a3_production_scale` / `a3_production_scale_stress` in `A3_ACCOUNT_TYPES` → `is_a3_production` true
- `A3_PAPER_RUN_ORDER`: SMALL → 5B → 10B → 20B
- S3 shadow still rejected by `build_live_config_for_account`

### 3. Sizing (`sizing_policy.py`)
- `cap_to_liquidity`: `execution_value_VND = min(scan, max_order, cash, ADV50×participation)`
- Does **not** change `final_action`, eligibility, or use `a3_rank_score` / S3 / PTS
- `liquidity_cap_hit` / `capped_to_liquidity` reasons tracked for dashboard
- 10B `scan_size_strict` unchanged from 5B behavior

### 4. Run-all (`paper_run_all.py`, `cli.py`)
- Default runs 4 A3 accounts; S3 **only** with `--include-s3-shadow`
- S3 uses `s3-shadow update` path, not A3 `live-workflow`
- Compare report written for all 4 A3 accounts
- Per-account run locks (different accounts same date OK)

### 5. Dashboard / compare (`account_dashboard.py`)
- `compare_YYYYMMDD.md`: return %, cash drag %, gross exposure %, liquidity cap hits, scale sections A–D
- Daily summary: observation role, utilization, warnings for 20B cash drag / 30M size skips
- Traffic light unchanged in semantics (YELLOW for sizing constraints)

### 6. Path safety
- No paper account ledger under `data/paper_trade/`
- Init / run-all do not write research ledger

### 7. Regression
- A3_PRODUCTION gate, SELL path, manual review stale guard, S3 flag strict, DNSE NotImplementedError
- Prior 2-account behavior preserved for 30M + 5B

## CLI reference

```powershell
python -m src.trading.cli paper-accounts list
python -m src.trading.cli paper-accounts init --account A3_SCALE_PAPER_10B
python -m src.trading.cli paper-accounts init --account A3_SCALE_PAPER_20B
python -m src.trading.cli paper-accounts run-all --date YYYY-MM-DD --scan-path <phase36_csv> --include-s3-shadow
python -m src.trading.cli paper-accounts compare --date YYYY-MM-DD
python -m src.trading.cli paper-accounts summary --account A3_SCALE_PAPER_20B
```

## Tests

```powershell
cd <repo_root>
.\.venv\Scripts\python.exe -m pytest tests/test_trading_risk.py tests/test_trading_oms.py tests/test_trading_paper_broker.py tests/test_trading_reconciliation.py tests/test_trading_paper_ledger_live.py tests/test_trading_stale_data.py tests/test_trading_baseline_recon.py tests/test_trading_kill_switch.py tests/test_trading_daily_report_filter.py tests/test_trading_batch_risk.py tests/test_trading_trade_intent_lock.py tests/test_trading_order_intent.py tests/test_trading_p0_hardening.py tests/test_trading_p01_hardening.py tests/test_trading_live_workflow_e2e.py tests/test_trading_paper_accounts.py tests/test_trading_paper_usability.py tests/test_trading_paper_daily_ready.py tests/test_trading_paper_scale_accounts.py -q
# Expected: 88 passed
```

## Your deliverables

1. **FACTS** — architecture, 5-account set, data flow after patch
2. **SCALE PATCH VERIFICATION** — PASS/PARTIAL/FAIL per section 1–7 with file evidence
3. **SIZING VERIFICATION** — Is `cap_to_liquidity` correct for 20B stress? Any double-cap or bypass?
4. **COMPARE / DASHBOARD** — Are scale metrics and interpretation sections operator-useful? Any misleading strategy conclusions?
5. **REGRESSION** — 30M + 5B + P0/P0.1 unchanged?
6. **GAPS** — vs daily 4-account + optional S3 observation (ordered)
7. **RISKS** — P0/P1/P2 (ledger mix, S3 leak, compare misread as alpha, empty ledger crashes)
8. **RECOMMENDATIONS** (max 12, ordered)
9. **OPERATOR RUNBOOK** — Is `PAPER_TRADING_OPERATIONS_GUIDE.md` sufficient for 10B/20B init + run-all?
10. **VERDICT** — *Ready for 5-account daily paper observation* | *Needs fixes* | *Not ready*

**Do not recommend:** enabling real capital, DSE/DNSE live, `live_auto`, promoting S3/PTS, or changing A3 strategy logic based on 5B vs 20B P&L differences.

---

*End of prompt*
