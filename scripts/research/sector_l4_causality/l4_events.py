"""
Rebuild sector L4 daily panel and detect L4 turn events.
Always rebuilds from stock panel + sector map (never uses stale sector_l4_daily_metrics.csv).
Primary turn definition: l4_breadth_equal_weight crosses above 40% after resetting below 35%.
"""
from __future__ import annotations
import logging
from typing import Optional

import numpy as np
import pandas as pd

from .config import (
    OUTPUT_DIR,
    SECTOR_PANEL_CACHE,
    L4_EVENTS_CACHE,
    L4_TURN_THRESHOLDS,
    VIN_GROUP_SYMBOLS,
    MIN_L4_SYMBOLS,
)

log = logging.getLogger(__name__)


def build_sector_daily_panel(
    panel: pd.DataFrame,
    sector_map: pd.DataFrame,
    regimes: pd.DataFrame,
    include_unknown: bool = False,
) -> pd.DataFrame:
    """
    Aggregate stock-level cloud flags to sector-level daily panel.
    Returns L4-date panel with breadth columns and regime overlays.
    """
    # Merge sector map onto panel
    map_cols = ["symbol", "sector_l4", "is_bank", "is_vin_group",
                "is_securities", "is_broker"]
    map_cols = [c for c in map_cols if c in sector_map.columns]
    enriched = panel.merge(sector_map[map_cols].drop_duplicates("symbol"),
                           on="symbol", how="left")

    enriched["sector_l4"] = enriched["sector_l4"].fillna("Unknown")
    if not include_unknown:
        enriched = enriched[enriched["sector_l4"] != "Unknown"]

    enriched["is_ex_vin"] = (~enriched["symbol"].isin(VIN_GROUP_SYMBOLS)).astype(int)

    # ── Equal-weight breadth ──────────────────────────────────────────────────
    g = enriched.groupby(["date", "sector_l4"])

    agg = g.agg(
        n_symbols       =("symbol",          "nunique"),
        n_cloud_bull    =("cloud_bull_20_100","sum"),
        n_unknown       =("sector_l4",        lambda x: (x == "Unknown").sum()),
    ).reset_index()
    agg["l4_breadth_equal_weight"] = agg["n_cloud_bull"] / agg["n_symbols"].clip(lower=1)

    # ── Liquidity-weighted breadth (NOT "cap-weighted") ───────────────────────
    enriched["adv50_x_bull"] = enriched["adv50"] * enriched["cloud_bull_20_100"]
    liq = enriched.groupby(["date", "sector_l4"]).agg(
        total_adv50    =("adv50",       "sum"),
        bull_adv50     =("adv50_x_bull","sum"),
    ).reset_index()
    liq["l4_breadth_liquidity_weighted"] = (
        liq["bull_adv50"] / liq["total_adv50"].clip(lower=1)
    )
    agg = agg.merge(liq[["date", "sector_l4", "l4_breadth_liquidity_weighted"]],
                    on=["date", "sector_l4"], how="left")

    # ── ex-VIN breadth ────────────────────────────────────────────────────────
    ex_vin_agg = (
        enriched[enriched["is_ex_vin"] == 1]
        .groupby(["date", "sector_l4"])
        .agg(
            n_ex_vin      =("symbol",          "nunique"),
            n_bull_ex_vin =("cloud_bull_20_100","sum"),
        )
        .reset_index()
    )
    ex_vin_agg["l4_breadth_ex_vin"] = (
        ex_vin_agg["n_bull_ex_vin"] / ex_vin_agg["n_ex_vin"].clip(lower=1)
    )
    agg = agg.merge(
        ex_vin_agg[["date", "sector_l4", "l4_breadth_ex_vin"]],
        on=["date", "sector_l4"], how="left"
    )

    # ── Full breadth (including VIN) alias ───────────────────────────────────
    agg["l4_breadth_full"] = agg["l4_breadth_equal_weight"]

    # ── Sector size flags ─────────────────────────────────────────────────────
    agg["unknown_included_flag"] = int(include_unknown)

    # ── Merge regime overlays ─────────────────────────────────────────────────
    regime_cols = [c for c in regimes.columns if c != "date"]
    agg = agg.merge(regimes[["date"] + regime_cols], on="date", how="left")

    # ── Coverage note ─────────────────────────────────────────────────────────
    def _note(row):
        if row["n_symbols"] < 3:
            return "tiny_lt3"
        if row["n_symbols"] < MIN_L4_SYMBOLS:
            return "small_3_4"
        return ""
    agg["coverage_note"] = agg.apply(_note, axis=1)

    agg = agg.sort_values(["sector_l4", "date"]).reset_index(drop=True)
    agg.to_parquet(SECTOR_PANEL_CACHE, index=False)
    log.info("Sector daily panel saved: %s  shape=%s", SECTOR_PANEL_CACHE, agg.shape)
    return agg


def _hysteresis_turn_signal(series: pd.Series, enter: float, exit_: float) -> pd.Series:
    """
    Return boolean Series marking dates where series crosses above `enter`
    after having reset below `exit_`. Stateful hysteresis.
    """
    values = series.values
    n = len(values)
    signal = np.zeros(n, dtype=bool)
    armed = True  # starts armed (below threshold = ready to fire)

    for i in range(n):
        v = values[i]
        if np.isnan(v):
            continue
        if armed and v >= enter:
            signal[i] = True
            armed = False
        elif not armed and v < exit_:
            armed = True

    return pd.Series(signal, index=series.index)


def _alt_c_signal(series: pd.Series, enter: float = 0.40,
                  below_floor: float = 0.30, min_sessions_below: int = 20) -> pd.Series:
    """
    Alt C: first day >= enter after >= min_sessions_below consecutive days below below_floor.
    """
    values = series.values
    n = len(values)
    signal = np.zeros(n, dtype=bool)
    sessions_below = 0
    eligible = False

    for i in range(n):
        v = values[i]
        if np.isnan(v):
            continue
        if v < below_floor:
            sessions_below += 1
        else:
            if sessions_below >= min_sessions_below:
                eligible = True
            sessions_below = 0
        if eligible and v >= enter:
            signal[i] = True
            eligible = False

    return pd.Series(signal, index=series.index)


def build_l4_turn_events(
    sector_panel: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Detect L4 turn events for all threshold variants.
    Returns event table: sector_l4_turn_events.csv
    """
    if start_date:
        sector_panel = sector_panel[sector_panel["date"] >= start_date]
    if end_date:
        sector_panel = sector_panel[sector_panel["date"] <= end_date]

    eligible_sectors = sector_panel[
        sector_panel["coverage_note"].isin(["", None])
    ]["sector_l4"].unique()

    event_rows = []

    for sector in eligible_sectors:
        grp = sector_panel[sector_panel["sector_l4"] == sector].sort_values("date")

        # Primary + threshold variants on equal-weight breadth
        breadth_col_map = {
            "equal_weight": "l4_breadth_equal_weight",
            "liq_weighted":  "l4_breadth_liquidity_weighted",
            "ex_vin":        "l4_breadth_ex_vin",
        }

        for thresh in L4_TURN_THRESHOLDS:
            name = thresh["name"]
            enter = thresh["enter"]
            exit_ = thresh["exit"]
            use_liq = thresh.get("use_liq_weight", False)
            use_exv = thresh.get("use_ex_vin", False)

            if use_liq:
                col = "l4_breadth_liquidity_weighted"
            elif use_exv:
                col = "l4_breadth_ex_vin"
            else:
                col = "l4_breadth_equal_weight"

            if col not in grp.columns:
                continue

            signal = _hysteresis_turn_signal(grp.set_index("date")[col], enter, exit_)
            event_dates = signal[signal].index

            for edate in event_dates:
                row_data = grp[grp["date"] == edate].iloc[0]
                prev = grp[grp["date"] < edate].tail(1)
                prev_breadth = prev[col].iloc[0] if not prev.empty else np.nan

                row = {
                    "event_id":             f"{sector}__{str(edate)[:10]}__{name}",
                    "date":                 edate,
                    "sector_l4":            sector,
                    "definition":           name,
                    "l4_breadth_prev":      prev_breadth,
                    "l4_breadth":           row_data[col],
                    "l4_breadth_liq_weighted": row_data.get("l4_breadth_liquidity_weighted", np.nan),
                    "n_symbols_l4":         row_data["n_symbols"],
                    "n_cloud_bull":         row_data["n_cloud_bull"],
                }
                # Merge regime cols
                for rcol in [c for c in grp.columns if c.startswith("M0_") or c.startswith("M1_") or c.startswith("M2_") or c.startswith("M4_")]:
                    row[rcol] = row_data.get(rcol, np.nan)
                event_rows.append(row)

        # Alt C variant
        if "l4_breadth_equal_weight" in grp.columns:
            sig_c = _alt_c_signal(grp.set_index("date")["l4_breadth_equal_weight"])
            for edate in sig_c[sig_c].index:
                row_data = grp[grp["date"] == edate].iloc[0]
                event_rows.append({
                    "event_id":    f"{sector}__{str(edate)[:10]}__altC",
                    "date":        edate,
                    "sector_l4":   sector,
                    "definition":  "altC_after20_below30",
                    "l4_breadth_prev": np.nan,
                    "l4_breadth":  row_data["l4_breadth_equal_weight"],
                    "l4_breadth_liq_weighted": row_data.get("l4_breadth_liquidity_weighted", np.nan),
                    "n_symbols_l4": row_data["n_symbols"],
                    "n_cloud_bull": row_data["n_cloud_bull"],
                })

    events = pd.DataFrame(event_rows)
    if events.empty:
        log.warning("No L4 turn events generated!")
        events = pd.DataFrame(columns=["event_id", "date", "sector_l4", "definition"])
    else:
        events = events.sort_values(["sector_l4", "date"]).reset_index(drop=True)

    events.to_csv(L4_EVENTS_CACHE, index=False)
    log.info("L4 turn events: %d rows saved to %s", len(events), L4_EVENTS_CACHE)
    return events
