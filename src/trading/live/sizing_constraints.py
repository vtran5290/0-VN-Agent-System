"""Live sizing constraints — Stage 2 ADV participation stub (advisory only)."""
from __future__ import annotations

import logging
from math import floor
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BOARD_LOT = 100
MAX_PARTICIPATION_PCT_OF_ADV = 0.10


def adv_participation_cap_qty(
    signal_qty: int,
    *,
    adv_10d_shares: float,
    board_lot: int = BOARD_LOT,
    max_participation_pct: float = MAX_PARTICIPATION_PCT_OF_ADV,
) -> Tuple[int, Optional[str]]:
    """Compute ADV participation cap qty. Stage 2: advisory only — not enforced."""
    if signal_qty <= 0 or adv_10d_shares <= 0 or board_lot <= 0:
        return signal_qty, None
    max_shares = floor(adv_10d_shares * max_participation_pct / board_lot) * board_lot
    if max_shares <= 0:
        return signal_qty, None
    capped = min(signal_qty, int(max_shares))
    if capped >= signal_qty:
        return signal_qty, None
    msg = (
        f"ADV participation advisory: signal_qty={signal_qty} would cap to {capped} "
        f"(10% of adv_10d={adv_10d_shares:.0f} shares, board_lot={board_lot}) "
        f"— NOT enforced in Stage 2"
    )
    return capped, msg


def log_adv_participation_advisory(
    symbol: str,
    signal_qty: int,
    adv50_vnd: float,
    price: float,
) -> None:
    """Log what ADV cap would apply; does not change order qty (Stage 2)."""
    if price <= 0 or adv50_vnd <= 0 or signal_qty <= 0:
        return
    adv_shares = adv50_vnd / price
    _, msg = adv_participation_cap_qty(signal_qty, adv_10d_shares=adv_shares)
    if msg:
        logger.info("ADV cap advisory [%s]: %s", symbol, msg)
