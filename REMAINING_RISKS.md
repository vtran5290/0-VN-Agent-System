# Remaining Risks — Cloud Signal Timing Fix

**As-of:** 2026-05-19  
**Patch:** scan-layer latest-bar signal fix

---

## R1 — `cloud_was_bear_recent` uses EOD data only

**Risk:** Intraday provisional signal may show `a3_signal_today=True` but EOD final close differs slightly.  
**Severity:** Low — difference is partial vs final close, not a structural miss.  
**Mitigation:** Intraday always shows `final_action=INTRADAY_PREVIEW` and `auto_order_allowed=False`. No action until EOD confirmation.

---

## R2 — Backtest B3 not testable

**Risk:** Cannot measure value of intraday pre-lunch entry vs next-open fill without historical intraday snapshots.  
**Severity:** Low — B0 (next-open fill) remains unchanged as production baseline.  
**Mitigation:** B3 documented as `NOT_TESTABLE_WITH_CURRENT_DATA` in `ENTRY_TIMING_BACKTEST_FINDINGS.md`. No strategy change pending data availability.

---

## R3 — Pre-ATC trigger is informational only

**Risk:** `a3_pre_atc_trigger.py` gives the minimum close price to trigger A3, but:
1. Assumes today's close is the only variable (no intraday OHLC path affects EMA).
2. `cloud_was_bear_recent` is checked from prior-day data only.
3. Operator could act on trigger price without EOD close confirmation.  
**Severity:** Medium — trigger price is informational; an ATC order based on it bypasses EOD confirmation.  
**Mitigation:** `auto_order_allowed=False` always. Doc explicitly states: "Final signal requires full-day close via EOD scan."

---

## R4 — Entry-level nulls in pending rows

**Risk:** `pb_trigger_price / tp1_price / trail_price = NaN` when `a3_signal_today=True`. If any consumer of the scan CSV tries to use these as floats, they crash or produce NaN arithmetic.  
**Severity:** Low — OMS reads `final_action` only and ignores these fields. Report shows "pending*".  
**Mitigation:** 4 new tests verify null handling. OMS test confirms BUY_T1 is produced correctly with null fields present.

---

## R5 — `phase36_daily_scan_latest.csv` SSOT alignment

**Risk:** `scan_ssot.resolve_scan_path()` picks the first-found `phase36_daily_scan_latest.csv`. If this file is stale (from a pre-fix scan), the report writer uses it.  
**Severity:** Low — operator runs `--step scan` to regenerate; report writer is run after scan.  
**Mitigation:** `phase36_daily_scan_latest.csv` was updated to the 97-row post-fix CSV. No code change to SSOT resolver needed.

---

## R6 — S3 `s3_signal_today` not yet surfaced in report

**Risk:** `s3_signal_today` field is in the CSV but the daily scan report table does not show it. S3 is paper-shadow only; missing display is not a production risk.  
**Severity:** Negligible — S3 has no real capital.  
**Mitigation:** Field is in CSV for audit. Report can be extended if S3 paper-shadow becomes operator-visible.

---

## Not Risks (explicitly ruled out)

- OMS auto-order on signal_today: `auto_order_allowed = False` always. Tested.
- Backtest lookahead: `cloud_only_entry` uses close[T] and EMA[T] only. No lookahead. Tested.
- Strategy rule change: `cloud_only_entry`, T1/T2 sizing, exit policy, breadth gates — all unchanged.
