# Cloud Signal Timing Audit — A3/S3 Entry States

**As-of:** 2026-05-19  
**Author:** Claude Code automated audit  
**Status:** SCAN_LAYER_FIX_APPLIED

---

## Timing State Definitions

### A. EOD Signal Bar

At end of bar T, with `close[T]` known:

```
signal_T = cloud_only_entry(close[T], EMA20[T], EMA100[T], cloud_was_bear_recently)
```

Where:
- `cloud_bull[T] = EMA20[T] > EMA100[T]`
- `cloud_was_bear = (~cloud_bull).rolling(min_bars_bear=3).max().shift(1)` — prior 3 bars must have been bear
- Signal condition: `close[T] > EMA20[T] AND cloud_bull[T] AND cloud_was_bear[T]`

This is the **official A3 signal definition** (`pp_backtest/ema_levels/entry.py:219`).  
All signal computations are causal — no future data used.

### B. Backtest Fill

If `signal_T = True`, backtest fills at `open[T+1]`.

- This is documented at `entry.py:5`: *"All signals: True at bar t means enter at bar t+1 open."*
- **This rule is unchanged and remains the production baseline.**
- Fill at T+1 open is Variant B0 (baseline).

### C. EOD Daily Scan After Close

Run the scan after close T with `signal_T = True`:

- **Correct behavior:** scan shows a next-session actionable candidate with `final_action = NEW_T1`.
- **Operator action:** "prepare for next open" — not "already filled."
- **Prior behavior (pre-fix):** the scan required bar T+1 to already exist. Signal on the latest bar was silently dropped. `a3_active = False` despite the signal firing.
- **Post-fix behavior:** signal on the latest bar is correctly detected. `a3_signal_today = True`, `a3_planned_entry_timing = NEXT_OPEN`.

### D. Intraday Preview

During bar T (before close), a provisional bar is constructed:

- `provisional_close = current last price / partial daily bar close`
- EMAs and cloud are computed as-if today closed at provisional close
- If provisional signal = True:
  - `would_be_final_action` = NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH (IF_CLOSE_NOW engine result)
  - `final_action` = INTRADAY_PREVIEW (always)
  - `auto_order_allowed` = False (always)
  - `intraday_candidate` = True (triggers manual review flag for quoted symbols)

**Pre-fix:** provisional signal on the LATEST provisional bar was also silently dropped (same `li + 1 < len(c)` guard applied to the in-memory panel too).  
**Post-fix:** provisional signal on the latest bar is detected; `a3_signal_today = True`.

### E. ATC / Close-Fill Research Variant

Not production baseline. A separate research variant may test:
- Signal confirmed on close T → fill at close T / ATC price.
- This is Variant B1 in backtest comparisons.
- Labeled `close_confirmed_atc_fill` — optimistic unless verified pre-ATC order timestamps exist.

---

## Field Semantics (Post-Fix)

| Field | Meaning |
|---|---|
| `a3_active` | True when A3 signal is within 40 bars (including signal bar itself) |
| `a3_bars_since` | Bars elapsed since the entry bar (li+1). 0 = entry bar is latest bar (position just entered). Clamped to 0 when entry bar hasn't happened yet (`a3_signal_today=True`). |
| `a3_signal_today` | True when signal fires on the latest bar. Entry has NOT occurred yet; entry = next session open. |
| `a3_bars_since_signal` | Bars since the signal bar itself. 0 on signal day, 1 the next day, etc. |
| `a3_planned_entry_timing` | `NEXT_OPEN` when `a3_signal_today=True`; `FILLED` when entry bar has already occurred. |
| `final_action` | `NEW_T1` when `a3_bars=0` regardless of `a3_signal_today`. In intraday mode: always `INTRADAY_PREVIEW`. |

---

## Entry Timing Relationship

```
Bar T-1: signal fires (cloud_only_entry = True)
Bar T:   entry at open[T] (fill); a3_bars_since = 0; a3_signal_today = False
Bar T+1: first full bar in position; a3_bars_since = 1
...

Bar T:   signal fires on LATEST bar (no T+1 yet)
         a3_signal_today = True; a3_bars_since = 0; a3_planned_entry_timing = NEXT_OPEN
         Final action: NEW_T1 with note "Signal confirmed at today's close; planned fill is next session open."
Bar T+1: entry at open[T+1]; next scan run will show a3_signal_today=False, a3_bars_since=0
```

---

## Non-Negotiables

- A3 production entry signal rule is unchanged.
- Backtest B0 (signal T → fill T+1 open) is unchanged.
- T1/T2/TP1/trail/max_hold contract is unchanged.
- Intraday `final_action = INTRADAY_PREVIEW` always.
- Intraday `auto_order_allowed = False` always.
- S3 is research-only, no live capital.
- No EOD parquet writes from intraday.
