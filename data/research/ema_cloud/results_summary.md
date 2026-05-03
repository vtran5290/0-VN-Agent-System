# EMA Cloud + Price Level Research — Results Summary

Data: Vietnam equities, 2023-01-01 to latest (ADV50 ≥ 2B VND/day)

## OOS Aggregate (walk-forward monthly, signal_type × horizon)

| Signal | Months | Trades | Success63d | Win63d | Median63d | Success126d | Win126d |
|--------|--------|--------|-----------|--------|-----------|------------|---------|
| all | 18 | 154 | 44.7% | 54.2% | 3.4% | 39.0% | 50.8% |
| breakout | 17 | 109 | 38.3% | 48.4% | 2.8% | 31.0% | 46.4% |
| retest | 5 | 24 | 31.1% | 43.3% | -1.0% | 31.1% | 41.1% |

## Most Selected Parameters (OOS fold count)

- `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30`: selected 14 fold(s)
- `f10_s50_rb0_mc120_rbw120_pd0.50_mm5_cb0.30`: selected 10 fold(s)

## Recent-Base-Only vs Broad-Level Comparison (event study, 63d)

- **Broad**: n=120618, success=31.4%, win=38.3%, median=-3.9%
- **Recent-Base**: n=73619, success=30.9%, win=37.2%, median=-4.8%

## Portfolio Backtest (best params, 63d hold, max 10 positions)

- **n_trades**: 111
- **total_return**: 0.0569
- **cagr**: 0.0182
- **hit_rate**: 0.4955
- **avg_trade_ret**: 0.0069
- **max_drawdown**: 0.2947
- **sharpe_approx**: 0.07

## Recommended Default Parameters

**Most OOS-robust param key:** `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30`

Decode: `f{fast}_s{slow}_rb{recent_base}_mc{max_candles}_rbw{rbw}_pd{pct_diff}_mm{min_matches}_cb{close_buffer}`

## Caveats

### Universe / VIN research baseline (this run)

- Excluded VPL: 242 bars in panel (< 252 per research baseline).
- For robustness, compare **full universe** vs **`--ex-vin`** runs; VIN can distort **return tails** even when aggregate success rates move little (`docs/research/VIN_EMA_CLOUD_BASELINE.md`).

- OOS walk-forward uses expanding window from 2023-01; early folds have thin sample sizes.
- Level detection is bar-by-bar with strict no-leakage (local highs confirmed to t-2).
- Entry at next-bar open; slippage and transaction costs not modeled.
- VN T+2.5 settlement not modeled — live implementation must account for this.
- ADV50 ≥ 2B VND filter applied; results may differ for smaller stocks.
- `trade_success` = hit +15% before -8% within horizon; does not model pyramiding or partial exits.

## Files

| File | Description |
|------|-------------|
| `trades.csv` | All signal events + forward returns for every param combo |
| `event_study.csv` | Aggregated statistics per (param_key, signal_type) |
| `parameter_results.csv` | Ranked param combos by OOS success rate |
| `oos_summary.csv` | Monthly walk-forward OOS results |