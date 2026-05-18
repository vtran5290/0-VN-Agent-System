"""S3 shadow scan-row validation warnings (defense-in-depth; no order routing)."""
from __future__ import annotations

from typing import Any, Dict, List

from src.trading.live.s3_flag import s3_shadow_block_reason

S3_SHADOW_MAX_HOLD_BARS = 60


def validate_s3_shadow_contract(row: Dict[str, Any]) -> List[str]:
    """Return non-fatal warnings for S3 shadow rows. Does not alter final_action."""
    warnings: List[str] = []
    cls = str(row.get("strategy_classification") or row.get("s3_shadow_classification") or "")
    shadow = row.get("s3_shadow_candidate") in (True, "True", "true", 1, "1")
    if not shadow and "PAPER_TRADE_SHADOW" not in cls and "S3_SHADOW" not in cls:
        return warnings

    mh = row.get("s3_max_hold")
    if mh is not None and mh != "":
        try:
            if int(float(mh)) != S3_SHADOW_MAX_HOLD_BARS:
                warnings.append(f"S3_SHADOW_MAX_HOLD_NOT_60:{mh}")
        except (TypeError, ValueError):
            warnings.append(f"S3_SHADOW_MAX_HOLD_INVALID:{mh}")

    if row.get("s3_max_hold_60_flag") in (False, "False", "false", 0, "0"):
        warnings.append("S3_MAX_HOLD_60_FLAG_FALSE")

    bars = row.get("s3_bars_since")
    if bars is not None and bars != "":
        try:
            if int(float(bars)) > S3_SHADOW_MAX_HOLD_BARS:
                warnings.append("S3_SHADOW_EXPIRED_BARS_GT_60")
        except (TypeError, ValueError):
            warnings.append("S3_SHADOW_BARS_INVALID")

    block = s3_shadow_block_reason(row.get("s3_no_real_order_flag"))
    if block:
        warnings.append(f"S3_NO_REAL_ORDER_FLAG:{block}")

    return warnings
