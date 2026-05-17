# S3 + GK Confirmation — Findings

## Results — Standalone GK Filter (S3 max_hold=250 baseline)

| Variant | N | % Kept | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Missed W | Avoided L |
|---------|---|--------|-----|------|-------|----------|----------|----------|-----------|
| no_gk_filter | 11632 | N/A | -0.011 | -0.4% | -37.5% | 67.4% | 60.3% | N/A | N/A |
| gk_within_3bars | 1977 | 17.0% | 0.153 | 5.2% | -33.7% | 68.8% | 62.3% | 6479 | 3176 |
| gk_within_5bars | 2713 | 23.3% | 0.229 | 6.1% | -26.8% | 69.1% | 62.7% | 5966 | 2953 |
| gk_within_10bars | 4322 | 37.2% | 0.207 | 6.6% | -32.0% | 70.2% | 64.4% | 4805 | 2505 |
| gk_mult_125x | 11632 | 23.3% | -0.011 | -0.4% | -37.5% | 67.4% | 60.3% | 0 | 0 |

Source: `s3_gk_overlay_tests.csv`

## Verdict: GK_IMPROVES_S3 (but does not reach 0.30 gate standalone)

Baseline MAR: -0.011. Best GK variant (GK within 5 bars): MAR=0.229.

GK substantially improves S3 — from negative to 0.229 — but the 0.30 gate is not met.
The cost: 6,479 missed winners vs 3,176 avoided losers (ratio 2:1 missed vs avoided).
GK is too selective: it keeps only 23% of S3 trades, eliminating more than double the
winners it avoids losers for.

**GK as multiplier (1.25×) is neutral** — applying GK as a size boost to all trades
produces MAR=-0.011 (identical to baseline).

## Combined GK5 + max_hold=60

GK5 + max60 = MAR=0.185, MaxDD=-37.4% — **worse** than max60 alone (MAR=0.377).
GK hurts when combined with max_hold=60 because the fast-exit already cuts bad trades,
making the GK filter's exclusion of good trades more damaging than its protection.

Source: `s3_exit_optimization_tests.csv` (combined variant rows)

## Combined GK5 + max_hold=60 + top-50 ADV (from combined variant tests)

GK5 + max60 + top50 = MAR=0.501, MaxDD=-19.77%, n=457.
This is the highest MAR combination tested. However, 457 trades over 10+ years is
too thin for reliable conclusions. Not ready for shadow deployment.

Source: `s3_exit_optimization_tests.csv` + `s3_liquidity_subset_tests.csv` combined run.

## S3_GK5_max60_top100 — STATUS: FUTURE_RETEST_REQUIRED

**Classification: FUTURE_RETEST_REQUIRED (downgraded from PARALLEL_PAPER_RESEARCH)**

Previously reported: GK5+max60+top100 = MAR=0.449, CAGR=12.9%, MaxDD=-28.73%.

This result was reported but is **not backed by a standalone CSV** in the current package.
Evidence available:
- top_100_adv_symbols standalone (no GK): MAR=0.3335 (`s3_liquidity_subset_tests.csv`)
- GK5 standalone (no max60 or liquidity filter): MAR=0.229 (`s3_gk_overlay_tests.csv`)
- GK5+max60 (no liquidity filter): MAR=0.185 (`s3_exit_optimization_tests.csv`)
- GK5+max60+top50: MAR=0.501, n=457 (referenced in combined tests, thin n)

The exact combination GK5+max60+top100 was run in the `s3_combined_test.py` session
but no verified output CSV was persisted for that exact config. The MAR=0.449 figure
should be treated as **unverified until re-run produces a confirmed output CSV**.

Required to restore PARALLEL_PAPER_RESEARCH classification:
1. Re-run `pp_backtest/s3_combined_test.py` with explicit top_100 ADV filter + GK5 + max_hold=60
2. Save output to `s3_gk5_max60_top100_evidence.csv` with year-by-year breakdown
3. Confirm MAR ≥ 0.35 and MaxDD ≤ -30% before upgrading classification
