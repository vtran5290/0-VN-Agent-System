from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


DATE_COL = "date"
CLOSE_COL = "close"
OPEN_COL = "open"
HIGH_COL = "high"
LOW_COL = "low"
VOLUME_COL = "volume"
VALUE_COL = "value"

# Workspace-specific fallback path for raw CSVs (Downloads)
DOWNLOADS_DIR = Path(r"C:\Users\LOLII\Downloads")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _select_price_column(df: pd.DataFrame) -> pd.Series:
    """Prefer adjusted close if available, else close."""
    cols = df.columns
    for candidate in ("adj_close", "adjusted_close", "adjclose"):
        if candidate in cols:
            return df[candidate].astype(float)
    if CLOSE_COL not in cols:
        raise ValueError("No close or adjusted close column found.")
    return df[CLOSE_COL].astype(float)


def _ensure_value_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    missing_value = VALUE_COL not in df.columns
    if missing_value:
        if CLOSE_COL not in df.columns or VOLUME_COL not in df.columns:
            raise ValueError("Cannot construct 'value' without 'close' and 'volume'.")
        df[VALUE_COL] = df[CLOSE_COL].astype(float) * df[VOLUME_COL].astype(float)
    else:
        df[VALUE_COL] = df[VALUE_COL].astype(float)
    return df


def load_ohlcv_csv(path: Path) -> pd.DataFrame:
    """Load a single OHLCV CSV file with basic cleaning."""
    df = pd.read_csv(path)
    df = _normalize_columns(df)

    if DATE_COL not in df.columns:
        raise ValueError(f"Missing '{DATE_COL}' column in {path}.")

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL])
    df = df.sort_values(DATE_COL).drop_duplicates(subset=[DATE_COL])
    df = df.reset_index(drop=True)

    # Basic type coercion
    for col in (OPEN_COL, HIGH_COL, LOW_COL, CLOSE_COL, VOLUME_COL):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = _ensure_value_column(df)

    # Drop rows with missing close or volume/value
    df = df.dropna(subset=[CLOSE_COL, VALUE_COL])
    return df


@dataclass
class LoadedUniverse:
    benchmark: pd.DataFrame
    stocks: Dict[str, pd.DataFrame]
    broken_files: List[str]


def load_benchmark(benchmark_dir: Path, ticker: str) -> pd.DataFrame:
    """
    Load benchmark CSV.

    Primary location:
        <project_root>/data/benchmark/<ticker>.csv

    Fallback (for this workspace):
        C:/Users/LOLII/Downloads/<ticker>.csv
    """
    primary_path = benchmark_dir / f"{ticker}.csv"
    if primary_path.exists():
        return load_ohlcv_csv(primary_path)

    # Workspace-specific fallback: look in Downloads if not found in data/benchmark
    downloads_path = Path(r"C:\Users\LOLII\Downloads") / f"{ticker}.csv"
    if downloads_path.exists():
        logger.warning(
            "Benchmark file not found at %s, using fallback %s",
            primary_path,
            downloads_path,
        )
        return load_ohlcv_csv(downloads_path)

    raise FileNotFoundError(
        f"Benchmark file not found at {primary_path} or fallback {downloads_path}"
    )


def load_stock_universe(stocks_dir: Path) -> LoadedUniverse:
    """
    Load all stock CSVs in directory, skipping broken ones.

    Primary location:
        <project_root>/data/stocks/*.csv

    Fallback (for this workspace only):
        C:/Users/LOLII/Downloads/*.csv
    """
    from .config import RSEngineConfig  # local import to avoid cycles

    broken: List[str] = []
    stocks: Dict[str, pd.DataFrame] = {}

    cfg = RSEngineConfig()

    # Load benchmark first so alignment can be done later
    benchmark = load_benchmark(cfg.data_benchmark_dir, cfg.benchmark_ticker)

    # Discover stock files
    stock_paths = sorted(stocks_dir.glob("*.csv"))

    # If no files in data/stocks, fall back to Downloads
    if not stock_paths and DOWNLOADS_DIR.exists():
        fallback_paths = sorted(DOWNLOADS_DIR.glob("*.csv"))
        # Exclude the benchmark file itself if present there
        stock_paths = [
            p
            for p in fallback_paths
            if p.stem.upper() != cfg.benchmark_ticker.upper()
        ]
        logger.warning(
            "No stock CSVs found in %s, using fallback directory %s with %d files",
            stocks_dir,
            DOWNLOADS_DIR,
            len(stock_paths),
        )

    for path in stock_paths:
        ticker = path.stem.upper()
        try:
            df = load_ohlcv_csv(path)
            stocks[ticker] = df
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load %s: %s", path, exc)
            broken.append(str(path))

    logger.info(
        "Loaded universe: %d stocks, %d broken files",
        len(stocks),
        len(broken),
    )

    return LoadedUniverse(benchmark=benchmark, stocks=stocks, broken_files=broken)

