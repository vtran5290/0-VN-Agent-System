# Signal Data Schema (partial — S17 discovery 2026-07-05)

## FireAnt historical-quotes — buy/sell flow (S17)
- **source**: FireAnt REST `GET /symbols/{symbol}/historical-quotes`
- **method**: API
- **buy field**: `buyQuantity` (matched buy-side quantity)
- **sell field**: `sellQuantity` (matched sell-side quantity)
- **put-through**: `putthroughVolume` (separate; exclude from S17 ratios unless council decides otherwise)
- **NOT in repo OHLCV CSVs**: `data/stocks/*.csv` has date, OHLCV only — S17 requires live FireAnt fetch or extended cache
- **OOS coverage**: 261/261 symbols, 99.1% signal-day match
- **S17 pre-check verdict**: EXPRESSIBLE
