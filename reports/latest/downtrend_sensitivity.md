# Downtrend Sensitivity

| test_type | setting | target | n | brier | auc | event_rate |
| --- | --- | --- | --- | --- | --- | --- |
| k_neighbors | k=5 | outcome_B | 124 | 0.205806 | 0.748617 |  |
| k_neighbors | k=10 | outcome_B | 124 | 0.208952 | 0.727273 |  |
| k_neighbors | k=20 | outcome_B | 124 | 0.201472 | 0.735441 |  |
| event_method | nonoverlap_8 | outcome_B_baseline | 144 |  |  | 0.5625 |
| event_method | overlap | outcome_B_baseline | 599 |  |  | 0.519199 |
| event_method | cooldown_5 | outcome_B_baseline | 177 |  |  | 0.553672 |
| event_method | cooldown_10 | outcome_B_baseline | 134 |  |  | 0.574627 |
| dist_rule | thr=-0.002,vol=prev | outcome_B_baseline | 144 |  |  | 0.5625 |
| dist_rule | thr=-0.002,vol=prev_105 | outcome_B_baseline | 182 |  |  | 0.582418 |
| dist_rule | thr=-0.002,vol=ma20 | outcome_B_baseline | 191 |  |  | 0.612565 |
| dist_rule | thr=-0.005,vol=prev | outcome_B_baseline | 214 |  |  | 0.593458 |
| dist_rule | thr=-0.005,vol=prev_105 | outcome_B_baseline | 244 |  |  | 0.586066 |
| dist_rule | thr=-0.005,vol=ma20 | outcome_B_baseline | 237 |  |  | 0.616034 |
| dist_rule | thr=-0.01,vol=prev | outcome_B_baseline | 293 |  |  | 0.587031 |
| dist_rule | thr=-0.01,vol=prev_105 | outcome_B_baseline | 310 |  |  | 0.587097 |
| dist_rule | thr=-0.01,vol=ma20 | outcome_B_baseline | 312 |  |  | 0.596154 |
