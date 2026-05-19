# Patch Summary — Cloud Signal Timing Fix

**Commit:** `0bef400` — "Fix scan-layer bug: latest-bar A3/S3 signals silently dropped."  
**Date:** 2026-05-19  
**Status:** IMPLEMENTED AND TESTED

---

## Problem Fixed

`compute_phase36_scan_df` dropped A3/S3 signals on the latest EOD bar.  
Guard `li + 1 < len(c)` required the entry bar (T+1) to exist before marking `a3_active=True`.  
Operators missed same-day signals for next-session entry.

---

## Files Changed

| File | Change |
|------|--------|
| `pp_backtest/portfolio_optimization_final_steps.py` | Core fix — signal guard, new fields, reason annotation |
| `src/trading/intraday/intraday_scan.py` | New fields propagated via `scan_df.to_csv` (no change needed) |
| `tests/test_cloud_signal_timing.py` | 18 new tests |
| `tests/test_phase36_daily_scan.py` | 4 new tests (null handling, OMS unchanged) |
| `scripts/reporting/daily_scan_report.py` | Pending-entry display ("pending*" cells + footnote wording) |
| `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` | Pending-entry section added |

### New files (research / diagnostic)

| File | Purpose |
|------|---------|
| `scripts/research/a3_signal_timing_audit.py` | Per-symbol signal detection comparison (pre/post fix) |
| `scripts/research/a3_pre_atc_trigger.py` | Analytical ATC trigger price helper |
| `docs/trading/CLOUD_SIGNAL_TIMING_AUDIT.md` | Audit memo |
| `docs/trading/CLOUD_SIGNAL_TIMING_CODE_AUDIT.md` | Code-level audit |
| `docs/trading/DAILY_SCAN_LATEST_BAR_SIGNAL_AUDIT.md` | Bug evidence and fix table |
| `docs/trading/DAILY_SCAN_SIGNAL_TIMING_FIX_PROPOSAL.md` | Fix proposal (IMPLEMENTED) |
| `docs/trading/ENTRY_TIMING_BACKTEST_FINDINGS.md` | B0–B4 variant definitions |
| `docs/trading/A3_PRE_ATC_TRIGGER_PRICE_HELPER.md` | Pre-ATC trigger helper doc |
| `scripts/reporting/daily_scan_report.py` | Daily scan report writer |

---

## New Scan Fields (post-fix)

| Field | Description |
|-------|-------------|
| `a3_signal_today` | True when A3 signal fires on latest bar; entry = next open |
| `a3_bars_since_signal` | 0 on signal day; k bars after |
| `a3_planned_entry_timing` | `NEXT_OPEN` when pending, `FILLED` when already entered |
| `s3_signal_today` | Mirrors a3_signal_today for S3 |

---

## What Is Unchanged

- `cloud_only_entry` signal rule — unchanged
- A3 T1/T2/TP1/trail/maxhold contract — unchanged
- Backtest B0 baseline (fill at T+1 open) — unchanged
- S3 paper-shadow — unchanged
- OMS: reads `final_action` only; new fields are ignored
- `auto_order_allowed = False` for intraday — unchanged

---

## Test Results

```
63 targeted tests: 63 passed
Full suite: 427 passed, 6 pre-existing failures (test_renderer, test_weekly_report_regression)
```

---

## Report Wording for Pending Entry

When `a3_signal_today=True`:
> Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.

pb_trigger_price / tp1_price / trail_price shown as "pending*" in daily_scan.md until fill is recorded.
