# Downtrend Sensitivity

| test_type | setting | target | n | brier | auc | event_rate |
| --- | --- | --- | --- | --- | --- | --- |
| k_neighbors | k=5 | outcome_B | 123 | 0.20748 | 0.744767 |  |
| k_neighbors | k=10 | outcome_B | 123 | 0.210325 | 0.723564 |  |
| k_neighbors | k=20 | outcome_B | 123 | 0.202785 | 0.731616 |  |
| event_method | nonoverlap_8 | outcome_B_baseline | 143 |  |  | 0.566434 |
| event_method | overlap | outcome_B_baseline | 593 |  |  | 0.524452 |
| event_method | cooldown_5 | outcome_B_baseline | 176 |  |  | 0.556818 |
| event_method | cooldown_10 | outcome_B_baseline | 133 |  |  | 0.578947 |
| dist_rule | thr=-0.002,vol=prev | outcome_B_baseline | 143 |  |  | 0.566434 |
| dist_rule | thr=-0.002,vol=prev_105 | outcome_B_baseline | 181 |  |  | 0.585635 |
| dist_rule | thr=-0.002,vol=ma20 | outcome_B_baseline | 190 |  |  | 0.615789 |
| dist_rule | thr=-0.005,vol=prev | outcome_B_baseline | 213 |  |  | 0.596244 |
| dist_rule | thr=-0.005,vol=prev_105 | outcome_B_baseline | 243 |  |  | 0.588477 |
| dist_rule | thr=-0.005,vol=ma20 | outcome_B_baseline | 236 |  |  | 0.618644 |
| dist_rule | thr=-0.01,vol=prev | outcome_B_baseline | 292 |  |  | 0.589041 |
| dist_rule | thr=-0.01,vol=prev_105 | outcome_B_baseline | 309 |  |  | 0.588997 |
| dist_rule | thr=-0.01,vol=ma20 | outcome_B_baseline | 311 |  |  | 0.598071 |
