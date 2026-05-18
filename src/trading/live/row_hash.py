"""Deterministic row hashes for manual-review stale approval guard."""
from __future__ import annotations

import hashlib
from typing import Any, Union

import pandas as pd


def make_manual_review_key(asof_date: str, symbol: str, source_scan_row_id: Any) -> str:
    return f"{asof_date[:10]}|{str(symbol).upper()}|{source_scan_row_id}"


def compute_row_hash(row: Union[pd.Series, dict]) -> str:
    """Hash material execution fields; any change invalidates prior approval."""
    if isinstance(row, pd.Series):
        g = row.get
    else:
        g = row.get

    fields = [
        str(g("date", ""))[:10],
        str(g("symbol", "")).upper(),
        str(g("strategy_classification", "")),
        str(g("reason_code", "") or g("final_action", "")),
        str(g("action", "")),
        str(g("side", "")),
        str(g("limit_price", "")),
        str(g("quantity_estimate", "")),
        str(g("execution_value_VND", "") or g("value_VND", "")),
        str(g("risk_flags", "")),
        str(g("source_scan_row_id", "")),
    ]
    raw = "|".join(fields)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
