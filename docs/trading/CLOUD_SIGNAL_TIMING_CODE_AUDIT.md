# Cloud Signal Timing — Code Audit Findings

**As-of:** 2026-05-19  
**Files audited:** pp_backtest/ema_levels/entry.py, pp_backtest/portfolio_optimization_final_steps.py, src/trading/intraday/intraday_scan.py, src/trading/intraday/panel_overlay.py, tests/test_phase36_daily_scan.py, tests/test_intraday_scan.py

---

## 1. Does `cloud_only_entry` use `close[T]` and EMA values computed including `close[T]`?

**YES — correct.**

`pp_backtest/ema_levels/entry.py:219-234`:
```python
def cloud_only_entry(close, ema_fast, cloud_bull, min_bars_bear=3, warmup=60):
    cloud_was_bear = (~cloud_bull).rolling(min_bars_bear, min_periods=1).max().shift(1).fillna(False)
    sig = (close > ema_fast) & cloud_bull & cloud_was_bear.astype(bool)
```

- `close[T]` is used directly (no shift)
- `EMA20[T]` and `EMA100[T]` are computed from close including close[T]
- `cloud_bull[T] = EMA20[T] > EMA100[T]` at bar T
- `cloud_was_bear` uses `.shift(1)` — checks that prior bars (not T) had bear cloud

Signal at T is fully determined by T's close and EMAs. No lookahead.

---

## 2. Does the backtest fill at T+1 open?

**YES — documented at entry level.**

`pp_backtest/ema_levels/entry.py:5`:
```
All signals: True at bar t means "enter at bar t+1 open".
```

No dedicated `sim.py` found. Fill timing is enforced by the signal indexing convention: signal at T means position taken at index T+1. In `compute_phase36_scan_df`, the entry bar index is computed as `li + 1` where `li` is the signal bar.

---

## 3. Does `compute_phase36_scan_df` detect signal on the latest bar when there is no T+1 bar?

**NO — BUG FOUND AND FIXED.**

`pp_backtest/portfolio_optimization_final_steps.py:1566` (pre-fix):
```python
if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
    a3_active = True
    a3_bars   = len(c) - 1 - (li + 1)
```

The condition `li + 1 < len(c)` requires the entry bar (li+1) to exist in the close series. If signal fires on the latest bar (`li = len(c) - 1`), then `li + 1 = len(c)`, so the condition fails and `a3_active = False`.

**Result:** EOD scan run after close T misses any signal that just fired at close T. The signal only appears in the next run after T+1 closes.

**Fix applied** (`pp_backtest/portfolio_optimization_final_steps.py:1563-1578`):
```python
a3_active = False; a3_bars = None; a3_signal_today = False
_a3_bars_since_signal = None
if len(a3_idxs) > 0:
    li = int(a3_idxs[-1])
    _bss = len(c) - 1 - li          # bars since signal bar; 0 on signal day
    if _bss <= 40:
        a3_active = True
        a3_bars   = max(0, len(c) - 1 - (li + 1))  # clamp to 0 when entry bar doesn't exist yet
        a3_signal_today = (_bss == 0)
        _a3_bars_since_signal = _bss
```

---

## 4. Does the daily scan require a next bar before showing NEW_T1?

**YES — was the bug. Fixed as above.**

Pre-fix: `li + 1 < len(c)` gate prevented latest-bar signals.  
Post-fix: `_bss <= 40` gate allows latest-bar signals. `a3_signal_today = True` distinguishes "entry pending next open" from "already filled."

---

## 5. Does the intraday scan detect provisional signal on the current bar?

**YES — but was blocked by the same bug pre-fix.**

`src/trading/intraday/intraday_scan.py:340-342`:
```python
scan_df, scan_meta = compute_phase36_scan_df(
    prov_panel, vnx, gk_cache, sector_map=None, intraday_macro=True,
)
```

The provisional panel appends today's partial bar as the latest bar. `compute_phase36_scan_df` runs on this panel. Pre-fix: if cloud turned positive on the provisional bar, `li + 1 < len(c)` failed → `a3_active = False` → no signal shown. Post-fix: signal on the provisional bar is detected with `a3_signal_today = True`.

---

## 6. Cases where `signal_T=True` on latest bar but `a3_active=False`?

**Was: YES (bug). Post-fix: NO for valid signals.**

The only case where `a3_active = False` with a valid signal is now: signal fires more than 40 bars ago. This is intentional — signals expire after 40 bars.

---

## 7. Cases where intraday provisional signal=True but `would_be_final_action` does not show it?

**Was: YES (same bug). Post-fix: NO.**

`_apply_intraday_policy` sets `would_be_final_action = final_action` before transformation (line 160). Pre-fix: the scan produced `WATCH_ONLY` instead of `NEW_T1` for provisional signals on the latest bar, so `would_be_final_action` was also `WATCH_ONLY`. Post-fix: scan correctly produces `NEW_T1` for the provisional bar, so `would_be_final_action = NEW_T1`.

---

## 8. Does `a3_bars_since = 0` mean signal today, or first day after signal?

**`a3_bars_since = 0` means the entry bar (li+1) is the CURRENT (latest) bar.**

Interpretation:
- `a3_bars_since = 0`: Entry bar is the latest bar. Position entered at this bar's open. Currently at this bar's close.  
  - Pre-fix: could only happen when signal was at li = latest-bar-1.  
  - Post-fix: also represents "signal today" case (a3_signal_today=True), where entry bar doesn't exist yet and we clamp to 0.

- `a3_bars_since = 1`: One bar has elapsed since the entry bar. Position entered two bars ago.

- New field `a3_signal_today = True`: Explicitly flags when `a3_bars_since = 0` is due to a fresh signal on the latest bar (entry pending, not yet filled).

- New field `a3_bars_since_signal`: Counts bars since the signal bar itself. 0 on signal day.

---

## Summary Table

| Question | Pre-fix | Post-fix |
|---|---|---|
| Signal uses close[T] | YES | YES (unchanged) |
| Fill at T+1 open | YES | YES (unchanged) |
| Latest-bar signal detected by scan | NO — BUG | YES — fixed |
| Next bar required for NEW_T1 | YES — BUG | NO — fixed |
| Intraday provisional signal on latest bar | NO — BUG | YES — fixed |
| `would_be_final_action` shows provisional signal | NO — BUG | YES — fixed |
| `a3_signal_today=True` means entry pending | N/A | YES — new field |
| `a3_bars_since_signal` available | NO | YES — new field |

---

## Files Changed

- `pp_backtest/portfolio_optimization_final_steps.py:1563-1578` — A3/S3 signal detection
- `pp_backtest/portfolio_optimization_final_steps.py:1646` — entry-price guard
- `pp_backtest/portfolio_optimization_final_steps.py:1668-1671` — reason annotation
- `pp_backtest/portfolio_optimization_final_steps.py:1710-1714` — new row fields

## Files Unchanged

- `pp_backtest/ema_levels/entry.py` — signal rule unchanged
- `src/trading/intraday/intraday_scan.py` — policy unchanged (benefits from scan fix)
- `src/trading/intraday/panel_overlay.py` — unchanged
- A3 production T1/T2/TP1/trail/maxhold contract — unchanged
