"""
P1 Test 5 — Leader/follower classification for group turn events.
For each group turn, identify first-flip leader, max-ADV50 leader, top-5d-return leader.
Classify event: BROAD_BASED, LEADER_DRIVEN, COINCIDENT, NOISY_OR_THIN.
Output: group_leader_follower_classification.csv
"""
from __future__ import annotations
import logging
from collections import Counter

import numpy as np
import pandas as pd

from .p1_config import P1_MIN_EVENTS, P1_LEADER_PATH

log = logging.getLogger(__name__)

LEADER_PRECEDE_SESSIONS = 5


def classify_group_leaders(
    group_turn_events: pd.DataFrame,
    panel: pd.DataFrame,
    group_sym_map: dict,
    definition_filter: str = "primary_40_35",
) -> pd.DataFrame:
    """
    For each group turn event, run 3-rule leader classification and classify the event.
    """
    if group_turn_events.empty:
        log.warning("No group turn events; skipping leader classification.")
        return pd.DataFrame()

    events = group_turn_events[group_turn_events["definition"] == definition_filter].copy()
    events["date"] = pd.to_datetime(events["date"])
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    all_dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    rows = []

    for (layer, name), evt_grp in events.groupby(["grouping_layer", "group_name"]):
        symbols = group_sym_map.get((layer, name), frozenset())
        if len(symbols) == 0:
            continue

        n_events = len(evt_grp)
        n_leader_before = 0

        for _, evt in evt_grp.iterrows():
            edate = evt["date"]
            try:
                epos = all_dates.get_loc(edate)
            except KeyError:
                continue

            lo_pos = max(0, epos - 10)
            date_lo = all_dates[lo_pos]

            sector_members = panel[
                panel["symbol"].isin(symbols) &
                (panel["date"] >= date_lo) &
                (panel["date"] <= edate)
            ].copy()

            if sector_members.empty:
                continue

            # Rule 1: first stock to flip cloud within -10 sessions
            prev_state = panel[
                panel["symbol"].isin(symbols) & (panel["date"] < date_lo)
            ].groupby("symbol")["cloud_bull_20_100"].last()

            first_flip_sym, first_flip_date = None, None
            earliest = pd.Timestamp.max
            for sym, sym_grp in sector_members.groupby("symbol"):
                sym_grp = sym_grp.sort_values("date")
                was_bear = int(prev_state.get(sym, 0)) == 0
                if not was_bear:
                    continue
                flips = sym_grp[sym_grp["cloud_bull_20_100"] == 1]
                if flips.empty:
                    continue
                fd = flips.iloc[0]["date"]
                if fd < earliest:
                    earliest, first_flip_sym, first_flip_date = fd, sym, fd

            # Rule 2: max ADV50 at event date
            snap = sector_members[sector_members["date"] == edate]
            max_adv50_sym = None
            if not snap.empty and "adv50" in snap.columns and not snap["adv50"].isna().all():
                max_adv50_sym = snap.loc[snap["adv50"].idxmax(), "symbol"]

            # Rule 3: top 5d return before event
            lo5 = max(0, epos - 5)
            date_lo5 = all_dates[lo5]
            window5d = panel[
                panel["symbol"].isin(symbols) &
                (panel["date"] >= date_lo5) &
                (panel["date"] <= edate)
            ]
            top_ret_sym = None
            if not window5d.empty:
                ret5 = window5d.groupby("symbol")["close"].apply(
                    lambda x: x.iloc[-1] / x.iloc[0] - 1 if len(x) > 1 else 0
                )
                if not ret5.empty:
                    top_ret_sym = ret5.idxmax()

            # Leader agreement vote
            candidates = [s for s in [first_flip_sym, max_adv50_sym, top_ret_sym] if s is not None]
            top_leader = Counter(candidates).most_common(1)[0][0] if candidates else None

            leader_precedes = (
                first_flip_date is not None and
                first_flip_date <= edate - pd.Timedelta(days=LEADER_PRECEDE_SESSIONS)
            )
            if leader_precedes:
                n_leader_before += 1

            rows.append({
                "turn_event_id":         evt.get("turn_event_id", ""),
                "grouping_layer":        layer,
                "group_name":            name,
                "date":                  edate,
                "first_flip_leader":     first_flip_sym,
                "first_flip_date":       first_flip_date,
                "max_adv50_leader":      max_adv50_sym,
                "top_5d_return_leader":  top_ret_sym,
                "top_leader_by_vote":    top_leader,
                "leader_before_sector":  int(leader_precedes),
                "n_leaders_agree":       len(set(candidates)),
            })

        if n_events >= P1_MIN_EVENTS:
            pct = n_leader_before / n_events * 100
            log.debug("[%s] %s: leader_before=%.1f%%  n=%d", layer, name, pct, n_events)

    result = pd.DataFrame(rows)
    if result.empty:
        log.warning("No leader classifications produced.")
        result.to_csv(P1_LEADER_PATH, index=False)
        return result

    # Add group-level classification
    grp_class = result.groupby(["grouping_layer", "group_name"])["leader_before_sector"].agg(
        leader_pct=lambda x: x.mean() * 100,
        n=len,
    ).reset_index()

    def _verdict(row):
        if row["n"] < P1_MIN_EVENTS:
            return "NOISY_OR_THIN"
        if row["leader_pct"] > 50:
            return "LEADER_DRIVEN"
        elif row["leader_pct"] < 30:
            return "BROAD_BASED"
        else:
            return "COINCIDENT"

    grp_class["group_classification"] = grp_class.apply(_verdict, axis=1)
    result = result.merge(grp_class[["grouping_layer", "group_name", "group_classification"]],
                          on=["grouping_layer", "group_name"], how="left")

    result.to_csv(P1_LEADER_PATH, index=False)
    log.info("Group leader classification: %d events, saved to %s", len(result), P1_LEADER_PATH)
    return result
