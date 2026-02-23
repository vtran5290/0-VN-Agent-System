# pp_backtest/signals.py — Pocket Pivot + Sell v4 (Morales/Kacher)
from __future__ import annotations
import numpy as np
import pandas as pd

try:
    from pp_backtest.config import PocketPivotParams, SellParams
except ImportError:
    from config import PocketPivotParams, SellParams


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def distribution_day_count_series(
    df: pd.DataFrame,
    lb: int = 20,
    min_drop_pct: float = 0.002,
) -> pd.Series:
    """
    O'Neil-style: close down + volume up + %change <= -min_drop_pct.
    Returns rolling count of distribution days in last `lb` bars (per row).
    """
    c = df["close"]
    v = df["volume"]
    prev_c = c.shift(1)
    pct_chg = (c - prev_c) / prev_c.replace(0, np.nan)
    is_dd = (c < prev_c) & (v > v.shift(1)) & (pct_chg <= -min_drop_pct)
    return is_dd.rolling(lb, min_periods=lb).sum().astype(float)


def pocket_pivot(df: pd.DataFrame, p: PocketPivotParams) -> pd.DataFrame:
    out = df.copy()
    c, h, l, v = out["close"], out["high"], out["low"], out["volume"]

    out["ma10"] = sma(c, 10)
    out["ma20"] = sma(c, 20)
    out["ma50"] = sma(c, 50)

    down_vol = np.where(c < c.shift(1), v, 0.0)
    down_vol = pd.Series(down_vol, index=out.index)
    max_down_vol = down_vol.rolling(p.vol_lookback, min_periods=p.vol_lookback).max().shift(1)
    vol_ok = v > max_down_vol

    up_day = c >= c.shift(1)

    # Structural gates (PP_GIL_V4.2 — book-aligned, pre-registered, no tuning)
    out["above_ma50"] = c > out["ma50"]
    rng = (h - l).replace(0, np.nan).fillna(1e-9)
    out["demand_thrust"] = (c > c.shift(1)) & (c >= h - 0.3 * rng)  # upper 30% of range
    ma20_vol = sma(v, 20)
    out["tightness_ok"] = (v < ma20_vol).shift(1).rolling(5, min_periods=5).sum() >= 2  # at least 2 of last 5 bars vol < MA20 vol

    on10 = (c >= out["ma10"]) & (l <= out["ma10"] * (1 + p.ma_touch_tol_pct))
    on20 = (c >= out["ma20"]) & (l <= out["ma20"] * (1 + p.ma_touch_tol_pct))
    on50 = (c >= out["ma50"]) & (l <= out["ma50"] * (1 + p.ma_touch_tol_pct))

    def slope_ok(ma: pd.Series) -> pd.Series:
        den = ma.shift(p.slope_bars).replace(0, np.nan).abs().clip(lower=1e-6)
        slope = (ma - ma.shift(p.slope_bars)) / den
        return slope >= -p.slope_tol_pct

    slope_ok10 = slope_ok(out["ma10"])
    slope_ok20 = slope_ok(out["ma20"])
    slope_ok50 = slope_ok(out["ma50"])

    use50 = on50 & slope_ok50
    use20 = on20 & (~use50) & slope_ok20
    use10 = on10 & (~use50) & (~use20) & slope_ok10

    out["pp_use10"] = use10
    out["pp_use20"] = use20
    out["pp_use50"] = use50
    out["pp"] = up_day & vol_ok & (use10 | use20 | use50)

    return out


def sell_morales_kacher_v4(df: pd.DataFrame, s: SellParams) -> pd.DataFrame:
    out = df.copy()
    c, h, l, v = out["close"], out["high"], out["low"], out["volume"]

    out["ma10"] = out.get("ma10", sma(c, 10))
    out["ma20"] = out.get("ma20", sma(c, 20))
    out["ma50"] = out.get("ma50", sma(c, 50))

    a14 = atr(out, 14)
    rng = (h - l).clip(lower=1e-6)
    close_pos = (c - l) / rng

    down_day = c < c.shift(1)

    wide_spread = (h - l) >= s.ugly_atr_mult * a14
    close_near_low = close_pos <= s.ugly_closepos
    heavy_vol = v >= sma(v, 50) * s.heavy_vol_x_ma50
    # UglyBar: current bar O,H,L,C,V + ATR14/MA50(vol) only — no lookahead (audit A)
    ugly_bar = down_day & wide_spread & close_near_low & heavy_vol

    not_viol10 = c >= out["ma10"] * (1 - s.ride_tol_10)
    not_viol20 = c >= out["ma20"] * (1 - s.ride_tol_20)

    ride10_ok = not_viol10.rolling(s.ride_bars_10, min_periods=s.ride_bars_10).sum() >= (s.ride_bars_10 - 3)
    ride20_ok = not_viol20.rolling(s.ride_bars_20, min_periods=s.ride_bars_20).sum() >= (s.ride_bars_20 - 3)

    tier3 = ride10_ok
    tier2 = s.enable_ma20_tier & ride20_ok & (~tier3)
    tier1 = (~tier3) & (~tier2)

    n_confirm = max(1, getattr(s, "confirmation_closes", 1))

    # Tier 3: MA10 — confirmation on MA10 (tier_ma)
    day1_10 = tier3 & (c < out["ma10"])
    reclaim10 = day1_10.shift(1) & (c >= out["ma10"])
    day2_10 = day1_10.shift(1) & (l < l.shift(1)) & (~reclaim10)
    two_close_below_10 = (c < out["ma10"]) & (c.shift(1) < out["ma10"].shift(1)) & tier3
    ugly10 = day1_10 & ugly_bar  # UglyBar stays fast exit override
    if n_confirm >= 2:
        sell10 = ugly10 | two_close_below_10
    else:
        sell10 = ugly10 | day2_10

    # Tier 2: MA20 — confirmation on MA20 (tier_ma)
    day1_20 = tier2 & (c < out["ma20"])
    reclaim20 = day1_20.shift(1) & (c >= out["ma20"])
    day2_20 = day1_20.shift(1) & (l < l.shift(1)) & (~reclaim20)
    two_close_below_20 = (c < out["ma20"]) & (c.shift(1) < out["ma20"].shift(1)) & tier2
    ugly20 = day1_20 & ugly_bar
    if n_confirm >= 2:
        sell20 = ugly20 | two_close_below_20
    else:
        sell20 = ugly20 | day2_20

    # Tier 1: MA50 — confirmation on MA50 (tier_ma); UglyBar and linger unchanged
    below50 = c < out["ma50"]
    below50_hard = c < out["ma50"] * (1 - s.porosity_50)
    break50 = below50 & (c.shift(1) >= out["ma50"].shift(1))
    reclaim_fast = (break50.shift(1) | break50.shift(2)) & (c >= out["ma50"])

    day1_50 = break50 & (~reclaim_fast)
    reclaim50 = day1_50.shift(1) & (c >= out["ma50"])
    day2_50 = day1_50.shift(1) & (l < l.shift(1)) & (~reclaim50)
    ugly50 = day1_50 & ugly_bar
    two_close_below_50 = (c < out["ma50"]) & (c.shift(1) < out["ma50"].shift(1))

    recent_break50 = break50.rolling(10, min_periods=10).sum() > 0
    linger_below50 = (below50.rolling(s.linger_bars_50, min_periods=s.linger_bars_50).sum() >= s.linger_bars_50) & recent_break50 & (~reclaim_fast)
    ugly_break50 = below50_hard & ugly_bar

    if n_confirm >= 2:
        sell50_signal = ugly_break50 | ugly50 | linger_below50 | two_close_below_50
    else:
        sell50_signal = ugly_break50 | day2_50 | ugly50 | linger_below50
    sell50_casea = sell50_signal & tier1
    recent_sell10 = sell10.rolling(20, min_periods=20).sum() > 0
    sell50_caseb = sell50_signal & recent_sell10
    sell50 = sell50_casea | sell50_caseb

    fire10 = sell10 & (~sell10.shift(1).fillna(False))
    fire20 = sell20 & (~sell20.shift(1).fillna(False))
    fire50 = sell50 & (~sell50.shift(1).fillna(False))
    caseb_fire = sell50_caseb & (~sell50_caseb.shift(1).fillna(False))

    use_fire10 = fire10 & (~caseb_fire)
    use_fire20 = fire20 & (~use_fire10) & (~caseb_fire)
    use_fire50 = (fire50 & (~use_fire10) & (~use_fire20)) | caseb_fire

    out["sell"] = use_fire10 | use_fire20 | use_fire50
    out["sell_tier"] = np.select([use_fire10, use_fire20, use_fire50], ["MA10", "MA20", "MA50"], default="")
    # UglyBar-only exit (for no_SELL_V4 variant: keep UglyBar, drop MA-trailing)
    out["sell_ugly_only"] = (use_fire10 & ugly10) | (use_fire20 & ugly20) | (use_fire50 & (ugly50 | ugly_break50))

    return out


# --- Pre-registered tweaks (docs/PP_TWEAKS_RESEARCH.md) ---


def undercut_rally_signal(
    df: pd.DataFrame,
    prior_low_bars: int = 20,
    volume_filter: bool = True,
) -> pd.Series:
    """
    Undercut & Rally (U&R): prior significant low = min(low) over [i-20, i-2].
    Undercut = low[i] < prior_low; Rally = close[i] > prior_low.
    Pre-registered: prior_low_bars=20, optional vol > avg(vol,20).
    """
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    # prior_low at i = min(low[i-20 : i-1]) excluding yesterday; use [i-20..i-2] = 19 bars
    prior_low = low.shift(2).rolling(prior_low_bars - 1, min_periods=prior_low_bars - 1).min()
    undercut = low < prior_low
    rally = close > prior_low
    sig = undercut & rally
    if volume_filter and "volume" in df.columns:
        vol = df["volume"].astype(float)
        sig = sig & (vol > sma(vol, 20))
    return sig.fillna(False)


def established_uptrend_filter(
    df: pd.DataFrame,
    ma50_slope_bars: int = 20,
    min_bars_above_ma50: int = 15,
    lookback: int = 20,
) -> pd.Series:
    """
    CPP filter: MA50 slope > 0 and close > MA50 in >= min_bars_above_ma50 of last lookback bars.
    Pre-registered: ma50_slope_bars=20, min_bars_above_ma50=15, lookback=20.
    """
    c = df["close"].astype(float)
    ma50 = sma(c, 50)
    slope_pct = (ma50 - ma50.shift(ma50_slope_bars)) / ma50.shift(ma50_slope_bars).replace(0, np.nan)
    slope_ok = slope_pct > 0
    above = (c > ma50).astype(float)
    bars_above = above.rolling(lookback, min_periods=lookback).sum()
    return (slope_ok & (bars_above >= min_bars_above_ma50)).fillna(False)


def buyable_gap_up_signal(
    df: pd.DataFrame,
    gap_pct_min: float = 0.03,
    volume_ratio_min: float = 1.5,
    avg_vol_days: int = 20,
) -> pd.Series:
    """
    Buyable Gap-Up (BGU): gap > gap_pct_min (e.g. 3%), volume > volume_ratio_min * avg_volume.
    Sách 2010/2012. Stop at low of gap day.
    """
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    v = df["volume"].astype(float)
    prev_c = c.shift(1)
    gap_pct = (o - prev_c) / prev_c.replace(0, np.nan)
    avg_vol = sma(v, avg_vol_days)
    return (gap_pct >= gap_pct_min) & (v >= volume_ratio_min * avg_vol).fillna(False)


def right_side_of_base_signal(
    df: pd.DataFrame,
    lookback_bars: int = 63,
) -> pd.Series:
    """
    Right-side-of-base: close > midpoint of last lookback range (e.g. 3 months ≈ 63 bars).
    """
    c = df["close"].astype(float)
    roll_high = c.rolling(lookback_bars, min_periods=lookback_bars).max().shift(1)
    roll_low = c.rolling(lookback_bars, min_periods=lookback_bars).min().shift(1)
    mid = (roll_high + roll_low) / 2
    return (c > mid).fillna(False)


def avoid_extended_signal(
    df: pd.DataFrame,
    ma_period: int = 10,
    max_distance_pct: float = 0.05,
) -> pd.Series:
    """
    Avoid extended (Book 2): distance from MA10 < max_distance_pct (e.g. 5%).
    True = not extended, safe to consider buy.
    """
    c = df["close"].astype(float)
    ma = sma(c, ma_period)
    dist = (c - ma).abs() / ma.replace(0, np.nan)
    return (dist < max_distance_pct).fillna(False)
