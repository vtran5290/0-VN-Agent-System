# Stage 5 — Wyckoff Tags Incremental Value

**Universe:** ex-VIN | **Run date:** 2026-05-22

## Objective
Test whether mechanical Wyckoff tags add value beyond price/volume tightness.
Three feature sets compared: tightness_only → tightness+breakout → +wyckoff.

## Feature set comparison (Q5 = top 20% of signals by score, 63-bar horizon)

| feature_set          |   n_all |   n_q5 |   baseline_wr |   q5_win_rate |   q5_avg_ret |   delta_vs_baseline |
|:---------------------|--------:|-------:|--------------:|--------------:|-------------:|--------------------:|
| tightness_only       |    2771 |    546 |        0.2241 |        0.1575 |      -0.0034 |             -0.0666 |
| tightness_bo         |    2771 |    543 |        0.2241 |        0.1842 |       0.0120 |             -0.0399 |
| tightness_bo_wyckoff |    2771 |    542 |        0.2241 |        0.1900 |       0.0158 |             -0.0341 |

## Wyckoff tag presence by return bucket
(Higher rate in winner bucket = tag is positively predictive)

| tag    |   gain_0_10pct |   gain_10_18pct |   loss_0_8pct |   loss_gt8pct |   winner_gt18pct |
|:-------|---------------:|----------------:|--------------:|--------------:|-----------------:|
| efvr   |          0.443 |           0.466 |         0.399 |         0.460 |            0.404 |
| lps    |          0.052 |           0.027 |         0.040 |         0.040 |            0.034 |
| sos    |          0.162 |           0.210 |         0.177 |         0.216 |            0.238 |
| spring |          0.004 |           0.000 |         0.003 |         0.000 |            0.004 |
| utad   |          0.383 |           0.409 |         0.381 |         0.384 |            0.428 |

## FACTS vs INTERPRETATION

**FACTS:**
- N total trades: 2855
- Feature sets tested: tightness_only, tightness_bo, tightness_bo_wyckoff

**INTERPRETATION:**
- Wyckoff adds value if tightness_bo_wyckoff Q5 win_rate > tightness_bo Q5 by > 3 pp.
- Tag presence in winner_gt18pct bucket > loss_gt8pct bucket = directionally correct.
- UTAD should appear more in loss buckets (it is a warning tag, not bullish).
- efvr: low score (high vol / low net move) should appear more in loss buckets.

## Next step
Proceed to Stage 6 (robustness across years, regimes, sectors, liquidity).