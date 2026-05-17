# S3 Breadth Regime Filter — Findings

## Results

| Filter | N | % Kept | MAR | CAGR | MaxDD | Hit Rate | Missed W | Avoided L |
|--------|---|--------|-----|------|-------|----------|----------|-----------|
| no_breadth_filter | 11632 | 100.0% | -0.011 | -0.4% | -37.5% | 67.4% | 0 | 0 |
| a3_breadth>=40% | 9311 | 80.0% | -0.008 | -0.3% | -38.0% | 67.9% | 1515 | 806 |
| a3_breadth>=50% | 7049 | 60.6% | 0.070 | 2.4% | -33.7% | 68.7% | 2997 | 1586 |
| a3_breadth>=60% | 4081 | 35.1% | 0.021 | 0.9% | -41.9% | 70.9% | 4947 | 2604 |
| s3_breadth>=40% | 9308 | 80.0% | 0.016 | 0.5% | -34.0% | 67.7% | 1538 | 786 |
| s3_breadth>=50% | 7623 | 65.5% | 0.001 | 0.1% | -41.7% | 68.3% | 2634 | 1375 |
| s3_breadth>=60% | 4664 | 40.1% | 0.032 | 1.3% | -42.0% | 72.1% | 4478 | 2490 |
| a3_breadth_improving_10bars | 7970 | 68.5% | -0.003 | -0.1% | -45.7% | 68.7% | 2362 | 1300 |
| a3_breadth_improving_20bars | 7185 | 61.8% | 0.147 | 4.0% | -27.3% | 67.8% | 2965 | 1482 |

## Verdict: BREADTH_FILTER_HELPS

Baseline MAR: -0.011. Best breadth-filtered MAR: 0.147.

Note: Unlike A3, breadth may be a valid hard filter for S3 since S3 is currently RESEARCH_ONLY.
