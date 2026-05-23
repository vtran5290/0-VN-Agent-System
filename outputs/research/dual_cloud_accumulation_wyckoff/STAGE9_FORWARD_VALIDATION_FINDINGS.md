# Stage 9 — Forward Validation Findings

**Ledger rows:** 920  |  **63d matured:** 836  |  **Data cutoff:** 2026-05-21

## Overall Summary (per horizon)

|   horizon |   n_matured |   win_rate_15pct |   loss_rate_8pct |   avg_net_return |   med_net_return |   pct_positive |
|----------:|------------:|-----------------:|-----------------:|-----------------:|-----------------:|---------------:|
|         5 |         912 |        0.0263158 |        0.0405702 |       0.00274762 |      -0.00227415 |       0.447368 |
|        10 |         904 |        0.0442478 |        0.085177  |       0.00467534 |      -0.00202546 |       0.464602 |
|        20 |         889 |        0.0933633 |        0.188976  |       0.00701449 |      -0.00536673 |       0.467942 |
|        40 |         863 |        0.152955  |        0.280417  |       0.0143344  |      -0.012736   |       0.457706 |
|        63 |         836 |        0.196172  |        0.296651  |       0.0272354  |      -0.0155644  |       0.441388 |

## By Watchlist Flag (h=63)

| breakout_value_expansion_watchlist_flag   |   n_matured |   win_rate_15pct |   loss_rate_8pct |   avg_net_return |   med_net_return |   pct_positive |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|:------------------------------------------|------------:|-----------------:|-----------------:|-----------------:|-----------------:|---------------:|---------------:|--------------:|--------------:|
| False                                     |         475 |         0.183158 |         0.271579 |        0.0286384 |      -0.00770218 |       0.452632 |       0.324211 |     -0.120016 |      0.179394 |
| True                                      |         361 |         0.213296 |         0.32964  |        0.0253893 |      -0.0229781  |       0.426593 |       0.382271 |     -0.140314 |      0.204998 |

## By Year (h=63)

|   year |   n_matured |   win_rate_15pct |   loss_rate_8pct |   avg_net_return |   med_net_return |   pct_positive |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|-------:|------------:|-----------------:|-----------------:|-----------------:|-----------------:|---------------:|---------------:|--------------:|--------------:|
|   2024 |         393 |        0.127226  |         0.330789 |       -0.0122731 |       -0.0309889 |       0.374046 |       0.231552 |     -0.127616 |      0.133016 |
|   2025 |         371 |        0.291105  |         0.231806 |        0.0870652 |        0.0141844 |       0.533693 |       0.485175 |     -0.121246 |      0.253832 |
|   2026 |          72 |        0.0833333 |         0.444444 |       -0.0654044 |       -0.064235  |       0.333333 |       0.291667 |     -0.173963 |      0.177354 |

## By Liquidity Bucket (h=63)

| liquidity_bucket   |   n_matured |   win_rate_15pct |   loss_rate_8pct |   avg_net_return |   med_net_return |   pct_positive |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|:-------------------|------------:|-----------------:|-----------------:|-----------------:|-----------------:|---------------:|---------------:|--------------:|--------------:|
| 20B_plus           |         450 |         0.18     |         0.291111 |        0.0184054 |       -0.0162176 |       0.435556 |       0.304444 |     -0.129693 |      0.169242 |
| 2B_5B              |         132 |         0.212121 |         0.30303  |        0.0392504 |       -0.015772  |       0.439394 |       0.371212 |     -0.126618 |      0.21195  |
| 5B_20B             |         254 |         0.216535 |         0.30315  |        0.0366349 |       -0.0124546 |       0.452756 |       0.417323 |     -0.128289 |      0.216852 |

## Interpretation Notes

- Forward returns are close-to-close (signal bar close → close N bars later).
- Entry price (`close_kvnd`) = open of t+1 bar from Stage 8 ledger.
- TP1 = max(high) over [t+1, t+63] ≥ entry × 1.18.
- MAE = min(low) / entry − 1 over same window.
- MFE = max(high) / entry − 1 over same window.
- Rows with incomplete future windows have matured=False and NaN outcomes.
- **This file is RESEARCH ONLY. Not OMS input.**
