"""
EMA cloud + causal price level indicators.

All functions take pd.Series with a clean integer index (reset per symbol).
No lookahead: pivot detection uses a symmetric window then shifts forward by
pivot_window bars so the signal is "confirmed" with a lag.
"""

import numpy as np
import pandas as pd


# ── EMA cloud ────────────────────────────────────────────────────────────────

def ema_cloud(close: pd.Series, fast: int, slow: int) -> dict:
    """
    Returns dict of vectorized cloud indicators:
        ema_fast, ema_slow       -- raw EMAs
        cloud_bull               -- fast > slow (bullish cloud)
        cloud_spread             -- fast - slow (signed; positive = bullish)
        price_above_cloud        -- close > ema_fast when cloud_bull
        price_in_cloud           -- close between the two EMAs
        price_below_cloud        -- close < ema_slow when cloud_bear
    """
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    bull = ef > es
    return {
        "ema_fast":          ef,
        "ema_slow":          es,
        "cloud_bull":        bull,
        "cloud_spread":      ef - es,
        "price_above_cloud": close > ef,
        "price_in_cloud":    ((close >= es) & (close <= ef)) | ((close >= ef) & (close <= es)),
        "price_below_cloud": close < es,
    }


# ── Causal pivot detection ───────────────────────────────────────────────────

def pivot_highs(high: pd.Series, pivot_window: int = 5) -> pd.Series:
    """
    Causal pivot-high prices.

    A bar i is a pivot high if high[i] is the maximum of high over
    [i - pw, i + pw].  This requires knowing pivot_window future bars,
    so the signal is available only at bar i + pivot_window.

    Returns a Series where non-NaN values are pivot-high prices at the bar
    they become observable.
    """
    pw = pivot_window
    roll_max = high.rolling(2 * pw + 1, center=True, min_periods=pw + 1).max()
    is_pivot = high >= roll_max * 0.9999       # float-safe equality
    ph = high.where(is_pivot)                  # NaN where not a pivot
    return ph.shift(pw)                        # make causal: available at i+pw


def pivot_lows(low: pd.Series, pivot_window: int = 5) -> pd.Series:
    """Causal pivot-low prices (mirror of pivot_highs)."""
    pw = pivot_window
    roll_min = low.rolling(2 * pw + 1, center=True, min_periods=pw + 1).min()
    is_pivot = low <= roll_min * 1.0001
    pl = low.where(is_pivot)
    return pl.shift(pw)


# ── Rolling resistance / support ─────────────────────────────────────────────

def rolling_resistance(
    ph: pd.Series,
    lookback: int = 120,
    cluster_pct: float = 0.03,
    min_touches: int = 2,
) -> tuple[pd.Series, pd.Series]:
    """
    For each bar, derive the strongest resistance zone from recent pivot highs.

    resistance  = rolling max of pivot highs in the last `lookback` bars
                  (i.e. the highest tested level)

    r_strength  = count of pivot highs in the window that fall within
                  cluster_pct of the rolling max
                  (proxy for "how many times was this zone tested?")

    Both series use trailing-only windows → fully causal.
    """
    ph_max = ph.rolling(lookback, min_periods=1).max()

    # A pivot is "near the max at its own bar" if it sits within cluster_pct below
    # the rolling max of [j-lookback, j].  This approximates cluster density.
    near_max_mask = (ph >= ph_max * (1.0 - cluster_pct)).fillna(False)
    r_strength = near_max_mask.rolling(lookback, min_periods=1).sum()

    return ph_max, r_strength


def rolling_support(
    pl: pd.Series,
    lookback: int = 120,
    cluster_pct: float = 0.03,
    min_touches: int = 2,
) -> tuple[pd.Series, pd.Series]:
    """
    Mirror of rolling_resistance, operating on pivot lows.

    support     = rolling min of pivot lows  (lowest tested floor)
    s_strength  = count of pivot lows within cluster_pct above the rolling min
    """
    pl_min = pl.rolling(lookback, min_periods=1).min()

    near_min_mask = (pl <= pl_min * (1.0 + cluster_pct)).fillna(False)
    s_strength = near_min_mask.rolling(lookback, min_periods=1).sum()

    return pl_min, s_strength


# ── ATR ──────────────────────────────────────────────────────────────────────

def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Wilder ATR using exponential smoothing (EWM)."""
    tr = pd.concat(
        [high - low,
         (high - close.shift(1)).abs(),
         (low  - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()
