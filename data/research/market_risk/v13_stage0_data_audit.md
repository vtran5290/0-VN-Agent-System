# Distribution Risk v1.3 — Stage 0 Data Audit

## Source files
- OHLCV panel: `D:\V\0. VN Agent System\data\fireant_ssot\ta_ohlcv_panel.parquet`
- Index views: `minervini_backtest/data/raw/VNINDEX.csv`, `data/research/vnindex_ex_vin_daily_series.csv`

## Columns available (panel)
`ticker`, `date`, `open`, `high`, `low`, `close`, `volume`, `value`

## Date range
- Panel: **2017-05-18** → **2026-06-02**
- Distribution index features from 2012 where CSV available; breadth joins from panel start

## Latest liquid universe
- ADV50 threshold: **2,000,000,000 VND**
- Latest liquid count (as of panel max date): **258**

## Panel stats
- Rows: 1,282,395
- Tickers: 1,564
- Price unit: thousand_VND
- Value traded: computed close×volume (ratio=0.001)

## Assumptions
- ADV50 = rolling 50-day mean of daily value traded (tv), no lookahead
- Liquid if adv50_value >= 2,000,000,000 VND on that date
- Universe size varies by date; not a fixed ticker list
- Panel history starts 2017-05-18 (not full 2012 index history)

## Warnings
- value/close×volume ratio unusual: 0.001
