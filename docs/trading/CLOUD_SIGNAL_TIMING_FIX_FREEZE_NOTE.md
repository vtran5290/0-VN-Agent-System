# Cloud Signal Timing Fix — Freeze Note

**Status:** CLOUD_SIGNAL_TIMING_FIX_FROZEN  
**Verdict:** SCAN_LAYER_FIX_APPROVED  
**Date:** 2026-05-19  
**Commit:** `0bef400` — "Fix scan-layer bug: latest-bar A3/S3 signals silently dropped."  
**Package:** `cloud_signal_timing_all_20260519.zip`

---

## Scope

This freeze covers the **scan-layer fix only**. No strategy, OMS, or intraday order logic was changed.

---

## What Was Fixed

`compute_phase36_scan_df` dropped A3/S3 signals on the latest EOD bar. The guard
`li + 1 < len(c)` required the entry bar (T+1) to exist before emitting `a3_active=True`,
silently discarding same-day signals. Operators missed fresh entries for the next session.

**Fix:** Changed guard to `bars_since_signal <= 40`. Added fields `a3_signal_today`,
`a3_bars_since_signal`, `a3_planned_entry_timing`, `s3_signal_today` to distinguish
pending-entry rows from already-filled rows.

---

## Confirmed Behaviors

| Item | Status |
|------|--------|
| Latest-bar A3 signals surfaced in daily scan | ✓ Confirmed |
| `a3_signal_today=True` → `a3_planned_entry_timing=NEXT_OPEN` | ✓ Confirmed |
| `pb_trigger_price / tp1_price / trail_price` null for pending-entry rows | ✓ Allowed |
| Report shows `pending*` + footnote wording | ✓ Confirmed |
| Intraday `final_action=INTRADAY_PREVIEW` | ✓ Unchanged |
| Intraday `auto_order_allowed=False` | ✓ Unchanged |
| Backtest baseline: signal close T → fill open T+1 | ✓ Unchanged |
| A3 strategy rules (`cloud_only_entry`, T1/T2, exits, breadth gates) | ✓ Unchanged |
| OMS reads `final_action` only | ✓ Unchanged |
| S3 paper-shadow | ✓ Unchanged |

---

## Test Results

```
Targeted: tests/test_cloud_signal_timing.py + test_phase36_daily_scan.py + test_intraday_scan.py
  63 passed

Full suite:
  427 passed, 6 pre-existing failures (test_renderer, test_weekly_report_regression)
  Pre-existing failures: unchanged vs pre-fix baseline
```

---

## Pending-Entry Semantics

When `a3_signal_today=True`:

- Signal confirmed at today's close; planned fill is next session open.
- Entry levels are pending until the next-open fill price is known.
- `pb_trigger_price / tp1_price / trail_price` = NaN (shown as `pending*` in daily_scan.md).
- These fields are computed in the next EOD scan after the open fill is recorded.
- OMS is not affected — it reads `final_action` only.

---

## What Was NOT Changed

- `cloud_only_entry` signal logic (`pp_backtest/ema_levels/entry.py`)
- A3 T1/T2 sizing, TP1 (18%), trail (2.5×ATR14), max-hold contract
- Breadth gates, VNINDEX regime gate
- OMS `build_order_intents` — new fields are silently ignored
- S3 capital allocation — paper-shadow only, no real orders
- Intraday order enablement — `auto_order_allowed=False` always
- Backtest B0 baseline

---

## Related Docs

- `docs/trading/DAILY_SCAN_SIGNAL_TIMING_FIX_PROPOSAL.md` — fix design (IMPLEMENTED)
- `docs/trading/DAILY_SCAN_LATEST_BAR_SIGNAL_AUDIT.md` — bug evidence
- `docs/trading/CLOUD_SIGNAL_TIMING_AUDIT.md` — full audit memo
- `docs/trading/ENTRY_TIMING_BACKTEST_FINDINGS.md` — B0–B4 variants
- `docs/trading/A3_PRE_ATC_TRIGGER_PRICE_HELPER.md` — pre-ATC trigger diagnostic
- `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` — pending-entry operator workflow
- `PATCH_SUMMARY.md` — file-level change list
- `REMAINING_RISKS.md` — R1–R6 risk register
