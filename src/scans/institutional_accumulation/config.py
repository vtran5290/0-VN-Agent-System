from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


REPO = Path(__file__).resolve().parents[3]
DEFAULT_STOCKS_DIR = REPO / "data" / "stocks"
DEFAULT_BENCHMARK_DIR = REPO / "data" / "benchmark"
DEFAULT_BENCHMARK = "VNINDEX"
DEFAULT_OUTPUT_DIR = REPO / "outputs" / "scans"
SMART_MONEY_MONTHLY_DIR = REPO / "data" / "smart_money" / "monthly"
SMART_MONEY_PRIORS_PATH = REPO / "data" / "smart_money" / "priors" / "apr2026_default_priors.json"
SECTOR_MAP_PATH = REPO / "data" / "research" / "level4_stock_scan_adv2b_all.csv"

EX_VIN_SYMBOLS = ["VIC", "VHM", "VRE"]
VIN_DISTORTION_SYMBOLS = ["VIC", "VHM", "VRE", "VPL"]

FRAGILE_REGIME_LABEL = "fragile_uptrend_narrow_leadership"

# Score weights (positive blocks sum to 1.0; risk is penalty)
WEIGHT_CONTEXT = 0.18
WEIGHT_MONEY_FLOW = 0.38
WEIGHT_PRICE_STRUCTURE = 0.28
WEIGHT_RISK_PENALTY = 0.16

# Tier 1 — strict (all regimes)
TIER1_MIN_SCORE = 72.0
TIER1_MIN_MONEY_FLOW = 55.0
TIER1_MAX_RISK = 35.0

# Tier 2/3 — default
TIER2_MIN_SCORE = 58.0
TIER3_MIN_SCORE = 42.0

# Tier 2/3 — fragile narrow-leadership regime (lower fixed floors)
TIER2_MIN_SCORE_FRAGILE = 52.0
TIER3_MIN_SCORE_FRAGILE = 38.0

# Percentile overlay (deterministic; among liquid names with score floor)
TIER2_PCTL_FLOOR = 0.78
TIER2_PCTL_MIN_SCORE = 46.0
TIER2_PCTL_MIN_MONEY = 45.0
TIER2_PCTL_MAX_RISK = 45.0
TIER3_PCTL_FLOOR = 0.62
TIER3_PCTL_MIN_SCORE = 40.0
TIER3_PCTL_MAX_RISK = 50.0

# Consensus research names: minimum Tier 3 in fragile regime when flow not terrible
TIER3_CONSENSUS_MIN_SCORE = 40.0
TIER3_CONSENSUS_MIN_MONEY = 42.0

# Vingroup distortion thresholds
VIN_RS_STRONG = 0.08
VIN_EXTENSION_PCT = 12.0
VIN_CMF_WEEKLY_WEAK = 0.03

# Money-flow redundancy check
MF_CORR_WARN_THRESHOLD = 0.90

# Emerging accumulation (outside fund disclosure tags)
EMERGING_MIN_MONEY_FLOW = 48.0
EMERGING_MAX_RISK_PENALTY = 30.0
TOP_N_EXPORT = 80
COMPACT_TIER3_NEAR_MISS = 5

# ETF / open-fund vehicles — excluded from accumulation candidates
ETF_EXCLUSION_SECTORS = frozenset({"Quỹ mở"})
ETF_EXCLUSION_SYMBOLS = frozenset({"E1VFVN30"})


@dataclass
class ScanConfig:
    scan_date: Optional[str] = None
    stocks_dir: Path = field(default_factory=lambda: DEFAULT_STOCKS_DIR)
    benchmark_dir: Path = field(default_factory=lambda: DEFAULT_BENCHMARK_DIR)
    benchmark_ticker: str = DEFAULT_BENCHMARK
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    smart_money_month: Optional[str] = None
    min_history_days: int = 120
    min_adv20_vnd: float = 2_000_000_000.0
    min_adv50_vnd: float = 1_500_000_000.0
    watchlist_path: Optional[Path] = None
    symbols: Optional[List[str]] = None
    max_rejected_export: int = 80
    include_rejected_near_miss: bool = True
    near_miss_min_score: float = 38.0
    emerging_min_money_flow: float = EMERGING_MIN_MONEY_FLOW
    emerging_max_risk_penalty: float = EMERGING_MAX_RISK_PENALTY
    top_n_export: int = TOP_N_EXPORT
