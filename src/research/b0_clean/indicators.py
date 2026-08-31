"""Frozen B0 indicators (Wilder RSI14, SMA20, pullback3)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI: EWM alpha=1/period, adjust=False, min_periods=period."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rsi = pd.Series(np.nan, index=close.index, dtype=float)
    both = avg_gain.notna() & avg_loss.notna()
    zero_loss = both & (avg_loss == 0) & (avg_gain > 0)
    zero_both = both & (avg_loss == 0) & (avg_gain == 0)
    normal = both & (avg_loss > 0)
    rsi[zero_loss] = 100.0
    rsi[zero_both] = 50.0
    rs = avg_gain[normal] / avg_loss[normal]
    rsi[normal] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def add_symbol_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol OHLCV frame sorted by date → indicator columns."""
    out = df.sort_values("date").copy()
    out["sma20"] = sma(out["close"], 20)
    out["vol_sma20"] = sma(out["volume"], 20)
    out["pullback3"] = out["close"] / out["close"].shift(3) - 1.0
    out["rsi14"] = wilder_rsi(out["close"], 14)
    out["prev_close"] = out["close"].shift(1)
    return out


def add_vnindex_indicators(vni: pd.DataFrame) -> pd.DataFrame:
    out = vni.sort_values("date").copy()
    out["vni_sma20"] = sma(out["close"], 20)
    out = out.rename(columns={"close": "vnindex_close"})
    return out[["date", "vnindex_close", "vni_sma20"]]
