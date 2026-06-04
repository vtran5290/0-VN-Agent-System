"""
Stock-level cloud turn events with forward returns.
Output: stock_cloud_turn_events.csv
"""
from __future__ import annotations
import logging
from typing import Optional

import numpy as np
import pandas as pd

from .config import (
    OUTPUT_DIR,
    STOCK_EVENTS_CACHE,
    FORWARD_HORIZONS,
    VIN_GROUP_SYMBOLS,
    MIN_HISTORY_BARS,
)

log = logging.getLogger(__name__)


def _forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """Compute forward return horizon sessions ahead (shifted close / current close - 1)."""
    return close.shift(-horizon) / close - 1


def build_stock_turn_events(
    panel: pd.DataFrame,
    sector_map: pd.DataFrame,
    regimes: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_bars_bear: int = 3,
) -> pd.DataFrame:
    """
    Identify dates where stock cloud turns bullish (0→1 transition).
    Appends forward returns, sector tags, regime overlays.
    Requires panel to have: symbol, date, close, cloud_bull_20_100, adv20, adv50, ema_fast.
    """
    map_cols = [c for c in ["symbol", "sector_l4", "is_bank", "is_vin_group",
                             "is_securities", "is_broker", "is_real_estate",
                             "confidence"] if c in sector_map.columns]
    enriched = panel.merge(
        sector_map[map_cols].drop_duplicates("symbol"),
        on="symbol", how="left"
    )
    enriched["sector_l4"] = enriched["sector_l4"].fillna("Unknown")

    rows = []
    for sym, grp in enriched.groupby("symbol", sort=False):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < MIN_HISTORY_BARS:
            continue

        if start_date:
            mask = grp["date"] >= start_date
        else:
            mask = pd.Series(True, index=grp.index)
        if end_date:
            mask &= grp["date"] <= end_date

        # Cloud turn: 0→1 transition AND price above ema_fast
        prev_bull = grp["cloud_bull_20_100"].shift(1).fillna(0)
        # Require bear for min_bars_bear sessions before turn
        rolling_bear = (~grp["cloud_bull_20_100"].astype(bool)).rolling(
            min_bars_bear, min_periods=1
        ).sum().shift(1).fillna(0)
        turn_mask = (
            (grp["cloud_bull_20_100"] == 1) &
            (prev_bull == 0) &
            (rolling_bear >= min_bars_bear) &
            mask
        )
        turn_idx = grp.index[turn_mask]

        for idx in turn_idx:
            row = grp.loc[idx]
            entry = {
                "symbol":               sym,
                "date":                 row["date"],
                "sector_l4":            row["sector_l4"],
                "cloud_bull_20_100":    row["cloud_bull_20_100"],
                "ema_fast":             row.get("ema_fast", np.nan),
                "ema_slow":             row.get("ema_slow", np.nan),
                "close":                row["close"],
                "adv20":                row["adv20"],
                "adv50":                row["adv50"],
                "is_vin_group":         int(sym in VIN_GROUP_SYMBOLS),
                "is_bank":              row.get("is_bank", 0),
                "is_broker":            row.get("is_broker", 0),
                "is_real_estate":       row.get("is_real_estate", 0),
                "liquidity_pass_phase36": int(row["adv50"] >= 2e9),
            }
            for h in FORWARD_HORIZONS:
                if idx + h < len(grp):
                    entry[f"fwd_ret_{h}d"] = grp.loc[idx + h, "close"] / row["close"] - 1
                else:
                    entry[f"fwd_ret_{h}d"] = np.nan
            rows.append(entry)

    events = pd.DataFrame(rows) if rows else pd.DataFrame()
    if events.empty:
        log.warning("No stock cloud turn events found!")
        events.to_csv(STOCK_EVENTS_CACHE, index=False)
        return events

    # Merge regime overlays
    regime_cols = [c for c in regimes.columns if c != "date"]
    events = events.merge(regimes[["date"] + regime_cols], on="date", how="left")

    events.to_csv(STOCK_EVENTS_CACHE, index=False)
    log.info("Stock cloud turn events: %d rows saved to %s", len(events), STOCK_EVENTS_CACHE)
    return events
