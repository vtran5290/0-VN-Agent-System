# Downtrend Walk-forward Calibration

## outcome_B

- n_predictions: 124
- n_skipped: 20
- brier_raw: 0.20895161290322578
- brier_adj: 0.21702273288005872
- auc_raw: 0.7272727272727273
- auc_adj: 0.7038208168642951

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 25 | 0.168 | 0.32 |
| 20-40% | 47 | 0.340426 | 0.489362 |
| 40-60% | 23 | 0.53913 | 0.478261 |
| 60-80% | 2 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 7 | 0.363763 | 0.285714 |
| 40-60% | 88 | 0.491361 | 0.454545 |
| 60-80% | 29 | 0.694029 | 0.931034 |



## outcome_B_strict

- n_predictions: 124
- n_skipped: 20
- brier_raw: 0.18887096774193543
- brier_adj: 0.208784536161441
- auc_raw: 0.7491525423728813
- auc_adj: 0.717470664928292

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 50 | 0.15 | 0.28 |
| 20-40% | 34 | 0.332353 | 0.411765 |
| 40-60% | 13 | 0.523077 | 0.307692 |
| 60-80% | 1 | 0.8 | 1 |
| 80-100% | 26 | 0.992308 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 43 | 0.360155 | 0.325581 |
| 40-60% | 54 | 0.456368 | 0.333333 |
| 60-80% | 27 | 0.653727 | 1 |



## trend_break_20d

- n_predictions: 124
- n_skipped: 20
- brier_raw: 0.1965322580645161
- brier_adj: 0.21223500363796735
- auc_raw: 0.7487639864689045
- auc_adj: 0.7202706219099662

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 41 | 0.158537 | 0.268293 |
| 20-40% | 37 | 0.332432 | 0.486486 |
| 40-60% | 18 | 0.527778 | 0.388889 |
| 60-80% | 1 | 0.7 | 0 |
| 80-100% | 27 | 0.988889 | 1 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 20-40% | 28 | 0.370326 | 0.357143 |
| 40-60% | 69 | 0.474503 | 0.376812 |
| 60-80% | 27 | 0.671982 | 1 |



## confirmed_downtrend_20d

- n_predictions: 124
- n_skipped: 20
- brier_raw: 0.13387096774193552
- brier_adj: 0.1229087454661151
- auc_raw: 0.45382078064870807
- auc_adj: 0.4211105002748763

### Calibration buckets (raw)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 106 | 0.112264 | 0.160377 |
| 20-40% | 18 | 0.316667 | 0 |


### Calibration buckets (adjusted)

| bucket | n | pred_mean | obs_rate |
| --- | --- | --- | --- |
| 0-20% | 108 | 0.135089 | 0.157407 |
| 20-40% | 16 | 0.217916 | 0 |


