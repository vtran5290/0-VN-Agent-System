# Performance Scaling Final Findings

As of: 2026-05-16

## Baseline (A3 DP at 5B/10%)

- MAR = 0.416
- CAGR = 5.81%
- MaxDD = -13.99%

## Test Results

| Rule | MAR | CAGR | MaxDD | 2020 | 2021 | 2025 | Blocked |
|------|-----|------|-------|------|------|------|---------|
| baseline | 0.416 | 5.81% | -13.99% | 11.14% | 44.63% | 23.26% | 0 |
| ruleA_3M_5pct | 0.357 | 5.81% | -16.26% | 7.44% | 45.98% | 28.56% | 249 |
| ruleA_3M_10pct | 0.416 | 5.81% | -13.99% | 11.14% | 44.63% | 23.26% | 0 |
| ruleA_6M_15pct | 0.416 | 5.81% | -13.99% | 11.14% | 44.63% | 23.26% | 0 |
| ruleA_combo | 0.357 | 5.81% | -16.26% | 7.44% | 45.98% | 28.56% | 249 |
| ruleB_3M_br40 | 0.363 | 6.02% | -16.59% | 10.76% | 49.49% | 25.24% | 130 |
| ruleD_t2only_3M | 0.403 | 5.78% | -14.35% | 11.91% | 44.63% | 23.26% | 0 |
| ruleD_t2only_br | 0.403 | 5.78% | -14.35% | 11.91% | 44.63% | 23.26% | 0 |
| ruleE_gk_except | 0.357 | 5.81% | -16.26% | 7.44% | 45.98% | 28.56% | 249 |

## Acceptance Criteria

No rule materially improves MAR or MaxDD without hurting bull-year participation.
Recommendation: **REJECT performance throttle**. Keep breadth gate only.
