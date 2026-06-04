"""
P1 Test 1 — Group breadth panels and turn events.
Computes daily equal-weight and liquidity-weighted breadth for L3, flag, and theme groups.
Detects turn events using hysteresis for each group.
Output: group_breadth_turn_events.csv
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR
from .l4_events import _hysteresis_turn_signal
from .p1_config import (
    P1_TURN_THRESHOLDS, P1_MIN_SYMBOLS, P1_MIN_EVENTS,
    P1_FLAG_BUCKETS, P1_GROUP_BREADTH_CACHE, P1_GROUP_TURN_EVENTS_PATH,
)

log = logging.getLogger(__name__)


def build_group_symbol_map(sector_map: pd.DataFrame) -> dict[tuple[str, str], frozenset]:
    """
    Returns {(grouping_layer, group_name): frozenset_of_symbols}.
    Layers: L3, flag_bucket, theme_tag.
    """
    smap = sector_map.copy()
    smap.columns = smap.columns.str.strip().str.lower()
    result: dict[tuple[str, str], frozenset] = {}

    # ── L3 groups ─────────────────────────────────────────────────────────────
    if "sector_l3" in smap.columns:
        for l3, grp in smap[smap["sector_l3"] != "Unknown"].groupby("sector_l3"):
            result[("L3", str(l3))] = frozenset(grp["symbol"])

    # ── Flag buckets ──────────────────────────────────────────────────────────
    for bucket_name, col in P1_FLAG_BUCKETS:
        if col not in smap.columns:
            continue
        syms = frozenset(smap[smap[col] == 1]["symbol"])
        if syms:
            result[("flag_bucket", bucket_name)] = syms

    # ── Theme tags ────────────────────────────────────────────────────────────
    if "theme_tags" in smap.columns:
        theme_df = smap[smap["theme_tags"].notna()].copy()
        theme_df = theme_df.copy()
        theme_df["_tags"] = theme_df["theme_tags"].str.split(",")
        exploded = theme_df.explode("_tags")
        exploded["_tags"] = exploded["_tags"].str.strip()
        for tag, grp in exploded.groupby("_tags"):
            if tag and not pd.isna(tag):
                result[("theme_tag", str(tag))] = frozenset(grp["symbol"])

    log.info("Group symbol map: %d groups across %d layers", len(result),
             len({k[0] for k in result}))
    return result


def compute_single_group_breadth(
    panel: pd.DataFrame,
    symbols: frozenset,
) -> pd.DataFrame:
    """
    Compute daily equal-weight and liquidity-weighted breadth for one group.
    Returns DataFrame with columns: date, breadth_ew, breadth_liq, n_active.
    """
    grp = panel[panel["symbol"].isin(symbols)].copy()
    if grp.empty:
        return pd.DataFrame(columns=["date", "breadth_ew", "breadth_liq", "n_active"])

    # Equal weight
    ew = grp.groupby("date")["cloud_bull_20_100"].mean().rename("breadth_ew")
    n_active = grp.groupby("date")["cloud_bull_20_100"].count().rename("n_active")

    # Liquidity weighted (ADV50-weighted)
    grp["_bull_adv"] = grp["cloud_bull_20_100"].astype(float) * grp["adv50"].fillna(0)
    bull_sum = grp.groupby("date")["_bull_adv"].sum()
    adv_sum  = grp.groupby("date")["adv50"].sum().replace(0, np.nan)
    liq = (bull_sum / adv_sum).rename("breadth_liq")

    result = pd.concat([ew, liq, n_active], axis=1).reset_index()
    result["date"] = pd.to_datetime(result["date"])
    return result.sort_values("date").reset_index(drop=True)


def build_all_group_breadth_panels(
    panel: pd.DataFrame,
    sector_map: pd.DataFrame,
    force_rebuild: bool = False,
) -> tuple[dict, pd.DataFrame]:
    """
    Build breadth panels for all eligible groups.
    Returns (group_symbol_map, tall_breadth_df).
    tall_breadth_df columns: grouping_layer, group_name, date, breadth_ew, breadth_liq, n_active.
    """
    if P1_GROUP_BREADTH_CACHE.exists() and not force_rebuild:
        log.info("Loading cached P1 group breadth panels from %s", P1_GROUP_BREADTH_CACHE)
        tall_df = pd.read_parquet(P1_GROUP_BREADTH_CACHE)
        group_sym_map = build_group_symbol_map(sector_map)
        return group_sym_map, tall_df

    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    group_sym_map = build_group_symbol_map(sector_map)
    rows = []

    for (layer, name), symbols in group_sym_map.items():
        if len(symbols) < P1_MIN_SYMBOLS:
            continue
        bdf = compute_single_group_breadth(panel, symbols)
        if bdf.empty:
            continue
        bdf["grouping_layer"] = layer
        bdf["group_name"]     = name
        rows.append(bdf)
        log.debug("Breadth computed: [%s] %s  dates=%d  symbols=%d", layer, name, len(bdf), len(symbols))

    tall_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not tall_df.empty:
        tall_df.to_parquet(P1_GROUP_BREADTH_CACHE, index=False)
        log.info("P1 group breadth panels cached: %s rows, %d groups",
                 f"{len(tall_df):,}", len(rows))

    return group_sym_map, tall_df


def build_group_turn_events(
    tall_breadth_df: pd.DataFrame,
    regimes: pd.DataFrame,
    group_sym_map: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Detect turn events for each group using hysteresis.
    Attaches regime metadata.
    Output: group_breadth_turn_events.csv
    """
    if tall_breadth_df.empty:
        log.warning("No group breadth data; cannot build turn events.")
        return pd.DataFrame()

    regimes = regimes.copy()
    regimes["date"] = pd.to_datetime(regimes["date"])
    reg_lookup = regimes.set_index("date")

    event_rows = []
    event_id = 0

    for (layer, name), symbols in group_sym_map.items():
        if len(symbols) < P1_MIN_SYMBOLS:
            continue

        grp_breadth = tall_breadth_df[
            (tall_breadth_df["grouping_layer"] == layer) &
            (tall_breadth_df["group_name"]     == name)
        ].sort_values("date").copy()

        if grp_breadth.empty:
            continue

        if start_date:
            grp_breadth = grp_breadth[grp_breadth["date"] >= pd.Timestamp(start_date)]
        if end_date:
            grp_breadth = grp_breadth[grp_breadth["date"] <= pd.Timestamp(end_date)]
        if grp_breadth.empty:
            continue

        for thresh in P1_TURN_THRESHOLDS:
            defn  = thresh["name"]
            enter = thresh["enter"]
            exit_ = thresh["exit"]

            ew_signal  = _hysteresis_turn_signal(grp_breadth["breadth_ew"],  enter, exit_)
            liq_signal = _hysteresis_turn_signal(grp_breadth["breadth_liq"].fillna(0), enter, exit_)

            turn_dates = grp_breadth["date"][ew_signal].tolist()
            for tdate in turn_dates:
                # Regime metadata for this date
                reg_row = reg_lookup.loc[tdate] if tdate in reg_lookup.index else None
                def _safe_int(val, default=-1):
                    try:
                        return int(val) if not pd.isna(val) else default
                    except Exception:
                        return default

                m0_label  = reg_row["M0_ex_vin_label"] if reg_row is not None and not pd.isna(reg_row.get("M0_ex_vin_label", float("nan"))) else "unknown"
                vni_bull  = _safe_int(reg_row["M1_vnindex_cloud_bull"]) if reg_row is not None else -1
                exv_bull  = _safe_int(reg_row["M2_ex_vin_index_cloud_bull"]) if reg_row is not None else -1

                snap = grp_breadth[grp_breadth["date"] == tdate]
                bew  = float(snap["breadth_ew"].iloc[0])  if not snap.empty else np.nan
                bliq = float(snap["breadth_liq"].iloc[0]) if not snap.empty else np.nan

                event_id += 1
                event_rows.append({
                    "turn_event_id":          event_id,
                    "grouping_layer":         layer,
                    "group_name":             name,
                    "date":                   tdate,
                    "definition":             defn,
                    "n_symbols":              len(symbols),
                    "breadth_equal_weight":   round(bew, 4),
                    "breadth_liquidity_weighted": round(bliq, 4) if not np.isnan(bliq) else np.nan,
                    "m0_primary_regime":      m0_label,
                    "vnindex_cloud_bull":     vni_bull,
                    "ex_vin_cloud_bull":      exv_bull,
                })

    result = pd.DataFrame(event_rows)
    if result.empty:
        log.warning("No group turn events detected.")
        result.to_csv(P1_GROUP_TURN_EVENTS_PATH, index=False)
        return result

    # Report event counts per group (primary definition only)
    primary = result[result["definition"] == "primary_40_35"]
    event_counts = primary.groupby(["grouping_layer", "group_name"]).size().rename("n_events")
    eligible = event_counts[event_counts >= P1_MIN_EVENTS]
    log.info(
        "Group turn events: %d total (%d primary), %d eligible groups (>=%d events)",
        len(result), len(primary), len(eligible), P1_MIN_EVENTS
    )

    result.to_csv(P1_GROUP_TURN_EVENTS_PATH, index=False)
    log.info("Group turn events saved to %s", P1_GROUP_TURN_EVENTS_PATH)
    return result


def build_recent_turn_flags(
    tall_breadth_df: pd.DataFrame,
    group_turn_events: pd.DataFrame,
    windows: list[int],
    all_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    For each (grouping_layer, group_name, date), flag whether a turn occurred within N sessions.
    Returns tall DataFrame with columns: grouping_layer, group_name, date, recent_turn_Nd.
    Used by filter-value and A3 replay modules.
    """
    if group_turn_events.empty:
        return pd.DataFrame()

    primary_events = group_turn_events[group_turn_events["definition"] == "primary_40_35"].copy()
    primary_events["date"] = pd.to_datetime(primary_events["date"])

    date_pos = {d: i for i, d in enumerate(all_dates)}
    rows = []

    for (layer, name), evt_grp in primary_events.groupby(["grouping_layer", "group_name"]):
        bdf = tall_breadth_df[
            (tall_breadth_df["grouping_layer"] == layer) &
            (tall_breadth_df["group_name"]     == name)
        ][["date"]].copy()
        bdf["date"] = pd.to_datetime(bdf["date"])

        event_positions = [date_pos[d] for d in evt_grp["date"] if d in date_pos]

        for win in windows:
            col = f"recent_turn_{win}d"
            flags = []
            for d in bdf["date"]:
                pos = date_pos.get(d)
                if pos is None:
                    flags.append(0)
                    continue
                flags.append(int(any(pos - win <= ep <= pos for ep in event_positions)))
            bdf[col] = flags

        bdf["grouping_layer"] = layer
        bdf["group_name"]     = name
        rows.append(bdf)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)
