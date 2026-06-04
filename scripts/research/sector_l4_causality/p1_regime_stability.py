"""
P1 Test 6 — Regime stability and train/test split.
Stratifies group filter-value results by regime and period.
Output: group_regime_stability_summary.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .config import TRAIN_END, TEST_START, VIN_GROUP_SYMBOLS
from .p1_config import P1_MIN_EVENTS, P1_HORIZONS, P1_REGIME_STABILITY_PATH

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


def run_group_regime_stability(
    stock_events: pd.DataFrame,
    tall_breadth_df: pd.DataFrame,
    group_turn_events: pd.DataFrame,
    group_sym_map: dict,
    regimes: pd.DataFrame,
    threshold: float = 0.40,
    definition_filter: str = "primary_40_35",
) -> pd.DataFrame:
    """
    For each eligible group, compute filter-value at 60d across regime strata and time periods.
    """
    if stock_events.empty or tall_breadth_df.empty:
        log.warning("No data for regime stability analysis.")
        return pd.DataFrame()

    se = stock_events.copy()
    se["date"] = pd.to_datetime(se["date"])

    regimes = regimes.copy()
    regimes["date"] = pd.to_datetime(regimes["date"])

    # Merge regime info into stock events
    reg_cols = ["date", "M0_ex_vin_label", "M1_vnindex_cloud_bull", "M2_ex_vin_index_cloud_bull"]
    reg_cols = [c for c in reg_cols if c in regimes.columns]
    se = se.merge(regimes[reg_cols], on="date", how="left")

    primary_events = group_turn_events[group_turn_events["definition"] == definition_filter]
    event_counts   = primary_events.groupby(["grouping_layer", "group_name"]).size()
    eligible_groups = set(event_counts[event_counts >= P1_MIN_EVENTS].index.tolist())

    # Period masks (applied to se by date)
    period_masks = {
        "full":         se["date"].notna(),
        "train_2012_19":se["date"] <= pd.Timestamp(TRAIN_END),
        "test_2020_plus":se["date"] >= pd.Timestamp(TEST_START),
    }

    # Regime masks
    regime_masks = {
        "all":           se["date"].notna(),
        "m0_normal":     se.get("M0_ex_vin_label", pd.Series(dtype=str)) == "normal",
        "m0_defensive":  se.get("M0_ex_vin_label", pd.Series(dtype=str)) == "defensive",
        "vnindex_bull":  se.get("M1_vnindex_cloud_bull", pd.Series(dtype=int)) == 1,
        "ex_vin_bull":   se.get("M2_ex_vin_index_cloud_bull", pd.Series(dtype=int)) == 1,
        "ex_vin_only":   ~se["symbol"].isin(VIN_GROUP_SYMBOLS),
    }

    rows = []

    for (layer, name), symbols in group_sym_map.items():
        if (layer, name) not in eligible_groups:
            continue

        ev = se[se["symbol"].isin(symbols)].copy()
        if ev.empty:
            continue

        bdf = tall_breadth_df[
            (tall_breadth_df["grouping_layer"] == layer) &
            (tall_breadth_df["group_name"]     == name)
        ][["date", "breadth_ew"]].copy()
        bdf["date"] = pd.to_datetime(bdf["date"])

        ev = ev.merge(bdf.rename(columns={"breadth_ew": "_bew"}), on="date", how="left")
        ev_gated = ev[ev["_bew"].fillna(0) >= threshold]

        for period_name, period_mask in period_masks.items():
            for regime_name, regime_mask in regime_masks.items():
                # Align mask to ev's index
                pm = period_mask.reindex(ev.index, fill_value=False)
                rm = regime_mask.reindex(ev.index, fill_value=False)
                ev_sub = ev[pm & rm]
                ev_sub_gated = ev_gated[
                    period_mask.reindex(ev_gated.index, fill_value=False) &
                    regime_mask.reindex(ev_gated.index, fill_value=False)
                ]

                h = 60
                col = f"fwd_ret_{h}d"
                if col not in ev.columns or ev_sub.empty:
                    continue

                bs = _return_stats(ev_sub[col])
                gs = _return_stats(ev_sub_gated[col] if col in ev_sub_gated.columns else pd.Series(dtype=float))

                d_hit  = gs["hit_rate"] - bs["hit_rate"] if not np.isnan(gs["hit_rate"]) else np.nan
                d_mean = gs["mean"]     - bs["mean"]     if not np.isnan(gs["mean"])     else np.nan

                rows.append({
                    "grouping_layer":  layer,
                    "group_name":      name,
                    "period":          period_name,
                    "regime":          regime_name,
                    "threshold":       threshold,
                    "horizon":         h,
                    "n_base":          bs["n"],
                    "n_gate":          gs["n"],
                    "base_hit_rate":   bs["hit_rate"],
                    "gate_hit_rate":   gs["hit_rate"],
                    "delta_hit_rate":  d_hit,
                    "base_mean":       bs["mean"],
                    "gate_mean":       gs["mean"],
                    "delta_mean":      d_mean,
                })

    result = pd.DataFrame(rows)
    result.to_csv(P1_REGIME_STABILITY_PATH, index=False)
    log.info("Group regime stability: %d rows saved to %s", len(result), P1_REGIME_STABILITY_PATH)
    return result
