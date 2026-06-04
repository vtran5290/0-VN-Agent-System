"""
Data loading, ADV computation, and enriched panel caching.
Rules:
- Load from repo files only (no FireAnt client).
- OHLCV panel has cols: symbol, date, open, high, low, close, volume, value.
- adv20 / adv50 are computed here from value (turnover in VND).
- Enriched panel (+ cloud indicators + ADV) cached to stock_daily_cloud_panel.parquet.
"""
from __future__ import annotations
import logging
from pathlib import Path

import pandas as pd

from .config import (
    OHLCV_PANEL_PATH,
    SECTOR_MAP_PATH,
    VNINDEX_PARQUET,
    EX_VIN_SERIES_PATH,
    ENRICHED_PANEL_CACHE,
    OUTPUT_DIR,
    VIN_GROUP_SYMBOLS,
)
from .cloud import add_cloud_to_panel

log = logging.getLogger(__name__)

_REQUIRED_COLS = {"symbol", "date", "open", "high", "low", "close", "volume", "value"}


def load_ohlcv_panel(force_rebuild: bool = False) -> pd.DataFrame:
    """
    Load and enrich the OHLCV panel.
    Returns panel with added columns: adv20, adv50, cloud_bull_20_100, ema_fast, ema_slow.
    Uses cache if available and force_rebuild=False.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not force_rebuild and ENRICHED_PANEL_CACHE.exists():
        log.info("Loading enriched panel from cache: %s", ENRICHED_PANEL_CACHE)
        df = pd.read_parquet(ENRICHED_PANEL_CACHE)
        df["date"] = pd.to_datetime(df["date"])
        return df

    log.info("Building enriched panel from %s", OHLCV_PANEL_PATH)
    df = pd.read_parquet(OHLCV_PANEL_PATH)
    df["date"] = pd.to_datetime(df["date"])

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV panel missing required columns: {missing}")

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # ADV20 / ADV50 from turnover (value = VND turnover)
    log.info("Computing adv20 / adv50 from value column …")
    df["adv20"] = df.groupby("symbol")["value"].transform(
        lambda x: x.rolling(20, min_periods=1).mean()
    )
    df["adv50"] = df.groupby("symbol")["value"].transform(
        lambda x: x.rolling(50, min_periods=1).mean()
    )

    # EMA cloud (20/100)
    log.info("Computing EMA20/100 cloud …")
    df = add_cloud_to_panel(df)

    df["is_vin_group"] = df["symbol"].isin(VIN_GROUP_SYMBOLS).astype(int)

    log.info("Caching enriched panel to %s", ENRICHED_PANEL_CACHE)
    df.to_parquet(ENRICHED_PANEL_CACHE, index=False)
    log.info("Enriched panel shape: %s", df.shape)
    return df


def load_sector_map() -> pd.DataFrame:
    """Load sector map. Returns DataFrame with sector_l1..l4, flags, confidence."""
    df = pd.read_csv(SECTOR_MAP_PATH)
    df.columns = df.columns.str.strip()
    # Handle duplicate symbols if any
    dupes = df[df.duplicated("symbol", keep=False)].copy()
    if not dupes.empty:
        log.warning("Duplicate symbols in sector map: %s", dupes["symbol"].tolist())
        df["duplicate_symbol_flag"] = df.duplicated("symbol", keep=False).astype(int)
    else:
        df["duplicate_symbol_flag"] = 0
    return df


def load_vnindex(use_parquet: bool = True) -> pd.DataFrame:
    """Load VNINDEX OHLCV. Returns date, close, (optional ema_fast, ema_slow, cloud_bull)."""
    if use_parquet and Path(VNINDEX_PARQUET).exists():
        df = pd.read_parquet(VNINDEX_PARQUET)
    else:
        raise FileNotFoundError(f"VNINDEX parquet not found: {VNINDEX_PARQUET}")
    df["date"] = pd.to_datetime(df["date"] if "date" in df.columns else df.index)
    if "date" not in df.columns:
        df = df.reset_index()
    return df[["date", "close"]].sort_values("date").reset_index(drop=True)


def load_ex_vin_series() -> pd.DataFrame:
    """Load ex-VIN index series. Returns date + close (or returns column)."""
    df = pd.read_csv(EX_VIN_SERIES_PATH)
    df["date"] = pd.to_datetime(df["date"] if "date" in df.columns else df.iloc[:, 0])
    return df.sort_values("date").reset_index(drop=True)


def validate_enriched_panel(df: pd.DataFrame) -> list[str]:
    """Return list of validation errors (empty = pass)."""
    errors = []
    required = {"symbol", "date", "close", "adv20", "adv50", "cloud_bull_20_100"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing columns: {missing}")
    if df["adv20"].isna().mean() > 0.05:
        errors.append("adv20 has >5% NaN")
    if df["adv50"].isna().mean() > 0.05:
        errors.append("adv50 has >5% NaN")
    if df["cloud_bull_20_100"].isna().mean() > 0.05:
        errors.append("cloud_bull_20_100 has >5% NaN")
    return errors
