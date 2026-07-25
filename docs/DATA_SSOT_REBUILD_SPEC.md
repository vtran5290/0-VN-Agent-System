# DATA SSOT Rebuild Spec — `ta_ohlcv_panel`

**Date:** 2026-07-23  
**Status:** APPROVED (user ratify + architecture-advisor `RE-FETCH_PRIMARY`)  
**Artifact:** `data/fireant_ssot/ta_ohlcv_panel.parquet`  
**Builder:** `scripts/build_fireant_ssot.py`

## Canonical conventions

| Field | Convention |
|---|---|
| Price OHLC (`open/high/low/close`) | FireAnt `price*` back-adjusted **as-of fetch latest** via `adjRatio`: `px_adj = px * adjRatio_last / adjRatio_t`. Quote unit = FireAnt `unit` (typically **1000** ⇒ prices in thousand VND). |
| `close_raw` | Unadjusted FireAnt `priceClose` (same quote unit) — for turnover identity checks only. |
| `volume` | FireAnt `dealVolume` (shares). |
| `value` | FireAnt native `totalValue` (**raw VND** traded value, includes put-through). |
| `unit_vnd` | FireAnt `unit` (price × `unit_vnd` ⇒ VND per share). |
| `adjust_basis` | `fireant_adjRatio_asof_latest` |
| `source` | `fireant_restv2_historical_quotes` (fallback per-symbol: documented only if re-fetch fails) |

**Turnover identity:** `value / (close_raw × unit_vnd × volume)` clusters near **1** (dispersion from average-price / put-through is expected; not a second unit cluster at ~1000).

**Do not** concatenate `ema_cloud` LFS stubs with `data/stocks/*.csv` (that produced the 2024-01-30 mixed-unit / mixed-adjustment splice).

## Sole writer policy (hardened 2026-07-23)

- **Only** `scripts/build_fireant_ssot.py` may write `data/fireant_ssot/ta_ohlcv_panel.parquet`.
- `scripts/update_ohlcv_panel_incremental.py` is a **gate**: it refuses direct append (exit 2) unless `--via-builder` (delegates to the builder). `--dry-run` proves no panel write.
- Daily/EOD PowerShell operators must call the builder, not the old incremental appender.
- Family runners call `src.research._ssot_guard.assert_panel_certified()` before reading the panel.

## Corporate actions

- Preferred: dated CA calendar from FireAnt.  
- Available today: `GET /symbols/{sym}/dividends` = **year-level** cash/stock dividend summaries (no ex-date) → stored as low-confidence annual summaries.  
- `/corporate-actions`, `/events`, `/rights` → **404** (session probe 2026-07-23).  
- Fallback: `ca_suspect=True` on residual daily moves beyond exchange limit band after accounting for `adjRatio` changes; emit report under `data/fireant_ssot/`.

## Rebuild policy

1. Backup existing SSOT → `data/fireant_ssot/_backup_YYYY-MM-DD/`.  
2. Re-fetch each universe symbol as one continuous series.  
3. Write panel + provenance columns + CA artifacts + regenerated `manifest.json` (incl. SHA256).  
4. Run `tests/test_ssot_integrity.py`. Stop for Claude panel review — **no** B0/H1/H2.
