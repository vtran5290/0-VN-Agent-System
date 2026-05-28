from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from src.research.institutional_accumulation_backtest.data_loader import (
    load_benchmark_df,
    load_sector_map,
    resolve_sources,
)
from src.research.institutional_accumulation_backtest.panel import PanelConfig, build_panel
from src.research.institutional_accumulation_backtest.regimes import build_benchmark_regimes
from src.research.institutional_accumulation_backtest.schema import ContextMode, VinPolicy


def build_panel_chunk_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Process-pool worker: build one symbol chunk and write parquet part."""
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="src.scans.institutional_accumulation.indicators")
    sources = resolve_sources()
    benchmark = load_benchmark_df(Path(payload["benchmark_path"]))
    benchmark = benchmark[
        (pd.to_datetime(benchmark["date"]) >= pd.Timestamp(payload["start"]))
        & (pd.to_datetime(benchmark["date"]) <= pd.Timestamp(payload["end"]))
    ]
    sectors = load_sector_map(sources.sector_map_path)
    regimes = build_benchmark_regimes(benchmark)
    cfg = PanelConfig(
        start=payload["start"],
        end=payload["end"],
        cadence=payload["cadence"],
        context_mode=ContextMode.from_cli(payload["context_mode"]),
    )
    panel_chunk, notes = build_panel(
        cfg,
        benchmark=benchmark,
        benchmark_slice=benchmark,
        symbols=list(payload["symbols"]),
        stocks_dir=sources.stocks_dir,
        sector_map=sectors,
        regimes=regimes,
        vin_policy=VinPolicy(),
    )
    part = Path(payload["part_path"])
    part.parent.mkdir(parents=True, exist_ok=True)
    panel_chunk.to_parquet(part, index=False)
    return {
        "part_path": str(part),
        "symbols": list(payload["symbols"]),
        "rows": int(len(panel_chunk)),
        "blocked_columns": notes.get("blocked_columns", []),
    }
