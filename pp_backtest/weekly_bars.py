# pp_backtest/weekly_bars.py — Resample daily OHLCV to weekly (Gil/Kacher weekly setups)
from __future__ import annotations
import pandas as pd


def daily_to_weekly(daily_df: pd.DataFrame, week_end: str = "W-FRI") -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly. week_end: W-FRI = week ending Friday.
    Agg: open=first, high=max, low=min, close=last, volume=sum.
    """
    if daily_df.empty or "date" not in daily_df.columns:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = daily_df.set_index(pd.to_datetime(daily_df["date"])).sort_index()
    agg = df.resample(week_end).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(how="all")
    agg = agg[agg["close"].notna()]
    agg = agg.reset_index().rename(columns={"index": "date"})
    agg["date"] = agg["date"].dt.normalize()
    return agg[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
