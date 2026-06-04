"""
Sector map coverage audit → sector_l4_coverage_audit.csv
Test D01 / D02: unknown sensitivity and small-sector diagnostics.
"""
from __future__ import annotations
import logging

import pandas as pd

from .config import OUTPUT_DIR, MIN_L4_SYMBOLS, MIN_HISTORY_BARS, VIN_GROUP_SYMBOLS

log = logging.getLogger(__name__)


def build_coverage_audit(
    sector_map: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge sector map with panel availability stats.
    Returns symbol-level audit table.
    """
    panel_stats = (
        panel.groupby("symbol")["date"]
        .agg(first_date="min", last_date="max", n_bars="count")
        .reset_index()
    )
    panel_stats["has_ohlcv"] = 1

    audit = sector_map.merge(panel_stats, on="symbol", how="left")
    audit["has_ohlcv"] = audit["has_ohlcv"].fillna(0).astype(int)
    audit["n_bars"] = audit["n_bars"].fillna(0).astype(int)

    audit["is_unknown"] = (
        audit["sector_l4"].isna() | (audit["sector_l4"].str.strip() == "Unknown")
    ).astype(int)
    audit["is_vin_group"] = audit["symbol"].isin(VIN_GROUP_SYMBOLS).astype(int)

    # Sector size (n eligible per L4)
    l4_counts = (
        audit[audit["is_unknown"] == 0]
        .groupby("sector_l4")["symbol"]
        .transform("count")
    )
    audit["n_symbols_in_l4"] = l4_counts.fillna(0).astype(int)

    # Exclusion reasons
    def _exclusion(row):
        reasons = []
        if row["is_unknown"]:
            reasons.append("unknown_l4")
        if row["has_ohlcv"] == 0:
            reasons.append("no_ohlcv")
        if row["n_bars"] < MIN_HISTORY_BARS and row["has_ohlcv"]:
            reasons.append("n_bars_lt_min")
        if row["n_symbols_in_l4"] < MIN_L4_SYMBOLS and not row["is_unknown"]:
            reasons.append("tiny_l4")
        if row["duplicate_symbol_flag"]:
            reasons.append("duplicate")
        return ",".join(reasons) if reasons else ""

    audit["exclusion_reason"] = audit.apply(_exclusion, axis=1)
    audit["include_headline_flag"] = (audit["exclusion_reason"] == "").astype(int)

    out_path = OUTPUT_DIR / "sector_l4_coverage_audit.csv"
    audit.to_csv(out_path, index=False)
    log.info("Coverage audit: %d symbols, %d excluded, saved to %s",
             len(audit), (audit["include_headline_flag"] == 0).sum(), out_path)
    return audit


def small_sector_diagnostics(audit: pd.DataFrame) -> pd.DataFrame:
    """Bucket sectors by symbol count → small_sector_diagnostics.csv"""
    sector_counts = (
        audit[audit["is_unknown"] == 0]
        .groupby("sector_l4")["symbol"]
        .agg(n_symbols="count")
        .reset_index()
    )
    sector_counts["size_bucket"] = pd.cut(
        sector_counts["n_symbols"],
        bins=[0, 2, 4, 9, 999],
        labels=["n_lt_3", "n_3_4", "n_5_9", "n_ge_10"],
    )
    out_path = OUTPUT_DIR / "small_sector_diagnostics.csv"
    sector_counts.to_csv(out_path, index=False)
    log.info("Small sector diagnostics saved to %s", out_path)
    return sector_counts


def unknown_coverage_sensitivity(
    metrics_with_unknown: pd.DataFrame,
    metrics_without_unknown: pd.DataFrame,
    key_cols: list[str],
) -> pd.DataFrame:
    """Compare headline metrics with vs without Unknown sectors."""
    merged = metrics_with_unknown[key_cols].copy()
    merged.columns = [f"{c}_with_unknown" for c in key_cols]
    merged2 = metrics_without_unknown[key_cols].copy()
    merged2.columns = [f"{c}_without_unknown" for c in key_cols]
    result = pd.concat([merged, merged2], axis=1)
    for c in key_cols:
        result[f"delta_{c}"] = (
            result[f"{c}_with_unknown"] - result[f"{c}_without_unknown"]
        )
    out_path = OUTPUT_DIR / "unknown_coverage_sensitivity.csv"
    result.to_csv(out_path, index=False)
    return result
