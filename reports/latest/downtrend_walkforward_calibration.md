# Downtrend Walk-forward Calibration

## outcome_B

- n_predictions: 123
- n_skipped: 20
- brier_raw: 0.2103252032520325
- brier_adj: 0.2171823261971708
- auc_raw: 0.7235641438539989
- auc_adj: 0.7012882447665056

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 24 | 0.166667 | 0.333333 |
| 20-40% | 47 | 0.340426 | 0.489362 |
| 40-60% | 23 | 0.53913 | 0.478261 |
| 60-80% | 2 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 7 | 0.363763 | 0.285714 |
| 40-60% | 87 | 0.491902 | 0.45977 |
| 60-80% | 29 | 0.694029 | 0.931034 |



## outcome_B_strict

- n_predictions: 123
- n_skipped: 20
- brier_raw: 0.19008130081300809
- brier_adj: 0.20919627522204565
- auc_raw: 0.7478813559322034
- auc_adj: 0.7164989406779662

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 49 | 0.14898 | 0.285714 |
| 20-40% | 34 | 0.332353 | 0.411765 |
| 40-60% | 13 | 0.523077 | 0.307692 |
| 60-80% | 1 | 0.8 | 1 |
| 80-100% | 26 | 0.992308 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 42 | 0.359262 | 0.333333 |
| 40-60% | 54 | 0.456368 | 0.333333 |
| 60-80% | 27 | 0.653727 | 1 |



## trend_break_20d

- n_predictions: 123
- n_skipped: 20
- brier_raw: 0.19780487804878047
- brier_adj: 0.2125513869352264
- auc_raw: 0.7465608465608465
- auc_adj: 0.7187830687830687

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 40 | 0.1575 | 0.275 |
| 20-40% | 37 | 0.332432 | 0.486486 |
| 40-60% | 18 | 0.527778 | 0.388889 |
| 60-80% | 1 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 28 | 0.370326 | 0.357143 |
| 40-60% | 68 | 0.475359 | 0.382353 |
| 60-80% | 27 | 0.671982 | 1 |



## confirmed_downtrend_20d

- n_predictions: 123
- n_skipped: 20
- brier_raw: 0.13487804878048784
- brier_adj: 0.12376798129582701
- auc_raw: 0.4522752497225305
- auc_adj: 0.4200887902330744

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 105 | 0.112381 | 0.161905 |
| 20-40% | 18 | 0.316667 | 0 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 107 | 0.135125 | 0.158879 |
| 20-40% | 16 | 0.217916 | 0 |


