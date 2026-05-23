# Stage 12B — S3 MaxHold Robustness Findings

## 1. Executive Summary

Total S3 signals in study (BASE_REGIME, ADV ≥ 2B, full universe): 2744

**MAX_HOLD_60 (official baseline):** n=2669  |  win=22.9%  |  TP1=37.0%  |  avg_net=-0.0%  |  MaxDD=-27.1%  |  avg_hold=51.4 bars

**MAX_HOLD_120 (under review):** n=2583  |  win=31.0%  |  TP1=51.2%  |  avg_net=1.1%  |  MaxDD=-29.4%  |  avg_hold=86.4 bars

**Hold extension risk flag (MAX_HOLD_120):** True
**Final classification (MAX_HOLD_120):** WATCHLIST_ONLY
**Action:** improvement offset by hold-extension / DD risk

## 2. Why MAX_HOLD_120 Needed Separate Validation

MAX_HOLD_120 was flagged PARALLEL_PAPER_RESEARCH in Stage 12 based on win-rate and TP1-rate improvements alone. However, holding for 120 bars instead of 60 locks up capital for twice as long. This stage checks whether the improvement survives after accounting for:
- Increased average hold time and capital lock-up.
- MaxDD from the equity curve (sequential trade model).
- Weak-year performance (2022, 2024).
- Liquidity robustness.
- Hold-sweep continuity (is 120 special, or is longer always better?).

## 3. MaxHold Variant Results

| variant      |   n_trades |   win_rate |   tp1_rate |   avg_net_return |   avg_hold_bars |   p90_hold_bars |   max_drawdown |   cagr |    mar |   return_2022 |   return_2024 | hold_extension_risk_flag   | classification          |
|:-------------|-----------:|-----------:|-----------:|-----------------:|----------------:|----------------:|---------------:|-------:|-------:|--------------:|--------------:|:---------------------------|:------------------------|
| MAX_HOLD_45  |       2688 |      0.194 |      0.309 |           -0.003 |          40.511 |          45.000 |         -0.250 | -0.006 | -0.023 |        -0.202 |        -0.012 | False                      | PAPER_TRADE_SHADOW      |
| MAX_HOLD_60  |       2669 |      0.229 |      0.370 |           -0.000 |          51.371 |          60.000 |         -0.271 | -0.006 | -0.022 |        -0.238 |        -0.018 | False                      | PAPER_TRADE_SHADOW      |
| MAX_HOLD_75  |       2649 |      0.256 |      0.416 |            0.001 |          61.181 |          75.000 |         -0.289 | -0.006 | -0.020 |        -0.245 |        -0.024 | True                       | WATCHLIST_ONLY          |
| MAX_HOLD_90  |       2608 |      0.280 |      0.455 |            0.008 |          70.148 |          90.000 |         -0.277 |  0.008 |  0.028 |        -0.237 |        -0.020 | True                       | WATCHLIST_ONLY          |
| MAX_HOLD_105 |       2598 |      0.298 |      0.486 |            0.013 |          78.608 |         105.000 |         -0.257 |  0.012 |  0.047 |        -0.218 |        -0.017 | False                      | PARALLEL_PAPER_RESEARCH |
| MAX_HOLD_120 |       2583 |      0.310 |      0.512 |            0.011 |          86.391 |         120.000 |         -0.294 |  0.009 |  0.032 |        -0.228 |        -0.023 | True                       | WATCHLIST_ONLY          |
| MAX_HOLD_150 |       2570 |      0.339 |      0.560 |            0.010 |         100.857 |         150.000 |         -0.341 |  0.006 |  0.017 |        -0.281 |        -0.021 | True                       | WATCHLIST_ONLY          |

## 4. Drawdown and Capital Lock-Up Check

| variant      |   delta_win_rate_pp |   delta_tp1_rate_pp |   delta_avg_return_pp |   delta_maxdd_pp |   delta_avg_hold_bars |   delta_median_hold_bars |   delta_2022_return_pp |   delta_2024_return_pp | hold_extension_risk_flag   |
|:-------------|--------------------:|--------------------:|----------------------:|-----------------:|----------------------:|-------------------------:|-----------------------:|-----------------------:|:---------------------------|
| MAX_HOLD_45  |               -3.44 |               -6.14 |                 -0.28 |             2.09 |                -10.86 |                   -15.00 |                   3.64 |                   0.54 | False                      |
| MAX_HOLD_75  |                2.78 |                4.55 |                  0.13 |            -1.80 |                  9.81 |                    15.00 |                  -0.67 |                  -0.57 | True                       |
| MAX_HOLD_90  |                5.14 |                8.46 |                  0.84 |            -0.58 |                 18.78 |                    30.00 |                   0.16 |                  -0.23 | True                       |
| MAX_HOLD_105 |                6.94 |               11.60 |                  1.30 |             1.38 |                 27.24 |                    45.00 |                   2.01 |                   0.12 | False                      |
| MAX_HOLD_120 |                8.19 |               14.20 |                  1.19 |            -2.30 |                 35.02 |                    60.00 |                   1.07 |                  -0.47 | True                       |
| MAX_HOLD_150 |               11.07 |               18.94 |                  1.03 |            -6.95 |                 49.49 |                    68.00 |                  -4.22 |                  -0.32 | True                       |

## 5. By-Year Robustness

|   max_hold |   year | win_rate   | avg_net   |   n |
|-----------:|-------:|:-----------|:----------|----:|
|         45 |   2012 | 41.7%      | 15.5%     |  12 |
|         45 |   2013 | 20.8%      | 1.8%      | 106 |
|         45 |   2014 | 21.4%      | 3.4%      | 103 |
|         45 |   2015 | 8.2%       | -4.9%     |  85 |
|         45 |   2016 | 8.9%       | -2.0%     | 123 |
|         45 |   2017 | 23.8%      | 3.0%      | 210 |
|         45 |   2018 | 13.2%      | -8.5%     | 106 |
|         45 |   2019 | 6.0%       | -4.3%     | 168 |
|         45 |   2020 | 31.2%      | 6.8%      | 199 |
|         45 |   2021 | 28.1%      | 4.8%      | 292 |
|         45 |   2022 | 6.4%       | -20.2%    | 188 |
|         45 |   2023 | 24.0%      | 3.1%      | 221 |
|         45 |   2024 | 12.5%      | -1.2%     | 369 |
|         45 |   2025 | 28.2%      | 3.7%      | 390 |
|         45 |   2026 | 13.8%      | -4.6%     | 116 |
|         60 |   2012 | 41.7%      | 15.5%     |  12 |
|         60 |   2013 | 31.1%      | 2.3%      | 106 |
|         60 |   2014 | 22.3%      | 3.0%      | 103 |
|         60 |   2015 | 10.6%      | -5.6%     |  85 |
|         60 |   2016 | 17.9%      | -1.9%     | 123 |
|         60 |   2017 | 28.6%      | 3.8%      | 210 |
|         60 |   2018 | 14.2%      | -10.1%    | 106 |
|         60 |   2019 | 6.5%       | -5.4%     | 168 |
|         60 |   2020 | 36.7%      | 9.5%      | 199 |
|         60 |   2021 | 34.9%      | 7.0%      | 292 |
|         60 |   2022 | 7.4%       | -23.8%    | 188 |
|         60 |   2023 | 29.0%      | 3.1%      | 221 |
|         60 |   2024 | 13.8%      | -1.8%     | 369 |
|         60 |   2025 | 29.0%      | 4.6%      | 390 |
|         60 |   2026 | 15.5%      | -2.7%     |  97 |
|         75 |   2012 | 41.7%      | 16.2%     |  12 |
|         75 |   2013 | 35.8%      | 2.9%      | 106 |
|         75 |   2014 | 20.4%      | 2.0%      | 103 |
|         75 |   2015 | 11.8%      | -4.3%     |  85 |
|         75 |   2016 | 17.9%      | -2.9%     | 123 |
|         75 |   2017 | 34.3%      | 3.8%      | 210 |
|         75 |   2018 | 15.1%      | -12.8%    | 106 |
|         75 |   2019 | 7.7%       | -7.0%     | 168 |
|         75 |   2020 | 45.2%      | 12.1%     | 199 |
|         75 |   2021 | 37.0%      | 7.5%      | 292 |
|         75 |   2022 | 6.9%       | -24.5%    | 188 |
|         75 |   2023 | 32.6%      | 4.5%      | 221 |
|         75 |   2024 | 15.2%      | -2.4%     | 369 |
|         75 |   2025 | 32.8%      | 5.1%      | 390 |
|         75 |   2026 | 19.5%      | -1.2%     |  77 |
|         90 |   2012 | 50.0%      | 17.3%     |  12 |
|         90 |   2013 | 36.8%      | 5.2%      | 106 |
|         90 |   2014 | 21.4%      | 1.1%      | 103 |
|         90 |   2015 | 11.8%      | -3.7%     |  85 |
|         90 |   2016 | 21.1%      | -2.2%     | 123 |
|         90 |   2017 | 36.7%      | 4.0%      | 210 |
|         90 |   2018 | 17.9%      | -13.5%    | 106 |
|         90 |   2019 | 9.5%       | -9.3%     | 168 |
|         90 |   2020 | 56.3%      | 14.2%     | 199 |
|         90 |   2021 | 38.4%      | 7.9%      | 292 |
|         90 |   2022 | 7.4%       | -23.7%    | 188 |
|         90 |   2023 | 34.4%      | 4.9%      | 221 |
|         90 |   2024 | 14.6%      | -2.0%     | 369 |
|         90 |   2025 | 33.8%      | 6.2%      | 390 |
|         90 |   2026 | 41.7%      | 14.0%     |  36 |
|        105 |   2012 | 50.0%      | 17.8%     |  12 |
|        105 |   2013 | 37.7%      | 6.1%      | 106 |
|        105 |   2014 | 24.3%      | 1.8%      | 103 |
|        105 |   2015 | 16.5%      | -3.4%     |  85 |
|        105 |   2016 | 21.1%      | -2.4%     | 123 |
|        105 |   2017 | 37.6%      | 3.7%      | 210 |
|        105 |   2018 | 17.9%      | -12.0%    | 106 |
|        105 |   2019 | 10.7%      | -10.7%    | 168 |
|        105 |   2020 | 53.8%      | 14.4%     | 199 |
|        105 |   2021 | 42.5%      | 8.2%      | 292 |
|        105 |   2022 | 7.4%       | -21.8%    | 188 |
|        105 |   2023 | 35.7%      | 4.2%      | 221 |
|        105 |   2024 | 16.8%      | -1.7%     | 369 |
|        105 |   2025 | 38.3%      | 8.2%      | 381 |
|        105 |   2026 | 42.9%      | 14.2%     |  35 |
|        120 |   2012 | 50.0%      | 17.6%     |  12 |
|        120 |   2013 | 40.6%      | 6.7%      | 106 |
|        120 |   2014 | 23.3%      | 1.5%      | 103 |
|        120 |   2015 | 14.1%      | -6.0%     |  85 |
|        120 |   2016 | 26.0%      | -2.6%     | 123 |
|        120 |   2017 | 39.0%      | 3.5%      | 210 |
|        120 |   2018 | 17.9%      | -11.8%    | 106 |
|        120 |   2019 | 10.1%      | -11.6%    | 168 |
|        120 |   2020 | 54.3%      | 14.7%     | 199 |
|        120 |   2021 | 42.8%      | 7.9%      | 292 |
|        120 |   2022 | 7.4%       | -22.8%    | 188 |
|        120 |   2023 | 38.5%      | 4.5%      | 221 |
|        120 |   2024 | 17.1%      | -2.3%     | 369 |
|        120 |   2025 | 42.9%      | 9.7%      | 366 |
|        120 |   2026 | 42.9%      | 14.2%     |  35 |
|        150 |   2012 | 50.0%      | 17.6%     |  12 |
|        150 |   2013 | 46.2%      | 8.2%      | 106 |
|        150 |   2014 | 25.2%      | 1.2%      | 103 |
|        150 |   2015 | 16.5%      | -6.7%     |  85 |
|        150 |   2016 | 27.6%      | -2.3%     | 123 |
|        150 |   2017 | 41.0%      | 3.0%      | 210 |
|        150 |   2018 | 19.8%      | -12.8%    | 106 |
|        150 |   2019 | 13.1%      | -10.7%    | 168 |
|        150 |   2020 | 62.8%      | 17.0%     | 199 |
|        150 |   2021 | 45.2%      | 7.2%      | 292 |
|        150 |   2022 | 7.4%       | -28.1%    | 188 |
|        150 |   2023 | 35.7%      | 2.5%      | 221 |
|        150 |   2024 | 20.1%      | -2.1%     | 369 |
|        150 |   2025 | 49.6%      | 11.9%     | 353 |
|        150 |   2026 | 42.9%      | 14.2%     |  35 |

## 6. Liquidity Robustness

| variant      | liquidity_bucket   |   n_trades |   win_rate |   tp1_rate |   avg_net_return |
|:-------------|:-------------------|-----------:|-----------:|-----------:|-----------------:|
| MAX_HOLD_45  | high               |       1201 |      0.180 |      0.280 |           -0.015 |
| MAX_HOLD_45  | low                |        517 |      0.242 |      0.360 |            0.020 |
| MAX_HOLD_45  | mid                |        970 |      0.187 |      0.318 |           -0.001 |
| MAX_HOLD_60  | high               |       1193 |      0.210 |      0.333 |           -0.014 |
| MAX_HOLD_60  | low                |        513 |      0.271 |      0.415 |            0.023 |
| MAX_HOLD_60  | mid                |        963 |      0.228 |      0.393 |            0.003 |
| MAX_HOLD_75  | high               |       1183 |      0.238 |      0.374 |           -0.013 |
| MAX_HOLD_75  | low                |        512 |      0.291 |      0.461 |            0.024 |
| MAX_HOLD_75  | mid                |        954 |      0.261 |      0.442 |            0.006 |
| MAX_HOLD_90  | high               |       1160 |      0.260 |      0.418 |           -0.005 |
| MAX_HOLD_90  | low                |        506 |      0.312 |      0.496 |            0.029 |
| MAX_HOLD_90  | mid                |        942 |      0.287 |      0.478 |            0.012 |
| MAX_HOLD_105 | high               |       1157 |      0.279 |      0.452 |           -0.001 |
| MAX_HOLD_105 | low                |        505 |      0.333 |      0.527 |            0.034 |
| MAX_HOLD_105 | mid                |        936 |      0.302 |      0.506 |            0.018 |
| MAX_HOLD_120 | high               |       1148 |      0.294 |      0.478 |           -0.004 |
| MAX_HOLD_120 | low                |        503 |      0.340 |      0.553 |            0.032 |
| MAX_HOLD_120 | mid                |        932 |      0.315 |      0.532 |            0.019 |
| MAX_HOLD_150 | high               |       1141 |      0.322 |      0.529 |           -0.007 |
| MAX_HOLD_150 | low                |        502 |      0.378 |      0.606 |            0.035 |
| MAX_HOLD_150 | mid                |        927 |      0.340 |      0.572 |            0.017 |

## 7. Final Classification

| variant      | classification          | action                                         | hold_extension_risk_flag   |
|:-------------|:------------------------|:-----------------------------------------------|:---------------------------|
| MAX_HOLD_45  | PAPER_TRADE_SHADOW      | similar to baseline — no material improvement  | False                      |
| MAX_HOLD_60  | PAPER_TRADE_SHADOW      | keep as official S3 shadow baseline            | False                      |
| MAX_HOLD_75  | WATCHLIST_ONLY          | modest improvement vs baseline — monitor       | True                       |
| MAX_HOLD_90  | WATCHLIST_ONLY          | improvement offset by hold-extension / DD risk | True                       |
| MAX_HOLD_105 | PARALLEL_PAPER_RESEARCH | meets all improvement criteria — research-only | False                      |
| MAX_HOLD_120 | WATCHLIST_ONLY          | improvement offset by hold-extension / DD risk | True                       |
| MAX_HOLD_150 | WATCHLIST_ONLY          | improvement offset by hold-extension / DD risk | True                       |

**MAX_HOLD_120 Sensitivity Variants:**

| variant                        |   n_trades |   win_rate |   tp1_rate |   avg_net_return |   max_drawdown | hold_extension_risk_flag   | classification   |
|:-------------------------------|-----------:|-----------:|-----------:|-----------------:|---------------:|:---------------------------|:-----------------|
| MAX_HOLD_120_TOP100_ADV        |       1270 |      0.306 |      0.469 |            0.003 |         -0.323 | True                       | WATCHLIST_ONLY   |
| MAX_HOLD_120_TOP150_ADV        |       1823 |      0.312 |      0.505 |            0.013 |         -0.272 | True                       | WATCHLIST_ONLY   |
| MAX_HOLD_120_EX_VIN            |       2546 |      0.310 |      0.513 |            0.011 |         -0.295 | True                       | WATCHLIST_ONLY   |
| MAX_HOLD_120_BVE_Q4Q5          |       1864 |      0.312 |      0.520 |            0.011 |         -0.350 | True                       | WATCHLIST_ONLY   |
| MAX_HOLD_120_VNINDEX_BULL_ONLY |       2583 |      0.310 |      0.512 |            0.011 |         -0.294 | True                       | WATCHLIST_ONLY   |

## 8. Safety Confirmation

- **S3 max_hold=60 remains the official paper-shadow baseline.** ✓
- **MAX_HOLD_120 is research-only unless separately approved.** ✓
- No production / OMS / live logic modified. ✓
- A3 production contract unchanged. ✓
- DNSE/live not enabled. ✓
- `final_action` not modified. ✓
- S3 P&L completely separate from A3. ✓
- No combined sleeve simulation. ✓
- No production recommendation made. ✓

## 9. Remaining Limitations

- Equity-curve MaxDD assumes sequential non-overlapping trades (conservative estimate).
- CAGR/MAR computed from first-to-last signal date span — not a continuous-hold portfolio.
- avg_mae / avg_mfe not available (Stage 12 simulation did not store per-bar MAE/MFE).
- Full-history quintile (BVE, tightness) is non-causal — quintiles use data not available at entry.
- Hold-sweep continuity (is 120 special?) should be interpreted as: longer consistently improves until capital lock-up costs outweigh gains.

## 10. Recommended Next Step

MAX_HOLD_120 classification: **DOWNGRADED to WATCHLIST_ONLY**.
Reason: improvement offset by hold-extension / DD risk.
Next step: monitor 2025/2026 live paper trades before reconsidering.
