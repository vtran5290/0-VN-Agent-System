from __future__ import annotations

from typing import Tuple

import pandas as pd

from .config import RSEngineConfig
from .data_loader import CLOSE_COL, VALUE_COL


def apply_universe_filters(
    df: pd.DataFrame,
    cfg: RSEngineConfig,
    ticker: str,
) -> pd.DataFrame:
    """
    Compute liquidity/price/history filters and flags for a single-ticker DataFrame.

    Expects rolling liquidity stats already present:
      - avg_value_20
      - avg_value_50
      - median_value_20
    """
    out = df.copy()

    # Basic history length flag
    history_pass = len(out) >= cfg.min_history_days

    # Latest price filter
    latest = out.iloc[-1]
    price_pass = bool(latest[CLOSE_COL] >= cfg.min_price)

    # Liquidity filters based on latest rolling stats
    avg_value_50 = float(latest.get("avg_value_50", float("nan")))
    median_value_20 = float(latest.get("median_value_20", float("nan")))

    liquidity_pass = bool(
        (median_value_20 >= cfg.min_median_value_20d)
        and (avg_value_50 >= cfg.min_avg_value_50d)
    )

    excluded = ticker.upper() in cfg.exclude_tickers

    quality_universe_pass = (
        history_pass and price_pass and liquidity_pass and not excluded
    )

    # Attach flags to all rows (but they only really matter for latest)
    out["liquidity_pass"] = liquidity_pass
    out["price_pass"] = price_pass
    out["history_pass"] = history_pass
    out["quality_universe_pass"] = quality_universe_pass

    return out


def add_trend_flags(
    df: pd.DataFrame,
    cfg: RSEngineConfig,
) -> pd.DataFrame:
    """Add trend/leadership related flags to a single-ticker DataFrame."""
    out = df.copy()

    close = out[CLOSE_COL]
    sma50 = out["sma50"]
    sma150 = out["sma150"]
    sma200 = out["sma200"]
    high_252 = out["high_252"]
    low_252 = out["low_252"]

    out["above_sma50"] = close > sma50
    out["above_sma150"] = close > sma150
    out["above_sma200"] = close > sma200

    out["sma50_gt_sma150"] = sma50 > sma150
    out["sma150_gt_sma200"] = sma150 > sma200

    out["sma200_rising_20d"] = sma200 > sma200.shift(20)

    out["near_52w_high"] = close >= cfg.near_high_threshold * high_252
    out["off_52w_low"] = close >= cfg.off_low_threshold * low_252

    # Trend template: evaluate per-row
    out["trend_template"] = (
        (close > sma50)
        & (close > sma150)
        & (close > sma200)
        & (sma50 > sma150)
        & (sma150 > sma200)
        & (out["sma200_rising_20d"])
        & (out["near_52w_high"])
        & (out["off_52w_low"])
    )

    return out

