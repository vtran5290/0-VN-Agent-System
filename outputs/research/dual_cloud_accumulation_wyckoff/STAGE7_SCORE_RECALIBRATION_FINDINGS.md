# Stage 7 — Score Recalibration Findings

**Run date:** 2026-05-22  
**Source:** stage1_trades.csv  
**Horizon:** 63 bars  
**PAPER RESEARCH ONLY — no production changes**

---

## 1. Executive Summary

- **22 candidate score definitions** tested against 2771 A3 signal events at the 63-bar horizon.
- **Baseline (all signals) win rate:** 22.4%
- **PARALLEL_PAPER_RESEARCH:** 0 candidates passed all 5 classification gates.
- **WATCHLIST_ONLY:** 17 candidates show positive delta but below 5pp or inconsistent splits.
- **REJECT:** 5 candidates show no improvement over all-signals baseline.

---

## 2. Why Current Score Failed

**FACTS:**
- `old_composite_score` Q5 win rate = 15.3% vs baseline 22.4%
- Q5 delta = -7.1pp

**INTERPRETATION:**
- The original spec used `vol_drying` ascending=True (drying = better) and `vol_ratio` descending.
  Stage 1 Spearman/point-biserial data shows `vol_drying` has a NEGATIVE correlation with success
  (-0.053 pb_corr), meaning the original spec actively penalises signals that go on to succeed.
- `vol_ratio` descending also conflicts with `vol_trend_10` empirical direction (+0.051).
- The net effect: the score weighted poorly-correlated features and over-weighted theoretical priors.

---

## 3. Feature Direction Review

| Feature | pb_corr_success | Empirical Direction | Old Spec Direction | Match? |
|---------|-----------------|--------------------|--------------------|--------|
| pt_20 | +0.076 | ascending (higher=better) | descending | NO |
| pt_40 | +0.075 | ascending | not included | — |
| bo_vol_exp | +0.041 | ascending | ascending | YES |
| vol_ratio | +0.041 | ascending | descending | NO |
| vol_trend_10 | +0.051 | ascending | not included | — |
| bar_range_pct | +0.057 | ascending | not included | — |
| vol_drying | -0.053 | descending (penalise) | ascending (reward) | NO |
| vol_below_streak | -0.035 | descending | not included | — |
| bo_close_str | -0.012 | near-zero | ascending | WEAK |
| range_vs_ma20 | +0.017 | near-zero | not included | — |
| atr_ratio | +0.014 | near-zero | descending | WEAK |
| bo_range_exp | +0.015 | near-zero | not included | — |

**Note:** `pt_20` = std/mean (lower = tighter price). Empirically, signals with higher `pt_20`
at the A3 bar correlate with subsequent success, possibly because looser consolidation
reflects a wider base pattern rather than terminal compression.

---

## 4. Candidate Score Results

| candidate_name | q5_minus_all_pp | n_q5 | classification |
|----------------|-----------------|------|----------------|
| tightness_plus_breakout_close_quality | +4.3 | 554 | WATCHLIST_ONLY |
| breakout_value_expansion | +4.3 | 554 | WATCHLIST_ONLY |
| volume_dryup_positive_only_after_breakout | +4.3 | 554 | WATCHLIST_ONLY |
| tightness_plus_breakout_value | +3.9 | 554 | WATCHLIST_ONLY |
| anti_dead_liquidity_score | +3.8 | 554 | WATCHLIST_ONLY |
| wyckoff_sos_lps_combo | +3.6 | 554 | WATCHLIST_ONLY |
| price_tightness_low_volatility | +3.4 | 554 | WATCHLIST_ONLY |
| price_tightness_pt20_pt40 | +3.4 | 554 | WATCHLIST_ONLY |
| bull_regime_score | +3.2 | 554 | WATCHLIST_ONLY |
| wyckoff_sos_only | +3.2 | 554 | WATCHLIST_ONLY |
| regime_conditional_score | +3.0 | 554 | WATCHLIST_ONLY |
| tightness_plus_breakout | +3.0 | 554 | WATCHLIST_ONLY |
| liquidity_conditional_score | +2.1 | 554 | WATCHLIST_ONLY |
| breakout_only | +1.2 | 554 | WATCHLIST_ONLY |
| bear_sideways_score | +0.9 | 554 | WATCHLIST_ONLY |
| volume_dryup_as_negative | +0.7 | 554 | WATCHLIST_ONLY |
| breakout_close_quality | +0.3 | 554 | WATCHLIST_ONLY |
| no_volume_dryup_score | -2.6 | 554 | REJECT |
| wyckoff_spring_test_only | -2.7 | 554 | REJECT |
| price_tightness_range_compression | -4.2 | 554 | REJECT |
| old_composite_score | -7.1 | 554 | REJECT |
| wyckoff_lps_only | -7.8 | 554 | REJECT |

---

## 5. Train / Validation / Test Results

| candidate_name                            |   train_delta |   validate_delta |   test_delta |
|:------------------------------------------|--------------:|-----------------:|-------------:|
| price_tightness_pt20_pt40                 |           1.4 |              0.5 |          7.6 |
| price_tightness_low_volatility            |           0.3 |             -7.5 |          7.6 |
| breakout_value_expansion                  |           5.6 |              2.7 |          3.2 |
| tightness_plus_breakout_value             |           5.6 |              4.1 |          1.9 |
| bear_sideways_score                       |           2.4 |             -3.9 |          1.5 |
| tightness_plus_breakout                   |           5.6 |              1.2 |          1.5 |
| liquidity_conditional_score               |           4.0 |              0.5 |          1.0 |
| regime_conditional_score                  |           4.5 |              1.9 |          1.0 |
| wyckoff_sos_lps_combo                     |           7.2 |              2.7 |          1.0 |
| wyckoff_sos_only                          |           7.7 |              0.5 |          1.0 |
| volume_dryup_positive_only_after_breakout |           2.9 |             -1.0 |          1.0 |
| anti_dead_liquidity_score                 |           5.1 |              3.4 |          0.6 |
| tightness_plus_breakout_close_quality     |           4.5 |              4.9 |          0.6 |
| volume_dryup_as_negative                  |           1.9 |             -0.2 |         -1.1 |
| bull_regime_score                         |           5.6 |              4.1 |         -1.6 |
| breakout_close_quality                    |           4.0 |             -4.6 |         -1.6 |
| breakout_only                             |           6.1 |             -2.4 |         -1.6 |
| price_tightness_range_compression         |          -7.2 |             -3.2 |         -2.0 |
| no_volume_dryup_score                     |          -0.2 |             -5.3 |         -2.4 |
| wyckoff_spring_test_only                  |           3.5 |             -8.3 |         -4.2 |
| old_composite_score                       |          -5.6 |             -8.3 |         -5.5 |
| wyckoff_lps_only                          |           0.8 |            -24.3 |        -11.1 |

---

## 6. By-Year Stability

2024 is flagged as a weak year for accumulation signals in Vietnamese markets.
Candidates that maintain positive delta in 2024 are more likely to be robust.

**2024 performance by candidate:**

| candidate_name                            |   n_q5 |   q5_win_rate |   q5_minus_all_pp | classification   |
|:------------------------------------------|-------:|--------------:|------------------:|:-----------------|
| old_composite_score                       |     79 |          0.08 |             -4.36 | declining        |
| price_tightness_pt20_pt40                 |     79 |          0.16 |              4.50 | improving        |
| price_tightness_range_compression         |     79 |          0.09 |             -3.10 | declining        |
| price_tightness_low_volatility            |     79 |          0.15 |              3.23 | improving        |
| breakout_only                             |     79 |          0.15 |              3.23 | improving        |
| breakout_close_quality                    |     79 |          0.15 |              3.23 | improving        |
| breakout_value_expansion                  |     79 |          0.14 |              1.96 | improving        |
| tightness_plus_breakout                   |     79 |          0.16 |              4.50 | improving        |
| tightness_plus_breakout_value             |     79 |          0.15 |              3.23 | improving        |
| tightness_plus_breakout_close_quality     |     79 |          0.14 |              1.96 | improving        |
| no_volume_dryup_score                     |     79 |          0.11 |             -0.57 | declining        |
| volume_dryup_as_negative                  |     79 |          0.13 |              0.70 | improving        |
| wyckoff_sos_only                          |     79 |          0.14 |              1.96 | improving        |
| wyckoff_lps_only                          |     79 |          0.05 |             -6.90 | declining        |
| wyckoff_spring_test_only                  |     79 |          0.13 |              0.70 | improving        |
| wyckoff_sos_lps_combo                     |     79 |          0.10 |             -1.83 | declining        |
| anti_dead_liquidity_score                 |     79 |          0.14 |              1.96 | improving        |
| volume_dryup_positive_only_after_breakout |     79 |          0.16 |              4.50 | improving        |
| bull_regime_score                         |     79 |          0.15 |              3.23 | improving        |
| bear_sideways_score                       |     79 |          0.15 |              3.23 | improving        |
| regime_conditional_score                  |     79 |          0.16 |              4.50 | improving        |
| liquidity_conditional_score               |     79 |          0.15 |              3.23 | improving        |

---

## 7. Regime Robustness

| candidate_name                            | regime        |   n_total |   n_q5 |   all_win_rate |   q5_win_rate |   q5_minus_all_pp |
|:------------------------------------------|:--------------|----------:|-------:|---------------:|--------------:|------------------:|
| old_composite_score                       | bear_sideways |       684 |    142 |         0.2018 |        0.1799 |           -2.1900 |
| old_composite_score                       | bull          |      2087 |    429 |         0.2314 |        0.1485 |           -8.2900 |
| price_tightness_pt20_pt40                 | bear_sideways |       684 |    142 |         0.2018 |        0.2482 |            4.6400 |
| price_tightness_pt20_pt40                 | bull          |      2087 |    429 |         0.2314 |        0.2648 |            3.3300 |
| price_tightness_range_compression         | bear_sideways |       684 |    142 |         0.2018 |        0.1727 |           -2.9100 |
| price_tightness_range_compression         | bull          |      2087 |    429 |         0.2314 |        0.1849 |           -4.6500 |
| price_tightness_low_volatility            | bear_sideways |       684 |    142 |         0.2018 |        0.1594 |           -4.2300 |
| price_tightness_low_volatility            | bull          |      2087 |    429 |         0.2314 |        0.2959 |            6.4500 |
| breakout_only                             | bear_sideways |       684 |    142 |         0.2018 |        0.2263 |            2.4500 |
| breakout_only                             | bull          |      2087 |    429 |         0.2314 |        0.2381 |            0.6700 |
| breakout_close_quality                    | bear_sideways |       684 |    142 |         0.2018 |        0.2230 |            2.1300 |
| breakout_close_quality                    | bull          |      2087 |    429 |         0.2314 |        0.2286 |           -0.2900 |
| breakout_value_expansion                  | bear_sideways |       684 |    142 |         0.2018 |        0.2647 |            6.3000 |
| breakout_value_expansion                  | bull          |      2087 |    429 |         0.2314 |        0.2740 |            4.2600 |
| tightness_plus_breakout                   | bear_sideways |       684 |    142 |         0.2018 |        0.2482 |            4.6400 |
| tightness_plus_breakout                   | bull          |      2087 |    429 |         0.2314 |        0.2643 |            3.2900 |
| tightness_plus_breakout_value             | bear_sideways |       684 |    142 |         0.2018 |        0.2794 |            7.7700 |
| tightness_plus_breakout_value             | bull          |      2087 |    429 |         0.2314 |        0.2536 |            2.2200 |
| tightness_plus_breakout_close_quality     | bear_sideways |       684 |    142 |         0.2018 |        0.2681 |            6.6400 |
| tightness_plus_breakout_close_quality     | bull          |      2087 |    429 |         0.2314 |        0.2690 |            3.7600 |
| no_volume_dryup_score                     | bear_sideways |       684 |    142 |         0.2018 |        0.1631 |           -3.8600 |
| no_volume_dryup_score                     | bull          |      2087 |    429 |         0.2314 |        0.2152 |           -1.6300 |
| volume_dryup_as_negative                  | bear_sideways |       684 |    142 |         0.2018 |        0.1702 |           -3.1500 |
| volume_dryup_as_negative                  | bull          |      2087 |    429 |         0.2314 |        0.2404 |            0.9000 |
| wyckoff_sos_only                          | bear_sideways |       684 |    142 |         0.2018 |        0.2446 |            4.2800 |
| wyckoff_sos_only                          | bull          |      2087 |    429 |         0.2314 |        0.2584 |            2.6900 |
| wyckoff_lps_only                          | bear_sideways |       684 |    142 |         0.2018 |        0.1742 |           -2.7500 |
| wyckoff_lps_only                          | bull          |      2087 |    429 |         0.2314 |        0.1383 |           -9.3200 |
| wyckoff_spring_test_only                  | bear_sideways |       684 |    142 |         0.2018 |        0.1620 |           -3.9800 |
| wyckoff_spring_test_only                  | bull          |      2087 |    429 |         0.2314 |        0.2098 |           -2.1600 |
| wyckoff_sos_lps_combo                     | bear_sideways |       684 |    142 |         0.2018 |        0.2446 |            4.2800 |
| wyckoff_sos_lps_combo                     | bull          |      2087 |    429 |         0.2314 |        0.2679 |            3.6500 |
| anti_dead_liquidity_score                 | bear_sideways |       684 |    142 |         0.2018 |        0.2409 |            3.9100 |
| anti_dead_liquidity_score                 | bull          |      2087 |    429 |         0.2314 |        0.2712 |            3.9800 |
| volume_dryup_positive_only_after_breakout | bear_sideways |       684 |    142 |         0.2018 |        0.2847 |            8.2900 |
| volume_dryup_positive_only_after_breakout | bull          |      2087 |    429 |         0.2314 |        0.2614 |            3.0000 |
| bull_regime_score                         | bear_sideways |       684 |    142 |         0.2018 |        0.1799 |           -2.1900 |
| bull_regime_score                         | bull          |      2087 |    429 |         0.2314 |        0.2595 |            2.8100 |
| bear_sideways_score                       | bear_sideways |       684 |    142 |         0.2018 |        0.2409 |            3.9100 |
| bear_sideways_score                       | bull          |      2087 |    429 |         0.2314 |        0.2136 |           -1.7800 |
| regime_conditional_score                  | bear_sideways |       684 |    142 |         0.2018 |        0.2409 |            3.9100 |
| regime_conditional_score                  | bull          |      2087 |    429 |         0.2314 |        0.2595 |            2.8100 |
| liquidity_conditional_score               | bear_sideways |       684 |    142 |         0.2018 |        0.2426 |            4.0900 |
| liquidity_conditional_score               | bull          |      2087 |    429 |         0.2314 |        0.2524 |            2.0900 |

---

## 8. Liquidity Robustness

| candidate_name                            | liquidity_bucket   |   n_total |   n_q5 |   all_win_rate |   q5_win_rate |   q5_minus_all_pp |
|:------------------------------------------|:-------------------|----------:|-------:|---------------:|--------------:|------------------:|
| old_composite_score                       | 20B_plus           |      1187 |    247 |         0.2013 |        0.1502 |           -5.1100 |
| old_composite_score                       | 2B_5B              |       565 |    116 |         0.2478 |        0.1261 |          -12.1700 |
| old_composite_score                       | 5B_20B             |      1019 |    209 |         0.2375 |        0.1759 |           -6.1600 |
| price_tightness_pt20_pt40                 | 20B_plus           |      1187 |    247 |         0.2013 |        0.2050 |            0.3700 |
| price_tightness_pt20_pt40                 | 2B_5B              |       565 |    116 |         0.2478 |        0.3153 |            6.7500 |
| price_tightness_pt20_pt40                 | 5B_20B             |      1019 |    209 |         0.2375 |        0.2919 |            5.4400 |
| price_tightness_range_compression         | 20B_plus           |      1187 |    247 |         0.2013 |        0.1674 |           -3.4000 |
| price_tightness_range_compression         | 2B_5B              |       565 |    116 |         0.2478 |        0.1786 |           -6.9200 |
| price_tightness_range_compression         | 5B_20B             |      1019 |    209 |         0.2375 |        0.2000 |           -3.7500 |
| price_tightness_low_volatility            | 20B_plus           |      1187 |    247 |         0.2013 |        0.2008 |           -0.0500 |
| price_tightness_low_volatility            | 2B_5B              |       565 |    116 |         0.2478 |        0.3784 |           13.0600 |
| price_tightness_low_volatility            | 5B_20B             |      1019 |    209 |         0.2375 |        0.2740 |            3.6600 |
| breakout_only                             | 20B_plus           |      1187 |    247 |         0.2013 |        0.1674 |           -3.4000 |
| breakout_only                             | 2B_5B              |       565 |    116 |         0.2478 |        0.2931 |            4.5300 |
| breakout_only                             | 5B_20B             |      1019 |    209 |         0.2375 |        0.3005 |            6.3000 |
| breakout_close_quality                    | 20B_plus           |      1187 |    247 |         0.2013 |        0.1583 |           -4.3000 |
| breakout_close_quality                    | 2B_5B              |       565 |    116 |         0.2478 |        0.2414 |           -0.6400 |
| breakout_close_quality                    | 5B_20B             |      1019 |    209 |         0.2375 |        0.2843 |            4.6800 |
| breakout_value_expansion                  | 20B_plus           |      1187 |    247 |         0.2013 |        0.2278 |            2.6500 |
| breakout_value_expansion                  | 2B_5B              |       565 |    116 |         0.2478 |        0.2719 |            2.4100 |
| breakout_value_expansion                  | 5B_20B             |      1019 |    209 |         0.2375 |        0.3035 |            6.6000 |
| tightness_plus_breakout                   | 20B_plus           |      1187 |    247 |         0.2013 |        0.1983 |           -0.3000 |
| tightness_plus_breakout                   | 2B_5B              |       565 |    116 |         0.2478 |        0.2759 |            2.8100 |
| tightness_plus_breakout                   | 5B_20B             |      1019 |    209 |         0.2375 |        0.3088 |            7.1300 |
| tightness_plus_breakout_value             | 20B_plus           |      1187 |    247 |         0.2013 |        0.1915 |           -0.9900 |
| tightness_plus_breakout_value             | 2B_5B              |       565 |    116 |         0.2478 |        0.2931 |            4.5300 |
| tightness_plus_breakout_value             | 5B_20B             |      1019 |    209 |         0.2375 |        0.3069 |            6.9400 |
| tightness_plus_breakout_close_quality     | 20B_plus           |      1187 |    247 |         0.2013 |        0.2050 |            0.3700 |
| tightness_plus_breakout_close_quality     | 2B_5B              |       565 |    116 |         0.2478 |        0.3017 |            5.3900 |
| tightness_plus_breakout_close_quality     | 5B_20B             |      1019 |    209 |         0.2375 |        0.3122 |            7.4700 |
| no_volume_dryup_score                     | 20B_plus           |      1187 |    247 |         0.2013 |        0.1814 |           -1.9900 |
| no_volume_dryup_score                     | 2B_5B              |       565 |    116 |         0.2478 |        0.2035 |           -4.4200 |
| no_volume_dryup_score                     | 5B_20B             |      1019 |    209 |         0.2375 |        0.2090 |           -2.8500 |
| volume_dryup_as_negative                  | 20B_plus           |      1187 |    247 |         0.2013 |        0.2042 |            0.2800 |
| volume_dryup_as_negative                  | 2B_5B              |       565 |    116 |         0.2478 |        0.2348 |           -1.3000 |
| volume_dryup_as_negative                  | 5B_20B             |      1019 |    209 |         0.2375 |        0.2574 |            1.9900 |
| wyckoff_sos_only                          | 20B_plus           |      1187 |    247 |         0.2013 |        0.2042 |            0.2800 |
| wyckoff_sos_only                          | 2B_5B              |       565 |    116 |         0.2478 |        0.2895 |            4.1700 |
| wyckoff_sos_only                          | 5B_20B             |      1019 |    209 |         0.2375 |        0.2892 |            5.1700 |
| wyckoff_lps_only                          | 20B_plus           |      1187 |    247 |         0.2013 |        0.1022 |           -9.9100 |
| wyckoff_lps_only                          | 2B_5B              |       565 |    116 |         0.2478 |        0.1455 |          -10.2300 |
| wyckoff_lps_only                          | 5B_20B             |      1019 |    209 |         0.2375 |        0.2049 |           -3.2600 |
| wyckoff_spring_test_only                  | 20B_plus           |      1187 |    247 |         0.2013 |        0.1596 |           -4.1700 |
| wyckoff_spring_test_only                  | 2B_5B              |       565 |    116 |         0.2478 |        0.2069 |           -4.0900 |
| wyckoff_spring_test_only                  | 5B_20B             |      1019 |    209 |         0.2375 |        0.2297 |           -0.7800 |
| wyckoff_sos_lps_combo                     | 20B_plus           |      1187 |    247 |         0.2013 |        0.2000 |           -0.1300 |
| wyckoff_sos_lps_combo                     | 2B_5B              |       565 |    116 |         0.2478 |        0.2982 |            5.0500 |
| wyckoff_sos_lps_combo                     | 5B_20B             |      1019 |    209 |         0.2375 |        0.2941 |            5.6600 |
| anti_dead_liquidity_score                 | 20B_plus           |      1187 |    247 |         0.2013 |        0.2116 |            1.0300 |
| anti_dead_liquidity_score                 | 2B_5B              |       565 |    116 |         0.2478 |        0.2672 |            1.9500 |
| anti_dead_liquidity_score                 | 5B_20B             |      1019 |    209 |         0.2375 |        0.3317 |            9.4200 |
| volume_dryup_positive_only_after_breakout | 20B_plus           |      1187 |    247 |         0.2013 |        0.1814 |           -1.9900 |
| volume_dryup_positive_only_after_breakout | 2B_5B              |       565 |    116 |         0.2478 |        0.2845 |            3.6700 |
| volume_dryup_positive_only_after_breakout | 5B_20B             |      1019 |    209 |         0.2375 |        0.3103 |            7.2900 |
| bull_regime_score                         | 20B_plus           |      1187 |    247 |         0.2013 |        0.2017 |            0.0300 |
| bull_regime_score                         | 2B_5B              |       565 |    116 |         0.2478 |        0.2500 |            0.2200 |
| bull_regime_score                         | 5B_20B             |      1019 |    209 |         0.2375 |        0.3107 |            7.3200 |
| bear_sideways_score                       | 20B_plus           |      1187 |    247 |         0.2013 |        0.1538 |           -4.7500 |
| bear_sideways_score                       | 2B_5B              |       565 |    116 |         0.2478 |        0.3070 |            5.9200 |
| bear_sideways_score                       | 5B_20B             |      1019 |    209 |         0.2375 |        0.2647 |            2.7200 |
| regime_conditional_score                  | 20B_plus           |      1187 |    247 |         0.2013 |        0.1933 |           -0.8100 |
| regime_conditional_score                  | 2B_5B              |       565 |    116 |         0.2478 |        0.2759 |            2.8100 |
| regime_conditional_score                  | 5B_20B             |      1019 |    209 |         0.2375 |        0.2941 |            5.6600 |
| liquidity_conditional_score               | 20B_plus           |      1187 |    247 |         0.2013 |        0.1899 |           -1.1500 |
| liquidity_conditional_score               | 2B_5B              |       565 |    116 |         0.2478 |        0.2759 |            2.8100 |
| liquidity_conditional_score               | 5B_20B             |      1019 |    209 |         0.2375 |        0.3039 |            6.6400 |

---

## 9. Wyckoff Incremental Value

Tightness baseline (`tightness_plus_breakout`) Q5 delta: **3.0pp**

**Wyckoff candidates:**

| candidate_name           |   q5_minus_all_pp |   n_q5 | classification   |
|:-------------------------|------------------:|-------:|:-----------------|
| wyckoff_sos_only         |               3.2 |    554 | WATCHLIST_ONLY   |
| wyckoff_lps_only         |              -7.8 |    554 | REJECT           |
| wyckoff_spring_test_only |              -2.7 |    554 | REJECT           |
| wyckoff_sos_lps_combo    |               3.6 |    554 | WATCHLIST_ONLY   |

INTERPRETATION: Wyckoff tags (spring, SOS, LPS) fire on a small subset of signals
and are mechanically defined. They remain diagnostic markers for human review, not
a scoring input for automated selection. UTAD is excluded from all tradable candidates
as it requires future-bar confirmation.

---

## 10. Final Classifications

### old_composite_score
- **Classification:** REJECT
- **Action:** do_not_use
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Required REJECT by design; delta=-7.1pp

### price_tightness_pt20_pt40
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.4pp > 0 but < 5pp threshold

### price_tightness_range_compression
- **Classification:** REJECT
- **Action:** do_not_use
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=-4.2pp <= 0, no predictive value

### price_tightness_low_volatility
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.4pp > 0 but < 5pp threshold

### breakout_only
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=1.2pp > 0 but < 5pp threshold

### breakout_close_quality
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=0.3pp > 0 but < 5pp threshold

### breakout_value_expansion
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=4.3pp > 0 but < 5pp threshold

### tightness_plus_breakout
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.0pp > 0 but < 5pp threshold

### tightness_plus_breakout_value
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.9pp > 0 but < 5pp threshold

### tightness_plus_breakout_close_quality
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=4.3pp > 0 but < 5pp threshold

### no_volume_dryup_score
- **Classification:** REJECT
- **Action:** do_not_use
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=-2.6pp <= 0, no predictive value

### volume_dryup_as_negative
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=0.7pp > 0 but < 5pp threshold

### wyckoff_sos_only
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** diagnostic_only
- **Reason:** Q5 delta=3.2pp > 0 but < 5pp threshold

### wyckoff_lps_only
- **Classification:** REJECT
- **Action:** do_not_use
- **diagnostic_or_tradable:** diagnostic_only
- **Reason:** Q5 delta=-7.8pp <= 0, no predictive value

### wyckoff_spring_test_only
- **Classification:** REJECT
- **Action:** do_not_use
- **diagnostic_or_tradable:** diagnostic_only
- **Reason:** Q5 delta=-2.7pp <= 0, no predictive value

### wyckoff_sos_lps_combo
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** diagnostic_only
- **Reason:** Q5 delta=3.6pp > 0 but < 5pp threshold

### anti_dead_liquidity_score
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.8pp > 0 but < 5pp threshold

### volume_dryup_positive_only_after_breakout
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=4.3pp > 0 but < 5pp threshold

### bull_regime_score
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.2pp > 0 but < 5pp threshold

### bear_sideways_score
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=0.9pp > 0 but < 5pp threshold

### regime_conditional_score
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=3.0pp > 0 but < 5pp threshold

### liquidity_conditional_score
- **Classification:** WATCHLIST_ONLY
- **Action:** collect_more_data
- **diagnostic_or_tradable:** tradable_candidate
- **Reason:** Q5 delta=2.1pp > 0 but < 5pp threshold

---

## 11. Recommended Actions

**PAPER RESEARCH ONLY — no production/OMS changes.**

No candidates cleared PARALLEL_PAPER_RESEARCH threshold. Recommended next steps:

1. Review WATCHLIST_ONLY candidates for additional split-period data.
2. Consider feature engineering (interaction terms, nonlinear transforms).
3. Do not modify production scoring until a candidate passes all 5 gates.

---

## 12. Safety Confirmation

- `old_composite_score` classification: **REJECT** (required by design — confirms regression test passes)
- `utad` feature: excluded from ALL tradable candidates (future confirmation required)
- Wyckoff features (`spring`, `sos`, `lps`): **diagnostic_only** in all score variants
- No recommendation in this report constitutes a production trade signal
- All score computation uses `compute_candidate_score_dategroup` (date-group stable, no lookahead)

---

## 13. Open Questions

1. Does `pt_20` ascending direction hold across all market cap tiers, or only mid-cap?
2. Is `vol_ratio` ascending empirically stable, or sensitive to the 2020–2022 bull period?
3. Do any conditional candidates (regime/liquidity-conditional) outperform on out-of-sample 2023+?
4. Should `bo_range_exp` and `vol_trend_10` be added to tightness_plus_breakout?
5. Is the 5pp threshold for PARALLEL_PAPER_RESEARCH appropriately calibrated for this universe size?