# Regime Fixed Validation Report

**Date:** 2026-05-30
**Status:** Phase 2 breadth fix validation

## Breadth Fix

| Metric | Phase 1 (broken) | Phase 2 (fixed) |
|---|---|---|
| breadth_pct source | regime log CSV (all NaN) | Computed from OHLCV panel (% stocks above EMA50) |
| NaN rate | ~100% | 0.0% |
| Regime bucketing | All rows → STRESS | Properly bucketed |

## Regime Bucket Distribution (unique dates)

| Bucket | Count | % |
|---|---|---|
| BULL_BROAD | 459 | 22.2% |
| BULL_NARROW | 317 | 15.3% |
| NEUTRAL | 431 | 20.8% |
| BEAR | 477 | 23.0% |
| STRESS | 387 | 18.7% |

## Year-by-Year Average Market Breadth (% stocks above EMA50)

| Year | Avg Breadth |
|---|---|
| 2018 | 34.9% |
| 2019 | 40.1% |
| 2020 | 55.1% |
| 2021 | 67.1% |
| 2022 | 29.1% |
| 2023 | 45.0% |
| 2024 | 46.9% |
| 2025 | 48.3% |
| 2026 | 38.6% |

## Sector Coverage

| Metric | Value |
|---|---|
| Final sector coverage | 44.7% |

*Coverage uses sector_map.csv + FA icbName fallback.*