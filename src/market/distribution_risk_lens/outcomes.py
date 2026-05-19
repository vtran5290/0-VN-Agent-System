"""Forward outcomes from date t (future data only in outcome columns)."""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = (5, 10, 25, 75, 100)
CORR_PCTS = (3, 5, 10, 15)


def attach_forward_outcomes(feat: pd.DataFrame) -> pd.DataFrame:
    out = feat.copy()
    c = out["close"].astype(float)
    n = len(out)
    for h in HORIZONS:
        fwd = c.shift(-h) / c - 1.0
        out[f"fwd_ret_{h}d"] = fwd
        out[f"max_dd_{h}d"] = _forward_max_dd(c, h)
        for pct in CORR_PCTS:
            col = f"hit_correction_{pct}pct_next_{h}d"
            if (pct == 3 and h in (5, 10, 25, 75, 100)) or (pct == 5 and h in (5, 10, 25, 75, 100)) or (
                pct == 10 and h in (25, 75, 100)
            ) or (pct == 15 and h in (75, 100)):
                out[col] = _hit_correction(c, h, pct / 100.0)
    for h in (10, 25):
        out[f"close_below_ema20_next_{h}d"] = _future_below_ema(c, 20, h)
    out["close_below_ema50_next_25d"] = _future_below_ema(c, 50, 25)
    out["close_below_ema50_next_75d"] = _future_below_ema(c, 50, 75)
    out["close_below_ema100_next_75d"] = _future_below_ema(c, 100, 75)
    out["close_below_ema100_next_100d"] = _future_below_ema(c, 100, 100)
    out["distribution_cluster_next_25d"] = _future_dist_cluster(out["dist_day_flag"], 25, 4)
    out["drawdown_5pct_before_gain_5pct_25d"] = _dd_before_gain(c, 25, 0.05, 0.05)
    out["drawdown_10pct_before_gain_10pct_75d"] = _dd_before_gain(c, 75, 0.10, 0.10)
    return out


def _forward_max_dd(close: pd.Series, horizon: int) -> pd.Series:
    vals = []
    arr = close.values.astype(float)
    for i in range(len(arr)):
        if i + horizon >= len(arr):
            vals.append(np.nan)
            continue
        window = arr[i : i + horizon + 1]
        peak = window[0]
        mdd = 0.0
        for px in window[1:]:
            peak = max(peak, px)
            mdd = min(mdd, px / peak - 1.0)
        vals.append(mdd)
    return pd.Series(vals, index=close.index)


def _hit_correction(close: pd.Series, horizon: int, thresh: float) -> pd.Series:
    out = []
    arr = close.values.astype(float)
    for i in range(len(arr)):
        if i + horizon >= len(arr):
            out.append(np.nan)
            continue
        path = arr[i : i + horizon + 1]
        trough = np.nanmin(path[1:]) if len(path) > 1 else path[0]
        out.append(float(trough <= path[0] * (1.0 - thresh)))
    return pd.Series(out, index=close.index)


def _future_below_ema(close: pd.Series, span: int, horizon: int) -> pd.Series:
    ema = close.ewm(span=span, adjust=False, min_periods=span).mean()
    below = (close < ema).astype(float)
    return below.shift(-horizon).rolling(horizon, min_periods=1).max()


def _future_dist_cluster(flags: pd.Series, horizon: int, threshold: int) -> pd.Series:
    future = flags.shift(-1).rolling(horizon, min_periods=horizon).sum().shift(-(horizon - 1))
    return (future >= threshold).astype(float)


def _dd_before_gain(close: pd.Series, horizon: int, dd: float, gain: float) -> pd.Series:
    out = []
    arr = close.values.astype(float)
    for i in range(len(arr)):
        if i + horizon >= len(arr):
            out.append(np.nan)
            continue
        path = arr[i : i + horizon + 1]
        hit_dd = np.nanmin(path) <= path[0] * (1.0 - dd)
        hit_gain = np.nanmax(path) >= path[0] * (1.0 + gain)
        out.append(float(hit_dd and not hit_gain))
    return pd.Series(out, index=close.index)
