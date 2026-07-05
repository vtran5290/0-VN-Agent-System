# PA-008 Sector Cap — Degeneracy Pre-Check

**Date:** 2026-07-05
**Script:** `pp_backtest/cortex_pa008_degeneracy_precheck.py`
**Pool:** S1-filtered (prox ≥ 0.85) A3_RS OOS trades 2020–2026
**VERDICT: EXPRESSIBLE**

## Entry-cohort (same-day new signals per sector)
- OOS trades: 1732
- Entry cohort days: 724
- Max same-sector signals same day: **4**

| Cap | Cohort-days binding (count > cap) | % of cohort days |
|-----|-----------------------------------|------------------|
| 3 | 11 | 1.5% |
| 4 | 0 | 0.0% |
| 5 | 0 | 0.0% |

## Daily open positions (holding overlap)
- Daily sector observations: 15353
- Max open same-sector positions any day: **130**

| Cap | Daily obs binding (open > cap) | % of daily obs |
|-----|-------------------------------|----------------|
| 3 | 13586 | 88.5% |
| 4 | 13163 | 85.7% |
| 5 | 12380 | 80.6% |

## Interpretation
- Cap=4 binds on **0.0%** of entry cohort days (threshold: ≥5% to be EXPRESSIBLE).
- Cap=4 binds on **85.7%** of daily open-position observations.
- If DEGENERATE: skip full PA-008 harness; natural S1-filtered diversification already ≤4/sector.
