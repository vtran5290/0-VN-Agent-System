# Weekly full fetch — prompt & runbook

Use this when you need **all latest inputs** that feed the weekly report before generating outputs.

## One command (recommended)

```bash
python scripts/run_weekly_full_fetch.py
```

Optional:

```bash
python scripts/run_weekly_full_fetch.py --asof 2026-03-23
python scripts/run_weekly_full_fetch.py --skip-fetch          # only re-render from current JSON
python scripts/run_weekly_full_fetch.py --no-validate        # faster ingest if schema noisy
```

## What gets fetched (FACTS — by layer)

| Layer | Source | Method | Written to |
|--------|--------|--------|------------|
| **Open portfolio book** | FQuery Excel (`Open` sheet) | `python -m src.review.cli derive-current` | `data/raw/current_positions_derived.json` |
| **VNINDEX downtrend P(v2)** | FireAnt VNINDEX OHLCV | `python scripts/run_vnindex_downtrend_v2.py` | `data/decision/vnindex_downtrend_probability_v2.json` → weekly MD + HTML |
| UST 2Y/10Y, CPI YoY, NFP | FRED | REST (`FRED_API_KEY`) | `manual_inputs.json` → `global` |
| DXY | Yahoo ICE then FRED fallback | HTTP | `manual_inputs.json` → `global` |
| OMO net, interbank ON, credit growth, USD/VND | SBV | HTML scrape (`scripts/fetch_vietnam_liquidity.py`) | `manual_inputs.json` → `vietnam` |
| VNINDEX, VN30, HNX, UPCOM, distribution, breadth | FireAnt | REST (`src.data.fireant_client`, token) | Applied at weekly run → `weekly_report` / debug JSON |
| Regime + allocation probs | Rule engine | `src.report.weekly` | `regime_state.json`, `allocation_plan.json` |
| Sell/trim signals | FireAnt TA rules | `src.report.weekly` | `data/alerts/sell_signals.json` |

Skip steps when re-rendering only:

```bash
python scripts/run_weekly_full_fetch.py --skip-fetch --skip-positions --skip-downtrend
```

**Market (`manual_inputs.market`)** is kept **`{}`** in this pipeline so **FireAnt** remains the single writer for index levels and distribution math in `src.report.weekly` (see `build_auto_inputs` / `get_macro_snapshot`).

## Environment

- **`FRED_API_KEY`**: strongly recommended. Without it, UST/CPI/NFP are not refreshed from FRED; existing values in `manual_inputs.json` stay after merge.
- **`FIREANT_TOKEN`**: required for live VN market data in weekly (per repo client).

## Limitations / integrity

- **OMO net** often returns `null` (SBV table may be JS-rendered). See `docs/SBV_LIQUIDITY_SOURCES.md`.
- **Bond WoW** in features needs **`manual_inputs_prev.json`** aligned to the prior week; this script does not auto-roll it (avoid silent WoW errors).
- **Proxy disclosure**: ETF/index resolution follows existing FireAnt rules in repo.

## Agent prompt (copy-paste)

```
Run the full weekly data refresh and reports from repo root:
  python scripts/run_weekly_full_fetch.py

If FRED or FireAnt env vars are missing, report warnings and list which fields stayed from file vs fetched.

After success, point user to:
  data/decision/weekly_report.md
  reports/latest/index.html
```

## Relation to other scripts

- `scripts/run_full_weekly_cycle.py` — thin wrapper around `run_weekly_full_fetch.py` (same behavior).

## Implementation note

`run_weekly_full_fetch` runs `src.report.weekly --render` once, then `run_weekly_update --skip-weekly` so the weekly engine is **not** executed twice.
