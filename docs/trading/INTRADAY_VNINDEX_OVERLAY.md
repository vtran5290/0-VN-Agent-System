# Intraday VNINDEX overlay (preview only)

## Purpose

Provide a **provisional** VNINDEX macro regime for intraday preview scans. This does **not** replace the EOD Phase36 daily scan SSOT.

## Data source

| Item | Value |
|------|--------|
| Provider | FireAnt REST API |
| Endpoint | Same-day **historical-quotes** (partial daily bar) |
| Symbol | **VNINDEX** |
| Method | `src/trading/intraday/data_adapter.py` → `vnindex_overlay.py` |

## In-memory only

- Overlay updates the **in-memory** panel slice used by `compute_phase36_scan_df(..., intraday_macro=True)`.
- **No writes** to `data/fireant_ssot/ta_vnindex.parquet`.
- **No writes** to `data/research/ema_cloud/ohlcv_panel_ext2012.parquet`.

## Semantics

| Field | Meaning |
|-------|---------|
| `final_action` | Always **`INTRADAY_PREVIEW`** on intraday outputs |
| `would_be_final_action` | **IF_CLOSE_NOW** — Phase36 result if today closed at scan time |
| `auto_order_allowed` | **`False`** always |
| `vnindex_regime_changed` | Compares **EOD regime** vs **newly computed intraday regime** (not `None` vs intraday) |

EOD Phase36 scan remains the only path for OMS / `build_order_intents`. Intraday CSV paths are blocked by `scan_resolver._is_intraday_preview()`.

## Known limitations

- **Partial daily bar**, not tick or order-book data.
- No confirmed dedicated quote/priceboard endpoint for all fields.
- Timestamp may be **date-level** or session-open aligned (not sub-minute).
- **Breadth** may be **mixed**: quoted holdings use intraday partial bars; rest of panel may remain EOD until quoted (`breadth_source=mixed_intraday_eod_panel`).
- Volume may use session-time projection (`volume_projection.py`).

## Operator rule

Use intraday output for **manual planning only**. Orders require EOD `phase36_daily_scan_latest.csv` (or approved legacy alias with `--allow-sample`).
