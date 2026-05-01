# VNINDEX Downtrend Probability V2

## As-of
- asof_date: 2026-04-29
- mode: T10
- event_method: nonoverlap_8
- dist_rule: threshold=-0.002, volume_mode=prev

## Current state classification
- above_ma50: True
- close_vs_ma50: 0.0544797674218358
- ma50_slope_10d: 0.005880568073150405

## Raw analog table (target=outcome_B proxy, k=10)
| event_date | pred_date | close_vs_ma50 | ma50_slope_10d | outcome_B | trend_break_20d | confirmed_downtrend_20d | ret_20d | max_drawdown_20d | distance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2021-10-13 | 2021-10-27 | 0.0505734 | 0.00635904 | False | False | False | 0.0462748 | -0.0018271 | 0.000104881 |
| 2019-02-19 | 2019-03-05 | 0.0706639 | 0.00619468 | False | False | False | -0.00669051 | -0.0279006 | 0.000328988 |
| 2015-05-28 | 2015-06-11 | 0.0418493 | 0.00150879 | False | False | False | 0.070648 | -0.00889769 | 0.000339475 |
| 2017-10-13 | 2017-10-27 | 0.0471754 | 0.0125381 | False | False | False | 0.113283 | -0.0104597 | 0.000421202 |
| 2025-05-19 | 2025-06-02 | 0.0506253 | 0.000402549 | False | False | False | 0.0297613 | -0.0240814 | 0.000439122 |
| 2025-05-07 | 2025-05-21 | 0.0403767 | -0.00144792 | False | False | False | 0.0179736 | -0.0258418 | 0.000481772 |
| 2023-12-27 | 2024-01-11 | 0.0426782 | 0.013814 | False | False | False | 0.0346578 | -0.0133107 | 0.000490777 |
| 2016-04-12 | 2016-04-27 | 0.0393103 | 0.0143296 | False | False | False | 0.0238232 | -0.00671762 | 0.00057903 |
| 2014-07-01 | 2014-07-15 | 0.0494028 | 0.00670387 | False | False | False | 0.0211603 | -0.00604096 | 0.000584414 |
| 2020-11-09 | 2020-11-23 | 0.0648733 | 0.0168025 | False | False | False | 0.0873978 | -0.00932417 | 0.000598437 |


## Probability table
| target | baseline_rate | analog_k_n | raw_analog_p | wilson95_low | wilson95_high | shrinkage_adjusted_p | calibration_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MA50 breach proxy (outcome_B) | 0.570423 | 0/10 | 0 | 0 | 0.27754 | 0.380282 | walk-forward available |
| B strict (2 closes below MA50) | 0.5 | 0/10 | 0 | 0 | 0.27754 | 0.333333 | walk-forward available |
| trend_break_20d | 0.528169 | 0/10 | 0 | 0 | 0.27754 | 0.352113 | walk-forward available |
| confirmed_downtrend_20d | 0.147887 | 0/10 | 0 | 0 | 0.27754 | 0.0985915 | walk-forward available |


## Headline wording (corrected)
- Raw top-10 analog frequency for MA50-breach proxy = 0.0% at T10
- Shrinkage-adjusted MA50-breach proxy risk = 38.0% at T10
- Shrinkage-adjusted confirmed-downtrend risk = 9.9% at T10
- Regime = Yellow

## Calibration summary (walk-forward)
| target | n_predictions | n_skipped | brier_raw | brier_adj | auc_raw | auc_adj |
| --- | --- | --- | --- | --- | --- | --- |
| outcome_B | 122 | 20 | 0.211721 | 0.217325 | 0.719716 | 0.699207 |
| trend_break_20d | 122 | 20 | 0.199098 | 0.212856 | 0.744283 | 0.717514 |
| confirmed_downtrend_20d | 122 | 20 | 0.135902 | 0.12464 | 0.4507 | 0.419048 |

Not a calibrated probability; use as stabilized analog estimate only.

## Calibration buckets (0-20%,20-40%,40-60%,60-80%,80-100%)
### outcome_B (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 7 | 0.363763 | 0.285714 |
| 40-60% | 86 | 0.492425 | 0.465116 |
| 60-80% | 29 | 0.694029 | 0.931034 |

### trend_break_20d (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 28 | 0.370326 | 0.357143 |
| 40-60% | 67 | 0.476203 | 0.38806 |
| 60-80% | 27 | 0.671982 | 1 |

### confirmed_downtrend_20d (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 106 | 0.135155 | 0.160377 |
| 20-40% | 16 | 0.217916 | 0 |



## Breadth context
- breadth_available: True
- breadth_asof: 2026-04-29
- p20_mean: 0.13780635038108255
- p20_median: 0.1255492780916509
- pct_industries_p20_lt_0_2: 0.7560975609756098
- pct_industries_p20_ge_0_4: 0.0
- breadth_fusion: Breadth not fused quantitatively because historical breadth time series is unavailable.
- breadth_statement: Breadth snapshot is constructive but not statistically fused into probability. It should be treated as supporting context, not model evidence.

## Decision layer
- regime: Yellow
- reference_probability_used: 0.09859154929577466
- reference_target_used: confirmed_downtrend_20d
- regime_reason:
  - confirmed_downtrend_20d adjusted probability = 9.9%, below 25% risk threshold
  - outcome_B adjusted probability = 38.0%, so MA50-breach proxy risk remains non-trivial
  - trend_break adjusted probability = 35.2%, so not clean enough for Green
  - Breadth snapshot is constructive but not statistically fused into probability. It should be treated as supporting context, not model evidence.
  - top-10 analog sample has high uncertainty
- mapping_note:
  - Green: confirmed<10%, trend_break<25%, outcome_B<30%, breadth constructive, price above MA20/MA50
  - Yellow: confirmed<20% but trend_break/outcome_B >=30%, or uncertainty high, or breadth contextual only
  - Orange: confirmed 20-40% or trend_break>50% or price below MA50
  - Red: confirmed>40% or confirmed MA50 break + breadth deterioration + rising distribution

## Caveats
- outcome_B is MA50 breach proxy, not a full downtrend definition.
- raw analog probability is not calibrated by itself; use calibration report.
- small sample warnings apply when analog n is low.
