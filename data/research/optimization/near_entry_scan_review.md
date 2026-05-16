# Near-Entry Window — Code Review Note

Generated: 2026-05-14

## Current filter locations

### `scan_cloud_strategy()` — pp_backtest/daily_three_strategy_scan.py line ~343

```python
if abs(pct_vs) <= 0.07 and cur_close > slow_today * 0.97:
    watch_rows.append(...)
```

- Applied identically to B_cloud20_100 and B_cloud21_55.
- `pct_vs` = (current_close - signal_close) / signal_close, where signal_close is the
  close on the last cloud-turn bar within the last 30 bars (excluding today).
- `slow_today * 0.97` provides a soft floor: requires current price to be within 3%
  below the slow EMA. This already functions as a downside guard independent of the
  near-entry window.

### `scan_c_gk()` — same file, line ~469

```python
if abs(pct_vs) <= 0.07 and cur_close > es55 * 0.97:
    watch_rows.append(...)
```

- Identical threshold. C_GK has not been analysed for asymmetric windows.

## Current output: pass / fail only

The scan output currently is binary: a symbol either appears on the watchlist or it
does not. The `pct_vs_signal` column IS present in the watch_rows dict, but:
- It is displayed in the printed table.
- No label column exists to indicate entry quality.
- The hard ±7% filter is the only triage mechanism.

## What the patch will change

For cloud strategies only:
- Replace one symmetric constant with two per-strategy asymmetric constants.
- Pass `near_entry_up` / `near_entry_dn` into `scan_cloud_strategy()`.
- Add `entry_window_label` column to watchlist output.
- C_GK: leave unchanged on 0.07 symmetric until separately validated.

## C_GK recommendation

**NO** — do not inherit asymmetric thresholds for C_GK.

Reasons:
1. The near-entry analysis was run on A3 (ema_dist exit) and S3 (mom20 exit) only.
2. C_GK is a different signal family (Gaussian-Kernel channel + regime gate).
3. No drift-bucket analysis exists for GK entry quality.
4. The slow_ema guard (`es55 * 0.97`) provides meaningful downside protection already.

C_GK should keep `abs(pct_vs) <= 0.07` as explicit fallback constant `CGK_NEAR_ENTRY_PCT = 0.07`.

## Exact patch region

File: `pp_backtest/daily_three_strategy_scan.py`

1. Add at module level:
   - NEAR_ENTRY_B20100_UP  = 0.08
   - NEAR_ENTRY_B20100_DN  = 0.10
   - NEAR_ENTRY_B2155_UP   = 0.08
   - NEAR_ENTRY_B2155_DN   = 0.06
   - CGK_NEAR_ENTRY_PCT    = 0.07   # unchanged; explicit

2. `scan_cloud_strategy()` signature: add `near_entry_up: float`, `near_entry_dn: float`
3. Line ~343: replace `abs(pct_vs) <= 0.07` with
   `pct_vs >= -near_entry_dn and pct_vs <= near_entry_up`
4. Call sites: pass correct constants per strategy.
5. C_GK: keep `abs(pct_vs) <= CGK_NEAR_ENTRY_PCT` — no change to logic.

---

*End of code review*
