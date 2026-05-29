"""Full-history data loader for Institutional Accumulation backtest.

Loads ta_ohlcv_panel.parquet as primary source (2017-05-18 → 2026-05-27)
and supplements with minervini_backtest/data/raw/*.csv for pre-2017 history.

RESEARCH_ONLY_NOT_PRODUCTION — no A3/S3/OMS/final_action/DNSE touched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.scans.institutional_accumulation.config import REPO

PARQUET_PATH = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
MINERVINI_RAW_DIR = REPO / "minervini_backtest" / "data" / "raw"
VNINDEX_PATH = MINERVINI_RAW_DIR / "VNINDEX.csv"

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

# Non-stock tickers to skip when discovering symbols from minervini raw
_BENCH_TICKERS = frozenset({"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"})


def _normalize_ohlcv(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalize a per-symbol OHLCV DataFrame to the canonical format.

    Canonical: date(str/datetime), open, high, low, close, volume, [value].
    price units: thousand-VND (same as data/stocks CSVs).
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].dt.normalize()
    # Ensure required columns
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = float("nan")
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    df["_source"] = source
    return df


class ParquetSymbolLoader:
    """In-memory loader backed by ta_ohlcv_panel.parquet + minervini raw.

    Usage:
        loader = ParquetSymbolLoader.build()
        df = loader("HPG")   # returns OHLCV DataFrame or None
    """

    def __init__(self, data: Dict[str, pd.DataFrame]) -> None:
        self._data = data  # symbol.upper() → normalized DataFrame

    @classmethod
    def build(
        cls,
        parquet_path: Path = PARQUET_PATH,
        aux_dir: Path = MINERVINI_RAW_DIR,
        verbose: bool = False,
    ) -> "ParquetSymbolLoader":
        """Load parquet (primary) and merge in any older minervini raw CSVs."""
        data: Dict[str, pd.DataFrame] = {}

        # 1. Load parquet -------------------------------------------------------
        if parquet_path.is_file():
            if verbose:
                print(f"[fh_data_loader] Loading parquet: {parquet_path}")
            raw = pd.read_parquet(parquet_path)
            sym_col = "symbol" if "symbol" in raw.columns else "ticker"
            for sym, g in raw.groupby(sym_col):
                sym = str(sym).upper()
                # NOTE: The parquet 'value' column has inconsistent units across
                # time periods (sometimes kVND-scaled, sometimes VND-scaled).
                # Drop it so that downstream scoring code (filters.py _value_vnd_series)
                # computes value = close × volume and applies the correct 1000× scale.
                cols = ["date", "open", "high", "low", "close", "volume"]
                g2 = g[cols].copy()
                g2 = g2.loc[:, ~g2.columns.duplicated()]
                data[sym] = _normalize_ohlcv(g2, "parquet")
            if verbose:
                print(f"[fh_data_loader] Parquet: {len(data)} symbols loaded")

        # 2. Supplement with minervini raw CSVs ----------------------------------
        if aux_dir.is_dir():
            for csv_path in sorted(aux_dir.glob("*.csv")):
                sym = csv_path.stem.upper()
                if sym in _BENCH_TICKERS:
                    continue
                try:
                    df_raw = pd.read_csv(csv_path)
                    df_norm = _normalize_ohlcv(df_raw, "minervini_raw")
                except Exception:
                    continue
                if df_norm.empty:
                    continue
                if sym in data:
                    # Only prepend rows that are BEFORE the parquet's earliest date
                    parquet_start = data[sym]["date"].min()
                    older = df_norm[df_norm["date"] < parquet_start].copy()
                    if not older.empty:
                        merged = pd.concat([older, data[sym]], ignore_index=True)
                        merged = merged.sort_values("date").drop_duplicates("date").reset_index(drop=True)
                        data[sym] = merged
                else:
                    data[sym] = df_norm

        if verbose:
            print(f"[fh_data_loader] Final: {len(data)} symbols (parquet+aux)")
        return cls(data)

    def __call__(self, symbol: str) -> Optional[pd.DataFrame]:
        """Return OHLCV DataFrame for *symbol*, or None if not found."""
        return self._data.get(symbol.upper())

    @property
    def symbols(self) -> list[str]:
        return sorted(self._data.keys())

    def coverage_summary(self) -> pd.DataFrame:
        """Return a DataFrame with first_date, last_date, bar_count per symbol."""
        rows = []
        for sym, df in self._data.items():
            rows.append(
                {
                    "symbol": sym,
                    "first_date": df["date"].min(),
                    "last_date": df["date"].max(),
                    "bar_count": len(df),
                    "source": df["_source"].iloc[0] if "_source" in df.columns else "unknown",
                }
            )
        return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def load_fh_benchmark() -> pd.DataFrame:
    """Load VNINDEX benchmark from minervini_backtest/data/raw/VNINDEX.csv."""
    if not VNINDEX_PATH.is_file():
        raise FileNotFoundError(f"VNINDEX not found at {VNINDEX_PATH}")
    df = pd.read_csv(VNINDEX_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def discover_fh_symbols(loader: ParquetSymbolLoader) -> list[str]:
    """Return sorted list of all symbols available in the full-history loader."""
    skip = frozenset({"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX", "E1VFVN30"})
    return [s for s in loader.symbols if s not in skip]
