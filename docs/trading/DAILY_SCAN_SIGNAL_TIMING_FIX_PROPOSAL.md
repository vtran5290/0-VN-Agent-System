# Daily Scan Signal Timing Fix Proposal

**Status:** IMPLEMENTED  
**Date:** 2026-05-19

---

## Problem

`compute_phase36_scan_df` required the entry bar (signal_bar + 1) to exist before marking `a3_active = True`. Signals on the latest EOD bar were silently dropped. Operators missed same-day signals for next-session entry.

## Fix

**File:** `pp_backtest/portfolio_optimization_final_steps.py`

### A3/S3 Signal Detection (lines 1563–1578)

Changed guard from `li + 1 < len(c)` to `bars_since_signal <= 40`:

```python
# BEFORE (dropped latest-bar signals):
a3_active = False; a3_bars = None
if len(a3_idxs) > 0:
    li = int(a3_idxs[-1])
    if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
        a3_active = True
        a3_bars   = len(c) - 1 - (li + 1)

# AFTER (allows latest-bar signals):
a3_active = False; a3_bars = None; a3_signal_today = False
_a3_bars_since_signal = None
if len(a3_idxs) > 0:
    li = int(a3_idxs[-1])
    _bss = len(c) - 1 - li          # 0 on signal day
    if _bss <= 40:
        a3_active = True
        a3_bars   = max(0, len(c) - 1 - (li + 1))  # clamp -1 to 0
        a3_signal_today = (_bss == 0)
        _a3_bars_since_signal = _bss
```

### Entry-Price Guard (line 1646)

Skip entry-price calculations when entry bar hasn't happened yet:

```python
# BEFORE:
if a3_active and a3_bars is not None and a3_bars >= 0:
    a3_entry_idx = len(c) - 1 - a3_bars
    ...

# AFTER:
if a3_active and a3_bars is not None and a3_bars >= 0 and not a3_signal_today:
    a3_entry_idx = len(c) - 1 - a3_bars
    ...
```

### Final-Action Reason Annotation

When `a3_signal_today=True`:
```python
if a3_signal_today and action in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"):
    reason = reason + " Signal confirmed at today's close; planned fill is next session open."
```

### New Row Fields

```python
"a3_signal_today":         a3_signal_today,
"a3_bars_since_signal":    _a3_bars_since_signal,
"a3_planned_entry_timing": ("NEXT_OPEN" if a3_signal_today else ("FILLED" if a3_active else None)),
"s3_signal_today":         s3_signal_today,
```

---

## EOD Scan Fields (Post-Fix)

| Field | Description |
|---|---|
| `a3_active` | Signal within 40 bars (including signal bar itself) |
| `a3_signal_today` | True when signal fires on latest bar; entry = next open |
| `a3_bars_since` | Bars since entry bar; 0 = entry bar is current bar or pending |
| `a3_bars_since_signal` | Bars since signal bar; 0 on signal day |
| `a3_planned_entry_timing` | `NEXT_OPEN` / `FILLED` |
| `pb_trigger_price` | None when `a3_signal_today=True` (entry price unknown) |
| `tp1_price` | None when `a3_signal_today=True` |
| `trail_price` | None when `a3_signal_today=True` |

**EOD report language:**  
When `a3_signal_today=True`: "Signal confirmed at today's close; planned fill is next session open."

---

## Intraday Preview Fields (Post-Fix)

The intraday scan calls `compute_phase36_scan_df` with provisional panel. Fix applies automatically.

| Field | Description |
|---|---|
| `would_be_final_action` | NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH when provisional close triggers signal |
| `final_action` | Always INTRADAY_PREVIEW |
| `auto_order_allowed` | Always False |
| `intraday_candidate` | True when `would_be_final_action` in candidate set |
| `a3_signal_today` | True for provisional signal on current bar |

**Intraday report language:**  
"If current partial bar were the close, this would become a signal. Manual review only."

---

## What Is NOT Changed

- `cloud_only_entry` signal rule — unchanged
- A3 T1/T2/TP1/trail/maxhold contract — unchanged
- Backtest B0 baseline (fill at T+1 open) — unchanged
- S3 paper-shadow — unchanged
- OMS: reads `final_action` only; not impacted by new fields
- Intraday `auto_order_allowed = False` — unchanged

---

## Tests Added

See `tests/test_cloud_signal_timing.py` for:
1. `test_cloud_only_entry_signal_on_close`
2. `test_backtest_fill_next_open`
3. `test_daily_scan_latest_bar_signal_visible`
4. `test_daily_scan_does_not_require_next_bar_for_signal`
5. `test_intraday_preview_if_close_now_signal`
6. `test_intraday_preview_never_auto_order`
7. `test_trigger_price_helper_matches_cloud_signal`
8. `test_no_lookahead_intraday`
9. `test_scan_fields_documented`
