"""
P1 configuration: eligible groups, thresholds, constants.
All grouping layers: L3, flag_bucket, theme_tag.
"""
from pathlib import Path

from .config import OUTPUT_DIR, SECTOR_MAP_PATH, FORWARD_HORIZONS, TRAIN_END, TEST_START

# ── P1 eligibility gates ──────────────────────────────────────────────────────
P1_MIN_SYMBOLS    = 5
P1_MIN_EVENTS     = 5
P1_MIN_STOCK_TURNS = 50   # preferred (not hard filter for grouping inclusion)

# ── Turn thresholds ───────────────────────────────────────────────────────────
P1_TURN_THRESHOLDS = [
    {"name": "primary_40_35", "enter": 0.40, "exit": 0.35},
    {"name": "ew_30_25",      "enter": 0.30, "exit": 0.25},
    {"name": "ew_50_45",      "enter": 0.50, "exit": 0.45},
]

# ── Gate thresholds for filter-value tests ────────────────────────────────────
P1_GATE_THRESHOLDS      = [0.40, 0.50]
P1_RECENT_TURN_WINDOWS  = [10, 20]   # "group turned in last N sessions"
P1_HORIZONS             = FORWARD_HORIZONS   # [20, 60, 120]

# ── Flag bucket definitions (name -> column in sector_map) ───────────────────
P1_FLAG_BUCKETS = [
    ("bank",            "is_bank"),
    ("broker",          "is_broker"),
    ("real_estate",     "is_real_estate"),
    ("construction",    "is_construction"),
    ("industrial_park", "is_industrial_park"),
    ("oil_gas",         "is_oil_gas"),
    ("power",           "is_power"),
    ("steel",           "is_steel"),
    ("export",          "is_export"),
    ("high_beta",       "is_high_beta"),
    ("state_owned",     "is_state_owned"),
    ("retail",          "is_retail"),
]

# ── Output paths ──────────────────────────────────────────────────────────────
P1_GROUP_BREADTH_CACHE      = OUTPUT_DIR / "p1_group_breadth_panels.parquet"
P1_GROUP_TURN_EVENTS_PATH   = OUTPUT_DIR / "group_breadth_turn_events.csv"
P1_LEAD_LAG_PATH            = OUTPUT_DIR / "group_stock_lead_lag_summary.csv"
P1_FILTER_VALUE_PATH        = OUTPUT_DIR / "group_filter_value_ablation.csv"
P1_A3_REPLAY_PATH           = OUTPUT_DIR / "a3_group_gate_replay.csv"
P1_LEADER_PATH              = OUTPUT_DIR / "group_leader_follower_classification.csv"
P1_REGIME_STABILITY_PATH    = OUTPUT_DIR / "group_regime_stability_summary.csv"
P1_RANKING_PROPOSAL_PATH    = OUTPUT_DIR / "GROUP_BREADTH_RANKING_FEATURE_PROPOSAL.md"
P1_IMPL_REPORT_PATH         = OUTPUT_DIR / "P1_IMPLEMENTATION_REPORT.md"
