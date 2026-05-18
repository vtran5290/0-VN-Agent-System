# Intraday data source discovery — FireAnt

**Date:** 2026-05-15 (probe run in repo)  
**Source:** FireAnt REST `https://restv2.fireant.vn`  
**Method:** API (read-only probe via `scripts/research/fireant_intraday_probe.py`)

## Summary

| Question | Answer |
|----------|--------|
| Partial daily bar during session? | **Yes** — `GET /symbols/{symbol}/historical-quotes` with `startDate=endDate=today` returns OHLCV including cumulative volume for the current session day when markets are open / same-day bar exists. |
| Separate intraday/tick endpoint? | **Not confirmed** — probed paths (`/quotes`, `/quote`, `/priceboard`, `/markets/quotes`) returned **404** or non-JSON from this environment. |
| Credentials | Same as EOD: `FIREANT_TOKEN` env or `.env` (Bearer JWT). |
| Latency | **Unknown / likely delayed** — treat as preview, not tick-accurate HFT. |
| Lunch break | Session phase `LUNCH_BREAK` — scan status `OUT_OF_SESSION_NO_ACTION` (no fake orders). |
| Pre-ATC / ATC | Phases `PRE_ATC`, `ATC` — preview allowed with manual review; volume projection higher confidence. |
| Fallback | If token missing or empty quotes → `SOURCE_UNAVAILABLE`; **no synthetic prices**. |

## Fields available (historical-quotes partial daily)

Native / parsed fields (see `src/data/fireant_client.py::_parse_ohlcv`):

- `date` (trading day)
- `open`, `high`, `low`, `close` (kVND)
- `volume` (cumulative shares for the day)
- Derived: `value` ≈ close × volume × 1000 when built in panel overlay

**Not available** from confirmed endpoint:

- bid/ask (unless dedicated endpoint found later)
- ceiling/floor/reference (not in historical-quotes row)
- sub-minute bars

## Recommended adapter

1. **Primary:** `FireAntClient.get_ohlcv(symbol, today, today)` → partial daily bar.  
2. **Future:** If DevTools captures a live quote JSON endpoint, extend `data_adapter.py` without changing scan policy.  
3. **Never:** Write intraday bars into `ohlcv_panel_ext2012.parquet`.

## Probe artifacts

- `data/research/intraday/source_probe/fireant_probe_YYYYMMDD_HHMM.json`
- Run: `python scripts/research/fireant_intraday_probe.py --symbols HPG,VPB,FPT,MWG,SSI`

## Operator contract

- Intraday output: `data/research/intraday/phase36_intraday_scan_*.csv`
- `is_intraday_preview=True`, `auto_order_allowed=False`
- OMS / `build-intents` **blocks** intraday CSV paths (`scan_resolver.py`)
- EOD SSOT unchanged: `data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv`

## VNINDEX intraday overlay (2026-05+)

- Module: `src/trading/intraday/vnindex_overlay.py`
- Fetches `VNINDEX` partial daily bar via same FireAnt `historical-quotes` path.
- Overlays in-memory only — **does not write** `data/fireant_ssot/ta_vnindex.parquet`.
- `compute_phase36_scan_df(..., intraday_macro=True)` uses:
  - VNINDEX overlay for `regime_bull`
  - Live `_compute_cloud_breadth` on provisional equity panel (not stale `regime_decomposition_breadth.csv` alone).

## Reports

- Markdown: `data/research/intraday/phase36_intraday_scan_latest.md`
- HTML dashboard: `data/research/intraday/phase36_intraday_scan_latest.html`
