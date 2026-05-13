# Walk-Forward Validation Summary

**Date:** 2026-05-13

## OOS IC by Window × Horizon

### expanding
|   Horizon |   N |   OOS_IC |   ICIR |   t-stat | %pos   |
|-----------|-----|----------|--------|----------|--------|
|        25 |  92 |  -0.0479 | -0.264 |   -2.529 | 45%    |
|        50 |  90 |  -0.0536 | -0.324 |   -3.077 | 38%    |
|       100 |  83 |  -0.0177 | -0.107 |   -0.974 | 52%    |
|       150 |  81 |  -0.0028 | -0.017 |   -0.149 | 53%    |
|       200 |  78 |   0.0369 |  0.249 |    2.202 | 60%    |
|       250 |  76 |   0.0486 |  0.383 |    3.341 | 66%    |

### rolling_36
|   Horizon |   N |   OOS_IC |   ICIR |   t-stat | %pos   |
|-----------|-----|----------|--------|----------|--------|
|        25 |  71 |  -0.0166 | -0.104 |   -0.877 | 49%    |
|        50 |  69 |  -0.0086 | -0.047 |   -0.391 | 48%    |
|       100 |  62 |  -0.0186 | -0.105 |   -0.826 | 47%    |
|       150 |  60 |  -0.0073 | -0.044 |   -0.34  | 58%    |
|       200 |  57 |   0.0271 |  0.187 |    1.413 | 60%    |
|       250 |  55 |   0.053  |  0.36  |    2.671 | 66%    |

### rolling_60
|   Horizon |   N |   OOS_IC |   ICIR |   t-stat | %pos   |
|-----------|-----|----------|--------|----------|--------|
|        25 |  54 |  -0.0568 | -0.302 |   -2.216 | 39%    |
|        50 |  52 |  -0.0761 | -0.4   |   -2.883 | 31%    |
|       100 |  45 |  -0.0255 | -0.15  |   -1.006 | 49%    |
|       150 |  43 |   0.0012 |  0.007 |    0.043 | 60%    |
|       200 |  40 |   0.0448 |  0.346 |    2.191 | 65%    |
|       250 |  38 |   0.0644 |  0.532 |    3.278 | 68%    |

## Portfolio Returns (expanding, net of tx costs)

### Horizon 25d
| Metric          | Mean   | Median   | Hit%   |   N |
|-----------------|--------|----------|--------|-----|
| top10_tc3bp     | +1.04% | -0.46%   | 46%    |  92 |
| top10_tc5bp     | +0.84% | -0.66%   | 45%    |  92 |
| top10_tc8bp     | +0.54% | -0.96%   | 43%    |  92 |
| quintile_tc3bp  | -0.22% | -0.07%   | 50%    |  92 |
| quintile_spread | -1.44% | -0.68%   | 46%    |  92 |
| universe_mean   | +2.04% | +2.06%   | 58%    |  92 |

### Horizon 50d
| Metric          | Mean   | Median   | Hit%   |   N |
|-----------------|--------|----------|--------|-----|
| top10_tc3bp     | +0.20% | -0.29%   | 47%    |  90 |
| top10_tc5bp     | -0.00% | -0.49%   | 46%    |  90 |
| top10_tc8bp     | -0.30% | -0.79%   | 46%    |  90 |
| quintile_tc3bp  | +0.18% | -1.08%   | 44%    |  90 |
| quintile_spread | -3.21% | -1.42%   | 39%    |  90 |
| universe_mean   | +2.68% | +0.26%   | 52%    |  90 |

### Horizon 100d
| Metric          | Mean   | Median   | Hit%   |   N |
|-----------------|--------|----------|--------|-----|
| top10_tc3bp     | +3.78% | +0.06%   | 51%    |  83 |
| top10_tc5bp     | +3.58% | -0.14%   | 49%    |  83 |
| top10_tc8bp     | +3.28% | -0.44%   | 48%    |  83 |
| quintile_tc3bp  | +5.21% | +0.91%   | 55%    |  83 |
| quintile_spread | +0.14% | +1.75%   | 58%    |  83 |
| universe_mean   | +5.88% | +1.75%   | 58%    |  83 |

## Regime-Conditional OOS IC (expanding)

### Horizon 100d
| Regime       |   OOS_IC_mean |    std |   N |
|--------------|---------------|--------|-----|
| Accumulation |       -0.0816 | 0.1459 |  12 |
| Contraction  |        0.0104 | 0.2637 |  16 |
| Expansion    |       -0.0173 | 0.1357 |  37 |
| Warning      |       -0.0007 | 0.1168 |  18 |

## Go/No-Go Criteria

A factor family is considered **deployable** only if ALL of the following hold:

| Criterion | Threshold |
|-----------|-----------|
| OOS ICIR (expanding) | >= 0.30 |
| OOS IC t-stat | >= 1.5  |
| % positive IC months | >= 55%  |
| Works in Expansion AND Accumulation regimes | IC > 0 in both |
| Sector-neutral IC not much weaker than raw | SN_IC / IC > 0.5 |
| Net of 50bp cost still positive | > 0% mean |

**Current status: CANDIDATE_RESEARCH** — requires further validation before deployment.
