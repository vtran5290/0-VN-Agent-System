# VNINDEX Downtrend Probability V2

## As-of
- asof_date: 2026-05-17
- mode: T10
- event_method: nonoverlap_8
- dist_rule: threshold=-0.002, volume_mode=prev

## Current state classification
- above_ma50: True
- close_vs_ma50: 0.0861529069964615
- ma50_slope_10d: 0.006183331496339761

## Raw analog table (target=outcome_B proxy, k=10)
| event_date | pred_date | close_vs_ma50 | ma50_slope_10d | outcome_B | trend_break_20d | confirmed_downtrend_20d | ret_20d | max_drawdown_20d | distance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-02-19 | 2019-03-05 | 0.0706639 | 0.00619468 | False | False | False | -0.00669051 | -0.0279006 | 0.000266033 |
| 2020-05-14 | 2020-05-28 | 0.114744 | 0.00513596 | False | False | False | -0.00789422 | -0.0335736 | 0.00101447 |
| 2024-02-19 | 2024-03-04 | 0.0750612 | 0.0208715 | False | False | False | 0.0159425 | -0.0315044 | 0.00111326 |
| 2020-11-09 | 2020-11-23 | 0.0648733 | 0.0168025 | False | False | False | 0.0873978 | -0.00932417 | 0.00119007 |
| 2021-10-13 | 2021-10-27 | 0.0505734 | 0.00635904 | False | False | False | 0.0462748 | -0.0018271 | 0.0012809 |
| 2025-05-19 | 2025-06-02 | 0.0506253 | 0.000402549 | False | False | False | 0.0297613 | -0.0240814 | 0.00141324 |
| 2014-07-01 | 2014-07-15 | 0.0494028 | 0.00670387 | False | False | False | 0.0211603 | -0.00604096 | 0.00145778 |
| 2023-07-18 | 2023-08-01 | 0.0737275 | 0.0238067 | True | True | False | -0.0107839 | -0.0562026 | 0.00147421 |
| 2014-08-20 | 2014-09-05 | 0.061524 | 0.0205638 | True | True | False | -0.0424333 | -0.0696782 | 0.00147937 |
| 2020-11-26 | 2020-12-10 | 0.0711445 | 0.0239781 | False | False | False | 0.132679 | -0.000824514 | 0.00149453 |


## Probability table
| target | baseline_rate | analog_k_n | raw_analog_p | wilson95_low | wilson95_high | shrinkage_adjusted_p | calibration_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MA50 breach proxy (outcome_B) | 0.570423 | 2/10 | 0.2 | 0.0566809 | 0.509843 | 0.446948 | walk-forward available |
| B strict (2 closes below MA50) | 0.5 | 1/10 | 0.1 | 0.0178757 | 0.404156 | 0.366667 | walk-forward available |
| trend_break_20d | 0.528169 | 2/10 | 0.2 | 0.0566809 | 0.509843 | 0.418779 | walk-forward available |
| confirmed_downtrend_20d | 0.147887 | 0/10 | 0 | 0 | 0.27754 | 0.0985915 | walk-forward available |


## Headline wording (corrected)
- Raw top-10 analog frequency for MA50-breach proxy = 20.0% at T10
- Shrinkage-adjusted MA50-breach proxy risk = 44.7% at T10
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
  - outcome_B adjusted probability = 44.7%, so MA50-breach proxy risk remains non-trivial
  - trend_break adjusted probability = 41.9%, so not clean enough for Green
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
