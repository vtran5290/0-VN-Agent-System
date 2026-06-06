# VNINDEX Downtrend Probability V2

## As-of
- asof_date: 2026-06-05
- mode: T10
- event_method: nonoverlap_8
- dist_rule: threshold=-0.002, volume_mode=prev

## Current state classification
- above_ma50: True
- close_vs_ma50: 0.010486219218745596
- ma50_slope_10d: 0.019357072775298523

## Raw analog table (target=outcome_B proxy, k=10)
| event_date | pred_date | close_vs_ma50 | ma50_slope_10d | outcome_B | trend_break_20d | confirmed_downtrend_20d | ret_20d | max_drawdown_20d | distance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-04-04 | 2018-04-18 | 0.00695323 | 0.0159003 | True | True | True | -0.108517 | -0.118346 | 0.000137591 |
| 2020-10-14 | 2020-10-28 | 0.0154353 | 0.0222657 | False | False | False | 0.0856522 | -0.0106943 | 0.000145883 |
| 2018-09-26 | 2018-10-10 | 0.00782137 | 0.0146689 | True | True | True | -0.0722363 | -0.113797 | 0.000216713 |
| 2024-03-28 | 2024-04-11 | 0.0135042 | 0.0161858 | True | True | True | -0.00302814 | -0.0732872 | 0.000241152 |
| 2023-08-15 | 2023-08-29 | 0.0199146 | 0.0144813 | True | True | False | -0.0431739 | -0.064819 | 0.000398563 |
| 2017-06-26 | 2017-07-10 | 0.0237048 | 0.0166413 | False | False | False | 0.0344657 | -0.0166197 | 0.000527364 |
| 2016-10-13 | 2016-10-27 | 0.0060422 | 0.0104005 | True | True | False | 0.00189097 | -0.0298715 | 0.000528236 |
| 2014-09-03 | 2014-09-17 | 0.0267767 | 0.017442 | True | True | False | -0.0341559 | -0.0503628 | 0.000619516 |
| 2023-01-18 | 2023-02-08 | 0.0238139 | 0.0267135 | True | True | False | -0.0214881 | -0.0548861 | 0.000704118 |
| 2017-02-15 | 2017-03-01 | 0.0300864 | 0.0157001 | False | False | False | 0.015433 | -0.0052007 | 0.000995743 |


## Probability table
| target | baseline_rate | analog_k_n | raw_analog_p | wilson95_low | wilson95_high | shrinkage_adjusted_p | calibration_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MA50 breach proxy (outcome_B) | 0.5625 | 7/10 | 0.7 | 0.396773 | 0.892211 | 0.608333 | walk-forward available |
| B strict (2 closes below MA50) | 0.493056 | 7/10 | 0.7 | 0.396773 | 0.892211 | 0.562037 | walk-forward available |
| trend_break_20d | 0.520833 | 7/10 | 0.7 | 0.396773 | 0.892211 | 0.580556 | walk-forward available |
| confirmed_downtrend_20d | 0.145833 | 3/10 | 0.3 | 0.107789 | 0.603227 | 0.197222 | walk-forward available |


## Headline wording (corrected)
- Raw top-10 analog frequency for MA50-breach proxy = 70.0% at T10
- Shrinkage-adjusted MA50-breach proxy risk = 60.8% at T10
- Shrinkage-adjusted confirmed-downtrend risk = 19.7% at T10
- Regime = Orange

## Calibration summary (walk-forward)
| target | n_predictions | n_skipped | brier_raw | brier_adj | auc_raw | auc_adj |
| --- | --- | --- | --- | --- | --- | --- |
| outcome_B | 124 | 20 | 0.208952 | 0.217023 | 0.727273 | 0.703821 |
| trend_break_20d | 124 | 20 | 0.196532 | 0.212235 | 0.748764 | 0.720271 |
| confirmed_downtrend_20d | 124 | 20 | 0.133871 | 0.122909 | 0.453821 | 0.421111 |

Not a calibrated probability; use as stabilized analog estimate only.

## Calibration buckets (0-20%,20-40%,40-60%,60-80%,80-100%)
### outcome_B (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 7 | 0.363763 | 0.285714 |
| 40-60% | 88 | 0.491361 | 0.454545 |
| 60-80% | 29 | 0.694029 | 0.931034 |

### trend_break_20d (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 28 | 0.370326 | 0.357143 |
| 40-60% | 69 | 0.474503 | 0.376812 |
| 60-80% | 27 | 0.671982 | 1 |

### confirmed_downtrend_20d (adjusted)
| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 108 | 0.135089 | 0.157407 |
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
- regime: Orange
- reference_probability_used: 0.19722222222222224
- reference_target_used: confirmed_downtrend_20d
- regime_reason:
  - confirmed_downtrend_20d adjusted probability = 19.7%, below 25% risk threshold
  - outcome_B adjusted probability = 60.8%, so MA50-breach proxy risk remains non-trivial
  - trend_break adjusted probability = 58.1%, so not clean enough for Green
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
