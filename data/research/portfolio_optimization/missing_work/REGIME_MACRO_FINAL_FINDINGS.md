# Regime / Macro Final Findings

As of: 2026-05-16

## Key Questions

### When does A3 DP work best?
- Bull regime (EMA20 > EMA100): 96.5% of trades occur in bull regime (gate enforced)
- High breadth (>60%): 2013, 2017, 2020, 2021, 2025 — all bull years show positive annual return
- Low volatility entries (EMA dist 2-5%): better risk-adjusted returns than stretched entries

### When does A3 DP fail?
- 2016 (-4.7%), 2019 (-5.8%): regime gate opened but market structure was sideways/choppy
- 2024 (-4.0%): high trade count (1,014) but low win rate (63.2%) — breadth borderline
- Breadth <40%: weaker returns. Confirm with breadth_hysteresis test.

### Does breadth <40% explain weak periods better than VNINDEX?
- See breadth_rule_final.md from Step 5

### Is PTS useful in specific regimes?
- PTS strength-add captures no-pullback breakouts in high-momentum regimes
- Empirically weaker after corrected liquidity. Not regime-dependent improvement.

### Does S3 have any niche regime?
- S3 EMA21/55 shorter period → more signals but lower quality in all regimes tested
- MAR=0.190 not competitive in any regime subset tested

## Outputs

- regime_decomposition_market.csv: VNINDEX EMA labels daily
- regime_decomposition_breadth.csv: A3/S3 breadth daily
- regime_decomposition_liquidity.csv: per-trade regime tags
- MACRO_DATA_MISSING.md: required external data not yet loaded
