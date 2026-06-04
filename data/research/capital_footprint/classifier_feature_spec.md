# Classifier Feature Specification

**Date:** 2026-05-30
**Version:** Phase 2

---

## 6-Label Phase Classifier

Assigns one of six mutually-exclusive labels per (symbol, date).
Priority: EXTENSION > SUPPLY_ABSORPTION > BREAKOUT_CONFIRMED > BREAKOUT_PENDING > FAILED > NEUTRAL

### Label Definitions

| Label | Conditions | Expected Behavior |
|---|---|---|
| **EXTENSION_DISTRIBUTION_RISK** | distance_to_ema20 > 0.12 OR distribution_cluster_flag=1 OR rs_rank_market_20d >= 0.85 OR (turnover_z_20d > 2.0 AND close_location_value < 0.35) | Mean-reversion risk. Phase 1: IC=-0.025 for composite |
| **SUPPLY_ABSORPTION_SETUP** | dry_up_pullback_flag=1 AND near_high_60d=1 AND NOT extended | Supply exhaustion before potential next leg. Phase 1: IC=+0.011 for dry_up |
| **BREAKOUT_CONFIRMED** | new_high_60d_flag=1 AND breakout_volume_flag=1 AND cloud_bull_20_100=1 AND above_ema50=1 | Institutional-style breakout with volume |
| **BREAKOUT_FOLLOW_THROUGH_PENDING** | new_high_60d_flag=1 AND cloud_bull_20_100=1, NOT full confirmation | Watching for follow-through |
| **FAILED_BREAKOUT** | post_breakout_failure_flag=1 AND NOT extended | Breakout failed, returned below prior high |
| **NEUTRAL** | Default — no condition met | No actionable signal |

---

## Phase-Aware Features

### Existing (from Phase 1, confirmed backward-looking)

| Feature | Source | Lookahead Guard |
|---|---|---|
| dry_up_pullback_flag | close within 8% of 20d high + value < 0.7x ADV20 | .shift(1) on rolling high |
| near_high_60d | close/rolling_max_60d > 0.95 | .shift(1) on rolling max |
| new_high_60d_flag | close > prior 60d high | .shift(1) on rolling max |
| breakout_volume_flag | value > 1.5x ADV50 AND close > prior 60d high | .shift(1) on both |
| cloud_bull_20_100 | EMA20 > EMA100 | .shift(1) on EMA |
| above_ema50 | close > EMA50 | .shift(1) on EMA |
| distance_to_ema20 | (close - EMA20) / EMA20 | .shift(1) on EMA |
| distribution_day_count_20d | down days + high value + low CLV | .shift(1) on rolling |
| net_accumulation_score | acc_days - dist_days (20d) | No shift (accumulation count is contemporaneous) |
| rs_rank_market_20d | pct_change(20) rank vs market | pct_change uses past prices |
| base_tightness_20d | std(close_20d) / mean(close_20d) | .shift(1) on both |

### New Phase 2 Features

| Feature | Formula | Lookahead Guard |
|---|---|---|
| distribution_cluster_flag | distribution_day rolling(10) >= 3 | .shift not needed (distribution_day uses current bar) |
| post_breakout_failure_flag | new_high_60d in past 5 bars AND close < prior_high60 * 0.97 | was_breakout uses .shift(1) |
| dry_up_near_high_with_trend_support | dry_up AND near_high_60d AND cloud_bull | Inherits guards from components |
| pullback_depth_from_high | (close - rolling_high_20d) / rolling_high_20d | .shift(1) on rolling max |
| prior_runup_20d | alias for ret_20d (pct_change(20)) | pct_change uses past prices |
| prior_runup_60d | alias for ret_60d | pct_change uses past prices |

### Forward Return Labels (NOT features)

| Label | Formula | Use |
|---|---|---|
| fwd_ret_5d/20d/60d/120d | shift(-d) / close - 1 | Outcome evaluation only |
| fwd_max_gain_20d/60d | rolling max over next D bars | Classifier event study |
| fwd_max_drawdown_20d/60d | rolling min over next D bars | Risk profiling |
| tp1_18pct_hit_120d | fwd_max_gain_60d >= 0.18 | TP1 hit rate |

---

## Data Quality Notes

- **breadth_pct from regime log**: All NaN in Phase 1. Phase 2 fix: computed from OHLCV panel (% stocks above EMA50).
- **A3 universe**: Phase 2 uses min_adv50_vnd=0 (no filter) to include lower-liquidity A3 stocks.
- **Sector coverage**: sector_map.csv (115 symbols) + FA icbName fallback. Final coverage reported in regime_fixed_validation_report.md.
- **foreign flow**: NOT AVAILABLE. Cannot distinguish accumulation from distribution at account level.
