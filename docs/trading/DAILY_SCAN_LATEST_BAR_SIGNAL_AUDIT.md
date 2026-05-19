# Daily Scan Latest-Bar Signal Audit

**As-of:** 2026-05-19  
**Verdict:** SCAN_LAYER_FIX_REQUIRED — fix applied.

---

## Hypothesis

The daily scan may miss a fresh latest-bar signal because the active-trade detection requires the entry bar (T+1) to exist before emitting NEW_T1.

## Evidence

`pp_backtest/portfolio_optimization_final_steps.py:1566` (pre-fix):

```python
if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
    a3_active = True
    a3_bars   = len(c) - 1 - (li + 1)
```

Scenario:
- EOD scan run after close on date T
- Panel has bars 0 … T (T is the latest bar, len(c) = T+1 in 0-indexed space)
- `cloud_only_entry` returns True at index T (latest bar) → `li = T`
- `li + 1 = T + 1 = len(c)` → condition `li + 1 < len(c)` is False
- `a3_active = False`
- Signal dropped silently — operator sees WATCH_ONLY, not NEW_T1

**Effect:** operator misses the fresh entry signal for the next session.

## Field Definitions (Post-Fix)

| Field | When `signal_T = True` (just fired) | When `bars_since_signal = k > 0` |
|---|---|---|
| `a3_active` | True | True |
| `a3_signal_today` | True | False |
| `a3_bars_since` | 0 (clamped from -1) | k-1 |
| `a3_bars_since_signal` | 0 | k |
| `a3_planned_entry_timing` | `NEXT_OPEN` | `FILLED` |
| `final_action` | NEW_T1 (+ annotation) | NEW_T1 / WAIT_PB / NO_T2_BREADTH |
| `pb_trigger_price` | None (entry unknown) | Computed from entry close |
| `tp1_price` | None (entry unknown) | Computed from entry close |
| `trail_price` | None (entry unknown) | Computed from peak since entry |

## Comparison: Signal Shown on T vs T+1

| Behavior | Pre-fix | Post-fix |
|---|---|---|
| Signal at bar T-40 | Shown at T-39 (one day late) | Shown on T-40 |
| Signal at bar T-1 | Shown on T ✓ | Shown on T ✓ |
| Signal at bar T (latest) | Dropped ✗ | Shown on T ✓ with `a3_signal_today=True` |
| `a3_bars_since=0` on T-1 signal | Means "entry bar is T" | Same ✓ |
| `a3_signal_today=True` | N/A | True when entry at T+1 open |

## Scan Conflation: Signal Date vs Entry Date (Pre-Fix)

The pre-fix code conflated:
- "entry bar (T+1) exists" with "signal is actionable"

They are different:
- Signal bar T: cloud turned bull, price above EMA20 → **operator should prepare to buy**
- Entry bar T+1: position opened at T+1 open → **operator executes**

The scan showed actionability only after the entry bar existed, meaning a same-day EOD scan after close T would miss the signal and only show it on T+1's run — by which time the entry may have already gapped.

## Fix Applied

Changed `portfolio_optimization_final_steps.py:1563-1578` to use `bars_since_signal <= 40` as the guard. Added fields `a3_signal_today`, `a3_bars_since_signal`, `a3_planned_entry_timing` to distinguish "entry pending" from "already filled."

## Impact on Intraday Preview

Same fix resolves the intraday case: if the cloud turns positive on the provisional bar (partial close T), the scan now emits `a3_active=True, a3_signal_today=True, final_action=INTRADAY_PREVIEW, would_be_final_action=NEW_T1`. Operator sees "if close now → NEW_T1" correctly.
