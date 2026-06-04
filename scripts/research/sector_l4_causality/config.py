"""
All path constants and default run parameters.
All paths are relative to repo root (D:/V/0. VN Agent System).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# ── Input paths ──────────────────────────────────────────────────────────────
OHLCV_PANEL_PATH   = REPO_ROOT / "data/research/ema_cloud/ohlcv_panel_ext2012.parquet"
SECTOR_MAP_PATH    = REPO_ROOT / "data/research/portfolio_optimization/missing_work/sector_l4_map_coverage.csv"
A3_LEDGER_PATH     = REPO_ROOT / "data/research/portfolio_optimization/phase25/phase25a_dp_trade_ledger.csv"
VNINDEX_PARQUET    = REPO_ROOT / "data/fireant_ssot/ta_vnindex.parquet"
EX_VIN_SERIES_PATH = REPO_ROOT / "data/research/vnindex_ex_vin_daily_series.csv"
PRIOR_STRESS_PATH  = REPO_ROOT / "data/research/portfolio_optimization/missing_work/sector_l4_stress_rule_tests.csv"
VIN_BASELINE_DOC   = REPO_ROOT / "docs/research/VIN_EMA_CLOUD_BASELINE.md"

# ── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = REPO_ROOT / "data/research/sector_l4_causality"

# ── Cached intermediate files ─────────────────────────────────────────────────
ENRICHED_PANEL_CACHE  = OUTPUT_DIR / "stock_daily_cloud_panel.parquet"
SECTOR_PANEL_CACHE    = OUTPUT_DIR / "sector_l4_daily_panel.parquet"
STOCK_EVENTS_CACHE    = OUTPUT_DIR / "stock_cloud_turn_events.csv"
L4_EVENTS_CACHE       = OUTPUT_DIR / "sector_l4_turn_events.csv"

# ── Cloud parameters ─────────────────────────────────────────────────────────
EMA_FAST = 20
EMA_SLOW = 100

# ── VIN group — symbols to exclude for ex-VIN universe ───────────────────────
VIN_GROUP_SYMBOLS = {"VIC", "VHM", "VRE", "VPL"}

# ── Sector turn thresholds (primary and variants) ────────────────────────────
L4_TURN_THRESHOLDS = [
    {"name": "primary_40_35",     "enter": 0.40, "exit": 0.35},
    {"name": "ew_30_25",          "enter": 0.30, "exit": 0.25},
    {"name": "ew_50_45",          "enter": 0.50, "exit": 0.45},
    {"name": "liq_weight_40_35",  "enter": 0.40, "exit": 0.35, "use_liq_weight": True},
    {"name": "ex_vin_40_35",      "enter": 0.40, "exit": 0.35, "use_ex_vin": True},
]

# ── M0 regime thresholds ──────────────────────────────────────────────────────
M0_NORMAL_THRESHOLD    = 0.40   # breadth >= this → normal
M0_DEFENSIVE_THRESHOLD = 0.25   # breadth in [this, normal) → defensive; below → bear

# ── Filter-value ablation parameters ─────────────────────────────────────────
FORWARD_HORIZONS = [20, 60, 120]   # sessions
MIN_L4_SYMBOLS   = 5               # sectors with fewer symbols excluded from headline
MIN_HISTORY_BARS = 252 * 3         # ~3 years minimum stock history

# ── Placebo parameters ────────────────────────────────────────────────────────
PLACEBO_ITERS_P0 = 200
PLACEBO_ITERS_P1 = 500

# ── Structural break split ────────────────────────────────────────────────────
TRAIN_END   = "2019-12-31"
TEST_START  = "2020-01-01"
