"""Data loader for cloud daily report validation.

Loads phase36 daily scan CSVs and OHLCV panel for research use.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from .schema import OHLCV_PATH, RESEARCH_ONLY_LABEL, SCAN_DIR

logger = logging.getLogger(__name__)

# Label applied to all reconstructed/loaded data to signal it is not live
LABEL_RECONSTRUCTED = "RECONSTRUCTED_NOT_LIVE_SCAN"

# Pattern to match dated scan files (e.g. phase36_daily_scan_20260522.csv)
_SCAN_FILE_PATTERN = re.compile(r"phase36_daily_scan_(\d{8})\.csv$")


def load_scan_files(scan_dir: Path | None = None) -> pd.DataFrame:
    """Load all available phase36_daily_scan_YYYYMMDD.csv files.

    Returns a concatenated DataFrame with a 'source_file' column added.
    Returns an empty DataFrame with a warning if no files are found.
    """
    scan_dir = Path(scan_dir) if scan_dir else SCAN_DIR
    if not scan_dir.is_dir():
        logger.warning("Scan directory not found: %s", scan_dir)
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for path in sorted(scan_dir.glob("phase36_daily_scan_????????.csv")):
        m = _SCAN_FILE_PATTERN.search(path.name)
        if not m:
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
            df["source_file"] = path.name
            df["data_label"] = LABEL_RECONSTRUCTED
            frames.append(df)
        except Exception as exc:
            logger.warning("Failed to load scan file %s: %s", path, exc)

    if not frames:
        logger.warning(
            "No phase36 daily scan files found in %s — returning empty DataFrame", scan_dir
        )
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "Loaded %d scan files → %d rows from %s",
        len(frames),
        len(combined),
        scan_dir,
    )
    return combined


def load_ohlcv_panel(ohlcv_path: Path | None = None) -> pd.DataFrame:
    """Load the OHLCV panel parquet.

    Returns an empty DataFrame with a warning if the file is missing.
    """
    ohlcv_path = Path(ohlcv_path) if ohlcv_path else OHLCV_PATH
    if not ohlcv_path.is_file():
        logger.warning("OHLCV panel not found at %s — returning empty DataFrame", ohlcv_path)
        return pd.DataFrame()
    try:
        df = pd.read_parquet(ohlcv_path)
        df["data_label"] = LABEL_RECONSTRUCTED
        logger.info("OHLCV panel loaded: %d rows from %s", len(df), ohlcv_path)
        return df
    except Exception as exc:
        logger.warning("Failed to load OHLCV panel %s: %s", ohlcv_path, exc)
        return pd.DataFrame()


def get_scan_date_range(scan_df: pd.DataFrame | None = None) -> tuple[str | None, str | None]:
    """Return (min_date, max_date) of as_of_date column in scan data.

    If scan_df is None, loads from default scan directory.
    Returns (None, None) if no data is available.
    """
    if scan_df is None:
        scan_df = load_scan_files()
    if scan_df.empty or "as_of_date" not in scan_df.columns:
        return (None, None)
    dates = pd.to_datetime(scan_df["as_of_date"], errors="coerce").dropna()
    if dates.empty:
        return (None, None)
    return (str(dates.min().date()), str(dates.max().date()))
