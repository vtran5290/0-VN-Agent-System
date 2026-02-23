# pp_backtest/signals_weekly.py — Weekly PP, 3WT, weekly exit (Gil/Kacher book conditions)
from __future__ import annotations
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


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


def three_weeks_tight_signal(
    wdf: pd.DataFrame,
    max_range_pct: float = 0.03,
) -> pd.Series:
    """
    Three-weeks-tight (O'Neil): max(close last 3w) - min(close last 3w) < max_range_pct (e.g. 3%).
    True when range is tight; breakout entry is next week close > max(close last 3w). Caller can use
    this as filter or combine with breakout.
    """
    c = wdf["close"].astype(float)
    roll_max = c.rolling(3, min_periods=3).max().shift(1)
    roll_min = c.rolling(3, min_periods=3).min().shift(1)
    range_pct = (roll_max - roll_min) / roll_min.replace(0, np.nan)
    return (range_pct < max_range_pct).fillna(False)


def three_weeks_tight_breakout_signal(wdf: pd.DataFrame, max_range_pct: float = 0.03) -> pd.Series:
    """3WT breakout: previous 3 weeks were tight AND this week close > max(close last 3w)."""
    c = wdf["close"].astype(float)
    prev_3w_high = c.rolling(3, min_periods=3).max().shift(1)
    prev_3w_low = c.rolling(3, min_periods=3).min().shift(1)
    tight = (prev_3w_high - prev_3w_low) / prev_3w_low.replace(0, np.nan) < max_range_pct
    breakout = c > prev_3w_high
    return (tight & breakout).fillna(False)


def weekly_exit_ma10(wdf: pd.DataFrame) -> pd.Series:
    """Exit when close_week < MA10_week (weekly violation)."""
    c = wdf["close"].astype(float)
    ma10 = sma(c, 10)
    return (c < ma10).fillna(False)


def weekly_market_dd_series(wdf: pd.DataFrame, lb_weeks: int = 10, min_drop_pct: float = 0.002) -> pd.Series:
    """Distribution weeks: close down + volume up + %change <= -min_drop_pct. Rolling count last lb_weeks."""
    c = wdf["close"].astype(float)
    v = wdf["volume"].astype(float)
    prev_c = c.shift(1)
    pct_chg = (c - prev_c) / prev_c.replace(0, np.nan)
    is_dd = (c < prev_c) & (v > v.shift(1)) & (pct_chg <= -min_drop_pct)
    return is_dd.rolling(lb_weeks, min_periods=lb_weeks).sum().astype(float)


def weekly_exit_market_dd(wdf: pd.DataFrame, threshold: int = 3, lb_weeks: int = 10) -> pd.Series:
    """Exit when MARKET_DD (weekly) >= threshold in last lb_weeks."""
    dd_count = weekly_market_dd_series(wdf, lb_weeks=lb_weeks)
    return (dd_count >= threshold).fillna(False)
