# minervini_backtest/src/filters.py — Trend Template (TT) filters: TT_Strict, TT_Lite
from __future__ import annotations
import numpy as np
import pandas as pd


def ma200_slope(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """MA200 today > MA200 lookback bars ago."""
    if "ma200" not in df.columns:
        raise ValueError("Need ma200; run add_mas first.")
    ma200 = df["ma200"]
    ma200_ago = ma200.shift(lookback)
    return (ma200 > ma200_ago).fillna(False)


def tt_strict(df: pd.DataFrame, ma200_slope_bars: int = 20) -> pd.Series:
    """
    Minervini classic:
    - Close > MA50
    - MA50 > MA150 > MA200
    - MA200 sloping up (MA200 today > MA200 20 bars ago)
    - Close >= 1.30 * 52wLow
    - Close >= 0.75 * 52wHigh
    """
    c = df["close"]
    ok = (
        (c > df["ma50"])
        & (df["ma50"] > df["ma150"])
        & (df["ma150"] > df["ma200"])
        & ma200_slope(df, ma200_slope_bars)
        & (c >= 1.30 * df["low_252"])
        & (c >= 0.75 * df["high_252"])
    )
    return ok.fillna(False)


def tt_lite(df: pd.DataFrame, ma200_slope_bars: int = 20) -> pd.Series:
    """
    VN-friendly (more names pass):
    - Close > MA50
    - MA50 > MA200
    - MA200 sloping up
    """
    ok = (
        (df["close"] > df["ma50"])
        & (df["ma50"] > df["ma200"])
        & ma200_slope(df, ma200_slope_bars)
    )
    return ok.fillna(False)


def add_tt(df: pd.DataFrame, mode: str = "lite", ma200_slope_bars: int = 20) -> pd.DataFrame:
    """Add column tt_ok (bool). mode in ('strict', 'lite')."""
    out = df.copy()
    if mode.strip().lower() == "strict":
        out["tt_ok"] = tt_strict(out, ma200_slope_bars)
    else:
        out["tt_ok"] = tt_lite(out, ma200_slope_bars)
    return out


def liquidity_gate(
    df: pd.DataFrame,
    adtv_window: int = 50,
    min_adtv_vnd_by_year: dict | None = None,
) -> pd.Series:
    """
    Execution realism gate: bool Series 'eligible_liq' based on Average Daily Turnover (VND).

    ADTV_VND = rolling_mean(close * volume, window=adtv_window).
    For each bar (date), require ADTV_VND >= threshold for that calendar year:
      - thresholds taken from min_adtv_vnd_by_year (keys can be int years or strings).
      - a key like '2018+' applies to all years >= 2018.
      - if no threshold for a year, fallback to default (e.g. 20e9 VND).

    This gate is intended to block NEW ENTRIES on illiquid bars; it should not force exits.
    """
    out = df.copy()
    if "date" not in out.columns or "close" not in out.columns or "volume" not in out.columns:
        raise ValueError("liquidity_gate requires 'date', 'close', 'volume' columns.")
    out["date"] = pd.to_datetime(out["date"])
    value = out["close"].astype(float) * out["volume"].astype(float)
    adtv = value.rolling(adtv_window, min_periods=adtv_window).mean()

    # Default thresholds if none provided
    cfg_map = dict(min_adtv_vnd_by_year or {})
    default_threshold = float(cfg_map.get("default", 20e9))
    plus_start = None
    year_thresholds: dict[int, float] = {}

    for k, v in cfg_map.items():
        if k == "default":
            # handled above
            continue
        key_str = str(k)
        try:
            year = int(key_str)
            year_thresholds[year] = float(v)
        except ValueError:
            # handle "2018+" style keys
            if key_str.endswith("+"):
                base = key_str[:-1]
                if base.isdigit():
                    try:
                        plus_start = int(base)
                        default_threshold = float(v)
                    except ValueError:
                        continue
            # ignore anything else

    years = out["date"].dt.year
    thresh_series = years.map(year_thresholds).astype(float)
    if plus_start is not None:
        # for years >= plus_start, use default_threshold
        thresh_series = thresh_series.where(years < plus_start, default_threshold)
    thresh_series = thresh_series.fillna(default_threshold)

    eligible = (adtv >= thresh_series).fillna(False)
    return eligible
