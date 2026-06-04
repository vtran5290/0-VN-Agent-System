"""Trend Speed Analyzer (Zeiierman) — Pine-to-Python port for research backtests.

All features at bar t use OHLCV through close[t] only (causal).
Entry fills remain open[t+1] in the cloud backtest engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_PARAMS = {
    "max_length": 50,
    "accel_multiplier": 5.0,
    "collen": 100,
    "lookback_period": 100,
    "norm_speed_neutral": 0.5,
}


def _wma(s: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    weights = np.arange(1, length + 1, dtype=float)

    def _apply(arr: np.ndarray) -> float:
        if len(arr) < length or np.isnan(arr).any():
            return np.nan
        return float(np.dot(arr, weights) / weights.sum())

    return s.rolling(length, min_periods=length).apply(_apply, raw=True)


def _hma(s: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    half = max(1, length // 2)
    sqrt_n = max(1, int(round(length**0.5)))
    return _wma(2 * _wma(s, half) - _wma(s, length), sqrt_n)


def _rma(s: pd.Series, length: int) -> pd.Series:
    return s.ewm(alpha=1.0 / max(1, length), adjust=False).mean()


def _rolling_quintile_expanding(s: pd.Series) -> pd.Series:
    """Expanding historical quintile 1–5; NaN until 5 valid observations."""
    out = np.full(len(s), np.nan)
    vals = s.to_numpy(dtype=float)
    for i in range(len(vals)):
        hist = vals[: i + 1]
        hist = hist[~np.isnan(hist)]
        if len(hist) < 5:
            continue
        x = vals[i]
        if np.isnan(x):
            continue
        pct = (hist <= x).mean()
        out[i] = min(5, max(1, int(np.ceil(pct * 5))))
    return pd.Series(out, index=s.index)


def compute_tsa_features(
    df: pd.DataFrame,
    *,
    max_length: int = DEFAULT_PARAMS["max_length"],
    accel_multiplier: float = DEFAULT_PARAMS["accel_multiplier"],
    collen: int = DEFAULT_PARAMS["collen"],
    norm_speed_neutral: float = DEFAULT_PARAMS["norm_speed_neutral"],
) -> pd.DataFrame:
    """
    Compute Trend Speed Analyzer features aligned to df.index.

    Required columns: open, high, low, close.
    """
    close = df["close"].astype(float)
    open_ = df["open"].astype(float)
    n = len(close)

    max_abs_counts_diff = close.abs().rolling(200, min_periods=1).max()
    denom = 2.0 * max_abs_counts_diff.replace(0, np.nan)
    counts_diff_norm = (close + max_abs_counts_diff) / denom

    dyn_length = 5.0 + counts_diff_norm * (max_length - 5.0)

    delta = close.diff().abs()
    max_delta = delta.rolling(200, min_periods=1).max()
    accel_factor = delta / max_delta.replace(0, np.nan)

    alpha_base = 2.0 / (dyn_length + 1.0)
    alpha = np.minimum(1.0, alpha_base * (1.0 + accel_factor * accel_multiplier))

    dyn_ema = np.empty(n, dtype=float)
    dyn_ema[0] = close.iloc[0]
    c_arr = close.to_numpy()
    a_arr = alpha.to_numpy()
    for i in range(1, n):
        ai = a_arr[i]
        if np.isnan(ai):
            dyn_ema[i] = dyn_ema[i - 1]
        else:
            dyn_ema[i] = ai * c_arr[i] + (1.0 - ai) * dyn_ema[i - 1]

    dyn_ema_s = pd.Series(dyn_ema, index=df.index)

    c_rma = _rma(close, 10)
    o_rma = _rma(open_, 10)
    co = c_rma - o_rma

    prev_close = close.shift(1)
    cross_up = (close > dyn_ema_s) & (prev_close <= dyn_ema_s.shift(1))
    cross_dn = (close < dyn_ema_s) & (prev_close >= dyn_ema_s.shift(1))

    # Pine: on cross bar `speed := c-o` then unconditionally `speed := speed + c-o`
    # => cross bar effective increment is 2*(c-o); non-cross adds once.
    co_arr = co.to_numpy()
    cross_arr = (cross_up | cross_dn).to_numpy()
    speed = np.zeros(n, dtype=float)
    for i in range(1, n):
        ci = co_arr[i] if not np.isnan(co_arr[i]) else 0.0
        if cross_arr[i]:
            speed[i] = 2.0 * ci
        else:
            speed[i] = speed[i - 1] + ci

    speed_s = pd.Series(speed, index=df.index)
    trendspeed = _hma(speed_s, 5)

    min_speed = speed_s.rolling(collen, min_periods=1).min()
    max_speed = speed_s.rolling(collen, min_periods=1).max()
    span = (max_speed - min_speed).replace(0, np.nan)
    norm_speed = (speed_s - min_speed) / span
    norm_speed = norm_speed.where(span.notna(), norm_speed_neutral)

    bull_turn = (trendspeed > 0) & (trendspeed.shift(1) <= 0)
    bear_turn = (trendspeed < 0) & (trendspeed.shift(1) >= 0)

    bull_turn_5 = bull_turn.rolling(5, min_periods=1).max().astype(bool)
    bear_turn_5 = bear_turn.rolling(5, min_periods=1).max().astype(bool)

    deterioration = (trendspeed < trendspeed.shift(3)) & (trendspeed < 0)

    out = pd.DataFrame(
        {
            "tsa_dyn_ema": dyn_ema_s,
            "tsa_speed": speed_s,
            "tsa_trendspeed": trendspeed,
            "tsa_norm_speed": norm_speed,
            "tsa_dyn_trend_bull": close > dyn_ema_s,
            "tsa_speed_positive": speed_s > 0,
            "tsa_trendspeed_positive": trendspeed > 0,
            "tsa_speed_slope_3": speed_s - speed_s.shift(3),
            "tsa_trendspeed_slope_3": trendspeed - trendspeed.shift(3),
            "tsa_norm_speed_q": _rolling_quintile_expanding(norm_speed),
            "tsa_bull_turn": bull_turn,
            "tsa_bear_turn": bear_turn,
            "tsa_bull_turn_5": bull_turn_5,
            "tsa_bear_turn_5": bear_turn_5,
            "tsa_speed_deterioration": deterioration,
        },
        index=df.index,
    )
    return out


def compute_speed_series_pine_equiv(
    close: pd.Series,
    open_: pd.Series,
    dyn_ema: pd.Series,
) -> pd.Series:
    """Expose speed loop for unit tests (Pine double-add on cross bars)."""
    c_rma = _rma(close, 10)
    o_rma = _rma(open_, 10)
    co = (c_rma - o_rma).to_numpy()
    prev_close = close.shift(1)
    cross = (
        ((close > dyn_ema) & (prev_close <= dyn_ema.shift(1)))
        | ((close < dyn_ema) & (prev_close >= dyn_ema.shift(1)))
    ).to_numpy()
    n = len(close)
    speed = np.zeros(n, dtype=float)
    for i in range(1, n):
        ci = co[i] if not np.isnan(co[i]) else 0.0
        speed[i] = 2.0 * ci if cross[i] else speed[i - 1] + ci
    return pd.Series(speed, index=close.index)
