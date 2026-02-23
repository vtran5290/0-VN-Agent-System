# pp_backtest/signals_livermore.py — Livermore Pivotal Point + LOLR (rule-based, Swing/Position)
# Institutional-grade: vol filter LOLR; prior_trend for reversal; pivot failure within K bars (sweep 2/3/5).
from __future__ import annotations
import numpy as np
import pandas as pd

try:
    from pp_backtest.signals import sma, atr
except ImportError:
    from signals import sma, atr


def market_filter_lolr(
    index_df: pd.DataFrame,
    ma_period: int = 50,
    slope_bars: int = 5,
    vol_atr_pct_max: float | None = 0.05,
    atr_period: int = 14,
) -> pd.Series:
    """
    Line of Least Resistance: risk_on when index close > MA(50), MA(50) sloping up.
    Volatility filter (VN): khi ATR(index)/close quá cao thường là distribution phase.
    risk_on &= (ATR/close < vol_atr_pct_max). Nếu vol_atr_pct_max=None thì tắt vol filter.
    """
    c = index_df["close"].astype(float)
    ma = sma(c, ma_period)
    slope = (ma - ma.shift(slope_bars)) / ma.shift(slope_bars).replace(0, np.nan)
    risk_on = (c > ma) & (slope > 0)
    if vol_atr_pct_max is not None:
        a = atr(index_df, atr_period)
        vol_ratio = a / c.replace(0, np.nan)
        risk_on = risk_on & (vol_ratio < vol_atr_pct_max)
    return risk_on.fillna(False)


def entry_livermore_reversal_pivot(
    df: pd.DataFrame,
    N: int = 10,
    volume_confirm: bool = True,
    vol_ma_days: int = 20,
    prior_trend_ma: int = 50,
) -> pd.Series:
    """
    Entry L1 — Reversal Pivotal Point: sau down move, decisive thrust lên.
    prior_trend: trước breakout phải có close < MA(prior_trend_ma) hoặc 3 lower lows → tránh continuation disguised as reversal.
    Implemented: close.shift(1) < MA50.shift(1) AND close > highest(high, N).shift(1) + volume.
    """
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    ma = sma(c, prior_trend_ma)
    prior_trend = (c.shift(1) < ma.shift(1)).fillna(False)
    prior_high_N = h.shift(1).rolling(N, min_periods=N).max().shift(1)
    breakout = (c > prior_high_N) & prior_trend
    if volume_confirm and "volume" in df.columns:
        v = df["volume"].astype(float)
        vol_ok = v >= sma(v, vol_ma_days)
        breakout = breakout & vol_ok
    return breakout.fillna(False)


def entry_livermore_continuation_pivot(
    df: pd.DataFrame,
    L: int = 20,
    vol_k: float = 1.2,
    above_ma: int = 20,
) -> pd.Series:
    """
    Entry L2 — Continuation Pivotal Point: breakout from consolidation in uptrend.
    close > highest(high, L) + volume confirm; close > MA(above_ma).
    """
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    vol = df["volume"].astype(float)
    highest_L = h.rolling(L, min_periods=L).max().shift(1)
    ma = sma(c, above_ma)
    vol_ok = (vol >= sma(vol, 20) * vol_k).fillna(False)
    breakout = (c > highest_L) & (c > ma) & vol_ok
    return breakout.fillna(False)


def exit_livermore_pivot_failure(
    df: pd.DataFrame,
    trigger_col: str = "trigger_level",
    K: int = 3,
) -> pd.Series:
    """
    Exit Lx1 — Pivot failure: close < trigger_level (breakout level lost).
    K sweep: 2/3/5 (VN hay fake breakout). Stateful "exit if fails within K bars" xử lý trong backtest loop.
    """
    c = df["close"].astype(float)
    low = df["low"].astype(float)
    if trigger_col in df.columns:
        trigger = df[trigger_col].astype(float)
        return (c < trigger).fillna(False)
    recent_low = low.rolling(K, min_periods=K).min().shift(1)
    return (c < recent_low).fillna(False)


def exit_livermore_ma(
    df: pd.DataFrame,
    ma_period: int = 20,
) -> pd.Series:
    """Exit Lx2 — MA sell: close < MA(ma_period). Use 20 or 50 (tier like Gil)."""
    c = df["close"].astype(float)
    ma = sma(c, ma_period)
    return (c < ma).fillna(False)


def exit_livermore_ma20(df: pd.DataFrame) -> pd.Series:
    return exit_livermore_ma(df, ma_period=20)


def exit_livermore_ma50(df: pd.DataFrame) -> pd.Series:
    return exit_livermore_ma(df, ma_period=50)
