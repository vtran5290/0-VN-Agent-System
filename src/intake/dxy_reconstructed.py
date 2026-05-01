"""
Reconstruct a DXY-like index from 6 FX spot rates using the ICE U.S. Dollar Index methodology shape:

  geometric weighted product with constant 50.14348112 and fixed weights on
  EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%.

This is a *derived / reconstructed* series from public spot inputs (here: FRED H.10 daily),
not a licensed ICE/NYSE official closing print. Label accordingly in any consumer.

Formula (standard textbook form; exponents = weights as decimals):

  DXY ≈ 50.14348112
        × EURUSD^(-0.576) × USDJPY^(0.136) × GBPUSD^(-0.119)
        × USDCAD^(0.091) × USDSEK^(0.042) × USDCHF^(0.036)

FRED H.10 series used (U.S. Fed), units aligned to the pairs above:
  DEXUSEU  — U.S. dollars per euro  → EURUSD
  DEXJPUS  — Japanese yen per U.S. dollar → USDJPY
  DEXUSUK  — U.S. dollars per GBP → GBPUSD
  DEXCAUS  — Canadian dollars per U.S. dollar → USDCAD
  DEXSDUS  — Swedish kronor per U.S. dollar → USDSEK
  DEXSZUS  — Swiss francs per U.S. dollar → USDCHF
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ICE_DXY_CONSTANT = 50.14348112

# FRED H.10 daily spot (Board of Governors H.10)
FRED_FX_SERIES = {
    "eurusd": "DEXUSEU",
    "usdjpy": "DEXJPUS",
    "gbpusd": "DEXUSUK",
    "usdcad": "DEXCAUS",
    "usdsek": "DEXSDUS",
    "usdchf": "DEXSZUS",
}


def compute_dxy_from_fx_rates(
    *,
    eurusd: float,
    usdjpy: float,
    gbpusd: float,
    usdcad: float,
    usdsek: float,
    usdchf: float,
) -> float:
    """Return reconstructed index level; raises ValueError if any input <= 0."""
    for name, v in (
        ("eurusd", eurusd),
        ("usdjpy", usdjpy),
        ("gbpusd", gbpusd),
        ("usdcad", usdcad),
        ("usdsek", usdsek),
        ("usdchf", usdchf),
    ):
        if v is None or v <= 0:
            raise ValueError(f"invalid_fx_rate:{name}={v!r}")
    return float(
        ICE_DXY_CONSTANT
        * (eurusd ** -0.576)
        * (usdjpy ** 0.136)
        * (gbpusd ** -0.119)
        * (usdcad ** 0.091)
        * (usdsek ** 0.042)
        * (usdchf ** 0.036)
    )


def _aligned_fx_rates_fred(api_key: str, end: str, days_back: int = 21) -> Optional[Tuple[str, Dict[str, float]]]:
    """Latest calendar date on which all 6 FRED series have a positive observation."""
    from src.intake.fred_api import get_observations

    per_key: Dict[str, Dict[str, float]] = {}
    for k, sid in FRED_FX_SERIES.items():
        obs = get_observations(sid, api_key, end, days_back=days_back, limit=40)
        per_key[k] = {d: float(v) for d, v in obs if v is not None and float(v) > 0}

    if not all(per_key.values()):
        return None

    common_dates = set.intersection(*(set(per_key[k]) for k in FRED_FX_SERIES))
    if not common_dates:
        return None
    for d in sorted(common_dates, reverse=True):
        vals = {k: per_key[k][d] for k in FRED_FX_SERIES}
        if all(vals[k] > 0 for k in vals):
            return d, vals
    return None


def fetch_dxy_reconstructed_fred(api_key: str, end: str) -> Optional[Dict[str, Any]]:
    """
    Return dict with value, value_date, fx_snapshot, source detail; None if inputs cannot align.
    """
    try:
        aligned = _aligned_fx_rates_fred(api_key, end)
        if not aligned:
            return None
        d_str, fx = aligned
        level = round(
            compute_dxy_from_fx_rates(
                eurusd=fx["eurusd"],
                usdjpy=fx["usdjpy"],
                gbpusd=fx["gbpusd"],
                usdcad=fx["usdcad"],
                usdsek=fx["usdsek"],
                usdchf=fx["usdchf"],
            ),
            4,
        )
        return {
            "dxy_reconstructed": level,
            "dxy_reconstructed_value_date": d_str,
            "fx_snapshot": fx,
            "fred_series": dict(FRED_FX_SERIES),
            "method": "ice_weighted_geometric_fred_h10",
        }
    except Exception as e:
        logger.warning("dxy_reconstructed: %s", e)
        return None


__all__ = [
    "ICE_DXY_CONSTANT",
    "FRED_FX_SERIES",
    "compute_dxy_from_fx_rates",
    "fetch_dxy_reconstructed_fred",
]
