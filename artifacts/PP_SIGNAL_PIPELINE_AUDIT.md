# Pocket Pivot Signal Pipeline Audit

**Goal:** Determine exactly how `weekly_pp` is produced and what timeframe the signal logic uses. All claims cite actual code paths; no inference from comments.

---

## 1. Where `weekly_pp` is created

### FILE: `pp_backtest/run_weekly_ema21_portfolio.py`  
### FUNCTION: `build_weekly_dfs`

**Assignment (line 81):**
```python
wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
```

**Context (lines 69–88):**
```python
    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        # Merge regime
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        ...
        weekly_dfs[sym] = wdf
    return weekly_dfs, market_weekly_regime
```

Same pattern (assign `weekly_pp` from `weekly_pocket_pivot_signal(wdf)` with `wdf = daily_to_weekly(daily_df)`) appears in:
- `pp_backtest/run_validation.py` (line 83)
- `pp_backtest/run_validation_experiments.py` (line 91)
- `pp_backtest/run_walkforward_validation.py` (line 84)
- `pp_backtest/run_weekly.py` (line 225)
- `pp_backtest/run_weekly_ema21.py` (line 162)

### FILE: `pp_backtest/signals_weekly.py`  
### FUNCTION: `weekly_pocket_pivot_signal`

**Full code block where the signal is computed (lines 15–33):**
```python
def weekly_pocket_pivot_signal(
    wdf: pd.DataFrame,
    vol_lookback_weeks: int = 10,
) -> pd.Series:
    """
    Weekly Pocket Pivot (Gil/Kacher): volume_week > max(down_volume last 10 weeks),
    close_week > MA10_week, close_week > MA50_week.
    """
    c = wdf["close"].astype(float)
    v = wdf["volume"].astype(float)
    ma10 = sma(c, 10)
    ma50 = sma(c, 50)
    down_vol = np.where(c < c.shift(1), v, 0.0)
    down_vol = pd.Series(down_vol, index=wdf.index)
    max_down_vol = down_vol.rolling(vol_lookback_weeks, min_periods=vol_lookback_weeks).max().shift(1)
    vol_ok = v > max_down_vol
    above_ma10 = c > ma10
    above_ma50 = c > ma50
    return (vol_ok & above_ma10 & above_ma50).fillna(False)
```

So: **`weekly_pp` is produced only in `signals_weekly.weekly_pocket_pivot_signal(wdf)`**, and `wdf` is always a **weekly** DataFrame (one row per week).

---

## 2. Data source used to compute `weekly_pp`

**Case B does not apply.** There is no code path that:
- computes a daily Pocket Pivot on daily bars, then
- aggregates daily PP into a weekly flag (e.g. “any daily PP in the week”).

**Case A applies.** Pattern in the codebase:

1. **Weekly bars from daily:**  
   `pp_backtest/weekly_bars.py` (lines 6–19): `daily_to_weekly(daily_df)` resamples daily OHLCV to weekly (W-FRI), producing one row per week with `open`, `high`, `low`, `close`, `volume`.

2. **Signal on weekly bars:**  
   `weekly_pocket_pivot_signal(wdf)` receives that weekly DataFrame and uses:
   - `wdf["close"]` → weekly close  
   - `wdf["volume"]` → weekly volume (sum of daily volume in the week)  
   - `sma(c, 10)` / `sma(c, 50)` → 10- and 50-**week** SMAs on weekly close  
   - `down_vol` / `max_down_vol` → based on week-on-week close and weekly volume  

So: **`weekly_pp` is derived from weekly bars only.** It is **not** “daily PP signals aggregated into weeks.”

---

## 3. Where `weekly_dfs` is constructed

### Resampling (weekly bars from daily)

**FILE:** `pp_backtest/weekly_bars.py`  
**FUNCTION:** `daily_to_weekly`

```python
def daily_to_weekly(daily_df: pd.DataFrame, week_end: str = "W-FRI") -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly. week_end: W-FRI = week ending Friday.
    Agg: open=first, high=max, low=min, close=last, volume=sum.
    """
    if daily_df.empty or "date" not in daily_df.columns:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = daily_df.set_index(pd.to_datetime(daily_df["date"])).sort_index()
    agg = df.resample(week_end).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(how="all")
    agg = agg[agg["close"].notna()]
    agg = agg.reset_index().rename(columns={"index": "date"})
    agg["date"] = agg["date"].dt.normalize()
    return agg[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
```

So: **weekly data is resampled from daily** via `df.resample(week_end).agg(...)` (W-FRI). It is **not** loaded as native weekly data.

### Construction of `weekly_dfs`

**FILE:** `pp_backtest/run_weekly_ema21_portfolio.py`  
**FUNCTION:** `build_weekly_dfs` (lines 59–88)

- For each symbol: `daily_df = fetch(sym, cfg.start, cfg.end)` (daily OHLCV).  
- Then: `wdf = daily_to_weekly(daily_df)`.  
- Then columns are added on `wdf`: `ma10`, `ema21`, `weekly_pp`, `exit_ma10`, regime columns.  
- `weekly_dfs[sym] = wdf`.

So: **`weekly_dfs` is built from daily data resampled to weekly**, then signals and MAs are computed on that weekly DataFrame.

---

## 4. Timeframe of moving averages

### Where ema21, ma10, ma50 are calculated

**FILE:** `pp_backtest/run_weekly_ema21_portfolio.py`  
**FUNCTION:** `build_weekly_dfs` (lines 77–81)

```python
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
```

- `c` is `wdf["close"]` → **weekly** close (one value per week).  
- `sma(c, 10)` and `ema(c, 21)` are from `pp_backtest/signals_weekly.py` (same module as `weekly_pocket_pivot_signal`).  
- So **ma10** and **ema21** are computed on the **weekly** price series.

**FILE:** `pp_backtest/signals_weekly.py`  
**FUNCTION:** `weekly_pocket_pivot_signal` (lines 24–25)

```python
    ma10 = sma(c, 10)
    ma50 = sma(c, 50)
```

- `c = wdf["close"].astype(float)` → weekly close.  
- So **ma50** used inside the PP logic is also a **weekly** MA (50-week SMA on weekly close).

**FILE:** `pp_backtest/signals_weekly.py`  
**FUNCTION:** `weekly_exit_ema21_ma50` (lines 76–78)

```python
    c = wdf["close"].astype(float)
    ema21 = ema(c, 21)
    ma50 = sma(c, 50)
```

- Same `wdf["close"]` → **weekly** close. So exit logic uses **weekly** EMA21 and **weekly** MA50.

**Conclusion:**  
- **ema21, ma50, ma10** in the portfolio/strategy pipeline are all computed from the **weekly** close series.  
- There is no use of daily `ema21`/`ma50`/`ma10` in the weekly PP entry/exit flow.  
- (A separate daily PP exists in `pp_backtest/signals.py`: `pocket_pivot(df, p)` uses daily bars and daily MAs, but that function is **not** used by `run_weekly_ema21_portfolio`, `run_walkforward_validation`, `run_validation_experiments`, or `portfolio_sim`.)

---

## 5. Execution timing of entries (and exits)

### Entry

**FILE:** `pp_backtest/portfolio_sim.py`  
**Relevant blocks:**

- **Signal:** For a given week date `dt`, the row for that week is taken from `wdf` (lines 232–237). So the signal is the **weekly** bar for that week; `weekly_pp` is True for that **week** (week’s close has been used in the PP logic).
- **Execution:** Lines 336–346 (conceptually): `next_dt = all_dates[i + 1]`; then `next_row = wdf[wdf["date"].astype(str) == next_dt]`; `entry_price = float(next_row["open"].iloc[0])`. So entry is at the **next week’s open**.

So: **weekly signal (that week’s bar, including week close) → entry at next week’s open.** Not “daily signal → next day.”

### Exit

**FILE:** `pp_backtest/portfolio_sim.py` (lines 158–174)

- `exit_sig = bool(row.get("exit_ma10", False))` where `row` is the **current week’s** row in `wdf`. So the exit signal is the **weekly** exit rule for that week.
- If there is a next week, exit price is **next week’s open** (`next_row["open"]`); otherwise end-of-sample fallback to current week close.

So: **weekly exit signal (from that week’s close) → exit at next week’s open** (when available).

### Pipeline summary

- **Signal:** Weekly only (`weekly_pp`, `exit_ma10` from weekly bars and weekly MAs).  
- **Execution:** Next **week’s** open for both entry and exit. No daily signal or daily execution in this pipeline.

---

## 6. Final structured summary

### SECTION 1 — Signal timeframe

**Is Pocket Pivot computed from:**

- **Weekly bars.**  
- It is **not** computed from daily bars.  
- It is **not** “daily PP aggregated to weekly.”

**Evidence:**  
- `weekly_pp` is the return value of `weekly_pocket_pivot_signal(wdf)` in `pp_backtest/signals_weekly.py` (lines 15–33).  
- The only input is `wdf`, which is always the output of `daily_to_weekly(daily_df)` (weekly resample).  
- The function uses `wdf["close"]`, `wdf["volume"]`, and 10/50-**week** SMAs on weekly close. No daily series is passed in or used.

---

### SECTION 2 — Moving averages timeframe

**Are EMA21 / MA50 (and MA10):**

- **Weekly.**  
- They are computed from the **weekly** close series in:
  - `run_weekly_ema21_portfolio.build_weekly_dfs`: `c = wdf["close"]`, then `sma(c, 10)`, `ema(c, 21)`.
  - `signals_weekly.weekly_pocket_pivot_signal`: `sma(c, 10)`, `sma(c, 50)` on `wdf["close"]`.
  - `signals_weekly.weekly_exit_ema21_ma50`: `ema(c, 21)`, `sma(c, 50)` on `wdf["close"]`.

So: **EMA21 and MA50 (and MA10) are weekly** in this strategy.

---

### SECTION 3 — Entry timing

**Is entry triggered by:**

- **Weekly signal → next week execution.**  
- The strategy uses a **weekly** bar and weekly `weekly_pp` for the current week; if True, entry is at the **next** week’s open.  
- It is **not** “daily signal → next day execution.”

**Evidence:**  
- `pp_backtest/portfolio_sim.py`: candidate selection uses `row.get("weekly_pp", False)` for the current week `dt`; entry price is taken from `next_row["open"]` for `next_dt = all_dates[i + 1]`.

---

### SECTION 4 — Data pipeline

```
Daily OHLCV (fetch per symbol)
    ↓
daily_to_weekly(daily_df)   [pp_backtest/weekly_bars.py: resample("W-FRI"), open=first, high=max, low=min, close=last, volume=sum]
    ↓
Weekly DataFrame wdf (one row per week)
    ↓
On wdf:
  - ma10 = sma(close_week, 10)   [signals_weekly.sma]
  - ema21 = ema(close_week, 21)   [signals_weekly.ema]
  - weekly_pp = weekly_pocket_pivot_signal(wdf)   [signals_weekly: volume_week, close_week, MA10_week, MA50_week]
  - exit_ma10 = weekly_exit_ema21_ma50(wdf)       [signals_weekly: weekly close vs EMA21_week, MA50_week]
    ↓
weekly_dfs[sym] = wdf
    ↓
Portfolio engine (portfolio_sim.run_portfolio_backtest):
  - For each week dt: select symbols where row["weekly_pp"] is True; entry at next week open.
  - Exit when row["exit_ma10"] True; exit at next week open (or EOS fallback).
```

No daily signal computation sits between daily data and the portfolio engine; the only signal layer is on weekly bars.

---

### SECTION 5 — Conclusion

The system uses:

**Option B — Weekly pivot / accumulation system inspired by Pocket Pivot.**

- The **Pocket Pivot logic** (volume vs down-volume, close above MA10/MA50) is implemented on **weekly** bars in `signals_weekly.weekly_pocket_pivot_signal`: weekly volume, weekly close, 10- and 50-**week** SMAs.  
- Entry and exit are driven by these **weekly** signals, with execution at the **next week’s open**.  
- There is **no** Gil-style **daily** Pocket Pivot in this pipeline; the daily `pocket_pivot()` in `pp_backtest/signals.py` is not used by the weekly portfolio or validation runners.  
- So this is a **weekly** pivot/accumulation system inspired by the Gil/Kacher idea, not a true daily PP system with weekly execution (Option A), and not a hybrid (Option C) where the signal is detected on daily bars and only execution is weekly.

**Exact file references:**

- `weekly_pp` assignment: `pp_backtest/run_weekly_ema21_portfolio.py` line 81, and equivalent in other runners.  
- PP logic: `pp_backtest/signals_weekly.py` lines 15–33 (`weekly_pocket_pivot_signal`).  
- Weekly bars: `pp_backtest/weekly_bars.py` lines 6–19 (`daily_to_weekly`, `resample(week_end)`).  
- MAs: `pp_backtest/run_weekly_ema21_portfolio.py` lines 77–81; `pp_backtest/signals_weekly.py` lines 24–25, 76–78.  
- Entry/exit timing: `pp_backtest/portfolio_sim.py` lines 230–237 (candidates), 336–346 (entry at next open), 158–174 (exit at next open).
