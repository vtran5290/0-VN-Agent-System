"""Compatibility shim — canonical implementation lives in scripts.ingest.scan_ssot."""
from __future__ import annotations

from scripts.ingest.scan_ssot import (  # noqa: F401
    OPERATOR_ACTION_MAP,
    load_scan_lookup_all,
    load_scan_rows,
    map_operator_action,
    resolve_scan_path,
    watchlist_bucket,
)

__all__ = [
    "OPERATOR_ACTION_MAP",
    "resolve_scan_path",
    "load_scan_rows",
    "load_scan_lookup_all",
    "map_operator_action",
    "watchlist_bucket",
]
