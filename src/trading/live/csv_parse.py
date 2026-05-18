"""Robust parsing for boolean values loaded from CSV / JSON strings."""
from __future__ import annotations

from typing import Any

import pandas as pd

_TRUE = frozenset({"true", "1", "yes", "y"})
_FALSE = frozenset({"false", "0", "no", "n", ""})


def parse_csv_bool(value: Any) -> bool:
    """True only for explicit truthy tokens; False for False/0/no/empty/NaN."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return False
        return value == 1
    s = str(value).strip()
    if not s or s.lower() in _FALSE:
        return False
    if s.lower() in _TRUE:
        return True
    return False
