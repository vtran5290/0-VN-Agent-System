# pp_backtest/signals_darvas.py — Darvas Box Theory (rule-based, Swing/Position)
# Institutional-grade: box_confirm = 2+ high touches AND 1+ low touch; tolerance = 0.2*ATR; optional stability/gap/range.
from __future__ import annotations
import numpy as np
import pandas as pd

try:
    from pp_backtest.signals import sma, atr
except ImportError:
    from signals import sma, atr


def darvas_box(
    df: pd.DataFrame,
    L: int = 20,
    touch_high_min: int = 2,
    touch_low_min: int = 1,
    atr_tolerance_mult: float = 0.2,
    atr_period: int = 14,
    stability_bars: int = 0,
    touch_min_gap: int = 0,
    max_range_pct: float | None = None,
) -> pd.DataFrame:
    """
    Darvas box: box_high = highest(high,L), box_low = lowest(low,L).
    - tolerance = atr_tolerance_mult * ATR (VN: 0.2→0.3→0.4 sweep).
    - box_confirm = (high touches >= touch_high_min) AND (low touches >= touch_low_min).
    - stability_bars > 0: chỉ đếm touch khi box_high/box_low không đổi N bar (tránh đếm ảo).
    - touch_min_gap >= 1: đếm theo "run" (mỗi run consecutive touch = 1) tránh double-count.
    - max_range_pct: nếu set, box_confirm &= (box_range_pct <= max_range_pct).
    Option A (relaxed): tol 0.3, stability_bars 2, touch_min_gap 1, max_range_pct 0.015–0.02.
    """
    out = df.copy()
    h = out["high"].astype(float)
    l = out["low"].astype(float)
    a = atr(out, atr_period)
    tolerance = (atr_tolerance_mult * a).fillna(0).replace(0, np.nan).fillna(1e-9)

    out["box_high"] = h.rolling(L, min_periods=L).max()
    out["box_low"] = l.rolling(L, min_periods=L).min()
    mid = (out["box_high"] + out["box_low"]) / 2
    mid = mid.replace(0, np.nan).fillna(1e-9)
    out["box_range_pct"] = (out["box_high"] - out["box_low"]) / mid

    near_high = (h >= out["box_high"] - tolerance).astype(float)
    near_low = (l <= out["box_low"] + tolerance).astype(float)

    if stability_bars > 0:
        bh = out["box_high"]
        bl = out["box_low"]
        box_high_stable = (bh == bh.shift(1))
        box_low_stable = (bl == bl.shift(1))
        for j in range(2, stability_bars + 1):
            box_high_stable = box_high_stable & (bh == bh.shift(j))
            box_low_stable = box_low_stable & (bl == bl.shift(j))
        valid_high = near_high.astype(bool) & box_high_stable.fillna(False)
        valid_low = near_low.astype(bool) & box_low_stable.fillna(False)
    else:
        valid_high = near_high.astype(bool)
        valid_low = near_low.astype(bool)

    if touch_min_gap >= 1:
        run_high = valid_high & (~valid_high.shift(1).fillna(False))
        run_low = valid_low & (~valid_low.shift(1).fillna(False))
        touch_high_count = run_high.astype(float).rolling(L, min_periods=L).sum()
        touch_low_count = run_low.astype(float).rolling(L, min_periods=L).sum()
    else:
        touch_high_count = valid_high.astype(float).rolling(L, min_periods=L).sum()
        touch_low_count = valid_low.astype(float).rolling(L, min_periods=L).sum()

    out["box_touch_high_count"] = touch_high_count
    out["box_touch_low_count"] = touch_low_count
    out["box_confirm"] = (
        (touch_high_count >= touch_high_min) & (touch_low_count >= touch_low_min)
    ).fillna(False)
    if max_range_pct is not None:
        out["box_confirm"] = out["box_confirm"] & (out["box_range_pct"] <= max_range_pct)
    out["is_box_tight"] = out["box_confirm"]
    return out


def entry_darvas_breakout(
    df: pd.DataFrame,
    L: int = 20,
    vol_k: float = 1.5,
    new_high_N: int | None = 120,
    use_close_break: bool = True,
    require_box_confirm: bool = True,
    index_df: pd.DataFrame | None = None,
    rs_lookback: int = 60,
) -> pd.Series:
    """
    Entry D1 — Box breakout: close (or high) > box_high + volume >= vol_k * SMA(volume, 20).
    Chỉ khi box đã confirm (2+ high touches, 1+ low touch) nếu require_box_confirm=True.
    Entry D2 — New high filter (optional): close >= highest(close, new_high_N).
    Optional RS filter (VN): stock_return_60d > index_return_60d; cần index_df merge by date.
    """
    if "box_high" not in df.columns or "box_low" not in df.columns:
        df = darvas_box(df, L=L)
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    vol = df["volume"].astype(float)
    # Break above prior bar's box (same-bar box_high includes today's high => close > box_high is impossible).
    box_high_prev = df["box_high"].shift(1)
    ma20_vol = sma(vol, 20)
    vol_ok = (vol >= ma20_vol * vol_k).fillna(False)
    if use_close_break:
        breakout = c > box_high_prev
    else:
        breakout = h > box_high_prev
    if require_box_confirm and "box_confirm" in df.columns:
        breakout = breakout & df["box_confirm"].fillna(False)
    entry = breakout & vol_ok
    if new_high_N is not None:
        highest_N = c.rolling(new_high_N, min_periods=new_high_N).max().shift(1)
        new_high_ok = (c >= highest_N).fillna(False)
        entry = entry & new_high_ok
    # Relative strength: stock_ret_60d > index_ret_60d (VN rất cần RS filter)
    if index_df is not None and rs_lookback > 0:
        stock_ret = c.pct_change(rs_lookback)
        idx = index_df.copy()
        idx["index_ret"] = idx["close"].astype(float).pct_change(rs_lookback)
        merged = df[["date"]].merge(idx[["date", "index_ret"]], on="date", how="left")
        if "index_ret" in merged.columns:
            ir = merged["index_ret"].values
            sr = stock_ret.values
            valid = np.isfinite(ir) & np.isfinite(sr)
            rs_ok = np.where(valid, sr > ir, True)  # no filter when index data missing
            entry = entry & pd.Series(rs_ok, index=entry.index)
    return entry.fillna(False)


def exit_darvas_box_low(
    df: pd.DataFrame,
    atr_buffer: float = 0.25,
    atr_period: int = 14,
) -> pd.Series:
    """
    Stop = box_low − buffer (buffer = atr_buffer * ATR). Vectorized fallback only.
    Stateful trailing (dời stop theo box mới) phải dùng trong backtest loop — xem use_darvas_trailing.
    """
    if "box_low" not in df.columns:
        df = darvas_box(df, L=20)
    c = df["close"].astype(float)
    box_low = df["box_low"].astype(float)
    a = atr(df, atr_period)
    buffer = atr_buffer * a
    stop_level = box_low - buffer
    return (c < stop_level).fillna(False)
