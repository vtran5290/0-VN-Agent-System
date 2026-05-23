# Distribution Risk — Operator Integration (Stage 0)

**Stage:** 0 — Manual decision-support. **Real capital: NO-GO.**

Distribution Risk Lens provides **market context only**. It does **not** change `final_action`, order-intent, OMS, breadth gates, T1/T2 sizing, exit policy, or broker execution.

**Distribution Risk SSOT:** `data/research/market_risk/distribution_risk_latest.json`  
**Production action SSOT:** `phase36_daily_scan_latest.csv` → `final_action` only.

---

## 1. Purpose

Use the lens to answer: *Is broad market participation deteriorating? Is VIN distorting cap-weight VNINDEX?*  
Use the scan to answer: *What does the production system say to do per symbol?*

---

## 2. SSOT map

| Question | SSOT file | Refresh command |
|----------|-----------|-----------------|
| Distribution counts | `data/research/market_risk/distribution_risk_latest.json` | `python -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest` |
| Distribution probabilities | same JSON + `distribution_days_probability_table.csv` | same |
| Production trade action | `phase36_daily_scan_latest.csv` → `final_action` | `python pp_backtest/portfolio_optimization_final_steps.py --step scan` |
| Positions | `data/raw/current_positions_derived.json` | `python -m src.review.cli derive-current` |
| NAV | `data/trading/live/portfolio_state.json` | user update |
| Daily board | `data/research/reports/cloud_daily_report_latest.html` | `python -m src.trading.cli cloud-daily-report --mode eod` |
| Weekly command center | `reports/latest/index.html` | `.\scripts\trading\weekly_pareto_operator.ps1` |

**Legacy `data/alerts/dist_session_*` is not SSOT.**

---

## 3. Canonical EOD sequence

**Driver:** `.\scripts\trading\eod_market_context_refresh.ps1 -Date YYYY-MM-DD`

```powershell
# Optional — if positions changed
python -m src.review.cli derive-current

# Mandatory if using current EOD data
python scripts/append_fireant_ohlcv_to_data_stocks.py --data-stocks --minervini-raw --end YYYY-MM-DD

# Mandatory before trusting ex-VIN lens
python scripts/research/vnindex_low_dist_ex_vin.py --end YYYY-MM-DD

# Market context only — does NOT change final_action
python -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest

# Production signal SSOT
python pp_backtest/portfolio_optimization_final_steps.py --step scan

# Daily text packet
python scripts/reporting/daily_scan_report.py

# Full daily board (Section G = lens card)
python -m src.trading.cli cloud-daily-report --mode eod
```

| Step | Mandatory? | When to skip |
|------|------------|--------------|
| derive-current | If book changed | Unchanged holdings |
| FireAnt OHLCV append | If panel current for as-of | Same-day rerun only |
| ex-VIN rebuild | After OHLCV refresh | No index update |
| distribution-risk | **Yes** on trading EOD days | Never before trusting lens |
| phase36 scan | **Yes** before trades / order-intent | — |
| daily_scan_report | Recommended | — |
| cloud-daily-report eod | Recommended | — |

---

## 4. Intraday preview

```powershell
python -m src.trading.cli cloud-daily-report --mode pre-lunch
python -m src.trading.cli cloud-daily-report --mode pre-atc
```

- Intraday output is **preview only**.
- Distribution Risk JSON is usually **stale** during the session (last EOD run).
- If `report_status=NEEDS_REVIEW` or `view_freshness.is_stale_for_as_of=true` → treat probabilities as caveated.
- **No intraday output routes to OMS.**
- **Do not** override `final_action` from lens warnings.

---

## 5. Weekly placement

Distribution Risk is **not** an eighth Pareto action. It sits inside existing **market regime / risk context** review.

| Path | Lens behavior |
|------|----------------|
| **Daily EOD** | Refresh via `eod_market_context_refresh.ps1` |
| **Weekly** | Read latest JSON/HTML; `weekly_pareto_operator.ps1` prints stale reminder if lens >7d old |
| **Weekly optional** | `-RefreshMarketContext` to recompute lens on Sunday |

```powershell
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "..."
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -RefreshMarketContext  # if stale
```

---

## 6. HTML routing

| File | Use |
|------|-----|
| `cloud_daily_report_latest.html` | Daily full board (A–I) |
| `distribution_risk_latest.html` | Quick **check dist** card |
| `reports/latest/index.html` | Weekly command center |

---

## 7. Legacy monitor policy

| Path | Status |
|------|--------|
| `scripts/monitor_vnindex_distribution_session.py` | **LEGACY** — optional snapshot |
| `data/alerts/dist_session_*` | **Not SSOT** |
| `distribution-risk` CLI | **Canonical** |

**LEGACY:** use `python -m src.trading.cli distribution-risk` for canonical distribution risk. `dist_session_*` is not SSOT.

---

## 8. Staleness protocol

If `report_status=NEEDS_REVIEW` **or** any `view_freshness.is_stale_for_as_of=true`:

1. Re-run FireAnt OHLCV append (`--end` = target date)  
2. Re-run ex-VIN rebuild  
3. Re-run `distribution-risk`  
4. Re-run `daily_scan_report.py` and/or `cloud-daily-report --mode eod` if reports already generated  

All surfaces show: **NEEDS_REVIEW: stale index view; probabilities may be caveated.**

---

## 9. Data discipline

| Field | Value |
|-------|--------|
| **source** | FireAnt REST + repo CSV merge for VNINDEX |
| **method** | REST append + derived ex-VIN proxy + O'Neil distribution-day rule |
| **symbols** | VNINDEX; ex-VIN proxy; VIN basket `VIC`, `VHM`, `VRE` |
| **ex-VIN** | Proxy-derived — **not** a native exchange index |
| **VPL** | Excluded until ≥252 daily bars |
| **limitations** | Cap-weight VNINDEX may be Vingroup-skewed 2025–2026; probabilities are historical conditional estimates, not forecasts or certainties |

---

## Related docs

- `docs/DIST_SESSION_MONITOR.md` — `check dist` in Cursor  
- `docs/OPERATING_BACKBONE_PARETO.md` — seven weekly actions  
- `docs/trading/CLOUD_DAILY_REPORT_GUIDE.md`  
- `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md`

**Review zip:** `python -m scripts.reporting.build_distribution_risk_workflow_integration_chatgpt_zip`
