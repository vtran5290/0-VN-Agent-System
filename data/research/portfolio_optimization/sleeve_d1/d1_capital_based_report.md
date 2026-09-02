# D1 Capital-Based Combined Validation

**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Recommendation:** B
**Gates passed:** 6/8

## Capital-based vs return-switched (DISPLAY-ONLY)
- Complementary MAR @1.0% slip (capital-based): **0.2212**
- A3 alone MAR (capital-based): **0.1915**
- Return-switched MAR (DISPLAY-ONLY / NOT A GATE): **0.9775**
- Mechanical inflation: **0.7563**

## Gate verdicts (capital-based curve only)
- **G1:** PASS — comp=0.2212 vs a3=0.1915 @1.0% slip
- **G2:** PASS — comp=0.2161 vs a3=0.1915 @1.5% slip
- **G3:** FAIL — comp_dd=-0.1553 a3_dd=-0.1828 improve=15.0%
- **G4:** FAIL — ex20 dd improve ~17.5% ex22 ~15.3%
- **G5:** PASS — ex2020+2022 incr MAR proxy: comp=0.2650 a3=0.2259
- **G6:** PASS — OOS MAR comp positive=True
- **G7:** PASS — Code assertion — no violation raised during simulation
- **G8:** PASS — max pnl share=33.6% max incr share=38.3%

## Slippage sweep (complementary)
 d1_slippage     slippage_label  mar_complementary  mar_a3_alone  mar_d1_alone  max_dd_complementary
       0.005 display_optimistic           0.226372      0.191485      0.294701             -0.154195
       0.010          base_case           0.221184      0.191485      0.237808             -0.155266
       0.015  hard_advance_gate           0.216117      0.191485      0.183702             -0.156325
       0.020  stress_diagnostic           0.211166      0.191485      0.127910             -0.157372
       0.030  stress_diagnostic           0.201597      0.191485      0.029753             -0.159434

## Crash-year removal
          filter    mar_a3  mar_complementary  incremental_mar
            full  0.191485           0.221184         0.029699
         ex_2020 -0.025924          -0.020689         0.005235
         ex_2022  0.191485           0.219206         0.027721
ex_2020_and_2022 -0.001570           0.004343         0.005912

## Concentration by year
 entry_year  n_trades  gross_pnl_vnd  pnl_share  incremental_return   incr_share
       2012         7   8.936693e+07   0.011598        3.803561e-04 1.104501e-03
       2013        22   7.394712e+08   0.095970        1.428554e-06 4.148323e-06
       2014        49   7.485749e+08   0.097151       -6.635799e-08 1.926944e-07
       2015        21   2.774806e+07   0.003601        1.867332e-03 5.422473e-03
       2016        48   2.050142e+08   0.026607        1.455002e-02 4.225124e-02
       2017        63  -6.099898e+07  -0.007917       -2.192142e-02 6.365676e-02
       2018        57   1.956637e+08   0.025394       -2.726832e-02 7.918341e-02
       2019        49   4.861014e+08   0.063087        1.996128e-02 5.796477e-02
       2020        86   9.734848e+08   0.126340        3.901539e-02 1.132953e-01
       2021        53   6.965242e+08   0.090396       -1.318011e-01 3.827321e-01
       2022       210   2.592333e+09   0.336437        3.723561e-02 1.081270e-01
       2023        62   7.669972e+08   0.099542        8.353210e-03 2.425656e-02
       2024        30  -3.045400e+07  -0.003952       -1.233328e-02 3.581414e-02
       2025        41   3.267452e+07   0.004241        2.786214e-02 8.090776e-02
       2026        40   2.427620e+08   0.031506       -1.818160e-03 5.279683e-03


## Interpretation
- All decision gates evaluate the **capital-based** shared cash account, not return-switched.
- Return-switched 0.977 is retained only to show mechanical inflation magnitude.
- Gate 7 enforced via AssertionError on settlement / over-allocation.
- Output A/B/C does NOT authorize live capital.