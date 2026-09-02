# D4 Cash-Plus / Exposure Timing Validation

**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Hierarchy winner:** Level 1 (cash-plus)
**Recommendation:** A
**Gates passed:** 6/7

## Baselines (capital-based only)
- A3 alone (L0): 0.1915 (reference 0.1915)
- D1 reference (L3 import): 0.2212
- D1 incremental vs A3: 0.0297

## Hierarchy results
level                                                arm      mar     cagr    max_dd
   L0                                A3_alone_0pct_yield 0.191485 0.034994 -0.182750
   L1                              cash_plus_0% baseline 0.191485 0.034994 -0.182750
   L1 cash_plus_1.9% net — VND savings ~2% gross, 5% WHT 0.281791 0.045860 -0.162744
   L1 cash_plus_2.85% net — VND T-bill ~3% gross, 5% WHT 0.336829 0.051362 -0.152485
   L1      cash_plus_3.8% net — VN MMF ~4% gross, 5% WHT 0.395088 0.056910 -0.144044
  L2a                          overlay_vnindex_25pct_off 0.202001 0.035721 -0.176837
  L2a                          overlay_vnindex_50pct_off 0.177913 0.033698 -0.189410
  L2a                          overlay_vnindex_75pct_off 0.110440 0.023610 -0.213785
   L3                             A3_D1_reference_import 0.221184      NaN       NaN

## Placebo (100 seeds)
 overlay_frac  placebo_mean_mar  placebo_p5  placebo_p95
         0.25         -0.102312   -0.108044    -0.096133
         0.50         -0.169683   -0.177608    -0.161759
         0.75         -0.244178   -0.255107    -0.232063

## Gate verdicts
- **G1:** PASS — MAR=0.3951
- **G2:** PASS — MaxDD=-0.1440
- **G3:** PASS — incr=0.2563
- **G4:** PASS — OOS MAR=0.6592
- **G5:** PASS — Settlement/cash assertions OK
- **G6:** FAIL — L2-L1=-0.1931
- **G7:** PASS — L2=0.2020 p95=-0.0961

**D1 benefit captured by D4 winner:** 685.6%

## Crash-year removal
    arm           filter      mar
L1_best             full 0.395088
L1_best          ex_2020 0.444279
L1_best          ex_2022 0.426164
L1_best ex_2020_and_2022 0.482231
L2_best             full 0.202001
L2_best          ex_2020 0.219857
L2_best          ex_2022 0.217718
L2_best ex_2020_and_2022 0.238419

## Interpretation
- Comparisons use capital-based A3 MAR 0.191 — NOT legacy 0.381.
- Level 1 (cash-plus) is the null hypothesis; Level 2 needs +0.02 MAR vs L1 and beat placebo p95.
- If cash-plus alone clears gates, that is a valid positive result (cheapest solution wins).