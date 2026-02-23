# minervini_backtest/src/exits.py — Exit modules: fail-fast, hard stop, time stop, trend break, climax proxy
from __future__ import annotations
import numpy as np
import pandas as pd


def exit_fail_fast(
    bars_held: int,
    close: float,
    entry_price: float,
    fail_fast_days: int,
) -> bool:
    """If bars_held <= fail_fast_days and close < entry -> exit."""
    if fail_fast_days <= 0:
        return False
    return bars_held <= fail_fast_days and close < entry_price


def exit_hard_stop(close: float, low: float, stop_price: float) -> bool:
    """True if stop was hit (low <= stop_price)."""
    return low <= stop_price


def exit_time_stop(
    bars_held: int,
    time_stop_days: int,
    r_multiple: float,
    min_r: float,
) -> bool:
    """If bars_held >= time_stop_days and haven't reached +min_r R -> exit. Caller passes current R."""
    if time_stop_days <= 0:
        return False
    return bars_held >= time_stop_days and r_multiple < min_r


def exit_trend_break(close: float, ma: float, use_ma50: bool = True) -> bool:
    """Close < MA50 (or MA20)."""
    return close < ma


def exit_climax_proxy(
    true_range: float,
    atr14: float,
    atr_mult: float = 2.0,
    close_off_high_pct: float = 0.25,
    high: float = 0.0,
    low: float = 0.0,
    close: float = 0.0,
    volume: float = 0.0,
    vol_sma20: float = 0.0,
    vol_spike_mult: float = 1.5,
) -> bool:
    """
    TrueRange > atr_mult * ATR(14) and close in lower part of range (off high) + volume spike.
    Simplified: TR > 2*ATR and close <= high - close_off_high_pct*(high-low) and vol > vol_spike_mult*vol_sma20.
    """
    if atr14 <= 0:
        return False
    tr_ok = true_range > atr_mult * atr14
    range_ = high - low
    if range_ <= 0:
        close_ok = False
    else:
        close_ok = close <= high - close_off_high_pct * range_
    vol_ok = vol_sma20 <= 0 or volume > vol_spike_mult * vol_sma20
    return bool(tr_ok and close_ok and vol_ok)


def exit_trailing_ma(close: float, ma: float) -> bool:
    """Close < MA (e.g. MA20 for trailing)."""
    return close < ma
