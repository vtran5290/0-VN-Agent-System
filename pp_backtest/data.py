# pp_backtest/data.py — Fetch OHLCV (FireAnt from project / fallback vnstock)
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

# Allow import from repo root when run as: PYTHONPATH=<repo> python -m pp_backtest.run
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def fetch_ohlcv_fireant(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Uses project's src.intake.fireant_historical (same cache/API as weekly report).
    No token required for public HistoricalQuotes endpoint.
    Returns DataFrame with: date, open, high, low, close, volume (volume=0 if missing).
    """
    try:
        from src.intake.fireant_historical import fetch_historical
    except ImportError:
        raise RuntimeError(
            "Run from repo root with PYTHONPATH=. (e.g. python -m pp_backtest.run) "
            "or install this project so 'src.intake.fireant_historical' is importable."
        )

    rows = fetch_historical(symbol, start, end)
    if not rows:
        raise ValueError(f"No data for {symbol} from {start} to {end}")

    df = pd.DataFrame([
        {
            "date": r.d,
            "open": r.o,
            "high": r.h,
            "low": r.l,
            "close": r.c,
            "volume": r.v if r.v is not None else 0.0,
        }
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close", "volume"]]


def fetch_ohlcv_vnstock(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Optional fallback if you prefer vnstock (pip install vnstock).
    Adapt source/column names to your vnstock version if needed.
    """
    try:
        from vnstock import Vnstock
    except ImportError:
        raise RuntimeError("vnstock not installed. pip install vnstock")

    s = Vnstock().stock(symbol=symbol, source="TCBS")
    df = s.quote.history(start=start, end=end)
    col_map = {"time": "date"}
    df = df.rename(columns=col_map)
    if "date" not in df.columns and "Time" in df.columns:
        df = df.rename(columns={"Time": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    required = ["date", "open", "high", "low", "close", "volume"]
    for c in required:
        if c not in df.columns and c.capitalize() in df.columns:
            df[c] = df[c.capitalize()]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"vnstock DataFrame missing columns: {missing}")
    return df[required]
