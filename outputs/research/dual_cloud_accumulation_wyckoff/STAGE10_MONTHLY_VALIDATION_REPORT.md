# Stage 10 Monthly Validation Report

**Report date:** 2026-05-22  |  **Data range:** 2024-01-02 — 2026-05-21

---

## 1. Executive Summary

- **Total ledger rows:** 920
- **63d-matured rows:** 836 (90.9% of total)
- **Baseline 63d win rate (≥15%):** 19.6%
- **Baseline 63d avg return:** 2.7%
- **Baseline TP1 rate (63d):** 34.9%

No production changes. No OMS changes. All fields are observation-only.

---

## 2. Data Coverage

- Stage 9 ledger: 920 rows, date range: 2024-01-02 — 2026-05-21
- 63d-matured: 836 rows used for primary conclusions.
- Immature rows (matured_63d=False) are **excluded** from all 63d conclusions.
- Immature rows are **not counted as losses or zeros**.

---

## 3. Mature-Only Result Summary (h=63)

| candidate        |   n_matured_63d |   win_rate_63d |   avg_return_63d |   med_return_63d |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |   pct_positive |
|:-----------------|----------------:|---------------:|-----------------:|-----------------:|---------------:|--------------:|--------------:|---------------:|
| all_rows         |             836 |       0.196172 |        0.0272354 |      -0.0155644  |       0.349282 |     -0.128781 |      0.190451 |       0.441388 |
| BVE_Q5           |             195 |       0.215385 |        0.0216059 |      -0.0236865  |       0.394872 |     -0.146355 |      0.210625 |       0.420513 |
| BVE_Q4Q5         |             361 |       0.213296 |        0.0253893 |      -0.0229781  |       0.382271 |     -0.140314 |      0.204998 |       0.426593 |
| TPBCQ_Q5         |             121 |       0.22314  |        0.0535431 |      -0.00879121 |       0.471074 |     -0.15606  |      0.258343 |       0.471074 |
| TPBCQ_Q4Q5       |             256 |       0.214844 |        0.0424666 |      -0.0151316  |       0.410156 |     -0.14324  |      0.222347 |       0.441406 |
| Wyckoff_SOS      |             171 |       0.175439 |        0.0191735 |      -0.0295031  |       0.380117 |     -0.142798 |      0.200776 |       0.421053 |
| old_composite_Q5 |             153 |       0.156863 |        0.0101695 |      -0.0229781  |       0.254902 |     -0.11437  |      0.145497 |       0.411765 |

---

## 4. Candidate Performance

### BVE_Q5

- **n_matured_63d:** 195
- **win_rate_63d:** 21.5% (baseline: 19.6%)
- **avg_return_63d:** 2.2% (baseline: 2.7%)
- **tp1_rate_63d:** 39.5% (baseline: 34.9%)
- **avg_mae_63d:** -14.6%
- **avg_mfe_63d:** 21.1%
- **Classification:** WATCHLIST_ONLY
- **Action:** Continue monitoring
- **Reason:** Positives: tp1_rate delta=4.6pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.9pp < 5pp; avg_return delta=-0.6pp ≤ 0; positive in 1 years < 2

### BVE_Q4Q5

- **n_matured_63d:** 361
- **win_rate_63d:** 21.3% (baseline: 19.6%)
- **avg_return_63d:** 2.5% (baseline: 2.7%)
- **tp1_rate_63d:** 38.2% (baseline: 34.9%)
- **avg_mae_63d:** -14.0%
- **avg_mfe_63d:** 20.5%
- **Classification:** WATCHLIST_ONLY
- **Action:** Continue monitoring
- **Reason:** Positives: tp1_rate delta=3.3pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.7pp < 5pp; avg_return delta=-0.2pp ≤ 0; positive in 1 years < 2

### TPBCQ_Q5

- **n_matured_63d:** 121
- **win_rate_63d:** 22.3% (baseline: 19.6%)
- **avg_return_63d:** 5.4% (baseline: 2.7%)
- **tp1_rate_63d:** 47.1% (baseline: 34.9%)
- **avg_mae_63d:** -15.6%
- **avg_mfe_63d:** 25.8%
- **Classification:** WATCHLIST_ONLY
- **Action:** Continue monitoring
- **Reason:** Positives: avg_return delta=2.6pp > 0; tp1_rate delta=12.2pp > 0; positive in 2 years ≥ 2; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=2.7pp < 5pp

### TPBCQ_Q4Q5

- **n_matured_63d:** 256
- **win_rate_63d:** 21.5% (baseline: 19.6%)
- **avg_return_63d:** 4.2% (baseline: 2.7%)
- **tp1_rate_63d:** 41.0% (baseline: 34.9%)
- **avg_mae_63d:** -14.3%
- **avg_mfe_63d:** 22.2%
- **Classification:** WATCHLIST_ONLY
- **Action:** Continue monitoring
- **Reason:** Positives: avg_return delta=1.5pp > 0; tp1_rate delta=6.1pp > 0; positive in 2 years ≥ 2; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.9pp < 5pp

### Wyckoff_SOS

- **n_matured_63d:** 171
- **win_rate_63d:** 17.5% (baseline: 19.6%)
- **avg_return_63d:** 1.9% (baseline: 2.7%)
- **tp1_rate_63d:** 38.0% (baseline: 34.9%)
- **avg_mae_63d:** -14.3%
- **avg_mfe_63d:** 20.1%
- **Classification:** WATCHLIST_ONLY
- **Action:** Continue monitoring
- **Reason:** Positives: tp1_rate delta=3.1pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=-2.1pp < 5pp; avg_return delta=-0.8pp ≤ 0; positive in 1 years < 2

### old_composite_Q5

- **n_matured_63d:** 153
- **win_rate_63d:** 15.7% (baseline: 19.6%)
- **avg_return_63d:** 1.0% (baseline: 2.7%)
- **tp1_rate_63d:** 25.5% (baseline: 34.9%)
- **avg_mae_63d:** -11.4%
- **avg_mfe_63d:** 14.5%
- **Classification:** REJECT
- **Action:** No action
- **Reason:** Old composite was rejected in Stage 7 — directionally unstable. Maintaining REJECT unless extremely strong evidence.

---

## 5. Regime / Year / Liquidity Decomposition

| group_type   |   year |   baseline_n |   baseline_win_rate |   baseline_avg_return |   candidate_n |   candidate_win_rate |   candidate_avg_return |   candidate_tp1_rate |   delta_win_rate_pp | vnindex_regime   | liquidity_bucket   |
|:-------------|-------:|-------------:|--------------------:|----------------------:|--------------:|---------------------:|-----------------------:|---------------------:|--------------------:|:-----------------|:-------------------|
| year         |   2024 |          393 |           0.127226  |            -0.0122731 |           153 |            0.150327  |            -0.00636586 |             0.27451  |            2.31003  | nan              | nan                |
| year         |   2025 |          371 |           0.291105  |             0.0870652 |           163 |            0.306748  |             0.0845231  |             0.496933 |            1.56433  | nan              | nan                |
| year         |   2026 |           72 |           0.0833333 |            -0.0654044 |            45 |            0.0888889 |            -0.0808388  |             0.333333 |            0.555556 | nan              | nan                |
| regime       |    nan |          139 |           0.223022  |             0.0794979 |            61 |            0.213115  |             0.0585443  |             0.360656 |           -0.990683 | bear_sideways    | nan                |
| regime       |    nan |          697 |           0.190818  |             0.0168129 |           300 |            0.213333  |             0.0186478  |             0.386667 |            2.25155  | bull             | nan                |
| liquidity    |    nan |          450 |           0.18      |             0.0184054 |           160 |            0.175     |             0.0112926  |             0.3125   |           -0.5      | nan              | 20B_plus           |
| liquidity    |    nan |          132 |           0.212121  |             0.0392504 |            77 |            0.233766  |             0.0268516  |             0.402597 |            2.1645   | nan              | 2B_5B              |
| liquidity    |    nan |          254 |           0.216535  |             0.0366349 |           124 |            0.25      |             0.0426705  |             0.459677 |            3.34646  | nan              | 5B_20B             |

---

## 6. Candidate Decision Table

| candidate        |   n_matured_63d |   win_rate_63d |   avg_return_63d |   tp1_rate_63d |   avg_mae_63d |   avg_mfe_63d |   delta_win_rate_vs_all_pp |   delta_avg_return_vs_all_pp |   delta_tp1_rate_vs_all_pp | classification   | action              | reason                                                                                                                                                       |
|:-----------------|----------------:|---------------:|-----------------:|---------------:|--------------:|--------------:|---------------------------:|-----------------------------:|---------------------------:|:-----------------|:--------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| BVE_Q5           |             195 |       0.215385 |        0.0216059 |       0.394872 |     -0.146355 |      0.210625 |                    1.92124 |                    -0.562948 |                    4.55895 | WATCHLIST_ONLY   | Continue monitoring | Positives: tp1_rate delta=4.6pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.9pp < 5pp; avg_return delta=-0.6pp ≤ 0; positive in 1 years < 2  |
| BVE_Q4Q5         |             361 |       0.213296 |        0.0253893 |       0.382271 |     -0.140314 |      0.204998 |                    1.71242 |                    -0.184606 |                    3.29892 | WATCHLIST_ONLY   | Continue monitoring | Positives: tp1_rate delta=3.3pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.7pp < 5pp; avg_return delta=-0.2pp ≤ 0; positive in 1 years < 2  |
| TPBCQ_Q5         |             121 |       0.22314  |        0.0535431 |       0.471074 |     -0.15606  |      0.258343 |                    2.69682 |                     2.63077  |                   12.1792  | WATCHLIST_ONLY   | Continue monitoring | Positives: avg_return delta=2.6pp > 0; tp1_rate delta=12.2pp > 0; positive in 2 years ≥ 2; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=2.7pp < 5pp  |
| TPBCQ_Q4Q5       |             256 |       0.214844 |        0.0424666 |       0.410156 |     -0.14324  |      0.222347 |                    1.86715 |                     1.52312  |                    6.0874  | WATCHLIST_ONLY   | Continue monitoring | Positives: avg_return delta=1.5pp > 0; tp1_rate delta=6.1pp > 0; positive in 2 years ≥ 2; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=1.9pp < 5pp   |
| Wyckoff_SOS      |             171 |       0.175439 |        0.0191735 |       0.380117 |     -0.142798 |      0.200776 |                   -2.07337 |                    -0.806185 |                    3.08347 | WATCHLIST_ONLY   | Continue monitoring | Positives: tp1_rate delta=3.1pp > 0; positive in 3 liq buckets ≥ 2 | Gaps: win_rate delta=-2.1pp < 5pp; avg_return delta=-0.8pp ≤ 0; positive in 1 years < 2 |
| old_composite_Q5 |             153 |       0.156863 |        0.0101695 |       0.254902 |     -0.11437  |      0.145497 |                   -3.93095 |                    -1.70659  |                   -9.43803 | REJECT           | No action           | Old composite was rejected in Stage 7 — directionally unstable. Maintaining REJECT unless extremely strong evidence.                                         |

---

## 7. Safety Confirmation

| Check | Status |
|---|---|
| A3 production contract unchanged | YES |
| S3 not promoted to production | YES |
| OMS / live trading untouched | YES |
| DNSE / live order paths untouched | YES |
| final_action not modified | YES |
| Mature-only analysis for 63d conclusions | YES |
| Immature rows not counted as losses | YES |
| Stage 10 fields observation-only | YES |

---

## 8. Recommended Actions

- No candidate cleared PARALLEL_PAPER_RESEARCH threshold this period.
- **Continue monitoring (WATCHLIST_ONLY):** BVE_Q5, BVE_Q4Q5, TPBCQ_Q5, TPBCQ_Q4Q5, Wyckoff_SOS
- **No action (REJECT):** old_composite_Q5

---

## 9. Open Questions

- Is 2025 outperformance driven by market regime (bull cycle) or signal quality?
- Will BVE TP1 lift persist across a full bear cycle?
- Can TPBCQ Q4/Q5 be combined with BVE Q4/Q5 for a stronger composite?
- Are 2026 incomplete rows being correctly excluded from all mature conclusions?

---

**This report is RESEARCH ONLY. Not OMS input. Not production recommendation.**
