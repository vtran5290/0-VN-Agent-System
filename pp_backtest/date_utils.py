from __future__ import annotations

import glob
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


def detect_latest_raw_date(stocks_dir: Optional[Path] = None) -> Optional[str]:
    """
    Detect the latest available daily date from data/stocks/*.csv.

    Returns YYYY-MM-DD as string, or None if detection fails.
    """
    if stocks_dir is None:
        stocks_dir = Path(__file__).resolve().parent.parent / "data" / "stocks"

    pattern = str(stocks_dir / "*.csv")
    files = glob.glob(pattern)
    if not files:
        return None

    latest: Optional[datetime] = None
    for fp in files:
        try:
            # Read only the date column and last row
            df = pd.read_csv(fp, usecols=["date"])
            if df.empty:
                continue
            d = pd.to_datetime(df["date"].iloc[-1])
        except Exception:
            continue
        if latest is None or d > latest:
            latest = d

    if latest is None:
        return None
    return latest.strftime("%Y-%m-%d")


