# Stage 6 — Robustness Checks

**Run date:** 2026-05-22
**Source:** stage1_trades.csv | **Horizon:** 63 bars

## Objective
Verify that accumulation score improvements are not period-specific.
Check by-year, by-regime, and by-liquidity-bucket consistency.

**Total trades:** 2771 | **Overall baseline win_rate:** 22.4%

## By year (all vs Q5)

|   n_trades |   win_rate |   loss_rate |   avg_net_ret |   pct_positive |   year | bucket   |
|-----------:|-----------:|------------:|--------------:|---------------:|-------:|:---------|
|         27 |     0.2963 |      0.4444 |       -0.0321 |         0.4444 |   2012 | all      |
|          6 |     0.3333 |      0.3333 |        0.0212 |         0.3333 |   2012 | Q5       |
|        102 |     0.3333 |      0.2255 |        0.0837 |         0.5490 |   2013 | all      |
|         21 |     0.2381 |      0.1905 |        0.0305 |         0.4762 |   2013 | Q5       |
|         98 |     0.1837 |      0.2551 |        0.0348 |         0.4796 |   2014 | all      |
|         30 |     0.1333 |      0.2333 |        0.0565 |         0.5333 |   2014 | Q5       |
|        110 |     0.0818 |      0.4545 |       -0.0625 |         0.2818 |   2015 | all      |
|         22 |     0.0455 |      0.4545 |       -0.0746 |         0.1818 |   2015 | Q5       |
|        115 |     0.1043 |      0.3739 |       -0.0342 |         0.3739 |   2016 | all      |
|         27 |     0.0370 |      0.4074 |       -0.0513 |         0.2593 |   2016 | Q5       |
|        163 |     0.3006 |      0.2699 |        0.0884 |         0.5706 |   2017 | all      |
|         33 |     0.2727 |      0.2424 |        0.1183 |         0.6970 |   2017 | Q5       |
|        156 |     0.1218 |      0.4808 |       -0.0647 |         0.2885 |   2018 | all      |
|         42 |     0.0952 |      0.4762 |       -0.0513 |         0.2619 |   2018 | Q5       |
|        167 |     0.0778 |      0.3653 |       -0.0454 |         0.3054 |   2019 | all      |
|         44 |     0.0227 |      0.3864 |       -0.0724 |         0.2045 |   2019 | Q5       |
|        274 |     0.3613 |      0.1825 |        0.1214 |         0.6715 |   2020 | all      |
|         54 |     0.2963 |      0.2037 |        0.0804 |         0.6481 |   2020 | Q5       |
|        212 |     0.4811 |      0.1698 |        0.2288 |         0.6698 |   2021 | all      |
|         15 |     0.4000 |      0.2000 |        0.0620 |         0.5333 |   2021 | Q5       |
|        197 |     0.0508 |      0.6954 |       -0.2114 |         0.1472 |   2022 | all      |
|         28 |     0.0000 |      0.6071 |       -0.1849 |         0.0714 |   2022 | Q5       |
|        314 |     0.2739 |      0.2452 |        0.0522 |         0.5732 |   2023 | all      |
|         70 |     0.2286 |      0.2857 |        0.0261 |         0.5143 |   2023 | Q5       |
|        393 |     0.1196 |      0.3461 |       -0.0170 |         0.3690 |   2024 | all      |
|         82 |     0.0732 |      0.2683 |       -0.0209 |         0.3780 |   2024 | Q5       |
|        371 |     0.2938 |      0.2345 |        0.0872 |         0.5256 |   2025 | all      |
|         67 |     0.2239 |      0.2985 |        0.0427 |         0.4478 |   2025 | Q5       |
|         72 |     0.0833 |      0.4722 |       -0.0695 |         0.3333 |   2026 | all      |
|          4 |     0.0000 |      0.2500 |       -0.0676 |         0.2500 |   2026 | Q5       |

**Year consistency:** Q5 outperformed 'all' by >3pp in 1/15 years; underperformed in 12/15 years.

## By VNINDEX regime (bull vs bear/sideways)

|   n_trades |   win_rate |   loss_rate |   avg_net_ret |   pct_positive | regime        | bucket   |
|-----------:|-----------:|------------:|--------------:|---------------:|:--------------|:---------|
|        684 |     0.2018 |      0.3260 |        0.0110 |         0.4488 | bear_sideways | all      |
|        160 |     0.1750 |      0.3438 |       -0.0112 |         0.4062 | bear_sideways | Q5       |
|       2087 |     0.2314 |      0.3196 |        0.0319 |         0.4648 | bull          | all      |
|        385 |     0.1506 |      0.3065 |        0.0067 |         0.4156 | bull          | Q5       |

## By liquidity bucket

|   n_trades |   win_rate |   loss_rate |   avg_net_ret |   pct_positive | liq_bucket   | bucket   |
|-----------:|-----------:|------------:|--------------:|---------------:|:-------------|:---------|
|        565 |     0.2478 |      0.2779 |        0.0554 |         0.5009 | 2B–5B        | all      |
|        111 |     0.1441 |      0.3514 |        0.0121 |         0.3964 | 2B–5B        | Q5       |
|       1019 |     0.2375 |      0.3131 |        0.0334 |         0.4681 | 5B–20B       | all      |
|        210 |     0.1714 |      0.2857 |        0.0040 |         0.4238 | 5B–20B       | Q5       |
|       1187 |     0.2013 |      0.3488 |        0.0074 |         0.4356 | 20B+         | all      |
|        224 |     0.1518 |      0.3304 |       -0.0062 |         0.4107 | 20B+         | Q5       |

## FACTS vs INTERPRETATION

**FACTS:**
- 2771 trades analysed at 63-bar horizon
- Overall win_rate = 22.4%

**INTERPRETATION:**
- Year consistency: if Q5 outperforms 'all' in < 50% of years → not robust.
- Regime: features expected to help more in bull regime (cloud already bullish).
  If features only work in bear/sideways regime → likely overfitting to reversal phase.
- Liquidity: if Q5 only wins in illiquid bucket → execution at scale is impossible.

## Decision framework
| Condition | Action |
|-----------|--------|
| Q5 > baseline by > 5pp in ≥ 3 of 4 most recent years | Recommend Stage 2 overlay for A3 |
| Liquidity: improvement holds in 5B+ bucket | Safe to use in liquid universe |
| Regime: improvement holds in bull only | Only apply score in bull VNINDEX regime |
| No consistent year/regime pattern | Do NOT promote — revisit features |

## Next steps
- If robust: document findings in a decision memo and propose A3 ranking overlay.
- If not robust: report which feature subsets (if any) are consistent and narrow scope.