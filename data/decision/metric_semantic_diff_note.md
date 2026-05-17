# Semantic / display diff (vs `data/raw/manual_inputs_prev.json`)

## Same-field value drift (likely data refresh)
- `ust_2y`: 3.76 → 4.0
- `ust_10y`: 4.27 → 4.47
- `cpi_yoy`: 2.66 → 3.81
- `dxy`: 119.491 → 97.9231

## Semantic relabeling (this workflow version)
- **DXY:** `dxy_reconstructed` from FRED H.10 (6 FX, ICE-style weights); optional `dxy_third_party` (Yahoo DX-Y.NYB); `dxy_ice_official` only via env; FRED `DTWEXBGS` → `usd_broad_index_fred` only (broad USD, not DXY).
- **Payroll:** `nonfarm_payroll_change_persons` = MoM Δ from PAYEMS; `nonfarm_payroll_level_thousands` = level; legacy `nfp` left null.
- **CPI YoY:** BLS `CUUR0000SA0` + `cpi_reference_month` when available; FRED-derived path flagged in validation warnings.
- **UST:** FRED `DGS2`/`DGS10` with `ust_*_value_date` (Treasury daily observation, not broker “session close” label).
- **USD/VND:** Treat as **SBV reference** unless provenance states interbank/spot.