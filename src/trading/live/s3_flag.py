"""Strict S3 shadow flag checks — must be explicitly true."""
from __future__ import annotations

from typing import Any, Optional, Tuple


def s3_no_real_order_flag_explicit(value: Any) -> bool:
    if value is True or value == "True" or value == "true" or value == 1 or value == "1":
        return True
    return False


def s3_shadow_block_reason(value: Any) -> Optional[str]:
    """Return diagnostic reason if shadow tracking must not proceed."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return "missing_no_real_order_flag"
    if s3_no_real_order_flag_explicit(value):
        return None
    return "false_no_real_order_flag"
