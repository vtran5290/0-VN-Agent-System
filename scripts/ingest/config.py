"""Ingestion config: paths, thresholds, confidence rules."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

# Repo root relative to this file
REPO = Path(__file__).resolve().parents[2]

# Paths
DATA_RAW = REPO / "data" / "raw"
DATA_PROCESSED = REPO / "data" / "processed"
DATA_CACHE = REPO / "data" / "cache"
DATA_EXAMPLES = REPO / "data" / "examples"
CONFIGS = REPO / "configs"
INPUTS_RESEARCH = REPO / "inputs" / "research"
MANUAL_OVERRIDES = REPO / "inputs" / "manual_overrides.json"
WEEKLY_SOURCES_YML = CONFIGS / "weekly_sources.yml"
DECISION_WEEKLY_JSON = REPO / "data" / "decision" / "weekly_report.json"
SCHEMA_PATH = REPO / "schemas" / "weekly_report.schema.json"
LOGS_DIR = REPO / "logs"

# Stale thresholds (days)
STALE_REPORT_DAYS = 7
STALE_MARKET_DAYS = 3

# Confidence: required metric list (missing these downgrades confidence)
REQUIRED_METRICS_GLOBAL = ["ust_2y", "ust_10y", "dxy"]
REQUIRED_METRICS_MARKET = ["vnindex_level", "vn30_level"]

# Confidence score: start 1.0, subtract per missing/stale
PENALTY_MISSING_REQUIRED = 0.15
PENALTY_STALE_REPORT = 0.1
PENALTY_MANUAL_FALLBACK = 0.05

# Bounds for confidence label
CONFIDENCE_HIGH_MIN = 0.75
CONFIDENCE_MEDIUM_MIN = 0.5


def load_weekly_sources() -> Dict[str, Any]:
    """Load configs/weekly_sources.yml."""
    if not WEEKLY_SOURCES_YML.exists():
        return {}
    try:
        with open(WEEKLY_SOURCES_YML, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}
