# Phase 2 — S3 Bad-Year Defense Findings

Date: 2026-05-17

---

## VNINDEX Regime Filter Tests (S3 max_hold=60)

| Filter | N | % Kept | MAR | CAGR | MaxDD | 2022 Return |
|--------|---|--------|-----|------|-------|-------------|
| no_filter | 17,324 | 100.0% | 0.174 | 7.1% | -40.7% | -38.9% |
| vnx_ema20>ema100 | 11,632 | 67.1% | 0.377 | 7.9% | -21.0% | -18.0% |
| vnx_ema20>ema200 | 11,986 | 69.2% | 0.136 | 4.9% | -36.1% | -15.8% |
| vnx_close>ema100 | 13,189 | 76.1% | 0.222 | 10.7% | -48.2% | -45.0% |
| vnx_close>ema200 | 12,818 | 74.0% | 0.303 | 7.7% | -25.4% | -19.0% |
| vnx_ema20>ema100+close>ema100 | 11,202 | 64.7% | 0.343 | 8.1% | -23.6% | -20.9% |

---

## Regime + Breadth Combined Tests

| Filter | N | % Kept | MAR | CAGR | MaxDD | 2022 |
|--------|---|--------|-----|------|-------|------|
| regime_only | 11,632 | 67.1% | 0.377 | 7.9% | -21.0% | -18.0% |
| regime+a3_breadth>=35% | 10,592 | 61.1% | 0.431 | 9.0% | -21.0% | -18.0% |
| regime+a3_breadth>=40% | 9,311 | 53.8% | 0.315 | 8.1% | -25.6% | -18.0% |
| regime+a3_breadth>=50% | 7,049 | 40.7% | 0.097 | 3.0% | -31.3% | -17.1% |
| regime+s3_breadth>=35% | 10,457 | 60.4% | 0.378 | 7.9% | -21.0% | -18.0% |
| regime+s3_breadth>=40% | 9,308 | 53.7% | 0.362 | 7.6% | -21.0% | -18.0% |
| regime+s3_breadth>=50% | 7,623 | 44.0% | 0.128 | 3.8% | -30.1% | -23.5% |
| regime+a3_breadth_improving_20bars | 7,185 | 41.5% | 0.240 | 6.0% | -25.1% | -22.0% |

---

## Year-by-Year Comparison

| Year | S3_max60_no_regime | S3_max60_regime | S3_max60_regime+a3b40pct |
|------|---|---|---|
| 2018 | -13.8% | -9.5% | -7.6% |
| 2019 | -6.1% | 3.3% | 2.6% |
| 2020 | 33.7% | 14.7% | 16.2% |
| 2021 | 103.7% | 67.7% | 67.7% |
| 2022 | -38.9% | -18.0% | -18.0% |
| 2023 | 27.2% | 6.6% | 6.6% |
| 2024 | 8.0% | 5.0% | -5.7% |
| 2025 | 41.6% | 45.3% | 46.0% |
| 2026 | -1.7% | -0.2% | 5.5% |

---

## Verdict

- Best regime filter: `vnx_ema20>ema100` — MAR=0.377
- Best regime+breadth: `regime+a3_breadth>=35%` — MAR=0.431

2022 improvement (no_filter→best_regime): +20.9%
**REGIME FILTER MATERIALLY IMPROVES 2022 DEFENSE.**
