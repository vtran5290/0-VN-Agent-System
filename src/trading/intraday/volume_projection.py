"""Volume projection for intraday preview (never used for official ADV50)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.trading.intraday.session import elapsed_tradable_fraction, load_session_config


def project_full_day_volume(
    current_volume: float,
    timestamp: datetime,
    *,
    exchange_calendar: Optional[Dict[str, Any]] = None,
    method: str = "session_time",
    min_elapsed_fraction: float = 0.15,
) -> Dict[str, Any]:
    """
    Project full-day volume from cumulative intraday volume.
    ADV50 must remain EOD-only; this is operator context only.
    """
    cfg = exchange_calendar or {}
    session_cfg = load_session_config(cfg)
    elapsed, phase = elapsed_tradable_fraction(timestamp, session_cfg=session_cfg)

    if current_volume is None or current_volume <= 0:
        return {
            "projected_volume": None,
            "volume_is_projected": False,
            "volume_projection_method": method,
            "volume_projection_confidence": "none",
            "elapsed_fraction": elapsed,
            "session_phase": phase,
        }

    if method == "no_projection":
        return {
            "projected_volume": float(current_volume),
            "volume_is_projected": False,
            "volume_projection_method": "no_projection",
            "volume_projection_confidence": "high",
            "elapsed_fraction": elapsed,
            "session_phase": phase,
        }

    if method == "historical_curve":
        # Placeholder: no intraday curve SSOT in repo yet — fall back to session_time
        method = "session_time"

    eff = max(min_elapsed_fraction, elapsed)
    if eff <= 0 or phase in ("CLOSED", "LUNCH_BREAK", "PRE_OPEN", "UNKNOWN"):
        return {
            "projected_volume": float(current_volume),
            "volume_is_projected": False,
            "volume_projection_method": "session_time",
            "volume_projection_confidence": "low",
            "elapsed_fraction": elapsed,
            "session_phase": phase,
        }

    projected = float(current_volume) / eff
    if elapsed < min_elapsed_fraction:
        conf = "low"
    elif elapsed < 0.45:
        conf = "medium"
    else:
        conf = "high"
    return {
        "projected_volume": projected,
        "volume_is_projected": True,
        "volume_projection_method": "session_time",
        "volume_projection_confidence": conf,
        "elapsed_fraction": elapsed,
        "session_phase": phase,
    }


def mode_volume_confidence_cap(mode: str) -> str:
    """Pre-lunch capped lower than pre-atc."""
    if mode == "pre-lunch":
        return "medium"
    if mode == "pre-atc":
        return "high"
    return "low"
