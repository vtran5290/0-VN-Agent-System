# Phase36G — Risk Warning Analysis

Generated: 2026-05-17

## Full-Period Drawdown Correlation

| Metric | Value |
|--------|-------|
| A3/S3 DD correlation (full period) | 0.438 |
| Days both A3 and S3 in DD > 10% | 694 of 3,681 (18.9%) |
| Days both A3 and S3 in DD > 15% | 117 of 3,681 (3.2%) |

## Annual DD by Year

| Year | A3 MaxDD | S3 MaxDD | Corr | Concurrent DD>10% |
|------|---------|---------|------|-------------------|
| 2014 | -3.34% | -7.27% | 0.7968 | 0 |
| 2015 | -5.37% | -10.73% | -0.5732 | 0 |
| 2016 | -9.24% | -18.81% | -0.4283 | 0 |
| 2017 | -9.31% | -13.71% | 0.5633 | 0 |
| 2018 | -9.13% | -15.83% | 0.8040 | 0 |
| 2019 | -10.33% | -16.98% | -0.6763 | 36 |
| 2020 | -10.72% | -15.03% | 0.7495 | 57 |
| 2021 | -3.81% | -1.21% | 0.0070 | 0 |
| 2022 | -7.36% | -20.58% | 0.2865 | 0 |
| 2023 | -18.58% | -20.58% | 0.2347 | 238 |
| 2024 | -15.19% | -20.99% | -0.1872 | 258 |
| 2025 | -22.12% | -11.99% | 0.6459 | 105 |
| 2026 | -5.90% | -7.84% | -0.0209 | 0 |

## Warning Triggers (Proposed)

If DD correlation > 0.70: flag "Correlated drawdown risk — S3 shadow losses
may coincide with A3 losses. Review sector concentration."

If both A3 DD > 15% AND S3 DD > 15% simultaneously: flag "Dual-strategy stress.
Do not add new A3 positions until A3 DD recovers to < 10%."

## Hard Rules

- S3 shadow losses DO NOT trigger A3 position reductions
- A3 position reductions are governed ONLY by VNINDEX regime + breadth gates
- Risk warnings are ADVISORY — they do not override A3 scan signals
