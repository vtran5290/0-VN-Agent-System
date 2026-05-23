# Stage 2 — A3 Candidate Ranking Overlay

**Universe:** ex-VIN | **Run date:** 2026-05-22

## Objective
Test whether ranking A3 candidates by accumulation score improves outcomes.
Top-3-per-day bucket vs all-signal baseline. Primary horizon: 63 bars.

## Bucket comparison (63-bar horizon)

| bucket            |   n_trades |   win_rate |   loss_rate |   avg_net_ret |   med_net_ret |   pct_positive |
|:------------------|-----------:|-----------:|------------:|--------------:|--------------:|---------------:|
| all_signals       |       2771 |     0.2241 |      0.3212 |        0.0268 |       -0.0146 |         0.4608 |
| top_3_by_score    |       2528 |     0.2211 |      0.3196 |        0.0272 |       -0.0150 |         0.4597 |
| top_quintile_q4q5 |       1097 |     0.1942 |      0.3081 |        0.0131 |       -0.0183 |         0.4412 |

**Delta top3 vs all:** -0.3%
**Delta topQ vs all:** -3.0%

## By-year breakdown

|   year | bucket   |   n_trades |   win_rate |   avg_ret |
|-------:|:---------|-----------:|-----------:|----------:|
|   2012 | all      |         27 |     0.2963 |   -0.0321 |
|   2012 | top3     |         27 |     0.2963 |   -0.0321 |
|   2012 | topq     |          7 |     0.2857 |   -0.0335 |
|   2013 | all      |        102 |     0.3333 |    0.0837 |
|   2013 | top3     |         99 |     0.3232 |    0.0802 |
|   2013 | topq     |         45 |     0.2667 |    0.0686 |
|   2014 | all      |         98 |     0.1837 |    0.0348 |
|   2014 | top3     |         97 |     0.1856 |    0.0365 |
|   2014 | topq     |         50 |     0.2000 |    0.0582 |
|   2015 | all      |        110 |     0.0818 |   -0.0625 |
|   2015 | top3     |        109 |     0.0826 |   -0.0626 |
|   2015 | topq     |         40 |     0.0750 |   -0.0679 |
|   2016 | all      |        115 |     0.1043 |   -0.0342 |
|   2016 | top3     |        114 |     0.1053 |   -0.0344 |
|   2016 | topq     |         52 |     0.0577 |   -0.0455 |
|   2017 | all      |        163 |     0.3006 |    0.0884 |
|   2017 | top3     |        162 |     0.2963 |    0.0854 |
|   2017 | topq     |         55 |     0.3091 |    0.0985 |
|   2018 | all      |        156 |     0.1218 |   -0.0647 |
|   2018 | top3     |        153 |     0.1176 |   -0.0656 |
|   2018 | topq     |         66 |     0.0909 |   -0.0448 |
|   2019 | all      |        167 |     0.0778 |   -0.0454 |
|   2019 | top3     |        160 |     0.0812 |   -0.0419 |
|   2019 | topq     |         78 |     0.0769 |   -0.0500 |
|   2020 | all      |        274 |     0.3613 |    0.1214 |
|   2020 | top3     |        247 |     0.3725 |    0.1292 |
|   2020 | topq     |        109 |     0.3303 |    0.0992 |
|   2021 | all      |        212 |     0.4811 |    0.2288 |
|   2021 | top3     |        197 |     0.4569 |    0.2151 |
|   2021 | topq     |         58 |     0.3966 |    0.1308 |
|   2022 | all      |        197 |     0.0508 |   -0.2114 |
|   2022 | top3     |        177 |     0.0565 |   -0.1978 |
|   2022 | topq     |         75 |     0.0400 |   -0.2101 |
|   2023 | all      |        314 |     0.2739 |    0.0522 |
|   2023 | top3     |        280 |     0.2679 |    0.0539 |
|   2023 | topq     |        133 |     0.2481 |    0.0295 |
|   2024 | all      |        393 |     0.1196 |   -0.0170 |
|   2024 | top3     |        341 |     0.1144 |   -0.0171 |
|   2024 | topq     |        175 |     0.1029 |   -0.0159 |
|   2025 | all      |        371 |     0.2938 |    0.0872 |
|   2025 | top3     |        308 |     0.2922 |    0.0862 |
|   2025 | topq     |        146 |     0.2808 |    0.0797 |
|   2026 | all      |         72 |     0.0833 |   -0.0695 |
|   2026 | top3     |         57 |     0.0877 |   -0.0558 |
|   2026 | topq     |          8 |     0.0000 |   -0.0302 |

## FACTS vs INTERPRETATION

**FACTS:**
- All signals: win_rate=22.4%
- Top-3 by score: win_rate=22.1%
- Top quintile (Q4/Q5): win_rate=19.4%

**INTERPRETATION:**
- Ranking adds value if top3 win_rate > all by > 5 pp with n > 40.
- If delta < 3 pp: score is not selective enough for ranking use.
- Year consistency required: check year_df above.

## Next step
- If ranking adds value: proceed to Stage 3 (T2 timing).
- If not: revisit score weights in features.py.