# Trend Speed × 2-Cloud Research — v2 Review Pack

## v2 changes (decision-grade T2)
- **P0-1:** Pine-equivalent speed reset — cross bar uses `2×(RMA(close,10)-RMA(open,10))`.
- **P0-2:** Exact A3 T2 re-simulation per gate (no `blended×0.85` approximation).
- **P1-1:** Ranking modes `fifo` + `tsa_composite_only` only (no Phase36 `a3_rank_score` on panel).
- **P1-2:** Exit overlay **removed** from conclusions (prior D-series used non-comparable single-leg sim).

## Contracts (unchanged)
- A3: EMA20/100, T1 50%, T2 on ≥4% pullback/30 bars, TP1 +18%, trail 2.5×ATR14, max hold 250, VNINDEX bear blocks T1, breadth <40% blocks T2.
- S3 shadow: EMA21/55, max hold 60, trail 3.5×ATR14 — separate P&L.

## Data
- Panel: `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` (FireAnt SSOT)
- Breadth: `regime_decomposition_breadth.csv`
- 2012-01-03 → 2026-05-22, ex-VIN, ADV≥2B, entry open[t+1], 40 bps RT
