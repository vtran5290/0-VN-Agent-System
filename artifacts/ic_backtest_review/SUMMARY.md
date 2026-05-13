# IC Backtest Review Package
**Date:** 2026-05-13  
**Market:** Vietnam (HOSE/HNX)  
**Objective:** Determine which technical indicators have statistically meaningful predictive power for stock forward returns at horizons 25d / 50d / 100d / 150d / 200d / 250d.

---

## What Was Built

### Scripts
| File | Purpose |
|------|---------|
| `scripts/research/indicator_predictive_backtest.py` | Main backtest: computes 17 indicators at monthly snapshots, runs Spearman IC, Q5-Q1 spread, hit rate, mutual information, and multi-factor composite optimization |
| `scripts/research/sector_stock_prob.py` | Per-stock rotation probability = sector_rotation_prob × (tech_score / 100) |
| `scripts/research/sector_deep_dive.py` | Full tech + FA deep-dive for BDS / Securities / Banks sectors |
| `scripts/research/rubber_deep_dive.py` | Full tech + FA deep-dive for Rubber sector |
| `scripts/update_ohlcv_panel_incremental.py` | Incremental OHLCV panel updater (fetches new bars since last date, deduplicates, backups) |

### Data
| File | Description |
|------|-------------|
| `data/research/indicator_backtest_single_factor.csv` | Spearman IC + Q5-Q1 spread + hit rate per (indicator, horizon) |
| `data/research/indicator_backtest_multifactor.csv` | Multi-factor composite IC for all pairs + triples of top-8 indicators |
| `data/research/indicator_snapshots.parquet` | Full panel: 24,572 monthly snapshots × 17 indicators + 6 forward return columns |
| `data/research/sector_stock_prob.csv` | Per-stock rotation probability table |
| `data/research/rubber_deep_dive_results.csv` | Rubber sector tech+FA composite scores |
| `data/research/bds8633_stock_prob_20260508.csv` | BDS/Securities/Banks deep-dive scores |

---

## Methodology

### Universe
- **485 liquid tickers** from HOSE/HNX with ADV50 ≥ 2B VND/day
- Data: 2017–2026-05-13 (OHLCV from FireAnt API)
- Snapshots: last trading day of each month per ticker (→ 24,572 observations)

### Indicators Computed (17 total)
| Category | Indicators |
|----------|-----------|
| Momentum | r5, r20, r60, r120, r252 (% return over N days) |
| Relative Strength | RS20, RS60 (stock return − VNINDEX return) |
| Trend / MA | stage2 (0–5 Minervini score), ma_align (strict boolean) |
| Proximity | dist_hi52 (% below 52-week high) |
| Oscillator | RSI14 (EWM) |
| Money Flow | CMF20 (Chaikin), OBV normalized slope (20d) |
| Volatility | ATR ratio (14d/50d), BB width (4σ/price × 100) |
| Volume | vol_ratio (5d avg / 50d avg) |
| Selling Pressure | dist_days (distribution days in last 25 sessions) |

### Forward Return Targets
- fwd25d, fwd50d, fwd100d, fwd150d, fwd200d, fwd250d
- Computed as: (close[t+h] / close[t] − 1) × 100

### Statistical Tests
1. **Spearman IC** (rank correlation) — primary metric; robust to outliers
2. **Q5-Q1 quintile spread** — avg return of top 20% minus bottom 20%
3. **Hit rate** — % of top-quintile snapshots with positive forward return
4. **Mutual Information** — captures non-linear relationships
5. **Multi-factor composite** — Z-score average of top-8 indicators (sign-corrected per IC direction); tested all 28 pairs + 20 triples

---

## Key Results

### Single-Factor IC Summary

| Rank | Indicator | Mean\|IC\| | Direction | Key Horizons |
|------|-----------|-----------|-----------|-------------|
| 1 | **r252** | **0.108** | Reversal (neg IC) | All horizons — strongest at 200-250d |
| 2 | r120 | 0.038 | Mixed (pos→neg) | Momentum at 25-100d, reversal at 200d+ |
| 3 | stage2 | 0.029 | Positive | 25-100d |
| 4 | CMF20 | 0.028 | Positive | 100-250d (slow-burn) |
| 5 | r5 | 0.026 | Reversal (neg) | Short-term mean-reversion |
| 6 | vol_ratio | 0.026 | Positive | 150-250d |
| 7 | dist_hi52 | 0.024 | Mixed | 200-250d |
| 8 | bb_width | 0.023 | Positive | **Best at 25d (IC=+0.053)** |
| — | r20, rs20, RSI14 | <0.015 | Weak/noisy | Not reliably significant |

**Interpretation of IC scale:**
- \|IC\| > 0.02 = weak but worth monitoring
- \|IC\| > 0.05 = meaningful in equity research
- \|IC\| > 0.10 = strong predictive power

### Multi-Factor Results (Top 5)

| Combo | N factors | Mean\|IC\| | 25d | 100d | 200d | 250d |
|-------|-----------|-----------|-----|------|------|------|
| **r252 + bb_width** | 2 | **0.103** | +0.068** | +0.057** | +0.152** | +0.172** |
| r252 + r120 | 2 | 0.100 | +0.055** | +0.103** | +0.128** | +0.126** |
| r252 + r120 + r5 | 3 | 0.097 | +0.058** | +0.099** | +0.125** | +0.139** |
| r252 + cmf20 | 2 | 0.091 | ns | +0.081** | +0.144** | +0.173** |
| r252 + r5 | 2 | 0.090 | +0.045** | +0.066** | +0.132** | +0.168** |

(\*\* = p < 0.01)

### Horizon-Optimal Recommendation

| Horizon | Best Single | IC | Best Combo | IC |
|---------|------------|-----|------------|-----|
| 25d (1M) | bb_width | +0.053 | r120 + bb_width | +0.083 |
| 50d (2M) | r120 | +0.047 | r252 + r120 | +0.092 |
| 100d (4M) | r60 | +0.057 | r252 + r120 | +0.103 |
| 150d (6M) | r252 (flipped) | −0.124 | r252 + bb_width | +0.103 |
| 200d (8M) | r252 (flipped) | −0.167 | r252 + bb_width | +0.152 |
| 250d (10M) | r252 (flipped) | −0.193 | r252 + bb_width | +0.172 |

---

## Key Economic Insights

1. **r252 is mean-reversion, not momentum** — past-year winners underperform at 6-12M. IC = −0.19 at 250d. In the composite it is sign-flipped (penalize high fliers, favor laggards).

2. **bb_width is the strongest 1-month predictor** — wide band = volatility expanding = breakout happening. IC = +0.053 at 25d, best short-term signal in the universe.

3. **CMF20 + vol_ratio = patient capital signals** — both take 3-5 months to manifest. For buy-and-hold, accumulation (CMF > 0.05) + volume expansion is the reliable combo.

4. **Stage2 (Minervini) works at 50-100d, fades beyond** — useful for medium-swing entries, not long-term holds.

5. **r20 / RS20 / RSI14 are noisy** — popular in retail trading but IC < 0.015. Do not rely on these alone.

6. **Vietnam market characteristics**: moderate efficiency (ICs modest vs global factors), but strong mean-reversion at 1-year horizon consistent with retail-driven momentum exhaustion.

---

## Limitations & Suggested Improvements

1. **In-sample only** — no train/test split or walk-forward validation. IC numbers are optimistic.
2. **Monthly snapshots** — misses intra-month setups. Consider weekly or daily sampling.
3. **Survivorship bias** — panel includes delisted/renamed tickers only if present in current SSOT.
4. **No transaction costs** — Q5-Q1 spread is gross; add 0.3-0.5% round-trip cost.
5. **Sector effects not controlled** — some IC may be captured by sector rotation, not stock-level signals.
6. **Missing indicators to test**: VWAP distance, earnings surprise, insider buying, short interest, FA momentum (EPS growth rate of change).
7. **Non-linear models** — only tested linear composites (Z-score). Try XGBoost or logistic classifier on quintile membership.
8. **Walk-forward IC decay** — test whether IC is stable across time periods (2018-2021 vs 2022-2026).

---

## File Index

```
artifacts/ic_backtest_review/
├── SUMMARY.md                          ← this file
scripts/research/
├── indicator_predictive_backtest.py    ← main backtest script
├── sector_stock_prob.py                ← per-stock rotation prob
├── sector_deep_dive.py                 ← BDS/Sec/Banks deep-dive
├── rubber_deep_dive.py                 ← Rubber deep-dive
scripts/
├── update_ohlcv_panel_incremental.py   ← OHLCV updater
data/research/
├── indicator_backtest_single_factor.csv
├── indicator_backtest_multifactor.csv
├── indicator_snapshots.parquet         ← 24,572 × (17 indicators + 6 fwd returns)
├── sector_stock_prob.csv
├── rubber_deep_dive_results.csv
├── bds8633_stock_prob_20260508.csv
```
