"""Registry of data sources and fallbacks for weekly ingestion."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from scripts.ingest.config import load_weekly_sources

_SOURCES: Optional[Dict[str, Any]] = None


def get_sources() -> Dict[str, Any]:
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = load_weekly_sources()
    return _SOURCES


def get_primary_source(bucket: str, metric: str) -> Optional[str]:
    """Return primary source name for a metric (e.g. 'fred', 'fireant')."""
    sources = get_sources()
    bucket_cfg = sources.get(bucket, {})
    metric_cfg = bucket_cfg.get(metric, {}) if isinstance(bucket_cfg, dict) else {}
    if isinstance(metric_cfg, dict):
        return metric_cfg.get("primary")
    return None


def get_fallback_source(bucket: str, metric: str) -> Optional[str]:
    """Return fallback source name for a metric."""
    sources = get_sources()
    bucket_cfg = sources.get(bucket, {})
    metric_cfg = bucket_cfg.get(metric, {}) if isinstance(bucket_cfg, dict) else {}
    if isinstance(metric_cfg, dict):
        return metric_cfg.get("fallback")
    return None


def research_intake_path() -> Path:
    """Path to research intake folder from config."""
    from scripts.ingest.config import REPO, INPUTS_RESEARCH
    sources = get_sources()
    ri = sources.get("research_intake", {})
    sub = ri.get("path", "inputs/research") if isinstance(ri, dict) else "inputs/research"
    return REPO / sub if not Path(sub).is_absolute() else Path(sub)
