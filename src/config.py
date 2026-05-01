from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class RSEngineConfig:
    """Central configuration for VN RS engine."""

    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parents[1]
    )

    # Directories
    data_stocks_dir: Path = field(init=False)
    data_benchmark_dir: Path = field(init=False)
    output_dir: Path = field(init=False)

    # Benchmark / scoring
    benchmark_ticker: str = "VNINDEX"
    scoring_mode: str = "tactical_vn"  # or "position_vn"

    # Liquidity / quality filters (VND units)
    min_price: float = 10_000.0
    min_median_value_20d: float = 2_000_000_000.0
    min_avg_value_50d: float = 5_000_000_000.0
    min_history_days: int = 260

    # Trend template thresholds
    near_high_threshold: float = 0.80  # 80% of 52w high
    off_low_threshold: float = 1.30  # 130% of 52w low

    # Optional universe controls
    exclude_tickers: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.data_stocks_dir = self.project_root / "data" / "stocks"
        self.data_benchmark_dir = self.project_root / "data" / "benchmark"
        self.output_dir = self.project_root / "output"

        # Normalize exclusions to upper-case tickers
        self.exclude_tickers = [t.strip().upper() for t in self.exclude_tickers]

