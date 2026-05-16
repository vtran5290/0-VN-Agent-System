# Portfolio Optimization Research — Top Findings
Generated: 2026-05-16

## Baseline Portfolio Performance

| Strategy | CAGR | MaxDD | Sharpe | MAR | N_Trades | Hit Rate |
|----------|------|-------|--------|-----|----------|----------|
| A3 | 13.61% | -26.51% | 1.18 | 0.51 | 12909 | 67.10% |
| S3 | 11.91% | -27.36% | 1.04 | 0.44 | 17324 | 65.32% |
| COMBINED | 9.47% | -33.77% | 0.90 | 0.28 | 33813 | 62.89% |

## Top 5 Sizing Experiments (by MAR)

| ID | Strategy | Method | CAGR | MaxDD | Sharpe | MAR |
|----|----------|--------|------|-------|--------|-----|
| D_A3_rp0.015_fixed_7pct | A3 | risk_per_trade | 59.80% | -72.79% | 1.22 | 0.82 |
| D_A3_rp0.020_fixed_7pct | A3 | risk_per_trade | 59.80% | -72.79% | 1.22 | 0.82 |
| D_A3_rp0.020_fixed_10pct | A3 | risk_per_trade | 59.80% | -72.79% | 1.22 | 0.82 |
| D_A3_rp0.020_atr_25 | A3 | risk_per_trade | 51.84% | -72.11% | 1.22 | 0.72 |
| D_A3_rp0.015_fixed_10pct | A3 | risk_per_trade | 43.62% | -61.64% | 1.21 | 0.71 |

## Top 5 Convergence Experiments (by MAR)

| ID | Mode | Multiplier | Window | N_Trades | Coverage | CAGR | MAR |
|----|------|------------|--------|----------|----------|------|-----|
| C3_M0_w5 | C3 | M0 | 5d | 1619 | 12.5% | 14.60% | 0.53 |
| C3_M1_w5 | C3 | M1 | 5d | 1619 | 12.5% | 14.60% | 0.53 |
| C3_M2_w5 | C3 | M2 | 5d | 1619 | 12.5% | 14.55% | 0.52 |
| C0_M0_w3 | C0 | M0 | 3d | 12909 | 100.0% | 13.61% | 0.51 |
| C0_M1_w3 | C0 | M1 | 3d | 12909 | 100.0% | 13.61% | 0.51 |

## Walk-Forward Summary

- Positive-return folds: 82 / 125
- Mean net return per fold: 4.86%
- Mean hit rate per fold: 63.86%
- Fold stability score: -1.819

## Key Observations

- Facts only: interpret from sizing_summary.csv, convergence_summary.csv
- Bucket and Kelly sizing require walk-forward training window (stubbed here)
- Near-entry labels (ideal_pullback / ideal) show highest expected trade returns per validated research
