# minervini_backtest/src/market_health.py — Market Health Composite v1 (Minervini-style, no circular dependency)
"""
Distribution (index behavior) + Breadth (% above MA50). No breakout failure rate (avoids circularity).
VN-adjusted: distribution day requires index down >= min_down_pct to avoid noise.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def compute_distribution(
    index_df: pd.DataFrame,
    lookback: int = 20,
    min_down_pct: float = 0.002,
) -> pd.Series:
    """
    Distribution days over rolling window. One day counts as distribution when:
    - close < prev_close
    - volume > prev_volume
    - (prev_close - close) / prev_close >= min_down_pct  (VN: avoid small pullback noise, e.g. 0.2–0.3%)
    Returns: Series with same index as index_df, value = count of distribution days in last lookback.
    """
    df = index_df.copy()
    if "date" in df.columns and df.index.dtype != "datetime64[ns]":
        df = df.set_index("date")
    prev_close = df["close"].shift(1)
    prev_vol = df["volume"].shift(1)
    down_pct = (prev_close - df["close"]) / prev_close.replace(0, np.nan)
    is_dist = (
        (df["close"] < prev_close)
        & (df["volume"] > prev_vol)
        & (down_pct >= min_down_pct)
    ).fillna(False).astype(int)
    out = is_dist.rolling(lookback, min_periods=1).sum()
    return out


def distribution_count(
    index_df: pd.DataFrame,
    lookback: int = 20,
    down_thresh: float = -0.003,
) -> pd.Series:
    """
    Distribution days in last lookback. down_thresh: e.g. -0.003 = index must be down >= 0.3%.
    Alias for compute_distribution with min_down_pct = -down_thresh.
    """
    min_down_pct = -float(down_thresh) if down_thresh <= 0 else 0.003
    return compute_distribution(index_df, lookback=lookback, min_down_pct=min_down_pct)


def compute_breadth(
    universe_dict: dict[str, pd.DataFrame],
    ma_window: int = 50,
) -> pd.Series:
    """
    For each date, % of stocks (in universe) with close > MA50.
    Only counts symbols that have data on that date. Returns Series index=date, value in [0, 1].
    """
    if not universe_dict:
        return pd.Series(dtype=float)
    all_dates = set()
    series_per_sym = {}
    for sym, df in universe_dict.items():
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        if len(d) < ma_window:
            continue
        d = d.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        ma = d["close"].rolling(ma_window, min_periods=ma_window).mean()
        above = (d["close"] > ma).astype(int)
        s = above.set_axis(d["date"])
        series_per_sym[sym] = s
        all_dates.update(d["date"].tolist())
    if not all_dates:
        return pd.Series(dtype=float)
    common = pd.Series(index=sorted(all_dates), dtype=float)
    for d in common.index:
        total = 0
        above = 0
        for s in series_per_sym.values():
            if d in s.index:
                total += 1
                if s.loc[d] == 1:
                    above += 1
        common.loc[d] = above / total if total else np.nan
    return common


def breadth_above_ma(
    universe_dict: dict[str, pd.DataFrame],
    ma: int = 50,
) -> pd.Series:
    """Alias: % of universe with close > MA(ma)."""
    return compute_breadth(universe_dict, ma_window=ma)


def new_high_pct(
    universe_dict: dict[str, pd.DataFrame],
    lookback: int = 20,
) -> pd.Series:
    """
    For each date, % of stocks (in universe) making a new lookback-day high.
    New high = close >= max(high of past lookback bars, excl. current). No ledger/circularity.
    Proxy for momentum persistence.
    """
    if not universe_dict:
        return pd.Series(dtype=float)
    series_list = []
    for sym, df in universe_dict.items():
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        if len(d) < lookback + 1:
            continue
        d = d.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        pivot = d["high"].rolling(lookback, min_periods=lookback).max().shift(1)
        nh = (d["close"] >= pivot).astype(float)
        nh.index = d["date"]
        nh.name = sym
        series_list.append(nh)
    if not series_list:
        return pd.Series(dtype=float)
    mat = pd.concat(series_list, axis=1)
    return mat.mean(axis=1, skipna=True)


def compute_breadth_above_ma(
    universe_dict: dict[str, pd.DataFrame],
    ma: int = 50,
) -> pd.Series:
    """Public helper: wrapper around breadth_above_ma for clarity in drivers."""
    return breadth_above_ma(universe_dict, ma=ma)


def compute_new_high_pct(
    universe_dict: dict[str, pd.DataFrame],
    lookback: int = 20,
) -> pd.Series:
    """Public helper: wrapper around new_high_pct (NH20% style)."""
    return new_high_pct(universe_dict, lookback=lookback)


def mhc_signal(
    dist20: pd.Series,
    breadth50: pd.Series,
    nh20: pd.Series,
) -> pd.Series:
    """
    Breadth-weighted ON/OFF/NEUTRAL. Thresholds initial; tune only after diagnostic confirms separation.
    OFF: breadth < 0.40 or nh20 < 0.03 or dist >= 5.
    ON:  breadth > 0.55 and nh20 > 0.08 and dist <= 3.
    Else NEUTRAL.
    """
    idx = dist20.index
    b50 = breadth50.reindex(idx).ffill()
    nh = nh20.reindex(idx).ffill()
    sig = pd.Series(index=idx, dtype="object")
    for t in idx:
        d = dist20.loc[t] if t in dist20.index else np.nan
        b = b50.loc[t] if t in b50.index else np.nan
        n = nh.loc[t] if t in nh.index else np.nan
        if (pd.notna(b) and b < 0.40) or (pd.notna(n) and n < 0.03) or (pd.notna(d) and d >= 5):
            sig.loc[t] = "OFF"
        elif (pd.notna(b) and b > 0.55) and (pd.notna(n) and n > 0.08) and (pd.notna(d) and d <= 3):
            sig.loc[t] = "ON"
        else:
            sig.loc[t] = "NEUTRAL"
    return sig


def composite_signal(
    dist_series: pd.Series,
    breadth_series: pd.Series | None = None,
    dist_off: int = 5,
    dist_warn: int = 4,
    breadth_weak: float = 0.4,
    breadth_strong: float = 0.5,
) -> pd.Series:
    """
    ON / OFF / NEUTRAL by day. Aligns dist and breadth on index (date).
    OFF: dist >= dist_off OR (dist >= dist_warn AND breadth < breadth_weak)
    ON:  dist <= 2 AND breadth > breadth_strong
    Else NEUTRAL.
    """
    if breadth_series is None or breadth_series.empty:
        breadth_series = pd.Series(index=dist_series.index, dtype=float)
        breadth_series[:] = 0.5
    # align to common index
    idx = dist_series.index.union(breadth_series.index).drop_duplicates()
    dist = dist_series.reindex(idx).fillna(0)
    breadth = breadth_series.reindex(idx).fillna(0.5)
    signal = pd.Series(index=idx, dtype="object")
    for i in idx:
        d = dist.loc[i]
        b = breadth.loc[i]
        if d >= dist_off or (d >= dist_warn and b < breadth_weak):
            signal.loc[i] = "OFF"
        elif d <= 2 and b > breadth_strong:
            signal.loc[i] = "ON"
        else:
            signal.loc[i] = "NEUTRAL"
    return signal


def mh_signal(
    breadth_ma50: pd.Series,
    nh20_pct: pd.Series,
    cfg: dict | None = None,
) -> pd.Series:
    """
    Market Health overlay signal (NH-heavy, no trades/circularity):
      - Inputs: daily breadth (% above MA50) and NH20% (new 20d highs fraction).
      - OFF if nh20_pct < nh20_off OR breadth_ma50 < breadth_off.
      - ON  if nh20_pct > nh20_on  AND breadth_ma50 > breadth_on.
      - Else NEUTRAL.

    Thresholds can be overridden via cfg:
      breadth_ma50_off (default 0.45)
      nh20_off        (default 0.06)
      breadth_ma50_on (default 0.55)
      nh20_on         (default 0.09)
    """
    cfg = cfg or {}
    b_off = float(cfg.get("breadth_ma50_off", 0.45))
    n_off = float(cfg.get("nh20_off", 0.06))
    b_on = float(cfg.get("breadth_ma50_on", 0.55))
    n_on = float(cfg.get("nh20_on", 0.09))

    idx = breadth_ma50.index.union(nh20_pct.index)
    idx = idx.sort_values()
    b = breadth_ma50.reindex(idx).ffill()
    n = nh20_pct.reindex(idx).ffill()

    sig = pd.Series(index=idx, dtype="object")
    for t in idx:
        bv = b.loc[t]
        nv = n.loc[t]
        if (pd.notna(nv) and nv < n_off) or (pd.notna(bv) and bv < b_off):
            sig.loc[t] = "OFF"
        elif (pd.notna(nv) and nv > n_on) and (pd.notna(bv) and bv > b_on):
            sig.loc[t] = "ON"
        else:
            sig.loc[t] = "NEUTRAL"
    return sig
