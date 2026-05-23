# Stage 4 — S3 Shadow Quality Filter

**Universe:** ex-VIN | **Run date:** 2026-05-22

## Objective
Test whether filtering S3 max60 signals by accumulation score improves quality.
S3 is PAPER_TRADE_SHADOW only — no real capital, no DNSE orders.

## S3 max60 simulation parameters
- TP1 = +18% (simplified: full exit at TP1; contract is 50/50 split — quality proxy only)
- Trail = 3.5× ATR14 from high-water
- Max hold = 60 bars
- VNINDEX regime gate applied
- ADV50 ≥ 2B VND (corrected formula)

## Bucket comparison

| bucket      |   n_trades |   win_rate |   loss_rate |   avg_net_ret |   med_net_ret |   tp1_rate |   trail_rate |   maxhold_rate |
|:------------|-----------:|-----------:|------------:|--------------:|--------------:|-----------:|-------------:|---------------:|
| all_s3      |       2706 |     0.2546 |      0.3182 |        0.0034 |       -0.0331 |     0.2506 |       0.6441 |         0.1053 |
| top_q45     |       1082 |     0.2135 |      0.2468 |        0.0050 |       -0.0272 |     0.2070 |       0.6821 |         0.1109 |
| top_q5_only |        541 |     0.1922 |      0.2255 |        0.0025 |       -0.0273 |     0.1867 |       0.6950 |         0.1183 |

**Delta top_q45 vs all_s3:** -4.1%

## By-year breakdown

|   year | bucket   |   n_trades |   win_rate |   avg_ret |
|-------:|:---------|-----------:|-----------:|----------:|
|   2012 | all      |         12 |     0.7500 |    0.1519 |
|   2012 | topq     |          5 |     0.4000 |    0.0973 |
|   2013 | all      |        102 |     0.3529 |    0.0392 |
|   2013 | topq     |         62 |     0.3226 |    0.0408 |
|   2014 | all      |        102 |     0.3039 |    0.0276 |
|   2014 | topq     |         52 |     0.2885 |    0.0325 |
|   2015 | all      |         82 |     0.1585 |   -0.0450 |
|   2015 | topq     |         28 |     0.1429 |   -0.0360 |
|   2016 | all      |        122 |     0.1721 |   -0.0182 |
|   2016 | topq     |         49 |     0.2041 |    0.0082 |
|   2017 | all      |        208 |     0.3221 |    0.0329 |
|   2017 | topq     |         83 |     0.2892 |    0.0342 |
|   2018 | all      |        106 |     0.1415 |   -0.0595 |
|   2018 | topq     |         36 |     0.1389 |   -0.0259 |
|   2019 | all      |        164 |     0.0671 |   -0.0360 |
|   2019 | topq     |         79 |     0.0633 |   -0.0306 |
|   2020 | all      |        194 |     0.3969 |    0.0615 |
|   2020 | topq     |         76 |     0.2368 |    0.0352 |
|   2021 | all      |        289 |     0.3668 |    0.0314 |
|   2021 | topq     |         66 |     0.3636 |    0.0400 |
|   2022 | all      |        187 |     0.1444 |   -0.0671 |
|   2022 | topq     |         76 |     0.0921 |   -0.0716 |
|   2023 | all      |        218 |     0.3257 |    0.0313 |
|   2023 | topq     |         85 |     0.2235 |    0.0212 |
|   2024 | all      |        365 |     0.1616 |   -0.0302 |
|   2024 | topq     |        145 |     0.0966 |   -0.0393 |
|   2025 | all      |        385 |     0.3325 |    0.0352 |
|   2025 | topq     |        188 |     0.3404 |    0.0477 |
|   2026 | all      |        170 |     0.1059 |   -0.0342 |
|   2026 | topq     |         52 |     0.0000 |   -0.0604 |

## FACTS vs INTERPRETATION

**FACTS:**
- All S3 signals: win_rate=25.5%, n=2706
- Top Q4/Q5: win_rate=21.3%

**INTERPRETATION:**
- If top_q45 win_rate > all_s3 by > 5 pp and n > 30: score adds value to S3 filtering.
- Check TP1 rate: higher TP1 rate in top_q45 confirms breakout quality.
- Year consistency required before drawing conclusions.

**Constraints reminder:**
- S3 is PAPER_SHADOW only. Do NOT promote S3 to production based on these results.
- Do NOT use S3 to gate A3.

## Next step
Proceed to Stage 5 (Wyckoff tag marginal value).