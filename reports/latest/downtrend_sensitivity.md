# Downtrend Sensitivity

| test_type | setting | target | n | brier | auc | event_rate |
| --- | --- | --- | --- | --- | --- | --- |
| k_neighbors | k=5 | outcome_B | 122 | 0.20918 | 0.740771 |  |
| k_neighbors | k=10 | outcome_B | 122 | 0.211721 | 0.719716 |  |
| k_neighbors | k=20 | outcome_B | 122 | 0.203709 | 0.72915 |  |
| event_method | nonoverlap_8 | outcome_B_baseline | 142 |  |  | 0.570423 |
| event_method | overlap | outcome_B_baseline | 585 |  |  | 0.531624 |
| event_method | cooldown_5 | outcome_B_baseline | 174 |  |  | 0.563218 |
| event_method | cooldown_10 | outcome_B_baseline | 132 |  |  | 0.583333 |
| dist_rule | thr=-0.002,vol=prev | outcome_B_baseline | 142 |  |  | 0.570423 |
| dist_rule | thr=-0.002,vol=prev_105 | outcome_B_baseline | 180 |  |  | 0.588889 |
| dist_rule | thr=-0.002,vol=ma20 | outcome_B_baseline | 188 |  |  | 0.617021 |
| dist_rule | thr=-0.005,vol=prev | outcome_B_baseline | 212 |  |  | 0.599057 |
| dist_rule | thr=-0.005,vol=prev_105 | outcome_B_baseline | 242 |  |  | 0.590909 |
| dist_rule | thr=-0.005,vol=ma20 | outcome_B_baseline | 234 |  |  | 0.619658 |
| dist_rule | thr=-0.01,vol=prev | outcome_B_baseline | 290 |  |  | 0.589655 |
| dist_rule | thr=-0.01,vol=prev_105 | outcome_B_baseline | 307 |  |  | 0.589577 |
| dist_rule | thr=-0.01,vol=ma20 | outcome_B_baseline | 309 |  |  | 0.598706 |
