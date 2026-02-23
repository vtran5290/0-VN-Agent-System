# pp_backtest/market_regime.py — Market context from Gil/O'Neil (luôn bật khi test book conditions)
from __future__ import annotations
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def distribution_day_count_series(
    df: pd.DataFrame,
    lb: int = 20,
    min_drop_pct: float = 0.002,
) -> pd.Series:
    """O'Neil-style: close down + volume up + %change <= -min_drop_pct. Rolling count in last lb bars."""
    c = df["close"]
    v = df["volume"]
    prev_c = c.shift(1)
    pct_chg = (c - prev_c) / prev_c.replace(0, np.nan)
    is_dd = (c < prev_c) & (v > v.shift(1)) & (pct_chg <= -min_drop_pct)
    return is_dd.rolling(lb, min_periods=lb).sum().astype(float)


def add_book_regime_columns(market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add columns for book-style market context (Gil/O'Neil). Call on VN30 daily DataFrame.
    - regime_ftd: FTD-style proxy — VN30 close > MA50 AND MA50 slope > 0 (trend confirmation; not true O'Neil FTD).
    - dist_days_last_10: distribution days in last 10 bars (sách: 3–4 trong 7–10 ngày là warning).
    - no_new_positions: True when dist_days_last_10 >= 3 (stop buying, không exit toàn bộ).
    """
    out = market_df.copy()
    c = out["close"].astype(float)
    ma50 = sma(c, 50)
    # MA50 slope: (MA50 - MA50[20]) / MA50[20]
    ma50_slope = (ma50 - ma50.shift(20)) / ma50.shift(20).replace(0, np.nan)
    out["regime_ftd"] = (c > ma50) & (ma50_slope > 0)
    out["regime_ftd"] = out["regime_ftd"].fillna(False)
    # Distribution days in last 10 (sách: 3–4 trong 7–10 = warning)
    out["dist_days_last_10"] = distribution_day_count_series(out, lb=10)
    out["no_new_positions"] = (out["dist_days_last_10"] >= 3).fillna(False)
    return out


def weekly_regime_from_daily(market_daily_df: pd.DataFrame, week_end: str = "W-FRI") -> pd.DataFrame:
    """
    Map daily book regime to weekly: each week gets regime_ftd and no_new_positions
    from the last trading day of that week. Requires add_book_regime_columns already applied.
    """
    if "regime_ftd" not in market_daily_df.columns or "no_new_positions" not in market_daily_df.columns:
        return pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
    df = market_daily_df.set_index(pd.to_datetime(market_daily_df["date"])).sort_index()
    weekly = df[["regime_ftd", "no_new_positions"]].resample(week_end).last().dropna(how="all")
    weekly = weekly.reset_index().rename(columns={"index": "date"})
    weekly["date"] = weekly["date"].dt.normalize()
    return weekly[["date", "regime_ftd", "no_new_positions"]]
