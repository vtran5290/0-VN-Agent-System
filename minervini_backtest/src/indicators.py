# minervini_backtest/src/indicators.py — OHLCV-based indicators for TT, VCP, breakout, risk
from __future__ import annotations
import numpy as np
import pandas as pd


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Require date, open, high, low, close, volume (lowercase)."""
    required = ["date", "open", "high", "low", "close", "volume"]
    for c in required:
        if c not in df.columns and c.capitalize() in df.columns:
            df = df.rename(columns={c.capitalize(): c})
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")
    return df


# --- MAs ---
def ma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def add_mas(df: pd.DataFrame, windows: list[int] = (20, 50, 150, 200)) -> pd.DataFrame:
    out = df.copy()
    c = out["close"]
    for w in windows:
        out[f"ma{w}"] = ma(c, w)
    return out


# --- ATR ---
def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def add_atr(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = atr(out, n)
    return out


# --- ATR% (for VCP contraction stack) ---
def atr_pct(df: pd.DataFrame, n: int) -> pd.Series:
    a = atr(df, n)
    return a / df["close"]


def add_atr_pct(df: pd.DataFrame, windows: list[int] = (5, 10, 20)) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"atr_pct_{w}"] = atr_pct(out, w)
    return out


# --- 52-week high/low (≈252 bars) ---
def high_low_252(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    c = df["close"]
    high_252 = c.rolling(252, min_periods=200).max()
    low_252 = c.rolling(252, min_periods=200).min()
    return high_252, low_252


# --- Volume SMAs ---
def vol_sma(df: pd.DataFrame, n: int) -> pd.Series:
    return df["volume"].rolling(n, min_periods=n).mean()


def add_vol_sma(df: pd.DataFrame, windows: list[int] = (5, 20)) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"vol_sma{w}"] = vol_sma(out, w)
    return out


# --- True Range (for climax proxy) ---
def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    return pd.concat([
        high - low,
        (high - prev).abs(),
        (low - prev).abs(),
    ], axis=1).max(axis=1)


def add_all_indicators(
    df: pd.DataFrame,
    ma_windows: list[int] = (20, 50, 150, 200),
    atr_n: int = 14,
    atr_pct_windows: list[int] = (5, 10, 20),
    vol_sma_windows: list[int] = (5, 20),
) -> pd.DataFrame:
    """Add MA, ATR, ATR%, Vol SMA, 52w high/low. In-place style; returns df."""
    df = ensure_columns(df)
    df = add_mas(df, ma_windows)
    df = add_atr(df, atr_n)
    df = add_atr_pct(df, atr_pct_windows)
    df = add_vol_sma(df, vol_sma_windows)
    h252, l252 = high_low_252(df)
    df["high_252"] = h252
    df["low_252"] = l252
    df["true_range"] = true_range(df)
    return df
