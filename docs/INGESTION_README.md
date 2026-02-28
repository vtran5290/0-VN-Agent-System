# Data ingestion — VN Investment Terminal

Auto-ingest global (FRED), VN market (vnstock / FireAnt), and distribution days into `data/raw/manual_inputs.json`.

## Prerequisites

- Python 3.10+
- `FRED_API_KEY` in environment or `.env` (copy from `.env.example`, paste your key).
- Optional: `vnstock` for VN index levels (else FireAnt fallback).

## Run

From repo root:

```bash
make ingestion
```

or:

```bash
python -m scripts.run_ingestion --all
```

Options:

- `--asof YYYY-MM-DD` — date for data (default: today).
- `--force-vn-liquidity` — allow overwriting `vietnam.omo_net`, `interbank_on`, `credit_growth_yoy` (default: do not overwrite).

## What it does

1. **fetch_global** — FRED: UST 2Y (DGS2), UST 10Y (DGS10), DXY (DTWEXBGS; fallback Yahoo DX-Y.NYB), CPI YoY (CPIAUCSL), NFP (PAYEMS).
2. **fetch_vietnam_market** — VNINDEX and VN30 levels (vnstock, then FireAnt).
3. **compute_distribution_days** — VN30 OHLC, rule: Close < Prev Close and Volume > Prev Volume, rolling 20.
4. **update_manual_inputs** — Merge into `data/raw/manual_inputs.json` with safe update (no wipe of `overrides.*` or VN liquidity unless `--force-vn-liquidity`). Sets `extraction_mode = macro_market_auto_v1` and `drift_guard`.

## Files

- `scripts/safe_json_io.py` — safe read/merge/atomic write.
- `scripts/fetch_global.py` — FRED + DXY fallback.
- `scripts/fetch_vietnam_market.py` — VN index levels.
- `scripts/compute_distribution_days.py` — dist days from OHLC.
- `scripts/update_manual_inputs.py` — merge into manual_inputs.
- `scripts/update_tech_status.py` — tech_status from watchlist OHLC (close_below_ma20, day1/day2 triggers).
- `scripts/run_ingestion.py` — entrypoint `--all`.
- `logs/ingestion.log` — log output.

## Idempotent

Safe to run multiple times; only provided keys are updated; no null-wipe of existing data.

## FRED key

1. Get key: https://fred.stlouisfed.org/docs/api/api_key.html  
2. Copy `.env.example` to `.env`, set `FRED_API_KEY=your_key`.  
3. Or export in shell: `export FRED_API_KEY=your_key` (Linux/Mac), `$env:FRED_API_KEY="your_key"` (PowerShell).
