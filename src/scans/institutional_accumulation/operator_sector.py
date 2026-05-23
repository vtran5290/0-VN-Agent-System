"""Read-only sector label enrichment for operator display (does not alter scan scores)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .config import REPO

MASTER_SECTOR_MAP = REPO / "data" / "master" / "sector_map.csv"


def load_master_sector_fallback() -> Dict[str, str]:
    """symbol -> primary_sector from repo master map; empty if unavailable."""
    if not MASTER_SECTOR_MAP.is_file():
        return {}
    try:
        df = pd.read_csv(MASTER_SECTOR_MAP)
        if "symbol" not in df.columns:
            return {}
        col = "primary_sector" if "primary_sector" in df.columns else None
        if not col:
            return {}
        out: Dict[str, str] = {}
        for _, row in df.iterrows():
            sym = str(row.get("symbol") or "").upper()
            if sym and sym not in out:
                val = str(row.get(col) or "").strip()
                if val:
                    out[sym] = val
        return out
    except Exception:
        return {}


def enrich_sectors_for_display(df: pd.DataFrame, fallback: Dict[str, str] | None = None) -> pd.DataFrame:
    """
    Fill Unknown sector from master map only — never invent labels beyond that file.
    Adds `sector_display` column; original `sector` unchanged.
    """
    if df.empty or "sector" not in df.columns:
        return df
    fb = fallback if fallback is not None else load_master_sector_fallback()
    out = df.copy()
    disp: list[str] = []
    enriched_from_master = 0
    for _, row in out.iterrows():
        base = str(row.get("sector") or "Unknown")
        sym = str(row.get("ticker") or "").upper()
        if base != "Unknown":
            disp.append(base)
            continue
        alt = fb.get(sym)
        if alt:
            disp.append(alt)
            enriched_from_master += 1
        else:
            disp.append("Unknown")
    out["sector_display"] = disp
    out.attrs["sector_enriched_from_master"] = enriched_from_master
    return out
