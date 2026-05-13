"""
Trade simulation: two modes.

fixed_horizon_trades(...)
    For each signal bar, record returns at 25/50/100/150-day horizons.
    Pure forward-return analysis — no exit logic, just "buy and hold N days."
    Fast and fully vectorized (no per-bar loop except over sparse signals).

variable_exit_trades(...)
    For each signal bar, simulate a trade with one of several exit modes:
        cloud_loss   -- exit when close < ema_slow for K consecutive closes
        level_loss   -- exit when close breaks support level at entry
        atr_stop     -- fixed ATR multiple stop from entry price
        trailing     -- trailing ATR-based high-water-mark stop
        partial_tp   -- take 50 % at +atr_mult*atr, trail rest
    Inner loop is per-trade (not per-bar), so it is fast when # trades << # bars.

Entry/exit fill: next-bar OPEN after signal/exit bar.
Costs: round-trip cost_bps applied to net_return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COST_BPS_DEFAULT = 40   # 15 fee + 5 slippage each side = 40 bps round-trip
MIN_ADV_DEFAULT  = 2e9  # 2 B VND
MIN_HIST_DEFAULT = 60   # min bars of history before signals allowed


# ── Fixed-horizon simulation ─────────────────────────────────────────────────

def fixed_horizon_trades(
    df:          pd.DataFrame,    # symbol OHLCV, integer-indexed, sorted by date
    signals:     pd.Series,       # bool, same index as df
    horizons:    list[int] = (25, 50, 100, 150),
    cost_bps:    int   = COST_BPS_DEFAULT,
    min_adv:     float = MIN_ADV_DEFAULT,
    min_history: int   = MIN_HIST_DEFAULT,
) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per (signal_bar, horizon).

    Columns:
        signal_bar, signal_date, entry_bar, entry_date,
        entry_price, exit_bar, exit_date, exit_price,
        horizon, gross_return, net_return
    """
    n = len(df)
    open_prices = df["open"].values
    dates       = df["date"].values

    adv50 = df["value"].rolling(50, min_periods=20).mean()

    # Liquidity + history guard
    valid = (
        signals
        & (adv50 >= min_adv)
        & (pd.Series(np.arange(n), index=df.index) >= min_history)
    )

    sig_bars = np.where(valid.values)[0]

    cost_frac = cost_bps / 10_000.0
    rows: list[dict] = []

    for bar in sig_bars:
        entry_bar = bar + 1
        if entry_bar >= n:
            continue
        ep = open_prices[entry_bar]
        if ep <= 0:
            continue

        for h in horizons:
            exit_bar = entry_bar + h
            if exit_bar < n:
                xp = open_prices[exit_bar]
                gr = xp / ep - 1.0
                nr = gr - cost_frac
                exit_date = dates[exit_bar]
            else:
                xp = np.nan
                gr = np.nan
                nr = np.nan
                exit_date = None

            rows.append({
                "signal_bar":  bar,
                "signal_date": dates[bar],
                "entry_bar":   entry_bar,
                "entry_date":  dates[entry_bar],
                "entry_price": ep,
                "exit_bar":    exit_bar,
                "exit_date":   exit_date,
                "exit_price":  xp,
                "horizon":     h,
                "gross_return": gr,
                "net_return":   nr,
            })

    return pd.DataFrame(rows)


# ── Variable-exit simulation ─────────────────────────────────────────────────

def variable_exit_trades(
    df:          pd.DataFrame,
    signals:     pd.Series,
    exit_mode:   str,           # 'cloud_loss' | 'level_loss' | 'atr_stop' | 'trailing' | 'partial_tp'
    ema_slow:    pd.Series | None = None,
    support:     pd.Series | None = None,
    atr_series:  pd.Series | None = None,
    atr_mult:    float = 2.0,
    trail_mult:  float = 2.5,
    cloud_loss_k: int  = 2,     # consecutive closes below cloud before exit
    max_hold:    int   = 200,
    cost_bps:    int   = COST_BPS_DEFAULT,
    min_adv:     float = MIN_ADV_DEFAULT,
    min_history: int   = MIN_HIST_DEFAULT,
) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per trade.

    Extra columns vs. fixed_horizon_trades:
        hold_bars, exit_reason, mfe (max favourable excursion), mae (max adverse)
    """
    n = len(df)
    close_arr = df["close"].values
    open_arr  = df["open"].values
    dates_arr = df["date"].values

    adv50 = df["value"].rolling(50, min_periods=20).mean()
    valid = (
        signals
        & (adv50 >= min_adv)
        & (pd.Series(np.arange(n), index=df.index) >= min_history)
    )

    sig_bars = np.where(valid.values)[0]

    ema_slow_arr = ema_slow.values   if ema_slow  is not None else None
    support_arr  = support.values    if support   is not None else None
    atr_arr      = atr_series.values if atr_series is not None else None

    cost_frac = cost_bps / 10_000.0
    rows: list[dict] = []

    for bar in sig_bars:
        entry_bar = bar + 1
        if entry_bar >= n:
            continue
        ep = open_arr[entry_bar]
        if ep <= 0:
            continue

        atr_at_entry     = atr_arr[entry_bar]    if atr_arr    is not None else None
        support_at_entry = support_arr[bar]       if support_arr is not None else None

        high_water = ep          # highest close since entry
        below_cloud_k = 0
        tp1_taken = False        # partial take-profit flag
        exit_bar = None
        exit_reason = "MAX_HOLD"
        mfe = 0.0
        mae = 0.0

        for t in range(entry_bar, min(entry_bar + max_hold, n)):
            c = close_arr[t]
            r_now = c / ep - 1.0

            if r_now > mfe:
                mfe = r_now
            if r_now < mae:
                mae = r_now

            if c > high_water:
                high_water = c

            # ── exit logic ──
            if exit_mode == "cloud_loss":
                if ema_slow_arr is not None:
                    if c < ema_slow_arr[t]:
                        below_cloud_k += 1
                    else:
                        below_cloud_k = 0
                    if below_cloud_k >= cloud_loss_k:
                        exit_bar = min(t + 1, n - 1)
                        exit_reason = "CLOUD_LOSS"
                        break

            elif exit_mode == "level_loss":
                if support_at_entry is not None and not np.isnan(support_at_entry):
                    if c < support_at_entry * 0.985:   # 1.5 % tolerance
                        exit_bar = min(t + 1, n - 1)
                        exit_reason = "LEVEL_LOSS"
                        break

            elif exit_mode == "atr_stop":
                if atr_at_entry is not None and not np.isnan(atr_at_entry):
                    stop = ep - atr_mult * atr_at_entry
                    if c < stop:
                        exit_bar = min(t + 1, n - 1)
                        exit_reason = "ATR_STOP"
                        break

            elif exit_mode == "trailing":
                if atr_at_entry is not None and not np.isnan(atr_at_entry):
                    trail_stop = high_water - trail_mult * atr_at_entry
                    if c < trail_stop:
                        exit_bar = min(t + 1, n - 1)
                        exit_reason = "TRAILING"
                        break

            elif exit_mode == "partial_tp":
                # Take 50 % at +atr_mult*atr, then trail remainder at trail_mult*atr
                if atr_at_entry is not None and not np.isnan(atr_at_entry):
                    if not tp1_taken and c >= ep + atr_mult * atr_at_entry:
                        tp1_taken = True     # marker; no partial size tracking here
                    trail_stop = high_water - trail_mult * atr_at_entry
                    if tp1_taken and c < trail_stop:
                        exit_bar = min(t + 1, n - 1)
                        exit_reason = "PARTIAL_TRAIL"
                        break

        if exit_bar is None:
            exit_bar = min(entry_bar + max_hold, n - 1)

        if exit_bar >= n:
            continue

        xp = open_arr[exit_bar]
        gr = xp / ep - 1.0
        nr = gr - cost_frac

        rows.append({
            "signal_bar":    bar,
            "signal_date":   dates_arr[bar],
            "entry_bar":     entry_bar,
            "entry_date":    dates_arr[entry_bar],
            "entry_price":   ep,
            "exit_bar":      exit_bar,
            "exit_date":     dates_arr[exit_bar],
            "exit_price":    xp,
            "hold_bars":     exit_bar - entry_bar,
            "exit_reason":   exit_reason,
            "gross_return":  gr,
            "net_return":    nr,
            "mfe":           mfe,
            "mae":           mae,
        })

    return pd.DataFrame(rows)
