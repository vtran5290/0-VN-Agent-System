# Macro Data Ingestion

Use this skill when updating global macro, Vietnam liquidity, or market data for the weekly report.

## Steps

1. **Refresh raw inputs**
   - Global: ensure `data/raw/manual_inputs.json` has `global` (ust_2y, ust_10y, dxy, cpi_yoy, nfp). Use FRED via `scripts/fetch_global.py`; set `FRED_API_KEY` if needed.
   - Vietnam liquidity: use **SBV scrape** — see skill **vn_sbv_liquidity** and `docs/SBV_LIQUIDITY_SOURCES.md`. Run `python scripts/update_manual_inputs.py --asof YYYY-MM-DD --force-vn-liquidity` to fetch omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd from SBV and merge into `manual_inputs.json`. Without `--force-vn-liquidity`, existing vietnam keys are preserved.
   - Market: run `python -m src.report.weekly --render` so FireAnt snapshot is fetched and `data/decision/market_snapshot_debug.json` is written; or fill `manual_inputs.json` → `market`.

2. **Run ingestion**
   - From repo root: `python -m scripts.ingest.run_weekly_update` (runs weekly report then normalizer).
   - Or `python -m src.report.weekly --render` then normalize only: `python -m scripts.ingest.run_weekly_update --skip-weekly`.

3. **Validate freshness**
   - Check `data/processed/weekly_report.json` → `metadata.report_age_days`. If > 3, report is stale.
   - Check `metadata.data_confidence` (High/Medium/Low) and `metadata.warnings`.

## Key paths

- `data/raw/manual_inputs.json` — canonical inputs; Vietnam liquidity from SBV via `scripts/fetch_vietnam_liquidity.py` when using `--force-vn-liquidity`.
- `docs/SBV_LIQUIDITY_SOURCES.md` — SBV URLs, table layout, parsing notes for omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd.
- `data/decision/market_snapshot_debug.json` — FireAnt snapshot (from weekly run)
- `configs/weekly_sources.yml` — source priority (primary/fallback) per metric

## Success criteria

- `data/processed/weekly_report.json` exists and `metadata.asof_date` is set.
- No crash; missing data produces warnings, not failure.

## Failure handling

- If FireAnt or FRED fails, pipeline continues using manual fallback; log and report in `metadata.warnings`.
