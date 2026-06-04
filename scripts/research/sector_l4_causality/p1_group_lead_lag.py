"""
P1 Test 2 — Lead/lag analysis for L3/theme/flag groups.
Replicates P0 lead/lag test: stock cloud turns T+1...T+10 after group turn vs matched random dates.
Output: group_stock_lead_lag_summary.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .p1_config import P1_MIN_EVENTS, P1_LEAD_LAG_PATH

log = logging.getLogger(__name__)

N_RANDOM_SAMPLES = 30


def _count_turns_in_window(
    stock_events: pd.DataFrame,
    group_symbols: frozenset,
    anchor_date: pd.Timestamp,
    t_start: int,
    t_end: int,
    all_dates: pd.DatetimeIndex,
) -> int:
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
    mask = (
        stock_events["symbol"].isin(group_symbols) &
        (stock_events["date"] >= all_dates[lo]) &
        (stock_events["date"] <= all_dates[hi])
    )
    return int(mask.sum())


def build_group_lead_lag_summary(
    group_turn_events: pd.DataFrame,
    stock_events: pd.DataFrame,
    panel_dates: pd.DatetimeIndex,
    group_sym_map: dict,
    definition_filter: str = "primary_40_35",
) -> pd.DataFrame:
    """
    For each eligible group, measure excess stock cloud turns after group turn vs random baseline.
    """
    if group_turn_events.empty or stock_events.empty:
        log.warning("No group turn events or stock events; skipping lead/lag.")
        return pd.DataFrame()

    events = group_turn_events[group_turn_events["definition"] == definition_filter].copy()
    events["date"] = pd.to_datetime(events["date"])
    stock_events = stock_events.copy()
    stock_events["date"] = pd.to_datetime(stock_events["date"])

    all_dates = pd.DatetimeIndex(sorted(panel_dates.unique()))
    rng = np.random.default_rng(42)

    rows = []

    for (layer, name), evt_grp in events.groupby(["grouping_layer", "group_name"]):
        n_events = len(evt_grp)
        if n_events < P1_MIN_EVENTS:
            continue

        symbols = group_sym_map.get((layer, name), frozenset())
        if len(symbols) == 0:
            continue

        event_dates = evt_grp["date"].tolist()

        t1_t10, t1_t5, t1_t20 = [], [], []
        rand_t1_t10 = []
        fwd_ret_20, fwd_ret_60 = [], []

        for edate in event_dates:
            t1_t10.append(_count_turns_in_window(stock_events, symbols, edate, 1, 10, all_dates))
            t1_t5.append( _count_turns_in_window(stock_events, symbols, edate, 1,  5, all_dates))
            t1_t20.append(_count_turns_in_window(stock_events, symbols, edate, 1, 20, all_dates))

        # Forward returns of follower stocks (t+1 to t+10)
        for edate in event_dates:
            try:
                pos = all_dates.get_loc(edate)
            except KeyError:
                continue
            lo = all_dates[max(0, pos + 1)]
            hi = all_dates[min(len(all_dates) - 1, pos + 10)]
            mask = (
                stock_events["symbol"].isin(symbols) &
                (stock_events["date"] >= lo) &
                (stock_events["date"] <= hi)
            )
            followers = stock_events[mask]
            if not followers.empty:
                if "fwd_ret_20d" in followers.columns:
                    fwd_ret_20.extend(followers["fwd_ret_20d"].dropna().tolist())
                if "fwd_ret_60d" in followers.columns:
                    fwd_ret_60.extend(followers["fwd_ret_60d"].dropna().tolist())

        # Random baseline
        sample_dates = rng.choice(all_dates, size=min(N_RANDOM_SAMPLES * n_events, len(all_dates)), replace=False)
        for rdate in sample_dates:
            rand_t1_t10.append(_count_turns_in_window(stock_events, symbols, rdate, 1, 10, all_dates))

        avg_event  = np.mean(t1_t10) if t1_t10 else 0
        avg_random = np.mean(rand_t1_t10) if rand_t1_t10 else 0
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

        if n_events < P1_MIN_EVENTS:
            conclusion = "insufficient_sample"

        rows.append({
            "grouping_layer":             layer,
            "group_name":                 name,
            "n_events":                   n_events,
            "avg_stock_turns_t1_t5":      round(np.mean(t1_t5),  3),
            "avg_stock_turns_t1_t10":     round(avg_event,        3),
            "avg_stock_turns_t1_t20":     round(np.mean(t1_t20),  3),
            "matched_random_avg_t1_t10":  round(avg_random,       3),
            "excess_turn_count_t1_t10":   round(excess,           3),
            "excess_turn_pct_t1_t10":     round(pct_lift,         4),
            "follower_median_ret_20d":    round(np.median(fwd_ret_20), 4) if fwd_ret_20 else np.nan,
            "follower_median_ret_60d":    round(np.median(fwd_ret_60), 4) if fwd_ret_60 else np.nan,
            "n_follower_obs":             len(fwd_ret_20),
            "conclusion_tag":             conclusion,
        })

    result = pd.DataFrame(rows).sort_values("excess_turn_pct_t1_t10", ascending=False)
    result.to_csv(P1_LEAD_LAG_PATH, index=False)
    log.info("Group lead/lag: %d groups, saved to %s", len(result), P1_LEAD_LAG_PATH)
    return result
