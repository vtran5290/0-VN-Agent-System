# Minervini 2012–2026 backtest summary
- Start: 2012-01-01
- End: 2026-02-24
- Versions: M0R, M4R, P2A, P2B

## Funnel diagnostics (fee=30 bps, min_hold=3)

| version   | universe             |   tt_pass |   setup_pass |   trigger_pass |   retest_pass |   entries |   exits |
|:----------|:---------------------|----------:|-------------:|---------------:|--------------:|----------:|--------:|
| M0R       | A_VN30_top_liquidity |      5543 |         5543 |            280 |             0 |       122 |     122 |
| M0R       | B_broad              |      5543 |         5543 |            280 |             0 |       122 |     122 |
| M4R       | A_VN30_top_liquidity |      8618 |         1814 |             25 |            19 |        19 |      19 |
| M4R       | B_broad              |      8618 |         1814 |             25 |            19 |        19 |      19 |
| P2A       | A_VN30_top_liquidity |      8649 |         8649 |             83 |             0 |        26 |      26 |
| P2A       | B_broad              |      8649 |         8649 |             83 |             0 |        26 |      26 |
| P2B       | A_VN30_top_liquidity |      8725 |         8725 |             83 |             0 |        23 |      23 |
| P2B       | B_broad              |      8725 |         8725 |             83 |             0 |        23 |      23 |

## Walk-forward realism (see script for split definitions)

| version   | split    | start      | end        |   trades |   profit_factor |   expectancy |   expectancy_r |   top10_pct_pnl |
|:----------|:---------|:-----------|:-----------|---------:|----------------:|-------------:|---------------:|----------------:|
| M0R       | train    | 2020-01-01 | 2022-12-31 |       49 |          3.6626 |       0.0751 |         1.2203 |          1.0846 |
| M0R       | validate | 2023-01-01 | 2023-12-31 |       17 |          0.5222 |      -0.0208 |        -0.3709 |         -0.4064 |
| M0R       | holdout  | 2024-01-01 | 2024-12-31 |       23 |          2.739  |       0.0331 |         0.6449 |          1.5589 |
| M4R       | train    | 2020-01-01 | 2022-12-31 |       21 |          1.0708 |       0.0019 |        -0.0265 |         14.0228 |
| M4R       | validate | 2023-01-01 | 2023-12-31 |        1 |        nan      |      -0.0087 |        -0.1744 |          1      |
| M4R       | holdout  | 2024-01-01 | 2024-12-31 |        3 |          0.8003 |      -0.005  |        -0.071  |          1      |
| P2A       | train    | 2020-01-01 | 2022-12-31 |       14 |          3.443  |       0.0634 |         1.2969 |          1.3673 |
| P2A       | validate | 2023-01-01 | 2023-12-31 |        9 |          0.4249 |      -0.0197 |        -0.3841 |          1      |
| P2A       | holdout  | 2024-01-01 | 2024-12-31 |        6 |          0.4604 |      -0.0105 |        -0.2229 |          1      |
| P2B       | train    | 2020-01-01 | 2022-12-31 |       13 |          3.9626 |       0.072  |         1.4319 |          1.2977 |
| P2B       | validate | 2023-01-01 | 2023-12-31 |        6 |          0.3786 |      -0.0224 |        -0.4242 |          1      |
| P2B       | holdout  | 2024-01-01 | 2024-12-31 |        6 |          0.4604 |      -0.0105 |        -0.2229 |          1      |

## Decision matrix (realism fee=20/30, min_hold=3)

|   trades |   expectancy_r |   profit_factor |   max_drawdown |   trades_per_year |   pct_hit_1r |   pct_hit_2r |   top10_pct_pnl | version   | setting        | realism   | pass_exp_r   | pass_pf   | pass_tpy   | pass_top10   |   pass_realism | group      |
|---------:|---------------:|----------------:|---------------:|------------------:|-------------:|-------------:|----------------:|:----------|:---------------|:----------|:-------------|:----------|:-----------|:-------------|---------------:|:-----------|
|        4 |      0.443575  |       1.45197   |     -0.0284654 |          1.04357  |     0.25     |     0.25     |               1 | M1        | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.406899  |       1.36831   |     -0.0304065 |          1.04357  |     0.25     |     0.25     |               1 | M1        | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.517115  |       1.63778   |     -0.0245714 |          1.04357  |     0.25     |     0.25     |               1 | M1        | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
|        0 |    nan         |     nan         |    nan         |        nan        |   nan        |   nan        |             nan | M2        | fee20_minhold3 | True      | False        | False     | False      | True         |              0 | Noise      |
|        0 |    nan         |     nan         |    nan         |        nan        |   nan        |   nan        |             nan | M2        | fee30_minhold3 | True      | False        | False     | False      | True         |              0 | Noise      |
|        0 |    nan         |     nan         |    nan         |        nan        |   nan        |   nan        |             nan | M2        | gross          | False     | False        | False     | False      | True         |            nan | Noise      |
|        5 |      0.49082   |       3.17498   |     -0.0501312 |          0.959669 |     0.2      |     0.2      |               1 | M3        | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        5 |      0.445439  |       2.83327   |     -0.0539231 |          0.959669 |     0.2      |     0.2      |               1 | M3        | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        5 |      0.581854  |       4.04726   |     -0.0425018 |          0.959669 |     0.2      |     0.2      |               1 | M3        | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
|        4 |     -0.584647  |     nan         |     -0.0744142 |          0.989837 |     0        |     0        |               1 | M4        | fee20_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.619524  |     nan         |     -0.0799511 |          0.989837 |     0        |     0        |               1 | M4        | fee30_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.30966   |       0.0665676 |     -0.0296164 |          0.988498 |     0        |     0        |               1 | M4        | gross          | False     | False        | False     | False      | False        |            nan | Noise      |
|        4 |      0.443575  |       1.45197   |     -0.0284654 |          1.04357  |     0.25     |     0.25     |               1 | M5        | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.406899  |       1.36831   |     -0.0304065 |          1.04357  |     0.25     |     0.25     |               1 | M5        | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.517115  |       1.63778   |     -0.0245714 |          1.04357  |     0.25     |     0.25     |               1 | M5        | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
|        3 |      0.456689  |       1.27365   |     -0.0284654 |          6.64091  |     0.333333 |     0.333333 |               1 | M6        | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        3 |      0.421377  |       1.21313   |     -0.0304065 |          6.64091  |     0.333333 |     0.333333 |               1 | M6        | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        3 |      0.527482  |       1.40806   |     -0.0245714 |          6.64091  |     0.333333 |     0.333333 |               1 | M6        | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
|        4 |     -0.588635  |       0.0752276 |     -0.0561092 |          0.989837 |     0        |     0        |               1 | M7        | fee20_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.665741  |       0.0571219 |     -0.0636079 |          0.989837 |     0        |     0        |               1 | M7        | fee30_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.492796  |       0.112928  |     -0.0485277 |          0.989837 |     0        |     0        |               1 | M7        | gross          | False     | False        | False     | False      | False        |            nan | Noise      |
|        4 |     -0.55371   |     nan         |     -0.0726867 |          1.00481  |     0        |     0        |               1 | M8        | fee20_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.588338  |     nan         |     -0.078234  |          1.00481  |     0        |     0        |               1 | M8        | fee30_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        4 |     -0.484279  |     nan         |     -0.0614919 |          1.00481  |     0        |     0        |               1 | M8        | gross          | False     | False        | False     | False      | False        |            nan | Noise      |
|        6 |     -0.0417225 |       0.733039  |     -0.0873914 |          1.04506  |     0.166667 |     0.166667 |               1 | M9        | fee20_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        6 |     -0.0779024 |       0.690572  |     -0.0910346 |          1.04506  |     0.166667 |     0.166667 |               1 | M9        | fee30_minhold3 | True      | False        | False     | False      | False        |              0 | Noise      |
|        6 |      0.0308005 |       0.827454  |     -0.0812112 |          1.04506  |     0.166667 |     0.166667 |               1 | M9        | gross          | False     | False        | False     | False      | False        |            nan | Noise      |
|        4 |      0.443575  |       1.45197   |     -0.0284654 |          1.04357  |     0.25     |     0.25     |               1 | M10       | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.406899  |       1.36831   |     -0.0304065 |          1.04357  |     0.25     |     0.25     |               1 | M10       | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.517115  |       1.63778   |     -0.0245714 |          1.04357  |     0.25     |     0.25     |               1 | M10       | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
|        4 |      0.443575  |       1.45197   |     -0.0284654 |          1.04357  |     0.25     |     0.25     |               1 | M11       | fee20_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.406899  |       1.36831   |     -0.0304065 |          1.04357  |     0.25     |     0.25     |               1 | M11       | fee30_minhold3 | True      | True         | True      | False      | False        |              0 | Gross-only |
|        4 |      0.517115  |       1.63778   |     -0.0245714 |          1.04357  |     0.25     |     0.25     |               1 | M11       | gross          | False     | True         | True      | False      | False        |            nan | Gross-only |
## Conclusion

Based on 2012–2026 realism results and existing gates (D1/D2/D3), these Minervini-style configs remain **RESEARCH ONLY / DO NOT DEPLOY**.
