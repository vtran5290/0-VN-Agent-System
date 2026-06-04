# Capital Footprint Feature Specification

**Date:** 2026-05-29

## Lookahead Guardrails

All rolling features shift(1) their rolling computation so the current bar's value
never contributes to its own signal.

Forward return columns (fwd_ret_*) use future prices — they are LABELS only and must
never be used as predictor features.

FA data uses a 45-day publication lag: availability date = quarter end + 45 days.

## Section A — Liquidity Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| adv20_vnd | rolling(20).mean().shift(1) of value | Yes |
| adv50_vnd | rolling(50).mean().shift(1) of value | Yes |
| adv120_vnd | rolling(120).mean().shift(1) of value | Yes |
| turnover_z_20d | (value - adv20) / std20 | Yes |
| turnover_z_60d | (value - adv60) / std60 | Yes |
| liquidity_rank_market | rank(pct=True) of adv50_vnd across all stocks on date | Yes |
| liquidity_rank_sector | rank(pct=True) of adv50_vnd within sector on date | Yes |

## Section B — Relative Strength Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| ret_20d | close.pct_change(20) | Yes |
| ret_60d | close.pct_change(60) | Yes |
| ret_120d | close.pct_change(120) | Yes |
| ret_252d | close.pct_change(252) | Yes |
| rel_ret_vnindex_20d | ret_20d - VNINDEX ret_20d | Yes |
| rel_ret_vnindex_60d | ret_60d - VNINDEX ret_60d | Yes |
| rel_ret_vnindex_120d | ret_120d - VNINDEX ret_120d | Yes |
| rel_ret_sector_20d | ret_20d - sector median ret_20d | Yes |
| rel_ret_sector_60d | ret_60d - sector median ret_60d | Yes |
| rel_ret_sector_120d | ret_120d - sector median ret_120d | Yes |
| rs_rank_market_20d | rank(pct) of ret_20d across all stocks on date | Yes |
| rs_rank_market_60d | rank(pct) of ret_60d across all stocks on date | Yes |
| rs_rank_market_120d | rank(pct) of ret_120d across all stocks on date | Yes |
| rs_rank_sector_20d | rank(pct) of ret_20d within sector on date | Yes |
| rs_rank_sector_60d | rank(pct) of ret_60d within sector on date | Yes |
| rs_rank_sector_120d | rank(pct) of ret_120d within sector on date | Yes |
| rs_persistence_score | mean(rs_rank_market_20d, _60d, _120d) | Yes |

## Section C — Price-Volume Accumulation Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| close_location_value | (close - low) / (high - low), clipped [0,1], 0.5 for flat bars | Yes |
| weekly_close_location_value | rolling(5, min_periods=3).mean() of CLV | Yes |
| value_z_20d | (value - adv20) / std20 | Yes |
| value_z_60d | (value - adv60) / std60 | Yes |
| breakout_volume_flag | (value > 1.5*adv50) AND (close > prior 60d high) | Yes — uses shift(1) on 60d high |
| up_day_value_sum_20d | sum(value) on days where close > prior close, 20d | Yes |
| down_day_value_sum_20d | sum(value) on days where close < prior close, 20d | Yes |
| up_down_value_ratio_20d | up_val_20 / down_val_20 | Yes |
| up_down_value_ratio_60d | up_val_60 / down_val_60 | Yes |
| dry_up_pullback_flag | (price within 8% of prior 20d high) AND (value < 0.7 * adv20) | Yes |
| tight_close_flag | (high - low) < 1.5 * ATR14 | Yes — ATR uses shift(1) |
| range_expansion_flag | (high - low) > 2.0 * ATR14 | Yes |
| accumulation_day | close up, CLV >= 0.65, value >= 1.2 * adv20 | Yes |
| distribution_day | close down, CLV <= 0.35, value >= 1.2 * adv20 | Yes |
| accumulation_day_count_20d | rolling(20).sum() of accumulation_day | Yes |
| distribution_day_count_20d | rolling(20).sum() of distribution_day | Yes |
| net_accumulation_score | accumulation_day_count_20d - distribution_day_count_20d | Yes |

## Section D — Trend Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| ema20 | ewm(span=20).mean().shift(1) | Yes |
| ema50 | ewm(span=50).mean().shift(1) | Yes |
| ema100 | ewm(span=100).mean().shift(1) | Yes |
| ema200 | ewm(span=200).mean().shift(1) | Yes |
| above_ema20/50/100/200 | close > ema_N, binary | Yes |
| cloud_bull_20_100 | ema20 > ema100, binary | Yes |
| ema20_above_ema100 | same as cloud_bull_20_100 | Yes |
| ema50_above_ema200 | ema50 > ema200, binary | Yes |
| distance_to_ema20/50/100 | (close - ema_N) / ema_N | Yes |
| base_tightness_20d | rolling_std(20) / rolling_mean(20) of close | Yes |
| base_tightness_60d | rolling_std(60) / rolling_mean(60) of close | Yes |
| near_high_60d | close / prior_60d_high > 0.95 | Yes |
| near_high_120d | close / prior_120d_high > 0.95 | Yes |
| new_high_60d_flag | close > prior_60d_high | Yes |
| new_high_120d_flag | close > prior_120d_high | Yes |

## Section E — Sector Rotation Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| sector_ret_20d/60d/120d | median of stock ret_Xd within sector on date | Yes |
| sector_rel_vnindex_20d/60d | sector_ret_Xd - VNINDEX ret_Xd | Yes |
| sector_rs_rank_20d/60d | rank of sector_ret_Xd among all sectors on date | Yes |
| sector_breadth_above_ma50 | mean(above_ema50) within sector on date | Yes |
| sector_breadth_above_ma100 | mean(above_ema100) within sector on date | Yes |
| sector_leader_count | count of stocks with rs_rank_market_20d >= 0.8 in sector | Yes |
| sector_breakout_count | count of breakout_volume_flag in sector on date | Yes |
| sector_rotation_score | weighted composite of sector rel-RS, breadth, rank, breakout count | Yes |

## Section F — Market Regime Features (from regime log)

| Feature | Source | Notes |
|---|---|---|
| market_status_combined | regime log | uptrend/correction/downtrend/etc |
| allow_new_buys | regime log | 0/1 flag |
| breadth_pct | regime log | % stocks above MA |
| distribution_count_20d | regime log | distribution day count |
| vnindex_above_ema50/200 | derived from regime log | 0/1 flag |
| vnindex_cloud_bull | ma50 > ma200 from regime log | 0/1 flag |
| market_pct_above_ma50 | same as breadth_pct | 0-100 |
| breadth_regime_bucket | rule-based: BULL_BROAD/NARROW/NEUTRAL/BEAR/STRESS | See bucketing rules |

**Breadth bucket rules:**
- BULL_BROAD: breadth >= 60% AND status contains "uptrend"
- BULL_NARROW: breadth >= 50% AND status contains "uptrend"
- NEUTRAL: breadth >= 40%
- BEAR: breadth >= 30%
- STRESS: breadth < 30%

## Section G — Foreign Flow (NOT AVAILABLE)

Not available in this dataset. All foreign flow features are NaN.
Residual proxy: high value traded without attributable foreign source may indicate
domestic large capital. Labeled as `big_individual_footprint_proxy` — a proxy, not proof.

## Section H — Index/ETF Flow (NOT AVAILABLE)

Not available in this dataset. All index/ETF features are NaN.

## Section I — Fundamental Features (with 45-day lag)

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| revenue_growth_yoy | (revenue_Q / revenue_Q_year_ago) - 1, clipped [-2, 10] | Yes — 45d lag |
| np_growth_yoy | (net_profit_Q / net_profit_Q_year_ago) - 1, clipped [-2, 10] | Yes — 45d lag |
| earnings_acceleration_flag | np_growth_yoy > 0.15 AND > prior quarter | Yes |
| fundamental_quality_score | percentile rank of revenue + NP growth, 40%/60% blend | Yes |

## Composite Scores

### capital_footprint_score_raw
Weights: RS 27.5% | PV 32.5% | Sector 15% | Regime 15% | Liquidity 10%
(Foreign/index flow 15% redistributed to RS and PV since unavailable)
Final score: cross-sectional percentile rank on each date (0-1).

### capital_footprint_score_pure_tech
Weights: RS 30% | PV 30% | Sector 20% | Regime 15% | Liquidity 5%
No FA. Cross-sectional percentile rank.

### big_individual_footprint_proxy
Captures domestic large-money via observable footprints only.
Components: high_value + strong_close (30%) | net_acc + dry_up (25%) | sector_rotation (20%) | tight_close (15%) | up/down ratio (10%)
IMPORTANT: This is a proxy. Cannot confirm account type or identity. Label as PROXY.

## Forward Return Labels (NOT FEATURES)

| Label | Definition | Notes |
|---|---|---|
| fwd_ret_5d | close.shift(-5) / close - 1 | 5-bar forward return |
| fwd_ret_10d | close.shift(-10) / close - 1 | 10-bar |
| fwd_ret_20d | close.shift(-20) / close - 1 | 20-bar (~1 month) |
| fwd_ret_60d | close.shift(-60) / close - 1 | 60-bar (~3 months) |
| fwd_ret_120d | close.shift(-120) / close - 1 | 120-bar (~6 months) |
| fwd_max_gain_20d | max(future high) / close - 1 over 20 bars | Upside potential |
| fwd_max_drawdown_20d | min(future low) / close - 1 over 20 bars | Downside risk |
| fwd_max_gain_60d | max(future high) / close - 1 over 60 bars | |
| fwd_max_drawdown_60d | min(future low) / close - 1 over 60 bars | |
| tp1_18pct_hit_120d | fwd_max_gain_60d >= 0.18 (proxy for TP1 hit) | A3 TP1 proxy |
| fwd_alpha_20d_vs_vnindex | fwd_ret_20d - VNINDEX fwd_ret_20d | Excess return |
| fwd_alpha_60d_vs_vnindex | fwd_ret_60d - VNINDEX fwd_ret_60d | |
| fwd_alpha_120d_vs_vnindex | fwd_ret_120d - VNINDEX fwd_ret_120d | |
