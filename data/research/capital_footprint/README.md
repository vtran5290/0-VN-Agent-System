# VN Capital Footprint Research

**Date:** 2026-05-29
**Status:** RESEARCH ONLY — not connected to production A3 or OMS

## What this is

A systematic test of whether observable "capital footprint" signals have predictive
power for Vietnam stock returns. Three use cases tested:
1. Standalone stock-ranking signal
2. A3 (EMA20/100 cloud) enhancement layer
3. Watchlist generation for early large-capital accumulation

## Data Coverage

- Symbols: 267
- Rows: 303,880
- Date range: 2018-02-06 to 2026-05-29
- Source: FireAnt OHLCV SSOT + sector map + regime log + FA quarterly

## What is NOT available

- Foreign institutional flow: NOT available (skipped cleanly)
- Index/ETF membership: NOT available (skipped cleanly)
- Broker revisions: NOT available (skipped cleanly)
- Margin data: macro proxy only

## Files

| File | Description |
|---|---|
| data_availability_report.md | What data exists, what's missing, proxies used |
| capital_footprint_feature_spec.md | Every feature definition with lookahead guardrails |
| capital_footprint_features.parquet | Full feature panel |
| capital_footprint_scores.parquet | Composite scores only |
| rank_ic_results.csv | Spearman IC by signal, horizon, regime, liquidity tier |
| rank_ic_by_year.csv | IC year-by-year breakdown |
| quantile_portfolio_results.csv | Q1-Q5 return spreads across cost/liquidity assumptions |
| event_study_results.csv | Average price path after high-score events |
| a3_enhancement_results.csv | A3 baseline vs all CF enhancement variants |
| feature_ablation_results.csv | Component-level IC comparison |
| false_positive_examples.csv | High-score failures classified by regime/pattern |
| best_winner_examples.csv | High-score winners classified by success pattern |
| regime_robustness_results.csv | IC and spread by regime and year |
| top_stocks_current.csv | Top 20 stocks by CF score on latest date |
| capital_footprint_decision_memo.md | Final verdict and recommendations |
| charts/ | Charts (if generated) |

## How to re-run

```bash
python scripts/research/run_capital_footprint_backtest.py
```

## IC Summary

Top 5 signals by 20d IC (all regimes):
  - dry_up_pullback_flag: IC=0.0107, t=3.75
  - cloud_bull_20_100: IC=0.0031, t=0.75
  - breakout_volume_flag: IC=0.0001, t=0.03
  - sector_rotation_score: IC=-0.0063, t=-1.62
  - big_individual_footprint_proxy: IC=-0.0072, t=-1.92


## Status

See `capital_footprint_decision_memo.md` for final verdict.
