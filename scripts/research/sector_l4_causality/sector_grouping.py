"""
P0.1 Task 4 — L3 / theme-bucket feasibility audit.
Compares coverage and signal density across grouping layers:
  L4 strict (n>=5), L4 diagnostic (n>=3), L3 (n>=5),
  theme_tags, flag-based buckets (bank, broker, real_estate, etc.).
Output: sector_grouping_feasibility_audit.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR

log = logging.getLogger(__name__)

# Flag columns present in sector map (subset — only check what exists)
FLAG_BUCKETS = [
    ("bank",           "is_bank"),
    ("broker",         "is_broker"),
    ("real_estate",    "is_real_estate"),
    ("industrial_park","is_industrial_park"),
    ("construction",   "is_construction"),
    ("steel",          "is_steel"),
    ("oil_gas",        "is_oil_gas"),
    ("power",          "is_power"),
    ("retail",         "is_retail"),
    ("export",         "is_export"),
    ("high_beta",      "is_high_beta"),
    ("state_owned",    "is_state_owned"),
]


def _count_stock_turns(stock_events: pd.DataFrame, symbols: set) -> int:
    if stock_events.empty:
        return 0
    return int(stock_events[stock_events["symbol"].isin(symbols)].shape[0])


def _count_theme_turns(
    panel: pd.DataFrame,
    symbols: set,
    enter: float = 0.40,
    exit_: float = 0.35,
) -> int:
    """
    Approximate group turn events for a custom symbol bucket using equal-weight breadth + hysteresis.
    Returns count of bullish turns (breadth crosses above enter from armed state).
    """
    grp = panel[panel["symbol"].isin(symbols)].copy()
    if grp.empty:
        return 0
    breadth = (
        grp.groupby("date")["cloud_bull_20_100"]
        .mean()
        .sort_index()
    )
    if breadth.empty:
        return 0

    armed = True
    count = 0
    for v in breadth.values:
        if armed and v >= enter:
            count += 1
            armed = False
        elif not armed and v < exit_:
            armed = True
    return count


def build_sector_grouping_feasibility(
    sector_map: pd.DataFrame,
    stock_events: pd.DataFrame,
    panel: pd.DataFrame,
    l4_events: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each candidate grouping layer, compute n_symbols, n_stock_cloud_turns,
    n_group_turn_events_40_35, eligible_for_p1, recommended_use.
    """
    smap = sector_map.copy()
    smap.columns = smap.columns.str.strip().str.lower()
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    stock_events = stock_events.copy()
    stock_events["date"] = pd.to_datetime(stock_events["date"])

    # Pre-compute L4 turn event counts
    l4_turn_counts = {}
    if l4_events is not None and not l4_events.empty:
        primary = l4_events[l4_events["definition"] == "primary_40_35"]
        l4_turn_counts = primary.groupby("sector_l4").size().to_dict()

    rows = []

    # ── Layer 1: L4 strict (n >= 5) ─────────────────────────────────────────
    l4_counts = (
        smap[smap["sector_l4"] != "Unknown"]
        .groupby("sector_l4")["symbol"]
        .apply(set)
    )
    for sector, syms in l4_counts.items():
        n = len(syms)
        n_turns = l4_turn_counts.get(sector, 0)
        eligible = n >= 5
        rows.append({
            "grouping_layer":            "L4_strict_n_ge_5",
            "group_name":                sector,
            "n_symbols":                 n,
            "n_stock_cloud_turns":       _count_stock_turns(stock_events, syms),
            "n_group_turn_events_40_35": n_turns,
            "eligible_for_p1":           int(eligible and n_turns >= 5),
            "recommended_use":           "primary_signal" if eligible else "exclude",
        })

    # ── Layer 2: L4 diagnostic (n >= 3) ──────────────────────────────────────
    for sector, syms in l4_counts.items():
        n = len(syms)
        n_turns = l4_turn_counts.get(sector, 0)
        eligible = 3 <= n < 5
        rows.append({
            "grouping_layer":            "L4_diagnostic_n_ge_3",
            "group_name":                sector,
            "n_symbols":                 n,
            "n_stock_cloud_turns":       _count_stock_turns(stock_events, syms),
            "n_group_turn_events_40_35": n_turns,
            "eligible_for_p1":           int(eligible and n_turns >= 3),
            "recommended_use":           "descriptive_only" if eligible else "same_as_strict_layer",
        })

    # ── Layer 3: L3 groupings (n >= 5) ───────────────────────────────────────
    l3_groups = (
        smap[smap["sector_l3"] != "Unknown"]
        .groupby("sector_l3")["symbol"]
        .apply(set)
    )
    for l3, syms in l3_groups.items():
        n = len(syms)
        n_turns = _count_theme_turns(panel, syms)
        eligible = n >= 5
        rows.append({
            "grouping_layer":            "L3_n_ge_5",
            "group_name":                l3,
            "n_symbols":                 n,
            "n_stock_cloud_turns":       _count_stock_turns(stock_events, syms),
            "n_group_turn_events_40_35": n_turns,
            "eligible_for_p1":           int(eligible and n_turns >= 5),
            "recommended_use":           "p1_candidate" if eligible and n_turns >= 5 else "low_coverage",
        })

    # ── Layer 4: Theme tags ───────────────────────────────────────────────────
    if "theme_tags" in smap.columns:
        # Explode comma-separated tags
        theme_df = smap[smap["theme_tags"].notna()].copy()
        theme_df["_tag"] = theme_df["theme_tags"].str.split(",")
        theme_exploded = theme_df.explode("_tag")
        theme_exploded["_tag"] = theme_exploded["_tag"].str.strip()
        theme_groups = theme_exploded.groupby("_tag")["symbol"].apply(set)
        for tag, syms in theme_groups.items():
            if not tag or pd.isna(tag):
                continue
            n = len(syms)
            n_turns = _count_theme_turns(panel, syms)
            eligible = n >= 5
            rows.append({
                "grouping_layer":            "theme_tag",
                "group_name":                str(tag),
                "n_symbols":                 n,
                "n_stock_cloud_turns":       _count_stock_turns(stock_events, syms),
                "n_group_turn_events_40_35": n_turns,
                "eligible_for_p1":           int(eligible and n_turns >= 5),
                "recommended_use":           "custom_bucket_candidate" if eligible else "too_small",
            })

    # ── Layer 5: Flag-based buckets ────────────────────────────────────────────
    for bucket_name, flag_col in FLAG_BUCKETS:
        if flag_col not in smap.columns:
            continue
        syms = set(smap[smap[flag_col] == 1]["symbol"].unique())
        if not syms:
            continue
        n = len(syms)
        n_turns = _count_theme_turns(panel, syms)
        eligible = n >= 5
        rows.append({
            "grouping_layer":            "flag_bucket",
            "group_name":                bucket_name,
            "n_symbols":                 n,
            "n_stock_cloud_turns":       _count_stock_turns(stock_events, syms),
            "n_group_turn_events_40_35": n_turns,
            "eligible_for_p1":           int(eligible and n_turns >= 5),
            "recommended_use":           "custom_bucket_candidate" if eligible and n_turns >= 5 else "coverage_check",
        })

    result = pd.DataFrame(rows).sort_values(
        ["grouping_layer", "n_symbols"], ascending=[True, False]
    )

    out_path = OUTPUT_DIR / "sector_grouping_feasibility_audit.csv"
    result.to_csv(out_path, index=False)
    log.info(
        "Sector grouping feasibility: %d rows across %d layers -> %s",
        len(result), result["grouping_layer"].nunique(), out_path,
    )
    return result
