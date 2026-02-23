# minervini_backtest/src/risk.py — Stop (pct / ATR), position sizing by R, portfolio heat (Champion)
from __future__ import annotations
import numpy as np
import pandas as pd


def stop_price(
    entry_price: float,
    stop_pct: float | None = None,
    atr: float | None = None,
    atr_k: float | None = None,
) -> float:
    """
    Stop = min( entry*(1 - stop_pct), entry - k*ATR ) when both given.
    If only stop_pct: entry * (1 - stop_pct).
    If only atr/atr_k: entry - atr_k * atr.
    """
    candidates = []
    if stop_pct is not None and stop_pct > 0:
        candidates.append(entry_price * (1 - stop_pct))
    if atr is not None and atr_k is not None and atr_k > 0:
        candidates.append(entry_price - atr_k * atr)
    if not candidates:
        return entry_price * 0.95  # fallback 5%
    return max(min(candidates), 0.0)


def position_size_r(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
) -> float:
    """
    Champion: position_size (shares) = (equity * risk_pct) / (entry - stop).
    Returns number of shares.
    """
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0.0
    return (equity * risk_pct) / risk_per_share


def shares_from_r(equity: float, risk_pct: float, entry: float, stop: float) -> float:
    """Shares = (equity * risk_pct) / (entry - stop). Alias for position_size_r."""
    return position_size_r(equity, risk_pct, entry, stop)
