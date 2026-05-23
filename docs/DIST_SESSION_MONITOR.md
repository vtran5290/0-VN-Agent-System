# VNINDEX distribution — per-session monitor

> **LEGACY:** use `python -m src.trading.cli distribution-risk` for canonical distribution risk. **`dist_session_*` outputs are not SSOT.** SSOT: `data/research/market_risk/distribution_risk_latest.json`.

**Distribution Risk Lens is market context only and does not change final_action.**  
**Distribution Risk SSOT is data/research/market_risk/distribution_risk_latest.json.**  
**Legacy dist_session outputs are not SSOT.**

**Canonical command (use this going forward):**

```powershell
cd "c:\Users\LOLII\Documents\V\0. VN Agent System"
.\.venv\Scripts\python.exe -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest
```

Or double-click / schedule:

```text
monitor_distribution_risk.cmd
```

## What it does

Runs **`src.market.distribution_risk_lens`** (v1.1): full + ex-VIN proxy + VIN basket views, historical probability buckets, event study, warning states.

## Primary outputs

| File | Purpose |
|------|---------|
| `data/research/market_risk/distribution_risk_latest.json` | **SSOT** for chat / cloud daily report card |
| `data/research/market_risk/distribution_risk_latest.html` | Standalone HTML card (written with every lens run) |
| `data/research/market_risk/distribution_risk_latest.md` | Standalone markdown mirror |
| `data/research/market_risk/distribution_days_probability_table.csv` | P(correction/downtrend) by bucket & horizon |
| `data/research/market_risk/distribution_days_features.csv` | Daily features per index view |
| `data/research/market_risk/distribution_days_forward_returns.csv` | Forward outcomes |
| `data/research/market_risk/distribution_days_event_study.csv` | Event-study aggregates |
| `data/research/market_risk/distribution_days_warning_backtest.csv` | Warning-state history |

## In this chat

After each HOSE close, run the command (or say **`check dist`**). The agent reads:

- `data/research/market_risk/distribution_risk_latest.json` (and optional `distribution_risk_latest.html` in browser)
- Key fields: `vnindex_raw`, `ex_vin_proxy`, `vin_group`, `comparison`, `primary_view`

**HTML:** Every `distribution-risk` run also writes `distribution_risk_latest.html` + `.md` (same styling as Cloud Daily Report Section G).

## Legacy (optional — not SSOT)

`scripts/monitor_vnindex_distribution_session.py` still writes `data/alerts/dist_session_latest.json` for a lighter O'Neil dist-count snapshot. **Legacy dist_session outputs are not SSOT.** Prefer **distribution-risk** CLI for probabilities and dual full/ex-VIN lens.

## Notes

- **Source:** FireAnt via index views loader (see `src/market/distribution_risk_lens/index_views.py`).
- **ex-VIN** is proxy-derived; read `comparison.vin_distortion_flag` and `interpretation`.
- Distribution lens is **context only** — does not override trading `final_action`.

## Operator integration (canonical)

**SSOT runbook:** `docs/DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md`

**Daily EOD driver:** `.\scripts\trading\eod_market_context_refresh.ps1` (alias: `daily_eod_operator.ps1`)

**Weekly:** lens not recomputed by default — `weekly_pareto_operator.ps1 -RefreshMarketContext` if stale.

## Workflow integration review (ChatGPT / Codex)

- Prompt: `docs/trading/CHATGPT_DISTRIBUTION_RISK_WORKFLOW_INTEGRATION_PROMPT.md`
- Zip: `python -m scripts.reporting.build_distribution_risk_workflow_integration_chatgpt_zip`
