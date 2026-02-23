# minervini_backtest/src/filters.py — Trend Template (TT) filters: TT_Strict, TT_Lite
from __future__ import annotations
import numpy as np
import pandas as pd


def ma200_slope(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """MA200 today > MA200 lookback bars ago."""
    if "ma200" not in df.columns:
        raise ValueError("Need ma200; run add_mas first.")
    ma200 = df["ma200"]
    ma200_ago = ma200.shift(lookback)
    return (ma200 > ma200_ago).fillna(False)


def tt_strict(df: pd.DataFrame, ma200_slope_bars: int = 20) -> pd.Series:
    """
    Minervini classic:
    - Close > MA50
    - MA50 > MA150 > MA200
    - MA200 sloping up (MA200 today > MA200 20 bars ago)
    - Close >= 1.30 * 52wLow
    - Close >= 0.75 * 52wHigh
    """
    c = df["close"]
    ok = (
        (c > df["ma50"])
        & (df["ma50"] > df["ma150"])
        & (df["ma150"] > df["ma200"])
        & ma200_slope(df, ma200_slope_bars)
        & (c >= 1.30 * df["low_252"])
        & (c >= 0.75 * df["high_252"])
    )
    return ok.fillna(False)


def tt_lite(df: pd.DataFrame, ma200_slope_bars: int = 20) -> pd.Series:
    """
    VN-friendly (more names pass):
    - Close > MA50
    - MA50 > MA200
    - MA200 sloping up
    """
    ok = (
        (df["close"] > df["ma50"])
        & (df["ma50"] > df["ma200"])
        & ma200_slope(df, ma200_slope_bars)
    )
    return ok.fillna(False)


def add_tt(df: pd.DataFrame, mode: str = "lite", ma200_slope_bars: int = 20) -> pd.DataFrame:
    """Add column tt_ok (bool). mode in ('strict', 'lite')."""
    out = df.copy()
    if mode.strip().lower() == "strict":
        out["tt_ok"] = tt_strict(out, ma200_slope_bars)
    else:
        out["tt_ok"] = tt_lite(out, ma200_slope_bars)
    return out
