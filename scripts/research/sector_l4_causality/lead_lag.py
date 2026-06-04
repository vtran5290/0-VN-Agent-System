"""
A02 — Lead/lag analysis: do stock cloud turns cluster after L4 turn events
vs matched random dates in the same sector and regime?
Output: sector_stock_lead_lag_summary.csv
"""
from __future__ import annotations
import logging
from typing import Optional

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR, FORWARD_HORIZONS

log = logging.getLogger(__name__)

LEAD_LAG_WINDOWS = [-10, -5, 0, 1, 3, 5, 10, 20]


def _count_turns_in_window(
    stock_events: pd.DataFrame,
    sector: str,
    anchor_date: pd.Timestamp,
    t_start: int,
    t_end: int,
    all_dates: pd.Index,
) -> int:
    """Count stock turns in sector in [anchor + t_start, anchor + t_end] (session offset)."""
    try:
        anchor_pos = all_dates.get_loc(anchor_date)
    except KeyError:
        return 0
    lo = anchor_pos + t_start
    hi = anchor_pos + t_end
    if lo >= len(all_dates) or hi < 0:
        return 0
    lo = max(0, lo)
    hi = min(len(all_dates) - 1, hi)
    date_lo = all_dates[lo]
    date_hi = all_dates[hi]
    mask = (
        (stock_events["sector_l4"] == sector) &
        (stock_events["date"] >= date_lo) &
        (stock_events["date"] <= date_hi)
    )
    return int(mask.sum())


def build_lead_lag_summary(
    l4_events: pd.DataFrame,
    stock_events: pd.DataFrame,
    panel_dates: pd.Index,
    n_random_samples: int = 30,
    definition_filter: str = "primary_40_35",
) -> pd.DataFrame:
    """
    For each L4 turn event (primary definition), count stock cloud turns
    in the event sector at t+1…t+10 vs matched random dates.
    """
    events = l4_events[l4_events["definition"] == definition_filter].copy()
    events["date"] = pd.to_datetime(events["date"])
    stock_events["date"] = pd.to_datetime(stock_events["date"])

    all_dates = pd.DatetimeIndex(sorted(panel_dates.unique()))

    sector_rows = []

    for sector, grp in events.groupby("sector_l4"):
        event_dates = grp["date"].tolist()

        turn_counts_t1_t10, random_counts_t1_t10 = [], []
        turn_counts_t1_t5,  random_counts_t1_t5  = [], []
        turn_counts_t1_t20, random_counts_t1_t20 = [], []
        fwd_ret_stock_20, fwd_ret_stock_60 = [], []

        # Event windows
        for edate in event_dates:
            c10 = _count_turns_in_window(stock_events, sector, edate, 1, 10, all_dates)
            c5  = _count_turns_in_window(stock_events, sector, edate, 1,  5, all_dates)
            c20 = _count_turns_in_window(stock_events, sector, edate, 1, 20, all_dates)
            turn_counts_t1_t10.append(c10)
            turn_counts_t1_t5.append(c5)
            turn_counts_t1_t20.append(c20)

        # Median forward return of stock turns that occur in [t+1, t+10]
        for edate in event_dates:
            try:
                pos = all_dates.get_loc(edate)
            except KeyError:
                continue
            lo = all_dates[max(0, pos + 1)]
            hi = all_dates[min(len(all_dates) - 1, pos + 10)]
            follower_mask = (
                (stock_events["sector_l4"] == sector) &
                (stock_events["date"] >= lo) &
                (stock_events["date"] <= hi)
            )
            followers = stock_events[follower_mask]
            if not followers.empty:
                if "fwd_ret_20d" in followers.columns:
                    fwd_ret_stock_20.extend(followers["fwd_ret_20d"].dropna().tolist())
                if "fwd_ret_60d" in followers.columns:
                    fwd_ret_stock_60.extend(followers["fwd_ret_60d"].dropna().tolist())

        # Random baseline
        sector_dates = all_dates[
            all_dates.isin(
                stock_events[stock_events["sector_l4"] == sector]["date"].unique()
            ) | np.ones(len(all_dates), dtype=bool)
        ]
        rng = np.random.default_rng(42)
        sample_dates = rng.choice(all_dates, size=min(n_random_samples * len(event_dates), len(all_dates)), replace=False)
        for rdate in sample_dates:
            c10 = _count_turns_in_window(stock_events, sector, rdate, 1, 10, all_dates)
            c5  = _count_turns_in_window(stock_events, sector, rdate, 1,  5, all_dates)
            c20 = _count_turns_in_window(stock_events, sector, rdate, 1, 20, all_dates)
            random_counts_t1_t10.append(c10)
            random_counts_t1_t5.append(c5)
            random_counts_t1_t20.append(c20)

        avg_event  = np.mean(turn_counts_t1_t10) if turn_counts_t1_t10 else 0
        avg_random = np.mean(random_counts_t1_t10) if random_counts_t1_t10 else 0
        excess     = avg_event - avg_random
        pct_lift   = excess / max(avg_random, 0.001)

        if excess > 0 and pct_lift >= 0.15:
            conclusion = "sector_leads"
        elif abs(excess) < 0.5:
            conclusion = "coincident"
        elif excess < 0:
            conclusion = "leader_drag_or_noisy"
        else:
            conclusion = "weak"

        if len(event_dates) < 5:
            conclusion = "insufficient_sample"

        sector_rows.append({
            "sector_l4":                    sector,
            "definition":                   definition_filter,
            "n_events":                     len(event_dates),
            "avg_stock_turns_t1_t5":        np.mean(turn_counts_t1_t5),
            "avg_stock_turns_t1_t10":       avg_event,
            "avg_stock_turns_t1_t20":       np.mean(turn_counts_t1_t20),
            "matched_random_avg_t1_t10":    avg_random,
            "excess_turn_count_t1_t10":     excess,
            "excess_turn_pct_t1_t10":       pct_lift,
            "follower_median_ret_20d":      np.median(fwd_ret_stock_20) if fwd_ret_stock_20 else np.nan,
            "follower_median_ret_60d":      np.median(fwd_ret_stock_60) if fwd_ret_stock_60 else np.nan,
            "n_follower_obs":               len(fwd_ret_stock_20),
            "conclusion_tag":               conclusion,
        })

    summary = pd.DataFrame(sector_rows).sort_values("excess_turn_count_t1_t10", ascending=False)
    out_path = OUTPUT_DIR / "sector_stock_lead_lag_summary.csv"
    summary.to_csv(out_path, index=False)
    log.info("Lead/lag summary: %d sectors, saved to %s", len(summary), out_path)
    return summary
