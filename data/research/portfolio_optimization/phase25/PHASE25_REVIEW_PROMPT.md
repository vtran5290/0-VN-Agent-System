# Phase 2.5 Review Prompt
Date: 2026-05-16

## Context

Vietnam EMA-cloud strategy (A3) backtested on HOSE 2012-2025.
Universe: ~272 stocks, equal-weight pos15, TP-trail exit, T+3 settlement.
Baseline (A3_pos15): CAGR=14.1%, MaxDD=-26.2%, MAR=0.54, Sharpe=1.15.

Phase 1 identified: pullback scale-in (d=4%, w=30) produces MAR=0.72 with CAGR=10.2%.
Phase 2 confirmed: A3+GK at 97.8th percentile vs random subsets; defense layers hurt; OOS 65% positive folds.

## Phase 2.5 Tests and Results

### 25A: Exposure-Matched Pullback

| experiment_id            |   avg_exposure |   cagr |   active_cagr |   max_dd |    mar |   worst_year |   worst_return |   blocked_winners |   blocked_losers | prod_class           |
|:-------------------------|---------------:|-------:|--------------:|---------:|-------:|-------------:|---------------:|------------------:|-----------------:|:---------------------|
| DP_A3_pb_only_t50_pb4w30 |         0.6587 | 0.1023 |        0.1554 |  -0.1422 | 0.7196 |         2019 |        -0.0648 |              6159 |             2398 | PRODUCTION_CANDIDATE |
| A3_pos15_exp100          |         0.9865 | 0.1410 |        0.1430 |  -0.2618 | 0.5388 |         2024 |        -0.0772 |              8411 |             4130 | PRODUCTION_CANDIDATE |
| A3_pos15_exp90           |         0.8562 | 0.1185 |        0.1384 |  -0.2399 | 0.4938 |         2024 |        -0.0988 |              8447 |             4143 | PRODUCTION_CANDIDATE |
| A3_pos15_exp70           |         0.6598 | 0.0861 |        0.1305 |  -0.2469 | 0.3487 |         2020 |        -0.0777 |              8496 |             4164 | PRODUCTION_CANDIDATE |
| A3_pos15_exp80           |         0.7909 | 0.0939 |        0.1188 |  -0.2894 | 0.3246 |         2020 |        -0.0933 |              8469 |             4146 | PRODUCTION_CANDIDATE |
| A3_pos15_exp75           |         0.7252 | 0.0851 |        0.1174 |  -0.2781 | 0.3060 |         2018 |        -0.0848 |              8486 |             4154 | PRODUCTION_CANDIDATE |
| A3_pos15_exp60           |         0.5946 | 0.0733 |        0.1233 |  -0.2402 | 0.3054 |         2020 |        -0.1116 |              8515 |             4171 | PRODUCTION_CANDIDATE |
| A3_pos15_exp50           |         0.4636 | 0.0473 |        0.1021 |  -0.2058 | 0.2300 |         2024 |        -0.0787 |              8551 |             4185 | PRODUCTION_CANDIDATE |

### 25B: No-Pullback Strength-Add

| experiment_id            |   pct_pullback |   pct_strength |   pct_no_add |   mean_net_str |   cagr |   max_dd |    mar | prod_class           |
|:-------------------------|---------------:|---------------:|-------------:|---------------:|-------:|---------:|-------:|:---------------------|
| PTS_A3_pb4w30_str6w10    |         0.4883 |         0.2864 |       0.2254 |         0.1170 | 0.1021 |  -0.1334 | 0.7654 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10_gk |         0.4883 |         0.0107 |       0.5010 |         0.0805 | 0.0992 |  -0.1396 | 0.7104 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w10_gk |         0.4883 |         0.0128 |       0.4989 |         0.0713 | 0.0979 |  -0.1396 | 0.7009 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w10    |         0.4883 |         0.3122 |       0.1996 |         0.1134 | 0.0974 |  -0.1635 | 0.5959 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w20    |         0.4883 |         0.3410 |       0.1708 |         0.1090 | 0.0795 |  -0.1962 | 0.4052 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w20    |         0.4883 |         0.3173 |       0.1945 |         0.1126 | 0.0760 |  -0.1902 | 0.3999 | PRODUCTION_CANDIDATE |

### 25C: GK Usage Modes

| experiment_id         | description                                                |   coverage_pct |   cagr |   active_cagr |   max_dd |    mar | prod_class           |
|:----------------------|:-----------------------------------------------------------|---------------:|-------:|--------------:|---------:|-------:|:---------------------|
| GK_size_mult_1p25_w10 | GK size mult 1.25x for has_gk_w10 trades (full universe)   |         0.2909 | 0.1420 |        0.1446 |  -0.2420 | 0.5867 | PRODUCTION_CANDIDATE |
| GK_fill_priority_w3   | GK fill priority w3 (all trades, GK enter first)           |         1.0000 | 0.1383 |        0.1383 |  -0.2455 | 0.5634 | PRODUCTION_CANDIDATE |
| GK_hard_filter_w10    | Hard filter: only GK-confirmed trades w10 (29% coverage)   |         0.2909 | 0.1285 |        0.4419 |  -0.2385 | 0.5390 | PRODUCTION_CANDIDATE |
| A3_pos15_baseline     | A3 pos15 equal-weight baseline                             |         1.0000 | 0.1410 |        0.1410 |  -0.2618 | 0.5388 | PRODUCTION_CANDIDATE |
| GK_add_trigger_w10    | GK add-trigger: T1=50% on signal, T2=50% when GK fires w10 |         0.0784 | 0.0596 |        0.1199 |  -0.1478 | 0.4036 | PRODUCTION_CANDIDATE |

### 25D: Bad-Year Diagnostics

| label                |   year |   annual_return |   n_trades |   hit_rate |   tp_trail_rate |   avg_exposure |   missed_winners |
|:---------------------|-------:|----------------:|-----------:|-----------:|----------------:|---------------:|-----------------:|
| A3_GK_hardfilter_w10 |   2018 |          0.0210 |        232 |     0.5776 |          1.0000 |         0.9638 |         nan      |
| A3_pos15             |   2018 |         -0.0620 |        865 |     0.5237 |          0.9988 |         0.9990 |         nan      |
| A3_pos15_exp75       |   2018 |         -0.0848 |        865 |     0.5237 |          0.9988 |         0.7323 |         nan      |
| A3_pos15_gk_priority |   2018 |         -0.1070 |        865 |     0.5237 |          0.9988 |         0.9990 |         nan      |
| DP_A3_pb_only        |   2018 |         -0.0141 |        486 |     0.5329 |          0.9979 |         0.6416 |         116.0000 |
| A3_GK_hardfilter_w10 |   2019 |         -0.0896 |        205 |     0.4293 |          0.9707 |         0.9807 |         nan      |
| A3_pos15             |   2019 |         -0.0436 |        943 |     0.5122 |          0.9745 |         1.0000 |         nan      |
| A3_pos15_exp75       |   2019 |         -0.0520 |        943 |     0.5122 |          0.9745 |         0.7333 |         nan      |
| A3_pos15_gk_priority |   2019 |         -0.0328 |        943 |     0.5122 |          0.9745 |         1.0000 |         nan      |
| DP_A3_pb_only        |   2019 |         -0.0648 |        593 |     0.5228 |          0.9815 |         0.7345 |         170.0000 |
| A3_GK_hardfilter_w10 |   2022 |         -0.0211 |        240 |     0.4125 |          0.9958 |         0.9454 |         nan      |
| A3_pos15             |   2022 |          0.0704 |        705 |     0.3617 |          0.9957 |         0.9905 |         nan      |
| A3_pos15_exp75       |   2022 |          0.0823 |        705 |     0.3617 |          0.9957 |         0.7272 |         nan      |
| A3_pos15_gk_priority |   2022 |          0.0977 |        705 |     0.3617 |          0.9957 |         0.9905 |         nan      |
| DP_A3_pb_only        |   2022 |          0.0932 |        342 |     0.4064 |          0.9971 |         0.6462 |          79.0000 |

### 25E: Cost / Liquidity Sensitivity

| experiment_id   |   cost_pct |   n_trades |   cagr |   max_dd |    mar | prod_class           |
|:----------------|-----------:|-----------:|-------:|---------:|-------:|:---------------------|
| COST2bps        |     0.2000 |      12909 | 0.1448 |  -0.2568 | 0.5640 | PRODUCTION_CANDIDATE |
| COST4bps        |     0.4000 |      12909 | 0.1410 |  -0.2618 | 0.5388 | PRODUCTION_CANDIDATE |
| COST6bps        |     0.6000 |      12909 | 0.1373 |  -0.2667 | 0.5148 | PRODUCTION_CANDIDATE |

## Questions for Reviewer

1. **Exposure test:** Does DP_A3_pb_only earn its MAR beyond mere exposure reduction? Is active_CAGR (CAGR/avg_exposure) higher for DP than for capped A3?

2. **Strength-add:** Does the pb_then_str mode close the gap on no-pullback winners without degrading pullback returns? Best strength threshold: +4% or +6%?

3. **GK usage:** Which mode gives the best MAR without excessive coverage loss? Is GK add-trigger better than hard filter?

4. **Bad years:** Does any candidate collapse in 2018 or 2022? Do the bad years reflect strategy weakness or Vietnam market structure?

5. **Liquidity:** At 5B VND ADV floor, what is the MAR delta? Is the strategy universe realistic for 20B VND portfolio?

6. **Phase 3 recommendation:** Which 1-2 candidates should enter live paper trade? State required conditions (min MAR, max drawdown, OOS requirement).

## Classification criteria

- PRODUCTION_CANDIDATE: MAR ≥ 0.50, MaxDD ≥ -30%, 65%+ OOS positive folds, no collapse year, cost/liq robust
- SHADOW_TEST: MAR 0.40-0.50, marginal on one dimension
- RESEARCH_ONLY: MAR < 0.40 or fails liquidity
- REJECT: exposure artifact, one-year driven, or OOS fails

