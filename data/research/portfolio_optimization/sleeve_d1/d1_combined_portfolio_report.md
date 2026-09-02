# D1 + A3 Combined Portfolio

**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**D1 slippage (combined test):** 1.0%
**A3 annual recompute vs p3_annual_returns.csv:** OK (max abs diff 0.0019820291412973798)

**Complementary beats A3 MAR alone:** True (A3=0.3811, complementary=0.9775)

## Variant summary

                  variant    mar   cagr  max_dd  worst_year_return  ex_best_year_mar  mean_cash_fraction  ret_2020  ret_2022  ret_2026
                 A3_alone 0.3811 0.0696 -0.1826            -0.1336            0.4114              0.5026   -0.1336    0.1569   -0.0544
                 D1_alone 0.2230 0.0211 -0.0947            -0.0702            0.2556              0.8064    0.0263    0.1763    0.0113
      A3_D1_complementary 0.9775 0.0925 -0.0947            -0.0499            1.0542              0.6020    0.0034    0.0981   -0.0499
A3_D1_unconstrained_70_30 0.4128 0.0558 -0.1351            -0.0879            0.4446              0.5937   -0.0879    0.1655   -0.0350
A3_D1_unconstrained_80_20 0.3970 0.0600 -0.1512            -0.1033            0.4276              0.5633   -0.1033    0.1629   -0.0415
A3_D1_unconstrained_60_40 0.4324 0.0514 -0.1189            -0.0723            0.4656              0.6241   -0.0723    0.1679   -0.0284

## Interpretation
- **A3_D1_complementary** is the primary diversification case (D1 only when EMA20<EMA100 gate OFF).
- Unconstrained splits are sensitivity only (70/30, 80/20, 60/40).
- Focus years 2020/2022/2026 are A3-weak periods where D1 should add value if diversification is real.