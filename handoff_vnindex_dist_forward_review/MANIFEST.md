# Handoff bundle — file layout

Extract the ZIP so this folder is the **project root** (the path that contains `scripts/`, `src/`, `data/`, `artifacts/`).

## Included data (minimal)

| Path | Role |
|------|------|
| `minervini_backtest/data/raw/VNINDEX.csv` | Daily VNINDEX history + base for merge |
| `data/stocks/{VIC,VHM,VRE}.csv` | OHLCV for Vin basket (ex-VIN synthetic) |
| `data/fireant_exports/financials/vin_basket_quarterly_shares.parquet` | Quarterly shares, **VIC/VHM/VRE only** (subset of full FA export) |
| `artifacts/vnindex_ex_vin_result.json` | Snapshot for cap calibration (as-of in JSON) |
| `docs/research/VIN_EMA_CLOUD_BASELINE.md` | Project rules: ex-VIN basket, VNINDEX caveat |

## Code

| Path | Role |
|------|------|
| `scripts/research/vnindex_low_dist_forward_returns.py` | Full VNINDEX low-dist study (original horizons 20/50/100/150/200) |
| `scripts/research/vnindex_low_dist_ex_vin.py` | **Handoff-patched:** `QUARTERLY_FA` points to `vin_basket_quarterly_shares.parquet` |
| `src/intake/fireant_historical.py` | Fetches recent bars from FireAnt web API (optional if CSV up to date) |
| `src/features/distribution_days.py` | Refined distribution-day definition (AFL-style); separate from simple rule in scripts |

## Python environment

- Python 3.10+ recommended  
- `pip install pandas numpy requests` (and `pyarrow` if parquet read warns)

## Commands (from this folder as cwd)

```powershell
# Ex-VIN study (writes under ./data/research/ if you run full main — may need mkdir)
python scripts/research/vnindex_low_dist_ex_vin.py --end 2026-05-14 --start-window 2026-03-23 --max-dist-in-window 1

# Full VNINDEX study
python scripts/research/vnindex_low_dist_forward_returns.py --end 2026-05-14 --start-window 2026-03-23
```

If `fetch_historical` fails offline, ensure `VNINDEX.csv` / stock CSVs already include bars through `--end`.

## Merging back into full “VN Agent System” repo

Replace only `scripts/research/vnindex_low_dist_ex_vin.py` if you revert `QUARTERLY_FA` to the full `all_financial_data_quarterly_*.parquet` path; otherwise keep this handoff’s parquet path or symlink the full parquet to the handoff filename.
