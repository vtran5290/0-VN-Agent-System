# Single-Split OOS Summary

**Train:** 2023-01-01 – 2024-12-31  
**Test:**  2025-01-01 – latest  
**VPL:** excluded entirely  
**CIs:** Wilson 95%  

---

## Universe: full

| Signal | n_test | success_63d | CI 95% | win_rate_63d | mean_ret_63d | best_param |
|--------|--------|-------------|--------|--------------|--------------|------------|
| all | 122 | 0.2295 | [0.1638, 0.3117] | 0.3279 | -0.0263 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| retest | 11 | 0.3636 | [0.1517, 0.6462] | 0.3636 | 0.0222 | `f10_s50_rb0_mc120_rbw120_pd0.50_mm5_cb0.` |
| reclaim | 20 | 0.25 | [0.1119, 0.4687] | 0.4 | 0.0387 | `f21_s55_rb1_mc240_rbw180_pd0.86_mm3_cb0.` |

## Universe: ex_VIC

| Signal | n_test | success_63d | CI 95% | win_rate_63d | mean_ret_63d | best_param |
|--------|--------|-------------|--------|--------------|--------------|------------|
| all | 122 | 0.2295 | [0.1638, 0.3117] | 0.3279 | -0.0263 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| retest | 11 | 0.3636 | [0.1517, 0.6462] | 0.3636 | 0.0222 | `f10_s50_rb0_mc120_rbw120_pd0.50_mm5_cb0.` |
| reclaim | 20 | 0.25 | [0.1119, 0.4687] | 0.4 | 0.0387 | `f21_s55_rb1_mc240_rbw180_pd0.86_mm3_cb0.` |

## Universe: ex_VIC_VHM_VRE

| Signal | n_test | success_63d | CI 95% | win_rate_63d | mean_ret_63d | best_param |
|--------|--------|-------------|--------|--------------|--------------|------------|
| all | 122 | 0.2295 | [0.1638, 0.3117] | 0.3279 | -0.0263 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.3` |
| retest | 11 | 0.3636 | [0.1517, 0.6462] | 0.3636 | 0.0222 | `f10_s50_rb0_mc120_rbw120_pd0.50_mm5_cb0.` |
| reclaim | 20 | 0.25 | [0.1119, 0.4687] | 0.4 | 0.0387 | `f21_s55_rb1_mc240_rbw180_pd0.86_mm3_cb0.` |

## Interpretation Notes

- CI width is driven by test-period n. Wide CIs = statistically underpowered.
- VIC/VHM concentration effect: compare full vs ex_VIC_VHM_VRE to isolate.
- Retest/reclaim counts are small — treat as directional only.

## Raw data
See `single_split_oos_summary.csv`.