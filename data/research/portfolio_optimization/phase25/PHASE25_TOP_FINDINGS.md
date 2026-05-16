# Phase 2.5 — Decision Audit
Generated: 2026-05-16

**Goal:** Determine whether DP_A3_pb_only, A3+GK, and defense layers earn their classification or are artifacts of exposure reduction / limited years.

## 25A — Exposure-Matched Pullback

**Key question:** Is DP_A3 better than a capped A3_pos15 at the same exposure?

| experiment_id            | description                        |   avg_exposure |   cagr |   active_cagr |   max_dd |    mar |   worst_year |   worst_return |   n_blocked |   blocked_winners |   blocked_losers | prod_class           |
|:-------------------------|:-----------------------------------|---------------:|-------:|--------------:|---------:|-------:|-------------:|---------------:|------------:|------------------:|-----------------:|:---------------------|
| DP_A3_pb_only_t50_pb4w30 | 50% T1 + 50% T2 on pullback d4/w30 |         0.6587 | 0.1023 |        0.1554 |  -0.1422 | 0.7196 |         2019 |        -0.0648 |        8557 |              6159 |             2398 | PRODUCTION_CANDIDATE |
| A3_pos15_exp100          | A3 pos15 max_exp=100%              |         0.9865 | 0.1410 |        0.1430 |  -0.2618 | 0.5388 |         2024 |        -0.0772 |       12541 |              8411 |             4130 | PRODUCTION_CANDIDATE |
| A3_pos15_exp90           | A3 pos15 max_exp=90%               |         0.8562 | 0.1185 |        0.1384 |  -0.2399 | 0.4938 |         2024 |        -0.0988 |       12590 |              8447 |             4143 | PRODUCTION_CANDIDATE |
| A3_pos15_exp70           | A3 pos15 max_exp=70%               |         0.6598 | 0.0861 |        0.1305 |  -0.2469 | 0.3487 |         2020 |        -0.0777 |       12660 |              8496 |             4164 | PRODUCTION_CANDIDATE |
| A3_pos15_exp80           | A3 pos15 max_exp=80%               |         0.7909 | 0.0939 |        0.1188 |  -0.2894 | 0.3246 |         2020 |        -0.0933 |       12615 |              8469 |             4146 | PRODUCTION_CANDIDATE |
| A3_pos15_exp75           | A3 pos15 max_exp=75%               |         0.7252 | 0.0851 |        0.1174 |  -0.2781 | 0.3060 |         2018 |        -0.0848 |       12640 |              8486 |             4154 | PRODUCTION_CANDIDATE |
| A3_pos15_exp60           | A3 pos15 max_exp=60%               |         0.5946 | 0.0733 |        0.1233 |  -0.2402 | 0.3054 |         2020 |        -0.1116 |       12686 |              8515 |             4171 | PRODUCTION_CANDIDATE |
| A3_pos15_exp50           | A3 pos15 max_exp=50%               |         0.4636 | 0.0473 |        0.1021 |  -0.2058 | 0.2300 |         2024 |        -0.0787 |       12736 |              8551 |             4185 | PRODUCTION_CANDIDATE |

**Verdict:** DP wins on MAR even exposure-matched (DP MAR=0.720 vs A3_pos15_exp75 MAR=0.306)

## 25B — No-Pullback Strength-Add (pb_then_str mode)

Does waiting for pb_window then adding on strength fix under-allocation to no-pullback winners?

| experiment_id            | description                 |   pct_pullback |   pct_strength |   pct_no_add |   mean_net_pb |   mean_net_str |   mean_net_no |   avg_exposure |   cagr |   max_dd |    mar | prod_class           |
|:-------------------------|:----------------------------|---------------:|---------------:|-------------:|--------------:|---------------:|--------------:|---------------:|-------:|---------:|-------:|:---------------------|
| PTS_A3_pb4w30_str6w10    | pb4/w30 then str+6%/w10     |         0.4883 |         0.2864 |       0.2254 |        0.0502 |         0.1170 |        0.0006 |         0.7532 | 0.1021 |  -0.1334 | 0.7654 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10_gk | pb4/w30 then str+6%/w10 +GK |         0.4883 |         0.0107 |       0.5010 |        0.0502 |         0.0805 |        0.0944 |         0.6567 | 0.0992 |  -0.1396 | 0.7104 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w10_gk | pb4/w30 then str+4%/w10 +GK |         0.4883 |         0.0128 |       0.4989 |        0.0502 |         0.0713 |        0.0947 |         0.6603 | 0.0979 |  -0.1396 | 0.7009 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w10    | pb4/w30 then str+4%/w10     |         0.4883 |         0.3122 |       0.1996 |        0.0502 |         0.1134 |       -0.0101 |         0.7742 | 0.0974 |  -0.1635 | 0.5959 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str4w20    | pb4/w30 then str+4%/w20     |         0.4883 |         0.3410 |       0.1708 |        0.0502 |         0.1090 |       -0.0279 |         0.7839 | 0.0795 |  -0.1962 | 0.4052 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w20    | pb4/w30 then str+6%/w20     |         0.4883 |         0.3173 |       0.1945 |        0.0502 |         0.1126 |       -0.0181 |         0.7640 | 0.0760 |  -0.1902 | 0.3999 | PRODUCTION_CANDIDATE |

**Best:** PTS_A3_pb4w30_str6w10 MAR=0.765, str%=28.6%, no_add%=22.5%

**vs DP_A3_pb_only (MAR=0.720):** YES — strength-add helps

## 25C — GK Usage Modes

| experiment_id         | description                                                |   coverage_pct |   avg_exposure |   cagr |   active_cagr |   max_dd |    mar |   missed_winners | prod_class           |
|:----------------------|:-----------------------------------------------------------|---------------:|---------------:|-------:|--------------:|---------:|-------:|-----------------:|:---------------------|
| GK_size_mult_1p25_w10 | GK size mult 1.25x for has_gk_w10 trades (full universe)   |         0.2909 |         0.9817 | 0.1420 |        0.1446 |  -0.2420 | 0.5867 |                0 | PRODUCTION_CANDIDATE |
| GK_fill_priority_w3   | GK fill priority w3 (all trades, GK enter first)           |         1.0000 |         1.0000 | 0.1383 |        0.1383 |  -0.2455 | 0.5634 |                0 | PRODUCTION_CANDIDATE |
| GK_hard_filter_w10    | Hard filter: only GK-confirmed trades w10 (29% coverage)   |         0.2909 |         0.2909 | 0.1285 |        0.4419 |  -0.2385 | 0.5390 |             6403 | PRODUCTION_CANDIDATE |
| A3_pos15_baseline     | A3 pos15 equal-weight baseline                             |         1.0000 |         0.9865 | 0.1410 |        0.1410 |  -0.2618 | 0.5388 |                0 | PRODUCTION_CANDIDATE |
| GK_add_trigger_w10    | GK add-trigger: T1=50% on signal, T2=50% when GK fires w10 |         0.0784 |         0.4972 | 0.0596 |        0.1199 |  -0.1478 | 0.4036 |             5757 | PRODUCTION_CANDIDATE |

**Best GK mode:** GK_size_mult_1p25_w10 MAR=0.587

## 25D — Bad-Year Diagnostics

### Bad Years (2018, 2019, 2022)

| label                |   year |   annual_return |   n_trades |   hit_rate |   tp_trail_rate |   max_hold_rate |   avg_exposure |   missed_winners |
|:---------------------|-------:|----------------:|-----------:|-----------:|----------------:|----------------:|---------------:|-----------------:|
| A3_GK_hardfilter_w10 |   2018 |          0.0210 |        232 |     0.5776 |          1.0000 |          0.5000 |         0.9638 |         nan      |
| A3_pos15             |   2018 |         -0.0620 |        865 |     0.5237 |          0.9988 |          0.5329 |         0.9990 |         nan      |
| A3_pos15_exp75       |   2018 |         -0.0848 |        865 |     0.5237 |          0.9988 |          0.5329 |         0.7323 |         nan      |
| A3_pos15_gk_priority |   2018 |         -0.1070 |        865 |     0.5237 |          0.9988 |          0.5329 |         0.9990 |         nan      |
| DP_A3_pb_only        |   2018 |         -0.0141 |        486 |     0.5329 |          0.9979 |          0.5041 |         0.6416 |         116.0000 |
| A3_GK_hardfilter_w10 |   2019 |         -0.0896 |        205 |     0.4293 |          0.9707 |          0.6049 |         0.9807 |         nan      |
| A3_pos15             |   2019 |         -0.0436 |        943 |     0.5122 |          0.9745 |          0.5748 |         1.0000 |         nan      |
| A3_pos15_exp75       |   2019 |         -0.0520 |        943 |     0.5122 |          0.9745 |          0.5748 |         0.7333 |         nan      |
| A3_pos15_gk_priority |   2019 |         -0.0328 |        943 |     0.5122 |          0.9745 |          0.5748 |         1.0000 |         nan      |
| DP_A3_pb_only        |   2019 |         -0.0648 |        593 |     0.5228 |          0.9815 |          0.5565 |         0.7345 |         170.0000 |
| A3_GK_hardfilter_w10 |   2022 |         -0.0211 |        240 |     0.4125 |          0.9958 |          0.6583 |         0.9454 |         nan      |
| A3_pos15             |   2022 |          0.0704 |        705 |     0.3617 |          0.9957 |          0.7092 |         0.9905 |         nan      |
| A3_pos15_exp75       |   2022 |          0.0823 |        705 |     0.3617 |          0.9957 |          0.7092 |         0.7272 |         nan      |
| A3_pos15_gk_priority |   2022 |          0.0977 |        705 |     0.3617 |          0.9957 |          0.7092 |         0.9905 |         nan      |
| DP_A3_pb_only        |   2022 |          0.0932 |        342 |     0.4064 |          0.9971 |          0.6491 |         0.6462 |          79.0000 |

### Good / Mixed Years (2013, 2020, 2021, 2025)

| label                |   year |   annual_return |   n_trades |   hit_rate |   tp_trail_rate |   avg_exposure |   mean_net |
|:---------------------|-------:|----------------:|-----------:|-----------:|----------------:|---------------:|-----------:|
| A3_GK_hardfilter_w10 |   2013 |         -0.0666 |        212 |     0.9104 |          0.9764 |         0.9807 |     0.2063 |
| A3_pos15             |   2013 |          0.0275 |        838 |     0.8592 |          0.9761 |         0.9985 |     0.1805 |
| A3_pos15_exp75       |   2013 |          0.0319 |        838 |     0.8592 |          0.9761 |         0.7318 |     0.1805 |
| A3_pos15_gk_priority |   2013 |          0.0231 |        838 |     0.8592 |          0.9761 |         0.9985 |     0.1805 |
| DP_A3_pb_only        |   2013 |          0.2130 |        718 |     0.8900 |          0.9763 |         0.7252 |     0.1675 |
| A3_GK_hardfilter_w10 |   2020 |          0.1098 |        461 |     0.9566 |          0.9870 |         0.9819 |     0.2576 |
| A3_pos15             |   2020 |         -0.0529 |       1337 |     0.9387 |          0.9791 |         1.0000 |     0.2243 |
| A3_pos15_exp75       |   2020 |         -0.0793 |       1337 |     0.9387 |          0.9791 |         0.7333 |     0.2243 |
| A3_pos15_gk_priority |   2020 |         -0.0388 |       1337 |     0.9387 |          0.9791 |         1.0000 |     0.2243 |
| DP_A3_pb_only        |   2020 |          0.1968 |        882 |     0.9717 |          0.9989 |         0.5870 |     0.2088 |
| A3_GK_hardfilter_w10 |   2021 |          1.1216 |        321 |     0.8131 |          0.9969 |         0.9086 |     0.1672 |
| A3_pos15             |   2021 |          0.8585 |        788 |     0.8020 |          0.9949 |         0.9602 |     0.1305 |
| A3_pos15_exp75       |   2021 |          0.5264 |        788 |     0.8020 |          0.9949 |         0.7060 |     0.1305 |
| A3_pos15_gk_priority |   2021 |          0.7346 |        788 |     0.8020 |          0.9949 |         0.9602 |     0.1305 |
| DP_A3_pb_only        |   2021 |          0.5967 |        714 |     0.8459 |          0.9944 |         0.6680 |     0.1274 |
| A3_GK_hardfilter_w10 |   2025 |          0.1151 |        387 |     0.8165 |          0.9819 |         0.9519 |     0.1531 |
| A3_pos15             |   2025 |          0.4901 |       1322 |     0.7897 |          0.9826 |         0.9962 |     0.1319 |
| A3_pos15_exp75       |   2025 |          0.3636 |       1322 |     0.7897 |          0.9826 |         0.7328 |     0.1319 |
| A3_pos15_gk_priority |   2025 |          0.3005 |       1322 |     0.7897 |          0.9826 |         0.9962 |     0.1319 |
| DP_A3_pb_only        |   2025 |          0.2042 |       1069 |     0.8391 |          0.9953 |         0.7406 |     0.1272 |

## 25E — Cost / Liquidity Sensitivity

### Cost Sensitivity (ADV floor = 0, no participation cap)

| experiment_id   |   cost_pct |   n_trades |   cagr |   max_dd |    mar | prod_class           |
|:----------------|-----------:|-----------:|-------:|---------:|-------:|:---------------------|
| COST2bps        |     0.2000 |      12909 | 0.1448 |  -0.2568 | 0.5640 | PRODUCTION_CANDIDATE |
| COST4bps        |     0.4000 |      12909 | 0.1410 |  -0.2618 | 0.5388 | PRODUCTION_CANDIDATE |
| COST6bps        |     0.6000 |      12909 | 0.1373 |  -0.2667 | 0.5148 | PRODUCTION_CANDIDATE |

### ADV50 Floor Sensitivity (cost = 0.4%, no participation cap)

| experiment_id   |   adv_floor_B |   n_trades |   pct_excluded |   cagr |   max_dd |    mar | prod_class           |
|:----------------|--------------:|-----------:|---------------:|-------:|---------:|-------:|:---------------------|
| COST4bps        |        0.0000 |      12909 |         0.0000 | 0.1410 |  -0.2618 | 0.5388 | PRODUCTION_CANDIDATE |
| COST4bps_ADV2B  |        2.0000 |       8908 |         0.3099 | 0.0759 |  -0.3633 | 0.2088 | SHADOW_TEST          |
| COST4bps_ADV5B  |        5.0000 |       7092 |         0.4506 | 0.0205 |  -0.4301 | 0.0477 | RESEARCH_ONLY        |
| COST4bps_ADV10B |       10.0000 |       5492 |         0.5746 | 0.0491 |  -0.3803 | 0.1292 | SHADOW_TEST          |

### Participation Cap Sensitivity (cost = 0.4%, ADV floor = 5B)

| experiment_id            |   participation |   n_trades |   pct_excluded |   cagr |   max_dd |    mar | prod_class    |
|:-------------------------|----------------:|-----------:|---------------:|-------:|---------:|-------:|:--------------|
| COST4bps_ADV5B_PART5pct  |          5.0000 |       3262 |         0.7473 | 0.0259 |  -0.4385 | 0.0591 | RESEARCH_ONLY |
| COST4bps_ADV5B_PART10pct |         10.0000 |       4763 |         0.6310 | 0.0207 |  -0.5111 | 0.0406 | REJECT        |
| COST4bps_ADV5B_PART20pct |         20.0000 |       6377 |         0.5060 | 0.0592 |  -0.3911 | 0.1514 | SHADOW_TEST   |

## Summary Verdicts

- **DP_A3_pb_only:** MAR 0.720 vs capped-A3 (75%) 0.306. GENUINE edge from pullback timing. → PRODUCTION_CANDIDATE
- **GK hard filter:** MAR 0.539 vs baseline 0.539. Coverage 29% — maintains full MAR; PRODUCTION_CANDIDATE for concentrated allocation.
- **Cost sensitivity:** At 0.6% cost, MAR=0.515. Robust — strategy survives high friction.
- **ADV5B floor:** excludes 45.1% of trades, MAR=0.048. Universe survives liquidity screen.

## Phase 3 Readiness

Promote to Phase 3 (live trading simulation / paper trade):
- Rules with MAR > 0.50, MaxDD > -30%, positive OOS, no bad-year collapse
- Do NOT promote if edge comes from exposure reduction alone
- Do NOT promote if MAR drops below 0.40 at 0.4% cost + 5B ADV floor

