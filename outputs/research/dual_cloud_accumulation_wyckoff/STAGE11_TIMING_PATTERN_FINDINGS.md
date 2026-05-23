# Stage 11 Timing & Pattern Decomposition Findings

**Report date:** 2026-05-22  |  **Total rows:** 920  |  **63d matured:** 836
**Baseline win rate (63d):** 19.6%  |  **Baseline avg return:** 2.7%

---

## 1. Executive Summary

Stage 11 classifies each A3/S3 signal into mechanical timing/pattern buckets.
All classifications are OBSERVATION / RESEARCH ONLY. No production changes.

---

## 2. Coverage Against Original Scheme

| Research Question | Bucket | Status |
|---|---|---|
| 1. Accumulation before S3 | PRE_S3_ACCUM | **COVERED** |
| 2. S3 breakout before A3 | S3_BREAKOUT_BEFORE_A3 | **COVERED** |
| 3. Breakout around A3 cloud turn | A3_CLOUD_TURN_BREAKOUT | **COVERED** |
| 4. A3 pullback accumulation breakout | A3_PULLBACK_ACCUM_BREAKOUT | **COVERED** |
| 5. Bottom accumulation before cloud | BOTTOM_ACCUM_PRE_CLOUD | **COVERED** |
| 6. Late breakouts after A3 | LATE_BREAKOUT_AFTER_A3 | **COVERED** |
| 7. S3 after A3 | S3_LATE_AFTER_A3 | **COVERED** |
| 8. Failed S3 before A3 warning | FAILED_S3_BEFORE_A3 | **COVERED** |
| 9. Mechanical inverse H&S | INVERSE_HS_BREAKOUT | **COVERED (diagnostic)** |
| Full timing bucket decomposition | All 9 buckets | **COVERED** |
| Pattern module testing | Stage 11 | **COVERED** |
| S3-specific timing analysis | S3 buckets | **PARTIALLY COVERED** |
| Inverse H&S mechanical annotation | INVERSE_HS_BREAKOUT | **COVERED** |
| Coverage audit vs original scheme | This section | **COVERED** |

**Remaining open after Stage 11:**
- Cross-asset radar / portfolio-level patterns (not in scope)
- Volume profile analysis (VPA) beyond simple ratio
- Sector rotation context mapping
- Live observation tracking (requires forward time)

---

## 3. Timing Bucket Results

### FAILED_S3_BEFORE_A3

- n_total=108, n_matured_63d=94
- win_rate_63d=16.0%, tp1_rate_63d=28.7%, avg_return_63d=3.5%
- **Classification:** WATCHLIST_ONLY  |  **Action:** Use as caution flag
- Notes: Warning indicator — S3 failure before A3 suggests prior trend weakness.

### A3_PULLBACK_ACCUM_BREAKOUT

- n_total=43, n_matured_63d=39
- win_rate_63d=20.5%, tp1_rate_63d=33.3%, avg_return_63d=1.3%
- **Classification:** needs_more_data  |  **Action:** Monitor
- Notes: n_matured=39 < 40

### S3_BREAKOUT_BEFORE_A3

- n_total=442, n_matured_63d=417
- win_rate_63d=19.4%, tp1_rate_63d=35.7%, avg_return_63d=2.0%
- **Classification:** WATCHLIST_ONLY  |  **Action:** Continue monitoring
- Notes: Δwin=-0.2pp, Δret=-0.7pp

### A3_CLOUD_TURN_BREAKOUT

- n_total=0, n_matured_63d=0
- win_rate_63d=N/A, tp1_rate_63d=N/A, avg_return_63d=N/A
- **Classification:** needs_more_data  |  **Action:** Monitor
- Notes: n_matured=0 < 40

### PRE_S3_ACCUM

- n_total=47, n_matured_63d=41
- win_rate_63d=24.4%, tp1_rate_63d=46.3%, avg_return_63d=5.3%
- **Classification:** WATCHLIST_ONLY  |  **Action:** Continue monitoring
- Notes: Δwin=4.8pp, Δret=2.5pp

### BOTTOM_ACCUM_PRE_CLOUD

- n_total=10, n_matured_63d=8
- win_rate_63d=12.5%, tp1_rate_63d=25.0%, avg_return_63d=-0.3%
- **Classification:** needs_more_data  |  **Action:** Monitor
- Notes: n_matured=8 < 40

### LATE_BREAKOUT_AFTER_A3

- n_total=0, n_matured_63d=0
- win_rate_63d=N/A, tp1_rate_63d=N/A, avg_return_63d=N/A
- **Classification:** needs_more_data  |  **Action:** Monitor
- Notes: n_matured=0 < 40

### S3_LATE_AFTER_A3

- n_total=0, n_matured_63d=0
- win_rate_63d=N/A, tp1_rate_63d=N/A, avg_return_63d=N/A
- **Classification:** needs_more_data  |  **Action:** Monitor
- Notes: n_matured=0 < 40

### INVERSE_HS_BREAKOUT

- n_total=1, n_matured_63d=1
- win_rate_63d=0.0%, tp1_rate_63d=0.0%, avg_return_63d=-23.4%
- **Classification:** DIAGNOSTIC_ONLY  |  **Action:** Monitor visually
- Notes: n_matured=1. Pattern-recognition label — needs visual confirmation. LOW_SAMPLE.

### NONE

- n_total=269, n_matured_63d=236
- win_rate_63d=20.8%, tp1_rate_63d=34.7%, avg_return_63d=3.7%
- **Classification:** WATCHLIST_ONLY  |  **Action:** Continue monitoring
- Notes: Δwin=1.1pp, Δret=1.0pp

---

## 4. By-Year / Regime / Liquidity Robustness

### By Year

|   year | bucket                     |   n_total |   n_matured_63d |   win_rate_63d |   avg_return_63d |   median_return_63d |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|-------:|:---------------------------|----------:|----------------:|---------------:|-----------------:|--------------------:|---------------:|--------------:|--------------:|
|   2024 | FAILED_S3_BEFORE_A3        |        44 |              44 |      0.0681818 |       0.00065938 |         -0.0301711  |       0.181818 |    -0.11142   |     0.135564  |
|   2024 | A3_PULLBACK_ACCUM_BREAKOUT |        18 |              18 |      0.111111  |      -0.0478826  |         -0.0494919  |       0.166667 |    -0.142094  |     0.0885702 |
|   2024 | S3_BREAKOUT_BEFORE_A3      |       170 |             170 |      0.123529  |      -0.024522   |         -0.0495354  |       0.235294 |    -0.141535  |     0.137418  |
|   2024 | PRE_S3_ACCUM               |        18 |              18 |      0.277778  |       0.0527415  |         -0.0177196  |       0.444444 |    -0.0973903 |     0.186462  |
|   2025 | FAILED_S3_BEFORE_A3        |        46 |              46 |      0.26087   |       0.0858904  |         -0.00396825 |       0.391304 |    -0.11574   |     0.254301  |
|   2025 | A3_PULLBACK_ACCUM_BREAKOUT |        13 |              13 |      0.384615  |       0.138932   |          0.0943757  |       0.461538 |    -0.119008  |     0.330772  |
|   2025 | S3_BREAKOUT_BEFORE_A3      |       209 |             208 |      0.274038  |       0.0709909  |          0.00059673 |       0.471154 |    -0.127797  |     0.24436   |
|   2025 | PRE_S3_ACCUM               |        17 |              17 |      0.294118  |       0.114027   |          0.046      |       0.647059 |    -0.100913  |     0.275108  |
|   2026 | FAILED_S3_BEFORE_A3        |        18 |               4 |      0         |      -0.176109   |         -0.158579   |       0.25     |    -0.266663  |     0.147921  |
|   2026 | A3_PULLBACK_ACCUM_BREAKOUT |        12 |               8 |      0.125     |      -0.0542088  |         -0.101553   |       0.5      |    -0.157559  |     0.197049  |
|   2026 | S3_BREAKOUT_BEFORE_A3      |        63 |              39 |      0.0769231 |      -0.0565938  |         -0.0332103  |       0.282051 |    -0.170416  |     0.184813  |
|   2026 | PRE_S3_ACCUM               |        12 |               6 |      0         |      -0.121077   |         -0.108135   |       0        |    -0.21022   |     0.0635163 |

### By Regime

| vnindex_regime   | bucket                     |   n_total |   n_matured_63d |   win_rate_63d |   avg_return_63d |   median_return_63d |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|:-----------------|:---------------------------|----------:|----------------:|---------------:|-----------------:|--------------------:|---------------:|--------------:|--------------:|
| bear_sideways    | FAILED_S3_BEFORE_A3        |        22 |              18 |       0.166667 |       0.129531   |         -0.00259965 |       0.166667 |    -0.0876325 |      0.228158 |
| bear_sideways    | A3_PULLBACK_ACCUM_BREAKOUT |        10 |               9 |       0.222222 |       0.0743409  |          0.0943757  |       0.222222 |    -0.109385  |      0.181004 |
| bear_sideways    | S3_BREAKOUT_BEFORE_A3      |        10 |              10 |       0.2      |       0.00968691 |         -0.00132819 |       0.3      |    -0.152262  |      0.132276 |
| bear_sideways    | PRE_S3_ACCUM               |         4 |               4 |       0.25     |       0.0497836  |         -0.0354891  |       0.5      |    -0.149623  |      0.188123 |
| bull             | FAILED_S3_BEFORE_A3        |        86 |              76 |       0.157895 |       0.0124207  |         -0.0301711  |       0.315789 |    -0.127839  |      0.186152 |
| bull             | A3_PULLBACK_ACCUM_BREAKOUT |        33 |              30 |       0.2      |      -0.0052837  |         -0.0761335  |       0.366667 |    -0.146027  |      0.194722 |
| bull             | S3_BREAKOUT_BEFORE_A3      |       432 |             407 |       0.194103 |       0.0203768  |         -0.0230024  |       0.358722 |    -0.137018  |      0.19674  |
| bull             | PRE_S3_ACCUM               |        43 |              37 |       0.243243 |       0.0530328  |         -0.0124611  |       0.459459 |    -0.111659  |      0.207074 |

### By Liquidity Bucket

| liquidity_bucket   | bucket                     |   n_total |   n_matured_63d |   win_rate_63d |   avg_return_63d |   median_return_63d |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |
|:-------------------|:---------------------------|----------:|----------------:|---------------:|-----------------:|--------------------:|---------------:|--------------:|--------------:|
| 20B_plus           | FAILED_S3_BEFORE_A3        |        64 |              58 |       0.137931 |       0.0155841  |          -0.0203581 |       0.241379 |    -0.120292  |      0.159425 |
| 20B_plus           | A3_PULLBACK_ACCUM_BREAKOUT |        19 |              16 |       0.25     |       0.0130968  |          -0.0231463 |       0.25     |    -0.127116  |      0.144009 |
| 20B_plus           | S3_BREAKOUT_BEFORE_A3      |       232 |             219 |       0.187215 |       0.0169777  |          -0.0276549 |       0.328767 |    -0.139055  |      0.181132 |
| 20B_plus           | PRE_S3_ACCUM               |        23 |              19 |       0.157895 |       0.00962851 |          -0.0282903 |       0.315789 |    -0.128119  |      0.143232 |
| 2B_5B              | FAILED_S3_BEFORE_A3        |        20 |              17 |       0.294118 |       0.0394965  |          -0.0300085 |       0.352941 |    -0.13446   |      0.220178 |
| 2B_5B              | A3_PULLBACK_ACCUM_BREAKOUT |         8 |               8 |       0.125    |       0.0709438  |          -0.0524976 |       0.375    |    -0.115903  |      0.276871 |
| 2B_5B              | S3_BREAKOUT_BEFORE_A3      |        71 |              65 |       0.153846 |      -0.00232836 |          -0.0262976 |       0.323077 |    -0.135699  |      0.166152 |
| 2B_5B              | PRE_S3_ACCUM               |         6 |               5 |       0.4      |       0.103195   |           0.0031679 |       0.4      |    -0.138304  |      0.265449 |
| 5B_20B             | FAILED_S3_BEFORE_A3        |        24 |              19 |       0.105263 |       0.0894852  |          -0.0277778 |       0.368421 |    -0.106866  |      0.27709  |
| 5B_20B             | A3_PULLBACK_ACCUM_BREAKOUT |        16 |              15 |       0.2      |      -0.0177694  |          -0.051129  |       0.4      |    -0.160279  |      0.196772 |
| 5B_20B             | S3_BREAKOUT_BEFORE_A3      |       139 |             133 |       0.225564 |       0.0362664  |          -0.0155039 |       0.421053 |    -0.135454  |      0.232542 |
| 5B_20B             | PRE_S3_ACCUM               |        18 |              17 |       0.294118 |       0.0860254  |           0.0389    |       0.647059 |    -0.0943584 |      0.2568   |

---

## 5. Inverse H&S Diagnostic Review

- Total inverse H&S breakout rows: 3
- Volume-confirmed: 3
- 63d matured: 3
- Classification: DIAGNOSTIC_ONLY
- Pattern is retrospective (pivot detection looks forward) — visual confirmation required.

| observation_date    | symbol   | signal_type   | a3_signal   | s3_signal   | s3lead5   |   close_kvnd |   adv50_vnd | liquidity_bucket   | vnindex_regime   |   fwd_20d_return |   fwd_40d_return |   fwd_63d_return | tp1_hit_63d   |   max_adverse_excursion_63d |   max_favorable_excursion_63d | ticker   | matured_63d   | pre_s3_accum_5b   | pre_s3_accum_10b   | pre_s3_accum_20b   | s3_breakout_before_a3_flag   | s3_before_a3_lead_bucket   | a3_cloud_turn_breakout_flag   | a3_pullback_accum_breakout_flag   | pullback_depth_bucket   | pullback_window_bucket   | bottom_accum_pre_cloud_flag   | bottom_accum_price_location   | late_breakout_after_a3_flag   | bars_after_a3_bucket   | s3_late_after_a3_flag   | s3_after_a3_bucket   | failed_s3_before_a3_flag   | failed_s3_failure_type   | inverse_hs_breakout_flag   |   inverse_hs_duration |   inverse_hs_neckline | inverse_hs_confirmed_by_value   | timing_pattern_primary_bucket   | breakout_value_expansion_watchlist_flag   | tightness_plus_breakout_watchlist_flag   | wyckoff_sos_diagnostic_flag   | old_composite_rejected_flag   | field_usage      |   year |
|:--------------------|:---------|:--------------|:------------|:------------|:----------|-------------:|------------:|:-------------------|:-----------------|-----------------:|-----------------:|-----------------:|:--------------|----------------------------:|------------------------------:|:---------|:--------------|:------------------|:-------------------|:-------------------|:-----------------------------|:---------------------------|:------------------------------|:----------------------------------|:------------------------|:-------------------------|:------------------------------|:------------------------------|:------------------------------|:-----------------------|:------------------------|:---------------------|:---------------------------|:-------------------------|:---------------------------|----------------------:|----------------------:|:--------------------------------|:--------------------------------|:------------------------------------------|:-----------------------------------------|:------------------------------|:------------------------------|:-----------------|-------:|
| 2024-06-10 00:00:00 | DXP      | A3            | True        | False       | False     |        14.38 | 5.178e+09   | 5B_20B             | bull             |        -0.121697 |        -0.267038 |       -0.234353  | False         |                   -0.300417 |                     0.0125174 | DXP      | True          | False             | False              | False              | False                        | none                       | False                         | False                             | none                    | none                     | False                         | above_ema100                  | False                         | none                   | False                   | none                 | False                      | none                     | True                       |                    48 |                 13.74 | True                            | INVERSE_HS_BREAKOUT             | True                                      | True                                     | True                          | True                          | observation_only |   2024 |
| 2025-03-21 00:00:00 | HQC      | A3            | True        | False       | False     |         3.52 | 9.57189e+09 | 5B_20B             | bull             |        -0.161932 |        -0.105114 |       -0.0880682 | False         |                   -0.278409 |                     0.0170455 | HQC      | True          | False             | False              | False              | True                         | 11_20                      | False                         | False                             | none                    | none                     | False                         | above_ema100                  | False                         | none                   | False                   | none                 | False                      | none                     | True                       |                    47 |                  3.4  | True                            | S3_BREAKOUT_BEFORE_A3           | True                                      | True                                     | True                          | True                          | observation_only |   2025 |
| 2026-01-14 00:00:00 | VTP      | A3            | True        | False       | True      |       126    | 6.94986e+10 | 20B_plus           | bull             |        -0.176984 |        -0.278571 |       -0.438095  | False         |                   -0.452381 |                     0.0436508 | VTP      | True          | False             | False              | False              | True                         | 1_5                        | False                         | False                             | none                    | none                     | False                         | above_ema100                  | False                         | none                   | False                   | none                 | False                      | none                     | True                       |                    43 |                122.5  | True                            | S3_BREAKOUT_BEFORE_A3           | True                                      | True                                     | True                          | True                          | observation_only |   2026 |

---

## 6. Final Classifications

| bucket                     |   n_matured_63d |   win_rate_63d | classification   | action              |
|:---------------------------|----------------:|---------------:|:-----------------|:--------------------|
| FAILED_S3_BEFORE_A3        |              94 |       0.159574 | WATCHLIST_ONLY   | Use as caution flag |
| A3_PULLBACK_ACCUM_BREAKOUT |              39 |       0.205128 | needs_more_data  | Monitor             |
| S3_BREAKOUT_BEFORE_A3      |             417 |       0.194245 | WATCHLIST_ONLY   | Continue monitoring |
| A3_CLOUD_TURN_BREAKOUT     |               0 |     nan        | needs_more_data  | Monitor             |
| PRE_S3_ACCUM               |              41 |       0.243902 | WATCHLIST_ONLY   | Continue monitoring |
| BOTTOM_ACCUM_PRE_CLOUD     |               8 |       0.125    | needs_more_data  | Monitor             |
| LATE_BREAKOUT_AFTER_A3     |               0 |     nan        | needs_more_data  | Monitor             |
| S3_LATE_AFTER_A3           |               0 |     nan        | needs_more_data  | Monitor             |
| INVERSE_HS_BREAKOUT        |               1 |       0        | DIAGNOSTIC_ONLY  | Monitor visually    |
| NONE                       |             236 |       0.207627 | WATCHLIST_ONLY   | Continue monitoring |

---

## 7. Safety Confirmation

| Check | Status |
|---|---|
| A3 production contract unchanged | YES |
| S3 not promoted to production | YES |
| OMS / live trading untouched | YES |
| DNSE / live order paths untouched | YES |
| final_action not modified | YES |
| Stage 11 fields observation-only | YES |
| Inverse H&S diagnostic-only | YES |
| Failed S3 before A3 warning-only (not a hard block) | YES |
| No production recommendation made | YES |

---

## 8. Remaining Gaps After Stage 11

- Cross-portfolio radar (multi-symbol concurrent pattern detection)
- VPA (volume profile analysis beyond expansion ratio)
- Sector rotation context
- 2026 rows partially immature — revisit when more 63d windows mature

---

## 9. Recommended Next Step

If any bucket clears PARALLEL_PAPER_RESEARCH threshold with n≥40 and Δwin≥5pp,
set up a paper portfolio tracking that specific pattern. Otherwise,
accumulate more 2025/2026 data and re-run Stages 9–11 monthly.

**This report is RESEARCH ONLY. Not OMS input. No production changes.**
