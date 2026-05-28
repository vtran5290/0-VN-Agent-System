from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data_loader import load_ohlcv_csv
from src.scans.institutional_accumulation.config import (
    DEFAULT_BENCHMARK,
    DEFAULT_BENCHMARK_DIR,
    DEFAULT_STOCKS_DIR,
    REPO,
    SECTOR_MAP_PATH,
)
from src.scans.institutional_accumulation.filters import (
    discover_symbols,
    resolve_benchmark_path,
)


@dataclass
class DataSources:
    stocks_dir: Path
    benchmark_path: Path
    benchmark_ticker: str
    sector_map_path: Path
    source_label: str


def resolve_sources() -> DataSources:
    parquet = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
    source_label = "data/stocks/*.csv"
    if parquet.is_file():
        source_label = "data/stocks/*.csv (canonical), ta_ohlcv_panel.parquet (available)"
    benchmark_path = resolve_benchmark_path(DEFAULT_BENCHMARK_DIR, DEFAULT_BENCHMARK)
    return DataSources(
        stocks_dir=DEFAULT_STOCKS_DIR,
        benchmark_path=benchmark_path,
        benchmark_ticker=DEFAULT_BENCHMARK,
        sector_map_path=SECTOR_MAP_PATH,
        source_label=source_label,
    )


def load_symbol_df(stocks_dir: Path, ticker: str) -> pd.DataFrame | None:
    path = stocks_dir / f"{ticker}.csv"
    if not path.is_file():
        return None
    try:
        return load_ohlcv_csv(path)
    except Exception:
        return None


def load_benchmark_df(benchmark_path: Path) -> pd.DataFrame:
    return load_ohlcv_csv(benchmark_path)


def load_sector_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if "symbol" not in df.columns:
        return {}
    col = "proxy_industryName_l4" if "proxy_industryName_l4" in df.columns else "industryCode_l3"
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        sym = str(row.get("symbol") or "").upper()
        if sym and sym not in out:
            out[sym] = str(row.get(col) or "Unknown")
    return out


def discover_universe(stocks_dir: Path) -> list[str]:
    return discover_symbols(stocks_dir)
