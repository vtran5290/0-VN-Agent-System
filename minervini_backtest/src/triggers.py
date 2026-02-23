# minervini_backtest/src/triggers.py — Pivot breakout, volume thrust, close strength; retest (2-step)
from __future__ import annotations
import numpy as np
import pandas as pd


def _strong_close_mask(out: pd.DataFrame) -> pd.Series:
    """Close in top 75% of range (close >= high - 0.25 * range)."""
    rng = out["high"] - out["low"]
    rng = rng.replace(0, np.nan)
    return (out["close"] >= out["high"] - 0.25 * rng).fillna(False)


def _vol_thrust_mask(out: pd.DataFrame, vol_mult: float) -> pd.Series:
    return (out["volume"] > (vol_mult * out["vol_sma20"])).fillna(False)


def _vol_dryup_mask(out: pd.DataFrame) -> pd.Series:
    """Dry-up proxy for quiet breakout (VCP). Volume <= SMA20."""
    return (out["volume"] <= out["vol_sma20"]).fillna(False)


def highest_high(df: pd.DataFrame, lookback: int, end_idx: int) -> float:
    """Highest high in [end_idx - lookback, end_idx] (inclusive of end_idx)."""
    start = max(0, end_idx - lookback)
    return df["high"].iloc[start : end_idx + 1].max()


def breakout(
    df: pd.DataFrame,
    lookback_base: int,
    vol_mult: float = 1.5,
    close_strength: bool = True,
    **kwargs,
) -> pd.Series:
    """
    Default (backward-compatible): Close > HH(past), Vol > vol_mult*Vol20, optional strong close.
    Optional kwargs: breakout_mode "close"|"high", vol_mode "thrust"|"off"|"either".
    """
    breakout_mode = (kwargs.get("breakout_mode") or "close").strip().lower()
    vol_mode = (kwargs.get("vol_mode") or "thrust").strip().lower()

    out = df.copy()
    if "vol_sma20" not in out.columns:
        from indicators import add_vol_sma
        out = add_vol_sma(out, [20])
    hh = out["high"].rolling(lookback_base, min_periods=lookback_base).max().shift(1)

    if breakout_mode == "high":
        break_mask = (out["high"] > hh).fillna(False)
    else:
        break_mask = (out["close"] > hh).fillna(False)

    if vol_mode == "off":
        vol_mask = pd.Series(True, index=out.index)
    elif vol_mode == "either":
        vol_mask = _vol_thrust_mask(out, vol_mult) | _vol_dryup_mask(out)
    else:
        vol_mask = _vol_thrust_mask(out, vol_mult)

    sig = break_mask & vol_mask
    if close_strength:
        sig = sig & _strong_close_mask(out)
    return sig


def pivot_level(df: pd.DataFrame, lookback: int, end_idx: int) -> float:
    """Pivot = highest high in base window ending at end_idx (exclusive of end_idx bar)."""
    start = max(0, end_idx - lookback)
    return df["high"].iloc[start:end_idx].max()


def retest_ok(
    df: pd.DataFrame,
    entry_bar: int,
    pivot: float,
    retest_max_bars: int = 5,
    max_undercut_pct: float = 0.02,
) -> bool:
    """
    After a breakout at entry_bar, check if retest succeeded within retest_max_bars:
    - low of retest bars doesn't undercut pivot by more than max_undercut_pct
    - close comes back above pivot
    Used for M4 (2-step entry).
    """
    for j in range(1, min(retest_max_bars + 1, len(df) - entry_bar)):
        i = entry_bar + j
        row = df.iloc[i]
        low_ok = row["low"] >= pivot * (1 - max_undercut_pct)
        close_above = row["close"] > pivot
        if close_above and low_ok:
            return True
        if row["low"] < pivot * (1 - max_undercut_pct):
            break
    return False


def pivot_tight_level(df: pd.DataFrame, window: int, end_idx: int) -> float:
    """Pivot = max(high) of tight range window [end_idx - window, end_idx) — excludes current bar."""
    start = max(0, end_idx - window)
    return df["high"].iloc[start:end_idx].max()


def pivot_low_level(df: pd.DataFrame, window: int, end_idx: int) -> float:
    """Pivot low = min(low) of window [end_idx - window, end_idx) — excludes current bar. For U&R stop/chase."""
    start = max(0, end_idx - window)
    return df["low"].iloc[start:end_idx].min()


def undercut_rally(
    df: pd.DataFrame,
    lookback_low: int = 10,
    undercut_pct: float = 0.0,
    close_strength: bool = True,
    **kwargs,
) -> pd.Series:
    """
    Undercut & Rally: low undercuts prior pivot low, then close reclaims above pivot low (washout → reversal).
    pivot_low = min(low) of last lookback_low bars (excl. current). Optional undercut_pct: allow undercut
    up to that fraction below pivot (e.g. 0.005 = 0.5%).
    """
    out = df.copy()
    pivot_low = out["low"].rolling(lookback_low, min_periods=lookback_low).min().shift(1)
    if undercut_pct <= 0:
        undercut = (out["low"] < pivot_low).fillna(False)
    else:
        undercut = (out["low"] <= pivot_low * (1 - undercut_pct)).fillna(False)
    rally = (out["close"] > pivot_low).fillna(False)
    sig = undercut & rally
    if close_strength:
        sig = sig & _strong_close_mask(out)
    return sig


def breakout_tight(
    df: pd.DataFrame,
    window: int,
    vol_mult: float = 1.5,
    close_strength: bool = True,
    **kwargs,
) -> pd.Series:
    """Breakout vs pivot = high of last `window` bars (excl. current). Optional: breakout_mode, vol_mode."""
    breakout_mode = (kwargs.get("breakout_mode") or "close").strip().lower()
    vol_mode = (kwargs.get("vol_mode") or "thrust").strip().lower()

    out = df.copy()
    if "vol_sma20" not in out.columns:
        from indicators import add_vol_sma
        out = add_vol_sma(out, [20])
    pivot = out["high"].rolling(window, min_periods=window).max().shift(1)

    if breakout_mode == "high":
        break_mask = (out["high"] > pivot).fillna(False)
    else:
        break_mask = (out["close"] > pivot).fillna(False)

    if vol_mode == "off":
        vol_mask = pd.Series(True, index=out.index)
    elif vol_mode == "either":
        vol_mask = _vol_thrust_mask(out, vol_mult) | _vol_dryup_mask(out)
    else:
        vol_mask = _vol_thrust_mask(out, vol_mult)

    sig = break_mask & vol_mask
    if close_strength:
        sig = sig & _strong_close_mask(out)
    return sig


def add_breakout(
    df: pd.DataFrame,
    lookback_base: int,
    vol_mult: float = 1.5,
    close_strength: bool = True,
    **kwargs,
) -> pd.DataFrame:
    """Add column 'trigger_breakout' (bool)."""
    out = df.copy()
    out["trigger_breakout"] = breakout(out, lookback_base, vol_mult, close_strength, **kwargs)
    return out
