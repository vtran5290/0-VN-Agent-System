# S3 GK5+max60+top100 Evidence Notes (Round 2)

Date: 2026-05-16

---

## Problem

Package claimed: `S3_GK5_max60_top100` with MAR=0.449, CAGR=12.9%, MaxDD=-28.73%.

Reviewer could not find the supporting CSV for this exact combination.

---

## Evidence Audit

| Source | Filter | MAR | Notes |
|--------|--------|-----|-------|
| `s3_liquidity_subset_tests.csv` | top_100_adv_symbols (no GK) | 0.3335 | No GK filter |
| `s3_gk_overlay_tests.csv` | gk_within_5bars (no max60, no liquidity) | 0.229 | Baseline S3 max_hold=250 |
| `s3_exit_optimization_tests.csv` | max_hold=60 alone | 0.377 | No GK filter |
| GK5 + max60 (combined) | GK5 + max_hold=60 | 0.185 | Worse than max60 alone |
| GK5 + max60 + top50 (referenced in S3_GK_FINDINGS.md) | GK5 + max60 + top-50 ADV | 0.501 | n=457, too thin |

The GK5+max60+top100 combination (MAR=0.449) was run in the `pp_backtest/s3_combined_test.py`
session but no verified output CSV was persisted for that exact config.

The nearest available numbers suggest the combination is plausible but unverified:
- top-100 standalone: 0.3335
- GK5 standalone: 0.229
- Their interaction at max60 could be additive, but the 0.449 figure has not been confirmed

---

## Action Taken

`S3_GK5_max60_top100` classification changed:
- From: `PARALLEL_PAPER_RESEARCH`
- To: **`FUTURE_RETEST_REQUIRED`**

MAR=0.449 marked as unverified (*) in classification CSV and decision memo.

No MAR figure removed (kept for context) but asterisked and labeled unverified.

---

## To Restore Classification

1. Re-run `pp_backtest/s3_combined_test.py` with explicit config:
   - `gk_window = 5` (GK within 5 bars)
   - `max_hold = 60`
   - `universe = top_100_adv_symbols` (symbols in top-100 by ADV50 at each scan date)
2. Save output to `s3_gk5_max60_top100_evidence.csv` with columns:
   - candidate_id, filters, MAR, CAGR, MaxDD, trade_count, cost_assumption, year_by_year
3. Verify MAR ≥ 0.35 and confirm MaxDD level
4. If confirmed, upgrade back to PARALLEL_PAPER_RESEARCH with CSV as evidence
