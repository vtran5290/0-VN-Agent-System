"""
P1 Test 3 — Filter-value ablation for L3/flag/theme group breadth gates.
Gates: baseline, breadth>=40%, breadth>=50%, turned in last 10/20 sessions.
Horizons: 20d, 60d, 120d.
Output: group_filter_value_ablation.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .p1_config import (
    P1_GATE_THRESHOLDS, P1_RECENT_TURN_WINDOWS, P1_HORIZONS,
    P1_MIN_EVENTS, P1_FILTER_VALUE_PATH,
)

log = logging.getLogger(__name__)


def _return_stats(series: pd.Series) -> dict:
    vals = series.dropna()
    if vals.empty:
        return {"mean": np.nan, "hit_rate": np.nan, "n": 0}
    return {
        "mean":     float(vals.mean()),
        "hit_rate": float((vals > 0).mean()),
        "n":        len(vals),
    }


def run_group_filter_value_ablation(
    stock_events: pd.DataFrame,
    tall_breadth_df: pd.DataFrame,
    group_turn_events: pd.DataFrame,
    group_sym_map: dict,
    recent_turn_flags: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each eligible group, compute forward-return improvement from group breadth gates.
    """
    if stock_events.empty or tall_breadth_df.empty:
        log.warning("No data for group filter value ablation.")
        return pd.DataFrame()

    stock_events = stock_events.copy()
    stock_events["date"] = pd.to_datetime(stock_events["date"])

    primary_events = group_turn_events[
        group_turn_events["definition"] == "primary_40_35"
    ]
    event_counts = primary_events.groupby(["grouping_layer", "group_name"]).size()
    eligible_groups = set(event_counts[event_counts >= P1_MIN_EVENTS].index.tolist())

    rows = []

    for (layer, name), symbols in group_sym_map.items():
        if (layer, name) not in eligible_groups:
            continue

        # Stock events for this group's symbols
        ev = stock_events[stock_events["symbol"].isin(symbols)].copy()
        if ev.empty:
            continue

        # Get group breadth on event dates via merge
        bdf = tall_breadth_df[
            (tall_breadth_df["grouping_layer"] == layer) &
            (tall_breadth_df["group_name"]     == name)
        ][["date", "breadth_ew", "breadth_liq"]].copy()
        bdf["date"] = pd.to_datetime(bdf["date"])

        ev = ev.merge(
            bdf.rename(columns={"breadth_ew": "_bew", "breadth_liq": "_bliq"}),
            on="date", how="left",
        )

        # Attach recent turn flags if available
        if recent_turn_flags is not None and not recent_turn_flags.empty:
            rtf = recent_turn_flags[
                (recent_turn_flags["grouping_layer"] == layer) &
                (recent_turn_flags["group_name"]     == name)
            ].copy()
            rtf["date"] = pd.to_datetime(rtf["date"])
            turn_cols = [c for c in rtf.columns if c.startswith("recent_turn_")]
            if turn_cols:
                ev = ev.merge(rtf[["date"] + turn_cols], on="date", how="left")
                for c in turn_cols:
                    ev[c] = ev[c].fillna(0)

        # Build gate rules
        rules = [
            ("baseline",                None,        None),
        ]
        for thresh in P1_GATE_THRESHOLDS:
            rules.append((f"breadth_ew_ge_{int(thresh*100)}",  "_bew",  thresh))
            rules.append((f"breadth_liq_ge_{int(thresh*100)}", "_bliq", thresh))
        for win in P1_RECENT_TURN_WINDOWS:
            col = f"recent_turn_{win}d"
            if col in ev.columns:
                rules.append((f"turned_last_{win}d", col, 1))

        n_base = len(ev)

        for rule_id, gate_col, gate_val in rules:
            if gate_col is None:
                filtered = ev
            elif gate_col.startswith("recent_"):
                filtered = ev[ev[gate_col] >= gate_val]
            elif gate_col in ev.columns:
                filtered = ev[ev[gate_col].fillna(0) >= gate_val]
            else:
                continue

            n_gate = len(filtered)

            for h in P1_HORIZONS:
                col = f"fwd_ret_{h}d"
                if col not in ev.columns:
                    continue

                bs = _return_stats(ev[col])
                gs = _return_stats(filtered[col] if col in filtered.columns else pd.Series(dtype=float))

                d_mean = gs["mean"] - bs["mean"] if not np.isnan(gs["mean"]) else np.nan
                d_hit  = gs["hit_rate"] - bs["hit_rate"] if not np.isnan(gs["hit_rate"]) else np.nan

                # Simple interpretation note
                if rule_id == "baseline":
                    note = "baseline"
                elif not np.isnan(d_hit):
                    if d_hit >= 0.03:
                        note = "G2_pass_candidate"
                    elif d_hit >= 0.01:
                        note = "marginal"
                    elif d_hit < -0.01:
                        note = "negative_filter"
                    else:
                        note = "neutral"
                else:
                    note = "insufficient_data"

                rows.append({
                    "grouping_layer":      layer,
                    "group_name":          name,
                    "rule_id":             rule_id,
                    "horizon":             h,
                    "n_base":              n_base,
                    "n_gate":              n_gate,
                    "retention_pct":       round(n_gate / max(n_base, 1), 4),
                    "base_mean":           bs["mean"],
                    "gate_mean":           gs["mean"],
                    "delta_mean":          d_mean,
                    "base_hit_rate":       bs["hit_rate"],
                    "gate_hit_rate":       gs["hit_rate"],
                    "delta_hit_rate":      d_hit,
                    "interpretation_note": note,
                })

    result = pd.DataFrame(rows)
    result.to_csv(P1_FILTER_VALUE_PATH, index=False)
    log.info("Group filter value ablation: %d rows saved to %s", len(result), P1_FILTER_VALUE_PATH)
    return result
