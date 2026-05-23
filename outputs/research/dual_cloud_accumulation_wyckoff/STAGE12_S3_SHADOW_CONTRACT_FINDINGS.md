# Stage 12 — S3 Paper-Shadow Contract Validation

**Total S3 signals (ADV-gated, full universe):** 3790
**Baseline (BASE_REGIME) matured:** 2669 | Win rate: 22.9% | TP1 rate: 37.0% | Avg net: -0.05%

## Contract Specification

- Entry: open[t+1]
- TP1: +18% → exits 50% of position
- Trail: 3.5× ATR14 on remainder
- MaxHold: 60 bars
- Cost: 40 bps round-trip
- Gate: VNINDEX regime (EMA21/55) + ADV50 ≥ 2 B VND

## Variant Summary

| variant_name        |   n_signals |   n_matured |   win_rate |   tp1_rate |   avg_net_return | classification          |
|:--------------------|------------:|------------:|-----------:|-----------:|-----------------:|:------------------------|
| BASE_NO_REGIME      |        3790 |        3681 |   0.220049 |   0.357783 |     -0.0036432   | PAPER_TRADE_SHADOW      |
| BASE_REGIME         |        2744 |        2669 |   0.22855  |   0.370176 |     -0.000473448 | PAPER_TRADE_SHADOW      |
| BVE_Q45             |        1978 |        1924 |   0.233368 |   0.385655 |      0.000425862 | WATCHLIST_ONLY          |
| BVE_Q5              |        1361 |        1327 |   0.239638 |   0.400904 |      0.00190742  | WATCHLIST_ONLY          |
| TPBCQ_Q45           |        1064 |        1030 |   0.236893 |   0.359223 |      0.0039166   | WATCHLIST_ONLY          |
| TPBCQ_Q5            |         430 |         413 |   0.227603 |   0.329298 |      0.00456694  | PAPER_TRADE_SHADOW      |
| BVE_TPBCQ_COMBO_Q45 |         763 |         743 |   0.236878 |   0.375505 |      0.00712504  | WATCHLIST_ONLY          |
| BVE_TPBCQ_COMBO_Q5  |         206 |         203 |   0.246305 |   0.374384 |      0.017206    | WATCHLIST_ONLY          |
| ADV5B               |        2215 |        2156 |   0.21846  |   0.359462 |     -0.0060228   | PAPER_TRADE_SHADOW      |
| ADV10B              |        1718 |        1674 |   0.213262 |   0.348268 |     -0.00951759  | PAPER_TRADE_SHADOW      |
| BVE_Q45_ADV5B       |        1596 |        1552 |   0.224871 |   0.375    |     -0.00452921  | PAPER_TRADE_SHADOW      |
| BVE_Q45_ADV10B      |        1222 |        1190 |   0.223529 |   0.362185 |     -0.00809378  | PAPER_TRADE_SHADOW      |
| EX_VIN_BASE         |        2706 |        2631 |   0.22881  |   0.370962 |     -0.00057723  | WATCHLIST_ONLY          |
| EX_VIN_BVE_Q45      |        1953 |        1899 |   0.233281 |   0.386519 |      0.000720428 | WATCHLIST_ONLY          |
| EXCL_2022           |        2556 |        2481 |   0.240226 |   0.381298 |      0.0175559   | WATCHLIST_ONLY          |
| EXCL_2024           |        2375 |        2300 |   0.243043 |   0.389565 |      0.00231599  | WATCHLIST_ONLY          |
| BVE_Q45_EXCL_2022   |        1841 |        1787 |   0.243984 |   0.398433 |      0.0179581   | WATCHLIST_ONLY          |
| BVE_Q45_EXCL_2024   |        1724 |        1670 |   0.251497 |   0.405988 |      0.00377099  | WATCHLIST_ONLY          |
| TP1_22PCT           |        2744 |        2667 |   0.287214 |   0.299588 |      0.00193706  | WATCHLIST_ONLY          |
| TP1_15PCT           |        2744 |        2672 |   0.156811 |   0.434506 |     -0.00277086  | PAPER_TRADE_SHADOW      |
| TRAIL_2_5X          |        2744 |        2669 |   0.247284 |   0.370176 |     -0.00286666  | WATCHLIST_ONLY          |
| TRAIL_4_5X          |        2744 |        2668 |   0.22976  |   0.36994  |      0.00224984  | WATCHLIST_ONLY          |
| MAX_HOLD_30         |        2744 |        2688 |   0.146949 |   0.220982 |     -0.00413433  | PAPER_TRADE_SHADOW      |
| MAX_HOLD_120        |        2744 |        2583 |   0.310492 |   0.512195 |      0.0113852   | PARALLEL_PAPER_RESEARCH |

## By Year (BASE_REGIME)

|   year |   n_matured |   win_rate |   tp1_rate |   avg_net_return |   pct_positive |   max_hold_rate |
|-------:|------------:|-----------:|-----------:|-----------------:|---------------:|----------------:|
|   2012 |          12 |  0.416667  |  0.916667  |        0.155327  |       0.916667 |       0.0833333 |
|   2013 |         106 |  0.311321  |  0.443396  |        0.023466  |       0.566038 |       0.650943  |
|   2014 |         103 |  0.223301  |  0.427184  |        0.0304891 |       0.572816 |       0.61165   |
|   2015 |          85 |  0.105882  |  0.211765  |       -0.0563901 |       0.305882 |       0.823529  |
|   2016 |         123 |  0.178862  |  0.317073  |       -0.0194823 |       0.463415 |       0.772358  |
|   2017 |         210 |  0.285714  |  0.433333  |        0.0383052 |       0.604762 |       0.614286  |
|   2018 |         106 |  0.141509  |  0.207547  |       -0.101485  |       0.283019 |       0.801887  |
|   2019 |         168 |  0.0654762 |  0.0892857 |       -0.0541311 |       0.309524 |       0.922619  |
|   2020 |         199 |  0.366834  |  0.557789  |        0.0950781 |       0.738693 |       0.517588  |
|   2021 |         292 |  0.349315  |  0.544521  |        0.0703633 |       0.664384 |       0.530822  |
|   2022 |         188 |  0.0744681 |  0.223404  |       -0.238404  |       0.255319 |       0.781915  |
|   2023 |         221 |  0.289593  |  0.371041  |        0.031182  |       0.547511 |       0.782805  |
|   2024 |         369 |  0.138211  |  0.249322  |       -0.0178602 |       0.409214 |       0.799458  |
|   2025 |         390 |  0.289744  |  0.461538  |        0.0459879 |       0.6      |       0.574359  |
|   2026 |          97 |  0.154639  |  0.360825  |       -0.0272298 |       0.42268  |       0.639175  |

## By Regime Gate

| regime_bull   |   n_matured |   win_rate |   tp1_rate |   avg_net_return |   pct_positive |   max_hold_rate |
|:--------------|------------:|-----------:|-----------:|-----------------:|---------------:|----------------:|
| False         |        1012 |   0.197628 |   0.325099 |     -0.012003    |       0.48913  |        0.756917 |
| True          |        2669 |   0.22855  |   0.370176 |     -0.000473448 |       0.508805 |        0.684151 |

## By Liquidity Bucket (BASE_REGIME)

| liquidity_bucket   |   n_matured |   win_rate |   tp1_rate |   avg_net_return |   pct_positive |   max_hold_rate |
|:-------------------|------------:|-----------:|-----------:|-----------------:|---------------:|----------------:|
| high               |        1193 |   0.210394 |   0.332775 |      -0.0136825  |       0.480302 |        0.714166 |
| low                |         513 |   0.270955 |   0.415205 |       0.022849   |       0.559454 |        0.641326 |
| mid                |         963 |   0.228453 |   0.392523 |       0.00346632 |       0.517134 |        0.669782 |

## Classification Summary

- **PAPER_TRADE_SHADOW**: 9 variant(s)
- **PARALLEL_PAPER_RESEARCH**: 1 variant(s)
- **WATCHLIST_ONLY**: 14 variant(s)

## Interpretation Notes

- Win rate = fraction of matured trades with blended_net_return ≥ +15%.
- Blended return = 50% × TP1_level_return + 50% × trail/max_hold_return.
- `missing_atr_flag=True` trades used 2% ATR fallback — treat as approximate.
- S3 classification cap: PAPER_TRADE_SHADOW (base) / PARALLEL_PAPER_RESEARCH (filters).
- S3 CANNOT be PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY.
- MAX_HOLD_REJECTED = 250 bars is defined for reference only; not used as a variant.
- **This file is RESEARCH / OBSERVATION ONLY. Not OMS input.**
