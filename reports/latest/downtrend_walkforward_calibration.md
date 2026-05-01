# Downtrend Walk-forward Calibration

## outcome_B

- n_predictions: 122
- n_skipped: 20
- brier_raw: 0.21172131147540982
- brier_adj: 0.2173251089229432
- auc_raw: 0.7197156138911677
- auc_adj: 0.6992070002734482

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 23 | 0.165217 | 0.347826 |
| 20-40% | 47 | 0.340426 | 0.489362 |
| 40-60% | 23 | 0.53913 | 0.478261 |
| 60-80% | 2 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 7 | 0.363763 | 0.285714 |
| 40-60% | 86 | 0.492425 | 0.465116 |
| 60-80% | 29 | 0.694029 | 0.931034 |



## outcome_B_strict

- n_predictions: 122
- n_skipped: 20
- brier_raw: 0.19131147540983603
- brier_adj: 0.20959952337960341
- auc_raw: 0.7465698143664246
- auc_adj: 0.7156308851224106

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 48 | 0.147917 | 0.291667 |
| 20-40% | 34 | 0.332353 | 0.411765 |
| 40-60% | 13 | 0.523077 | 0.307692 |
| 60-80% | 1 | 0.8 | 1 |
| 80-100% | 26 | 0.992308 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 41 | 0.358268 | 0.341463 |
| 40-60% | 54 | 0.456368 | 0.333333 |
| 60-80% | 27 | 0.653727 | 1 |



## trend_break_20d

- n_predictions: 122
- n_skipped: 20
- brier_raw: 0.1990983606557377
- brier_adj: 0.21285610209132244
- auc_raw: 0.7442830239440409
- auc_adj: 0.7175141242937854

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 39 | 0.15641 | 0.282051 |
| 20-40% | 37 | 0.332432 | 0.486486 |
| 40-60% | 18 | 0.527778 | 0.388889 |
| 60-80% | 1 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 28 | 0.370326 | 0.357143 |
| 40-60% | 67 | 0.476203 | 0.38806 |
| 60-80% | 27 | 0.671982 | 1 |



## confirmed_downtrend_20d

- n_predictions: 122
- n_skipped: 20
- brier_raw: 0.1359016393442623
- brier_adj: 0.12463981577647557
- auc_raw: 0.4507002801120448
- auc_adj: 0.41904761904761906

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 104 | 0.1125 | 0.163462 |
| 20-40% | 18 | 0.316667 | 0 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 106 | 0.135155 | 0.160377 |
| 20-40% | 16 | 0.217916 | 0 |


