"""
P0.1 Task 1 — Create research-enriched A3 ledger.
Joins A3 trade ledger with sector_l4 map. Research-only output.
Original ledger is NEVER modified.
Output: data/research/sector_l4_causality/a3_ledger_enriched_with_sector_l4.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .config import A3_LEDGER_PATH, SECTOR_MAP_PATH, OUTPUT_DIR, VIN_GROUP_SYMBOLS

log = logging.getLogger(__name__)

ENRICHED_LEDGER_PATH = OUTPUT_DIR / "a3_ledger_enriched_with_sector_l4.csv"


def _sector_size_bucket(n: int, is_unknown: bool) -> str:
    if is_unknown:
        return "unknown"
    if n == 1:
        return "n1"
    if n == 2:
        return "n2"
    if n <= 4:
        return "n3_4"
    return "n_ge_5"


def build_enriched_ledger(force_rebuild: bool = False) -> pd.DataFrame:
    """
    Left-join A3 ledger with sector map. Add sector metadata columns.
    Cached; pass force_rebuild=True to regenerate.
    """
    if ENRICHED_LEDGER_PATH.exists() and not force_rebuild:
        log.info("Loading cached enriched ledger from %s", ENRICHED_LEDGER_PATH)
        return pd.read_csv(ENRICHED_LEDGER_PATH)

    if not A3_LEDGER_PATH.exists():
        raise FileNotFoundError(f"A3 ledger not found: {A3_LEDGER_PATH}")
    if not SECTOR_MAP_PATH.exists():
        raise FileNotFoundError(f"Sector map not found: {SECTOR_MAP_PATH}")

    ledger = pd.read_csv(A3_LEDGER_PATH)
    ledger.columns = ledger.columns.str.strip().str.lower()
    log.info("Loaded A3 ledger: %d trades, columns: %s", len(ledger), list(ledger.columns))

    smap = pd.read_csv(SECTOR_MAP_PATH)
    smap.columns = smap.columns.str.strip().str.lower()
    log.info("Loaded sector map: %d symbols", len(smap))

    # Compute n_symbols per L4 sector (from map, not from OHLCV panel)
    l4_counts = (
        smap[smap["sector_l4"] != "Unknown"]
        .groupby("sector_l4")["symbol"]
        .nunique()
        .rename("n_symbols_in_l4")
        .reset_index()
    )

    # Build enrichment join table: symbol -> sector metadata
    enrich_cols = ["symbol", "sector_l4", "sector_l3", "is_vin_group"]
    # Add optional columns if present
    for col in ["sector_l1", "sector_l2", "theme_tags", "confidence"]:
        if col in smap.columns:
            enrich_cols.append(col)

    enrich = smap[enrich_cols].drop_duplicates("symbol").copy()
    enrich = enrich.merge(l4_counts, on="sector_l4", how="left")
    enrich["n_symbols_in_l4"] = enrich["n_symbols_in_l4"].fillna(0).astype(int)

    # Derive boolean flags
    enrich["is_unknown"] = (enrich["sector_l4"] == "Unknown").astype(int)
    enrich["sector_size_bucket"] = enrich.apply(
        lambda r: _sector_size_bucket(r["n_symbols_in_l4"], bool(r["is_unknown"])),
        axis=1,
    )

    # Detect symbol column in ledger
    sym_col = next((c for c in ledger.columns if c in ("symbol", "ticker", "stock")), None)
    if sym_col is None:
        raise ValueError(f"Cannot find symbol column in ledger. Columns: {list(ledger.columns)}")
    if sym_col != "symbol":
        ledger = ledger.rename(columns={sym_col: "symbol"})

    # Left join: every ledger trade keeps its row; sector info added from map
    result = ledger.merge(
        enrich,
        on="symbol",
        how="left",
        suffixes=("", "_map"),
    )

    # Fill unknowns for symbols absent from sector map
    for col in ["sector_l4", "sector_l3"]:
        if col in result.columns:
            result[col] = result[col].fillna("Unknown")
    result["is_unknown"]        = result["is_unknown"].fillna(1).astype(int)
    result["is_vin_group"]      = result["is_vin_group"].fillna(0).astype(int)
    result["n_symbols_in_l4"]   = result["n_symbols_in_l4"].fillna(0).astype(int)
    result["sector_size_bucket"] = result["sector_size_bucket"].fillna("unknown")

    log.info(
        "Enriched ledger: %d trades, %d unique symbols, sector_l4 distribution:\n%s",
        len(result),
        result["symbol"].nunique(),
        result["sector_l4"].value_counts().head(10).to_string(),
    )

    result.to_csv(ENRICHED_LEDGER_PATH, index=False)
    log.info("Enriched ledger saved to %s", ENRICHED_LEDGER_PATH)
    return result
