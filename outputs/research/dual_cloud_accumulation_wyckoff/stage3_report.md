# Stage 3 — A3 T2 Add-On Timing

**Universe:** ex-VIN | **Run date:** 2026-05-22

## Objective
Test whether accumulation score at T1 entry predicts T2 fill probability
and T2 outcome. A3 T2 = 50% add-on on ≥4% pullback within 30 bars.

**Overall T2 fill rate:** 70.9% across 2855 entries

## T2 fill rate and outcome by score quintile

|   score_q |   n_entries |   t2_fill_rate |   n_t2_filled |   t2_win_rate |   t2_avg_ret |   t1_avg_ret |
|----------:|------------:|---------------:|--------------:|--------------:|-------------:|-------------:|
|    1.0000 |    571.0000 |         0.7758 |      443.0000 |        0.2483 |       0.0404 |       0.0435 |
|    2.0000 |    571.0000 |         0.7320 |      418.0000 |        0.2225 |       0.0417 |       0.0418 |
|    3.0000 |    571.0000 |         0.7250 |      414.0000 |        0.1860 |       0.0079 |       0.0218 |
|    4.0000 |    571.0000 |         0.6690 |      382.0000 |        0.1911 |       0.0115 |       0.0312 |
|    5.0000 |    571.0000 |         0.6445 |      368.0000 |        0.1495 |      -0.0075 |      -0.0052 |

## By-year breakdown

|      year |   n_entries |   t2_fill_rate |   t2_avg_ret |
|----------:|------------:|---------------:|-------------:|
| 2012.0000 |     27.0000 |         0.7778 |      -0.0370 |
| 2013.0000 |    102.0000 |         0.6078 |       0.0484 |
| 2014.0000 |     98.0000 |         0.5918 |       0.0112 |
| 2015.0000 |    110.0000 |         0.7455 |      -0.0477 |
| 2016.0000 |    115.0000 |         0.7304 |      -0.0277 |
| 2017.0000 |    163.0000 |         0.6687 |       0.0698 |
| 2018.0000 |    156.0000 |         0.8462 |      -0.0583 |
| 2019.0000 |    167.0000 |         0.7365 |      -0.0536 |
| 2020.0000 |    274.0000 |         0.6241 |       0.1411 |
| 2021.0000 |    212.0000 |         0.7736 |       0.2481 |
| 2022.0000 |    197.0000 |         0.8528 |      -0.2186 |
| 2023.0000 |    314.0000 |         0.6561 |       0.0391 |
| 2024.0000 |    393.0000 |         0.7455 |      -0.0028 |
| 2025.0000 |    372.0000 |         0.6048 |       0.0806 |
| 2026.0000 |    155.0000 |         0.8194 |      -0.0791 |

## FACTS vs INTERPRETATION

**FACTS:**
- Overall T2 fill rate = 70.9%
- N entries = 2855 across 248 symbols

**INTERPRETATION:**
- If high-score (Q4/Q5) entries have meaningfully higher T2 fill rates AND
  better post-fill returns → score helps identify better T2 setups.
- If fill rate uniform across quintiles → score does not predict T2 timing.
- T2 win_rate > T2 fill rate × all-signal wr → T2 is accretive for high scores.

## Next step
Proceed to Stage 4 (S3 shadow quality) regardless of Stage 3 outcome.