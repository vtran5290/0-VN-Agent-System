# Stage 1 — Feature Predictive Value

**Universe:** ex-VIN | **Run date:** 2026-05-22

## Objective
Test whether accumulation/tightness features have predictive value over A3
cloud signals. Primary horizon: 63 bars (~quarter). Success = net_return ≥ +15%.

## Overall baseline (all A3 signals, 63-bar horizon)

| Metric | Value |
|--------|-------|
| N trades | 2771 |
| Win rate (≥+15%) | 21.8% |
| Avg net return | 2.68% |

## Quintile breakdown (score_q=5 = highest accumulation evidence)

|   score_q |   n_trades |   win_rate |   loss_rate |   avg_net_ret |   med_net_ret |   pct_positive |
|----------:|-----------:|-----------:|------------:|--------------:|--------------:|---------------:|
|         1 |   560.0000 |     0.2804 |      0.3304 |        0.0478 |       -0.0076 |         0.4786 |
|         2 |   553.0000 |     0.2351 |      0.3671 |        0.0315 |       -0.0240 |         0.4521 |
|         3 |   560.0000 |     0.2250 |      0.2893 |        0.0270 |       -0.0031 |         0.4946 |
|         4 |   553.0000 |     0.2206 |      0.3020 |        0.0255 |       -0.0090 |         0.4647 |
|         5 |   545.0000 |     0.1578 |      0.3174 |        0.0015 |       -0.0257 |         0.4128 |

**Q5 vs baseline win rate:** 15.8% vs 21.8% (delta = -6.0%, n=545.0)
**Q5 avg net return:** 0.15%
**Q1 win rate:** 28.0%

## Feature-return correlations (Spearman ρ, 63-bar horizon)

| feature          |   spearman_rho |   spearman_p |   pb_corr_success |   pb_p |    n |
|:-----------------|---------------:|-------------:|------------------:|-------:|-----:|
| pt_40            |         0.0296 |       0.1189 |            0.0785 | 0.0000 | 2771 |
| pt_20            |         0.0282 |       0.1374 |            0.0756 | 0.0001 | 2771 |
| bo_vol_exp       |         0.0174 |       0.3608 |            0.0413 | 0.0298 | 2771 |
| vol_ratio        |         0.0174 |       0.3608 |            0.0413 | 0.0298 | 2771 |
| vol_trend_10     |         0.0138 |       0.4663 |            0.0514 | 0.0068 | 2771 |
| bo_close_str     |         0.0111 |       0.5595 |           -0.0118 | 0.5353 | 2771 |
| atr_ratio        |         0.0099 |       0.6013 |            0.0141 | 0.4570 | 2771 |
| range_vs_ma20    |         0.0033 |       0.8634 |            0.0165 | 0.3842 | 2771 |
| bo_range_exp     |        -0.0033 |       0.8630 |            0.0147 | 0.4394 | 2771 |
| bar_range_pct    |        -0.0142 |       0.4541 |            0.0566 | 0.0029 | 2771 |
| vol_below_streak |        -0.0261 |       0.1697 |           -0.0353 | 0.0633 | 2771 |
| vol_drying       |        -0.0341 |       0.0730 |           -0.0526 | 0.0056 | 2771 |

## Overall horizon summary

|   horizon |   n_trades |   win_rate |   loss_rate |   avg_net_ret |   med_net_ret |   pct_positive |   avg_gross_ret |
|----------:|-----------:|-----------:|------------:|--------------:|--------------:|---------------:|----------------:|
|   25.0000 |  2811.0000 |     0.1242 |      0.2152 |        0.0098 |       -0.0040 |         0.4781 |          0.0138 |
|   50.0000 |  2791.0000 |     0.1953 |      0.3103 |        0.0152 |       -0.0151 |         0.4579 |          0.0192 |
|   63.0000 |  2771.0000 |     0.2241 |      0.3212 |        0.0268 |       -0.0146 |         0.4608 |          0.0308 |
|  100.0000 |  2689.0000 |     0.2629 |      0.3618 |        0.0489 |       -0.0117 |         0.4712 |          0.0529 |

## By-year breakdown (63-bar horizon)

|      year |   n_trades |   win_rate |   avg_net_ret |
|----------:|-----------:|-----------:|--------------:|
| 2012.0000 |    27.0000 |     0.2963 |       -0.0321 |
| 2013.0000 |   102.0000 |     0.3333 |        0.0837 |
| 2014.0000 |    98.0000 |     0.1837 |        0.0348 |
| 2015.0000 |   110.0000 |     0.0818 |       -0.0625 |
| 2016.0000 |   115.0000 |     0.1043 |       -0.0342 |
| 2017.0000 |   163.0000 |     0.3006 |        0.0884 |
| 2018.0000 |   156.0000 |     0.1218 |       -0.0647 |
| 2019.0000 |   167.0000 |     0.0778 |       -0.0454 |
| 2020.0000 |   274.0000 |     0.3613 |        0.1214 |
| 2021.0000 |   212.0000 |     0.4811 |        0.2288 |
| 2022.0000 |   197.0000 |     0.0508 |       -0.2114 |
| 2023.0000 |   314.0000 |     0.2739 |        0.0522 |
| 2024.0000 |   393.0000 |     0.1196 |       -0.0170 |
| 2025.0000 |   371.0000 |     0.2938 |        0.0872 |
| 2026.0000 |    72.0000 |     0.0833 |       -0.0695 |

## FACTS vs INTERPRETATION

**FACTS:**
- 2771 A3 cloud signals analysed across 248 symbols
- Q5 win rate = 15.8% vs baseline 21.8%

**INTERPRETATION:**
- If Q5 win rate > baseline by > 5 pp with n > 40 → features warrant Stage 2 ranking test.
- If strongest Spearman |ρ| < 0.05 across all features → features have no predictive signal.
- Year-by-year consistency required: a result only in one year is not actionable.

## Next step
If Q5 outperforms baseline by > 5 pp: proceed to Stage 2 (A3 candidate ranking).
If not: revisit feature definitions before proceeding.