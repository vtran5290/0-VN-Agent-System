# Phase 1 Revised — Top Findings
Generated: 2026-05-16

## Baseline (equal-weight, corrected engine)

A3: CAGR=13.61%, MaxDD=-26.51%, Sharpe=1.18, MAR=0.51 | S3: CAGR=11.91%, MaxDD=-27.36%, Sharpe=1.04, MAR=0.44

## Phase 1B — Pullback Scale-in Robustness

| ID | Strategy | Depth | Window | Quality | Split | CAGR | MaxDD | Sharpe | MAR | PB% |
|----|----------|-------|--------|---------|-------|------|-------|--------|-----|-----|
| PB_A3_d4_w30_slow097_5050 | A3 | 4% | 30b | slow_097 | 50_50 | 13.83% | -23.84% | 1.35 | 0.58 | 51.0% |
| PB_A3_d4_w20_slow097_5050 | A3 | 4% | 20b | slow_097 | 50_50 | 13.60% | -23.97% | 1.33 | 0.57 | 45.3% |
| PB_S3_d5_w20_slow097_5050 | S3 | 5% | 20b | slow_097 | 50_50 | 12.34% | -22.71% | 1.20 | 0.54 | 33.7% |
| PB_A3_d4_w5_slow097_5050 | A3 | 4% | 5b | slow_097 | 50_50 | 12.99% | -24.26% | 1.25 | 0.54 | 25.3% |
| PB_A3_d2_w5_slow097_5050 | A3 | 2% | 5b | slow_097 | 50_50 | 13.41% | -25.27% | 1.29 | 0.53 | 46.2% |

### Pullback vs No-Pullback Trade Quality

| Strategy | Group | N | Mean Net | Mean T1 | Benefit | Hit Rate |
|----------|-------|---|----------|---------|---------|----------|
| A3 | all | 9030 | 7.20% | 6.44% | 0.75% | 71.77% |
| A3 | pullback_occurred | 5964 | 5.26% | 4.12% | 1.14% | 67.24% |
| A3 | no_pullback | 3066 | 10.95% | 10.95% | 0.00% | 80.59% |
| S3 | all | 11819 | 7.19% | 6.29% | 0.90% | 69.90% |
| S3 | pullback_occurred | 7725 | 4.65% | 3.28% | 1.37% | 65.13% |
| S3 | no_pullback | 4094 | 11.97% | 11.97% | 0.00% | 78.92% |

## Phase 1C — Rank Sizing with Caps

| ID | Strategy | Mode | Pos | Pct | Exp | Guard | CAGR | MaxDD | MAR | Class |
|----|----------|------|-----|-----|-----|-------|------|-------|-----|-------|
| LINEAR_A3_pos15_pct10_exp100 | A3 | linear | 15 | 10.0% | 100% | none | 14.27% | -25.47% | 0.56 | PRODUCTION_CANDIDATE |
| LINEAR_A3_pos15_pct15_exp100 | A3 | linear | 15 | 15.0% | 100% | none | 14.27% | -25.47% | 0.56 | PRODUCTION_CANDIDATE |
| LINEAR_A3_pos15_pct20_exp100 | A3 | linear | 15 | 20.0% | 100% | none | 14.27% | -25.47% | 0.56 | PRODUCTION_CANDIDATE |
| TOP_HEAVY_A3_pos15_pct10_exp100 | A3 | top_heavy | 15 | 10.0% | 100% | none | 14.24% | -25.57% | 0.56 | PRODUCTION_CANDIDATE |
| TOP_HEAVY_A3_pos15_pct15_exp100 | A3 | top_heavy | 15 | 15.0% | 100% | none | 14.24% | -25.57% | 0.56 | PRODUCTION_CANDIDATE |

## Phase 1D — Risk-Per-Trade Feasibility

Production candidates (MaxDD > -30%): 51
Shadow test (MaxDD -30% to -40%): 46
Rejected (MaxDD < -50%): 13

| ID | Strategy | Risk% | Stop | CAGR | MaxDD | MAR |
|----|----------|-------|------|------|-------|-----|
| RPT_S3_rp5__hybrid_10_30 | S3 | 0.50% | hybrid_10_30 | 8.68% | -21.51% | 0.40 |
| RPT_S3_rp5__hybrid_7_25 | S3 | 0.50% | hybrid_7_25 | 8.75% | -21.73% | 0.40 |
| RPT_S3_rp5__atr_35 | S3 | 0.50% | atr_35 | 7.64% | -19.19% | 0.40 |
| RPT_S3_rp2__hybrid_7_25 | S3 | 0.25% | hybrid_7_25 | 5.28% | -13.78% | 0.38 |
| RPT_S3_rp2__hybrid_10_30 | S3 | 0.25% | hybrid_10_30 | 4.32% | -11.34% | 0.38 |

## Phase 1E — A3+GK and S3+GK Convergence

### A3+GK

| ID | Window | Has GK | Coverage | CAGR | MaxDD | MAR | Class |
|----|--------|--------|----------|------|-------|-----|-------|
| CONV_A3GK_w10_A3+GK | 10d | True | 29.1% | 12.85% | -23.85% | 0.54 | PRODUCTION_CANDIDATE |
| CONV_A3GK_w5_A3+GK | 5d | True | 17.8% | 12.13% | -24.88% | 0.49 | PRODUCTION_CANDIDATE |
| CONV_A3GK_w3_size125x | 3d | mult_125x | 100.0% | 13.30% | -27.51% | 0.48 | PRODUCTION_CANDIDATE |
| CONV_A3GK_w5_size125x | 5d | mult_125x | 100.0% | 12.90% | -26.74% | 0.48 | PRODUCTION_CANDIDATE |
| CONV_A3GK_w3_A3_no_GK | 3d | False | 86.9% | 12.37% | -27.84% | 0.44 | PRODUCTION_CANDIDATE |
| CONV_A3GK_w10_size125x | 10d | mult_125x | 100.0% | 12.83% | -29.02% | 0.44 | PRODUCTION_CANDIDATE |
### S3+GK

| ID | Window | Has GK | Coverage | CAGR | MaxDD | MAR | Class |
|----|--------|--------|----------|------|-------|-----|-------|
| CONV_S3GK_w3_S3_no_GK | 3d | False | 84.2% | 10.18% | -25.64% | 0.40 | PRODUCTION_CANDIDATE |
| CONV_S3GK_w10_S3+GK | 10d | True | 34.7% | 10.99% | -31.28% | 0.35 | SHADOW_TEST |
| CONV_S3GK_w5_S3+GK | 5d | True | 21.5% | 8.83% | -26.41% | 0.33 | PRODUCTION_CANDIDATE |
| CONV_S3GK_w5_S3_no_GK | 5d | False | 78.5% | 7.94% | -25.91% | 0.31 | PRODUCTION_CANDIDATE |
| CONV_S3GK_w10_S3_no_GK | 10d | False | 65.3% | 6.02% | -31.48% | 0.19 | SHADOW_TEST |
| CONV_S3GK_w3_S3+GK | 3d | True | 15.8% | 6.50% | -37.65% | 0.17 | SHADOW_TEST |
