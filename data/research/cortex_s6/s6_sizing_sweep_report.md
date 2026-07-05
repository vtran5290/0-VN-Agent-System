# S6 Kelly Sizing Sweep Report

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_cortex_s6_sizing_sweep_prereg.md`
**Signal pool:** S1 within_15pct (prox >= 0.85)

**FINAL VERDICT: DEGRADING**
**Recommended sizing:** flat_5pct

## Comparison (flat vs C1 vs C2)

| Arm | Full MAR | OOS MAR | OOS MaxDD | OOS CAGR | N OOS |
|-----|----------|---------|-----------|----------|-------|
| flat-5% | 1.4435 | 1.7844 | -8.17% | 14.57% | 1727 |
| C1 q-Kelly | 0.9153 | 1.1943 | -13.92% | 16.63% | 1727 |
| C2 h-Kelly | 0.7122 | 0.9538 | -18.14% | 17.30% | 1727 |

## Gate verdicts

### C1 q-Kelly
| Gate | Threshold | Pass |
|------|-----------|------|
| G1a | >= 1.8444 | FAIL |
| G1b | >= 0.516 | PASS |
| G2 | MaxDD >= -0.0940 | FAIL |
| G3 | CV >= 0.10 | PASS |

### C2 h-Kelly
| Gate | Threshold | Pass |
|------|-----------|------|
| G1a | >= 1.8444 | FAIL |
| G1b | >= 0.516 | PASS |
| G2 | MaxDD >= -0.0940 | FAIL |
| G3 | CV >= 0.10 | PASS |

## Sub-window OOS MAR

| Arm | Sub-A (2020-2022) | Sub-B (2023-2026) |
|-----|-------------------|-------------------|
| flat | 5.2762 | 0.5465 |
| C1 | 4.7843 | 0.1230 |
| C2 | 3.9227 | 0.1074 |

**M3 diagnostic:** C1 sub-B 0.1230 vs S1 flat sub-B 0.5465 (baseline ref 0.5465)

## Year attribution (OOS MAR by year)

| Year | flat | C1 | C2 |
|------|------|----|----|
| 2019 | 3.6823 | 3.2870 | 2.1556 |
| 2020 | -0.7346 | -0.8682 | -0.9529 |
| 2021 | nan | nan | nan |
| 2022 | 81.3126 | 50.0801 | 16.2226 |
| 2023 | nan | nan | nan |
| 2024 | -0.5146 | -0.7644 | -0.7459 |
| 2025 | 8.7903 | 6.9415 | 7.2977 |
| 2026 | 2.6333 | -0.1759 | -0.2835 |

## Decile attribution (mean weighted return contrib, OOS)

| Decile | flat | C1 | C2 |
|--------|------|----|----|
| 0 | -0.001607 | -0.005038 | -0.006078 |
| 1 | 0.005782 | 0.018988 | 0.023335 |
| 2 | 0.006878 | 0.019922 | 0.026184 |
| 3 | 0.005046 | 0.015513 | 0.017206 |
| 4 | 0.006709 | 0.017973 | 0.021344 |
| 5 | 0.004560 | 0.017300 | 0.017300 |
| 6 | 0.003624 | 0.011332 | 0.012609 |
| 7 | 0.002610 | 0.005455 | 0.010910 |
| 8 | 0.000223 | 0.001412 | 0.001987 |
| 9 | 0.008443 | 0.007331 | 0.014662 |

## Position-size histogram (OOS, % of trades)

**flat:** lt_3pct=35.8%, 3_5pct=46.1%, 5_8pct=18.1%, 8_10pct=0.0%, gt_10pct=0.0%
**C1:** lt_3pct=27.7%, 3_5pct=43.5%, 5_8pct=15.6%, 8_10pct=13.1%, gt_10pct=0.0%
**C2:** lt_3pct=12.2%, 3_5pct=19.6%, 5_8pct=42.4%, 8_10pct=25.8%, gt_10pct=0.0%

## Top-10 overweight (C1 weight > 8%)

| Symbol | Entry | Decile | Weight |
|--------|-------|--------|--------|
| AAA | 2020-12-03 | 5 | 10.00% |
| AAA | 2020-12-04 | 5 | 10.00% |
| ACB | 2026-06-03 | 5 | 10.00% |
| ACV | 2021-06-29 | 5 | 10.00% |
| ACV | 2025-08-08 | 5 | 10.00% |
| ANV | 2022-02-24 | 5 | 10.00% |
| BFC | 2022-03-10 | 5 | 10.00% |
| BFC | 2026-01-12 | 5 | 10.00% |
| BFC | 2026-01-13 | 5 | 10.00% |
| BIC | 2021-06-11 | 5 | 10.00% |

RESEARCH_ONLY_NOT_PRODUCTION
