from __future__ import annotations

import pandas as pd

from .data_loader import CLOSE_COL, VALUE_COL


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA50/150/200 based on close."""
    out = df.copy()
    out["sma50"] = out[CLOSE_COL].rolling(window=50, min_periods=25).mean()
    out["sma150"] = out[CLOSE_COL].rolling(window=150, min_periods=75).mean()
    out["sma200"] = out[CLOSE_COL].rolling(window=200, min_periods=100).mean()
    return out


def add_liquidity_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Add short/medium-term traded value statistics."""
    out = df.copy()
    out["avg_value_20"] = out[VALUE_COL].rolling(window=20, min_periods=10).mean()
    out["avg_value_50"] = out[VALUE_COL].rolling(window=50, min_periods=25).mean()
    out["median_value_20"] = out[VALUE_COL].rolling(window=20, min_periods=10).median()
    return out


def add_52w_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Add 52-week high/low based on close."""
    out = df.copy()
    window = 252
    out["high_252"] = out[CLOSE_COL].rolling(window=window, min_periods=126).max()
    out["low_252"] = out[CLOSE_COL].rolling(window=window, min_periods=126).min()
    return out

