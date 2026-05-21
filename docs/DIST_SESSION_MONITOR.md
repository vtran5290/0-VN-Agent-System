# VNINDEX distribution — per-session monitor

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

## Legacy (optional)

`scripts/monitor_vnindex_distribution_session.py` still writes `data/alerts/dist_session_latest.json` for a lighter O'Neil dist-count snapshot. Prefer **distribution-risk** CLI for probabilities and dual full/ex-VIN lens.

## Notes

- **Source:** FireAnt via index views loader (see `src/market/distribution_risk_lens/index_views.py`).
- **ex-VIN** is proxy-derived; read `comparison.vin_distortion_flag` and `interpretation`.
- Distribution lens is **context only** — does not override trading `final_action`.
