"""
Entry signal generators.

Three main entry types + two benchmarks (cloud-only, Donchian).
All signals: True at bar t means "enter at bar t+1 open".
All computations are causal (no future data).

Parameters are passed as plain scalars; callers pre-compute indicators.
"""

import numpy as np
import pandas as pd


# ── Utilities ────────────────────────────────────────────────────────────────

def _warmup_mask(n: int, warmup: int) -> np.ndarray:
    mask = np.ones(n, dtype=bool)
    mask[:warmup] = False
    return mask


# ── Main entry types ─────────────────────────────────────────────────────────

def breakout_signals(
    close:      pd.Series,
    volume:     pd.Series,
    resistance: pd.Series,      # rolling max of pivot highs
    r_strength: pd.Series,      # count of touches near that resistance
    cloud_bull: pd.Series,
    ema_fast:   pd.Series,
    buffer_pct:           float = 0.005,
    min_touches:          int   = 2,
    fresh_window:         int   = 10,   # price must have been <= res in last N bars
    require_vol_expansion: bool = False,
    vol_expansion_x:      float = 1.2,
    vol_ma_period:        int   = 20,
    warmup:               int   = 60,
) -> pd.Series:
    """
    Breakout: close crosses above a multi-touch resistance zone.

    Conditions (evaluated at bar t; signal fires for t+1 entry):
    1. close[t] > resistance[t-1] * (1 + buffer_pct)       -- broke the level
    2. r_strength[t-1] >= min_touches                        -- level tested enough
    3. cloud_bull[t]                                         -- cloud bullish
    4. close[t] > ema_fast[t]                                -- above fast EMA
    5. close was at/below resistance in last fresh_window bars  -- fresh breakout
    6. (optional) volume expansion

    The freshness filter (5) is critical: without it the signal stays True for
    the entire post-breakout trend, inflating trade counts by 10-50x.
    """
    res_prev = resistance.shift(1)
    str_prev = r_strength.shift(1)

    # Freshness: was price at or below the resistance threshold recently?
    at_or_below_res = (close <= res_prev * (1.0 + buffer_pct * 0.5))
    was_below_recently = (
        at_or_below_res.rolling(fresh_window, min_periods=1).max().shift(1).fillna(False)
    )

    sig = (
        (close > res_prev * (1.0 + buffer_pct))
        & (str_prev >= min_touches)
        & cloud_bull
        & (close > ema_fast)
        & was_below_recently.astype(bool)
    )

    if require_vol_expansion:
        vol_ma = volume.rolling(vol_ma_period, min_periods=vol_ma_period // 2).mean()
        sig = sig & (volume > vol_ma * vol_expansion_x)

    sig = sig.fillna(False).copy()
    sig.iloc[:warmup] = False
    return sig


def retest_signals(
    close:      pd.Series,
    volume:     pd.Series,
    resistance: pd.Series,
    r_strength: pd.Series,
    cloud_bull: pd.Series,
    ema_fast:   pd.Series,
    tolerance_pct:         float = 0.02,
    lookback_break:        int   = 30,   # bars to look back for prior breakout
    min_touches:           int   = 2,
    require_vol_contraction: bool = False,
    vol_contraction_x:     float = 0.8,
    vol_ma_period:         int   = 20,
    warmup:                int   = 60,
) -> pd.Series:
    """
    Retest: price pulls back to a level it previously broke above.

    Conditions:
    1. close[t] in [res[t-1]*(1-tol), res[t-1]*(1+tol/2)]   -- at the level
    2. close was clearly above res in last lookback_break bars  -- prior breakout
    3. r_strength[t-1] >= min_touches                           -- valid level
    4. cloud_bull[t]                                            -- still bullish
    5. close[t] >= ema_fast[t-1] * 0.98                        -- near cloud
    """
    res_prev = resistance.shift(1)
    str_prev = r_strength.shift(1)

    at_level = (
        (close >= res_prev * (1.0 - tolerance_pct))
        & (close <= res_prev * (1.0 + tolerance_pct * 0.5))
    )

    # Detect whether price was clearly above resistance recently
    was_above = close > res_prev * (1.0 + 0.005)
    had_prior_break = was_above.rolling(lookback_break, min_periods=1).max().shift(1).fillna(False)

    sig = (
        at_level
        & had_prior_break.astype(bool)
        & (str_prev >= min_touches)
        & cloud_bull
        & (close >= ema_fast.shift(1) * 0.98)
    )

    if require_vol_contraction:
        vol_ma = volume.rolling(vol_ma_period, min_periods=vol_ma_period // 2).mean()
        sig = sig & (volume < vol_ma * vol_contraction_x)

    sig = sig.fillna(False).copy()
    sig.iloc[:warmup] = False
    return sig


def reclaim_signals(
    close:    pd.Series,
    ema_fast: pd.Series,
    ema_slow: pd.Series,
    cloud_bull: pd.Series,
    min_bars_below: int = 5,
    confirm_closes: int = 1,
    warmup:         int = 60,
) -> pd.Series:
    """
    Reclaim: price was below the slow EMA for min_bars_below bars,
    then closes back above the fast EMA (cloud turning bullish).

    This captures the "recovery/reclaim" trade after a pullback into
    or below the cloud.
    """
    below_slow = (close < ema_slow).astype(float)

    # Rolling sum: how many of last min_bars_below bars were below the slow EMA?
    consec_below = below_slow.rolling(min_bars_below, min_periods=min_bars_below).sum()

    # Shift by confirm_closes: signal after the reclaim candle(s) confirm
    was_deeply_below = (consec_below.shift(confirm_closes) >= min_bars_below).fillna(False)

    now_above_fast = close > ema_fast

    sig = was_deeply_below & now_above_fast & cloud_bull
    sig = sig.fillna(False).copy()
    sig.iloc[:warmup] = False
    return sig


# ── Benchmarks ───────────────────────────────────────────────────────────────

def base_high_breakout(
    close:        pd.Series,
    cloud_bull:   pd.Series,
    ema_fast:     pd.Series,
    n:            int = 50,
    fresh_window: int = 10,
    warmup:       int = 60,
) -> pd.Series:
    """
    Donchian N-bar high + cloud condition + freshness filter.

    Simpler than level breakout (no touch counting / clustering), but adds:
    - cloud_bull: same EMA-cloud condition as main entries
    - freshness: price must have been at/below the rolling high recently

    Use to benchmark whether multi-touch level complexity adds value vs
    a clean Donchian + cloud filter.
    """
    rolling_high = close.rolling(n, min_periods=n).max().shift(1)
    at_or_below = close <= rolling_high * 1.002
    was_below_recently = (
        at_or_below.rolling(fresh_window, min_periods=1).max().shift(1).fillna(False)
    )
    sig = (
        (close > rolling_high)
        & cloud_bull
        & (close > ema_fast)
        & was_below_recently.astype(bool)
    )
    sig = sig.fillna(False).copy()
    sig.iloc[:max(warmup, n + 5)] = False
    return sig


def donchian_breakout(
    close:  pd.Series,
    n:      int = 20,
    warmup: int = None,
) -> pd.Series:
    """
    Benchmark: Donchian N-day high breakout.
    Fires when close[t] > max(close[t-n : t]).
    No EMA cloud condition; pure price momentum.
    """
    wm = (n + 5) if warmup is None else warmup
    rolling_high = close.rolling(n, min_periods=n).max().shift(1)
    sig = (close > rolling_high).fillna(False).copy()
    sig.iloc[:wm] = False
    return sig


def cloud_only_entry(
    close:      pd.Series,
    ema_fast:   pd.Series,
    cloud_bull: pd.Series,
    min_bars_bear: int = 3,    # cloud must have been bearish for K bars before
    warmup:        int = 60,
) -> pd.Series:
    """
    Benchmark: enter when cloud turns bullish and price is above fast EMA.
    Requires K bars of prior bearish cloud to avoid chasing established trends.
    """
    cloud_was_bear = (~cloud_bull).rolling(min_bars_bear, min_periods=1).max().shift(1).fillna(False)
    sig = (close > ema_fast) & cloud_bull & cloud_was_bear.astype(bool)
    sig = sig.fillna(False).copy()
    sig.iloc[:warmup] = False
    return sig
