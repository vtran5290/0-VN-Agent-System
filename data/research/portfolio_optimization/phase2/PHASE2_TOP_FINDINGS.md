# Phase 2 — Top Findings
Generated: 2026-05-16

## Phase 2A — Clean Baselines

| experiment_id   | strategy   |   max_positions |   n_trades |     cagr |    max_dd |   sharpe |      mar | prod_class           |
|:----------------|:-----------|----------------:|-----------:|---------:|----------:|---------:|---------:|:---------------------|
| A3_pos20        | A3         |              20 |      12909 | 0.136113 | -0.265146 | 1.18284  | 0.513352 | PRODUCTION_CANDIDATE |
| A3_pos15        | A3         |              15 |      12909 | 0.141042 | -0.261755 | 1.14683  | 0.538833 | PRODUCTION_CANDIDATE |
| S3_pos20        | S3         |              20 |      17324 | 0.11907  | -0.273593 | 1.04373  | 0.435208 | PRODUCTION_CANDIDATE |
| S3_pos15        | S3         |              15 |      17324 | 0.117158 | -0.263009 | 0.900844 | 0.445451 | PRODUCTION_CANDIDATE |

## Phase 2B — Dual-Path Scale-in (Top 10 by MAR)

| experiment_id                     | strategy   | mode    |   t1_frac |   pb_depth_pct |   pb_window |   str_thresh_pct |   str_window |   pct_pullback |   pct_strength |   pct_no_add |   mean_net_all |      cagr |    max_dd |   sharpe |      mar | prod_class           |
|:----------------------------------|:-----------|:--------|----------:|---------------:|------------:|-----------------:|-------------:|---------------:|---------------:|-------------:|---------------:|----------:|----------:|---------:|---------:|:---------------------|
| DP_A3_pb_only_t50_pb4w30          | A3         | pb_only |       0.5 |              4 |          30 |              nan |            0 |       0.488261 |       0        |     0.511739 |      0.0731428 | 0.102348  | -0.142222 |  1.36258 | 0.719634 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only_t50_pb5w20          | A3         | pb_only |       0.5 |              5 |          20 |              nan |            0 |       0.327353 |       0        |     0.672647 |      0.0715218 | 0.0863878 | -0.145247 |  1.29346 | 0.594766 | PRODUCTION_CANDIDATE |
| DP_A3_either_t50_pb4w30_str4w20   | A3         | either  |       0.5 |              4 |          30 |                4 |           20 |       0.395017 |       0.475748 |     0.129236 |      0.0611679 | 0.116103  | -0.19572  |  1.20363 | 0.593209 | PRODUCTION_CANDIDATE |
| DP_A3_stack_t40_pb4w30_str4w20_gk | A3         | stack   |       0.4 |              4 |          30 |                4 |           20 |       0.488261 |       0.101661 |     0.433666 |      0.0704269 | 0.0736597 | -0.133635 |  1.26007 | 0.551201 | PRODUCTION_CANDIDATE |
| DP_A3_either_t60_pb4w20_str6w10   | A3         | either  |       0.6 |              4 |          20 |                6 |           10 |       0.394352 |       0.282946 |     0.322702 |      0.064655  | 0.109062  | -0.204862 |  1.22657 | 0.532367 | PRODUCTION_CANDIDATE |
| DP_A3_either_t50_pb4w20_str4w10   | A3         | either  |       0.5 |              4 |          20 |                4 |           10 |       0.368549 |       0.388483 |     0.242968 |      0.0624883 | 0.106659  | -0.212455 |  1.20059 | 0.502029 | PRODUCTION_CANDIDATE |
| DP_A3_either_t60_pb4w30_str4w20   | A3         | either  |       0.6 |              4 |          30 |                4 |           20 |       0.395017 |       0.475748 |     0.129236 |      0.0620005 | 0.112073  | -0.224992 |  1.18045 | 0.498122 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only_t50_pb3w20          | A3         | pb_only |       0.5 |              3 |          20 |              nan |            0 |       0.536434 |       0        |     0.463566 |      0.0722827 | 0.0927586 | -0.206547 |  1.15958 | 0.449093 | PRODUCTION_CANDIDATE |
| DP_A3_stack_t40_pb4w30_str4w20    | A3         | stack   |       0.4 |              4 |          30 |                4 |           20 |       0.488261 |       0.560797 |     0.129236 |      0.0629562 | 0.0813602 | -0.185668 |  1.14688 | 0.438203 | PRODUCTION_CANDIDATE |
| DP_A3_either_t60_pb4w20_str4w10   | A3         | either  |       0.6 |              4 |          20 |                4 |           10 |       0.368549 |       0.388483 |     0.242968 |      0.0631948 | 0.107985  | -0.24752  |  1.20748 | 0.436268 | PRODUCTION_CANDIDATE |

## Phase 2C — A3+GK Overlay

| experiment_id      | strategy   |   gk_window | has_gk      |   n_trades |   coverage_pct |   mean_net |     cagr |    max_dd |   sharpe |      mar | prod_class           |
|:-------------------|:-----------|------------:|:------------|-----------:|---------------:|-----------:|---------:|----------:|---------:|---------:|:---------------------|
| A3_all_size125_w3  | A3         |           3 | gk_priority |      12909 |       1        |  0.0658807 | 0.138324 | -0.245506 | 1.17394  | 0.563422 | PRODUCTION_CANDIDATE |
| A3+GK_w10          | A3         |          10 | True        |       3755 |       0.290882 |  0.0775016 | 0.128532 | -0.23845  | 1.12529  | 0.539031 | PRODUCTION_CANDIDATE |
| A3_all_size125_w5  | A3         |           5 | gk_priority |      12909 |       1        |  0.0658807 | 0.12198  | -0.248558 | 1.04522  | 0.490751 | PRODUCTION_CANDIDATE |
| A3+GK_w5           | A3         |           5 | True        |       2302 |       0.178325 |  0.0685052 | 0.12134  | -0.248756 | 1.09542  | 0.487785 | PRODUCTION_CANDIDATE |
| A3_noGK_w3         | A3         |           3 | False       |      11220 |       0.869161 |  0.0652019 | 0.123725 | -0.278407 | 1.26418  | 0.444404 | PRODUCTION_CANDIDATE |
| A3_all_size125_w10 | A3         |          10 | gk_priority |      12909 |       1        |  0.0658807 | 0.116855 | -0.277243 | 1.11247  | 0.421488 | PRODUCTION_CANDIDATE |
| A3_noGK_w10        | A3         |          10 | False       |       9154 |       0.709118 |  0.0611138 | 0.111959 | -0.266549 | 1.15631  | 0.420029 | PRODUCTION_CANDIDATE |
| S3_noGK_w3         | S3         |           3 | False       |      14587 |       0.842011 |  0.0617987 | 0.101827 | -0.256432 | 0.977194 | 0.397094 | PRODUCTION_CANDIDATE |
| A3_noGK_w5         | A3         |           5 | False       |      10607 |       0.821675 |  0.0653112 | 0.117802 | -0.298737 | 1.20011  | 0.394332 | PRODUCTION_CANDIDATE |
| A3+GK_w3           | A3         |           3 | True        |       1689 |       0.130839 |  0.07039   | 0.10686  | -0.285031 | 0.988401 | 0.374908 | PRODUCTION_CANDIDATE |
| S3+GK_w10          | S3         |          10 | True        |       6011 |       0.346975 |  0.076309  | 0.109929 | -0.312831 | 0.905534 | 0.3514   | SHADOW_TEST          |
| S3+GK_w5           | S3         |           5 | True        |       3732 |       0.215424 |  0.0738158 | 0.088284 | -0.264146 | 0.878057 | 0.334224 | PRODUCTION_CANDIDATE |

**A3+GK bootstrap:** MAR=0.539 at 97.8% percentile of 500 random subsets (mean_random=0.319)

**S3+GK bootstrap:** MAR=0.351 at 79.4% percentile of 500 random subsets (mean_random=0.284)

## Phase 2D — Bad-Year Defense (Top Configs by MAR)

| experiment_id                  | strategy   | defense_type   | config              |   n_blocked |      cagr |    max_dd |   sharpe |      mar | prod_class           |
|:-------------------------------|:-----------|:---------------|:--------------------|------------:|----------:|----------:|---------:|---------:|:---------------------|
| PERF_A3_no_defense             | A3         | perf_window    | no_defense          |           0 | 0.136113  | -0.265146 | 1.18284  | 0.513352 | PRODUCTION_CANDIDATE |
| PERF_S3_no_defense             | S3         | perf_window    | no_defense          |           0 | 0.108367  | -0.223727 | 1.00619  | 0.484374 | PRODUCTION_CANDIDATE |
| PERF_S3_hysteresis_25          | S3         | perf_window    | hysteresis_25       |           0 | 0.108367  | -0.223727 | 1.00619  | 0.484374 | PRODUCTION_CANDIDATE |
| BREADTH_A3_breadth_30_50       | A3         | breadth        | breadth_30_50       |        1940 | 0.117582  | -0.258374 | 1.08588  | 0.455084 | PRODUCTION_CANDIDATE |
| PERF_A3_perf_3m_mild           | A3         | perf_window    | perf_3m_mild        |        1837 | 0.126726  | -0.28034  | 1.20774  | 0.452046 | PRODUCTION_CANDIDATE |
| PERF_A3_perf_3m_firm           | A3         | perf_window    | perf_3m_firm        |        1873 | 0.133731  | -0.300471 | 1.27026  | 0.445072 | SHADOW_TEST          |
| BREADTH_A3_breadth_30_25       | A3         | breadth        | breadth_30_25       |        1975 | 0.114021  | -0.263508 | 1.05791  | 0.432703 | PRODUCTION_CANDIDATE |
| PERF_A3_hysteresis_25          | A3         | perf_window    | hysteresis_25       |        3115 | 0.112392  | -0.265146 | 1.05545  | 0.423888 | PRODUCTION_CANDIDATE |
| BREADTH_A3_breadth_40_25       | A3         | breadth        | breadth_40_25       |        4394 | 0.121644  | -0.300468 | 1.13274  | 0.404846 | SHADOW_TEST          |
| BREADTH_A3_breadth_40_50       | A3         | breadth        | breadth_40_50       |        4355 | 0.119132  | -0.300468 | 1.12234  | 0.396489 | SHADOW_TEST          |
| PERF_S3_perf_3m_mild           | S3         | perf_window    | perf_3m_mild        |        2475 | 0.0997472 | -0.256959 | 0.842376 | 0.388183 | PRODUCTION_CANDIDATE |
| BREADTH_A3_breadth_tiered_firm | A3         | breadth        | breadth_tiered_firm |        6723 | 0.10291   | -0.265286 | 1.0519   | 0.387919 | PRODUCTION_CANDIDATE |

## Phase 2G — Combination Playbooks

| experiment_id           | strategy   | description                                       |   n_trades |      cagr |    max_dd |   sharpe |      mar | prod_class           |
|:------------------------|:-----------|:--------------------------------------------------|-----------:|----------:|----------:|---------:|---------:|:---------------------|
| PB5_A3_gkfilter_w10     | A3         | A3 GK-filter w10 (29% coverage)                   |       3755 | 0.128532  | -0.23845  | 1.12529  | 0.539031 | PRODUCTION_CANDIDATE |
| PB1_A3_pos15            | A3         | A3 pos15 equal-weight                             |      12909 | 0.141042  | -0.261755 | 1.14683  | 0.538833 | PRODUCTION_CANDIDATE |
| PB4_A3_pos15_gk_breadth | A3         | A3 pos15 + GK priority + breadth tiered           |      12909 | 0.124583  | -0.267275 | 1.08184  | 0.466123 | PRODUCTION_CANDIDATE |
| PB2_A3_pos15_gkpriority | A3         | A3 pos15 + GK priority                            |      12909 | 0.110172  | -0.275959 | 0.969807 | 0.399232 | PRODUCTION_CANDIDATE |
| PB1_S3_pos15            | S3         | S3 pos15 equal-weight                             |      17324 | 0.0985659 | -0.254721 | 0.924034 | 0.386956 | PRODUCTION_CANDIDATE |
| PB8_A3S3_combined       | A3+S3      | A3 primary + S3 shadow (no overlap), 25 positions |      26968 | 0.104359  | -0.292891 | 1.11756  | 0.356305 | PRODUCTION_CANDIDATE |
| PB5_S3_gkfilter_w10     | S3         | S3 GK-filter w10 (29% coverage)                   |       6011 | 0.109929  | -0.312831 | 0.905534 | 0.3514   | SHADOW_TEST          |
| PB6_S3_hysteresis       | S3         | S3 pos20 + hysteresis -18%/-10%                   |      17324 | 0.0878755 | -0.255554 | 0.900416 | 0.343863 | PRODUCTION_CANDIDATE |
| PB3_A3_pos15_breadth    | A3         | A3 pos15 + breadth tiered                         |      12909 | 0.106866  | -0.365759 | 0.976569 | 0.292175 | SHADOW_TEST          |
| PB6_A3_hysteresis       | A3         | A3 pos20 + hysteresis -18%/-10%                   |      12909 | 0.0831266 | -0.286432 | 0.801983 | 0.290214 | PRODUCTION_CANDIDATE |
| PB7_A3_full_candidate   | A3         | A3 pos15 + GK + breadth + hysteresis              |      12909 | 0.0729023 | -0.267275 | 0.799036 | 0.272761 | PRODUCTION_CANDIDATE |
| PB4_S3_pos15_gk_breadth | S3         | S3 pos15 + GK priority + breadth tiered           |      17324 | 0.0655239 | -0.35046  | 0.597624 | 0.186965 | SHADOW_TEST          |
| PB7_S3_full_candidate   | S3         | S3 pos15 + GK + breadth + hysteresis              |      17324 | 0.0633207 | -0.35046  | 0.609975 | 0.180679 | SHADOW_TEST          |
| PB3_S3_pos15_breadth    | S3         | S3 pos15 + breadth tiered                         |      17324 | 0.0550001 | -0.338936 | 0.505832 | 0.162273 | SHADOW_TEST          |
| PB2_S3_pos15_gkpriority | S3         | S3 pos15 + GK priority                            |      17324 | 0.0422742 | -0.369935 | 0.444739 | 0.114275 | SHADOW_TEST          |

## Phase 2H — OOS Walk-Forward Summary

**A3:** 93/143 positive-return folds (65.0%), mean net=4.758%, mean hit=64.1%

**S3:** 94/146 positive-return folds (64.4%), mean net=4.332%, mean hit=62.3%

**A3 block-bootstrap:** mean net=6.604% [p10=4.372%, p90=8.717%]

**S3 block-bootstrap:** mean net=6.325% [p10=3.753%, p90=8.595%]

## Phase 2I — Classification Summary

- PRODUCTION_CANDIDATE: 92
- SHADOW_TEST: 23
- RESEARCH_ONLY: 0
- REJECT: 0

## Summary Answers

1. **Best simple production candidate:** PB5_A3_gkfilter_w10

2. **Best shadow-test playbook:** see shadow_test_rules.md

3. **Best defense layer:** see phase2_exposure_scaling_summary.csv

4. **Cloud breadth vs VNINDEX regime:** see phase2_bad_year_defense_summary.csv year breakdown

5. **A3+GK vs random/matched:** see phase2_a3gk_random_subset_test.csv

6. **No-pullback strength-add:** see phase2_scalein_dual_path_trade_quality.csv

