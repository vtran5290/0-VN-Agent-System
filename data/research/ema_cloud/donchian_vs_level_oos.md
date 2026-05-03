# Donchian vs Level-Breakout — 2025 OOS Head-to-Head

**Test window:** 2025-01-01 – latest  
**Donchian rule:** `close > max(high[t-20:t]) AND bull_cloud AND above_cloud`, entry open[t+1]  
**Level model:** best OOS param `f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30`, breakout only  
**VPL:** excluded  |  **CIs:** Wilson 95%

---

## full

| model | n | success_63d | CI 95% | win_63d | mean_63d | median_63d |
|-------|---|-------------|--------|---------|----------|------------|
| donchian | 2831 | 0.3896 | [0.3718, 0.4077] | 0.4945 | 0.0554 | -0.001 |
| level_breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | -0.0468 |

## ex_VIC

| model | n | success_63d | CI 95% | win_63d | mean_63d | median_63d |
|-------|---|-------------|--------|---------|----------|------------|
| donchian | 2790 | 0.3875 | [0.3695, 0.4057] | 0.4889 | 0.0476 | -0.0049 |
| level_breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | -0.0468 |

## ex_VIC_VHM_VRE

| model | n | success_63d | CI 95% | win_63d | mean_63d | median_63d |
|-------|---|-------------|--------|---------|----------|------------|
| donchian | 2729 | 0.3866 | [0.3685, 0.405] | 0.483 | 0.0439 | -0.0079 |
| level_breakout | 85 | 0.2353 | [0.1578, 0.3357] | 0.3412 | -0.0204 | -0.0468 |

## Notes

- Donchian has no train-period params — rule is fixed.
- Level model best param selected on 2023–2024 train; applied to 2025 test.
- If Donchian OOS success ≥ 28% with positive mean_ret: use as Step 7 baseline.
- CI overlap = statistically indistinguishable.