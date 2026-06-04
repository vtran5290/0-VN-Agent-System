"""
C01 — Leader vs sector classification.
For each L4 turn event, identify the leader by three rules:
  1. first_stock_to_flip  — first symbol in sector to flip cloud_bull within 10 sessions before event
  2. max_adv50_leader     — highest adv50 symbol at time of event
  3. top_5d_return_leader — best 5-day pre-event return symbol
Output: leader_vs_sector_classification.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR

log = logging.getLogger(__name__)

LEADER_RULES = ["first_flip", "max_adv50", "top_5d_return"]
LEADER_PRECEDE_SESSIONS = 5   # leader flips at least this many sessions before sector


def classify_leaders(
    l4_events: pd.DataFrame,
    panel: pd.DataFrame,
    sector_map: pd.DataFrame,
    definition_filter: str = "primary_40_35",
) -> pd.DataFrame:
    """
    For each primary L4 turn event, identify leaders and classify.
    Returns event-level classification table.
    """
    events = l4_events[l4_events["definition"] == definition_filter].copy()
    events["date"] = pd.to_datetime(events["date"])
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    # Merge sector map
    sym_sector = sector_map[["symbol", "sector_l4"]].drop_duplicates("symbol")
    enriched = panel.merge(sym_sector, on="symbol", how="left")
    enriched["sector_l4"] = enriched["sector_l4"].fillna("Unknown")

    all_dates = pd.DatetimeIndex(sorted(panel["date"].unique()))

    rows = []
    for _, evt in events.iterrows():
        sector  = evt["sector_l4"]
        edate   = evt["date"]

        try:
            epos = all_dates.get_loc(edate)
        except KeyError:
            continue

        # Window: 10 sessions before event
        lo_pos = max(0, epos - 10)
        date_lo = all_dates[lo_pos]
        sector_members = enriched[
            (enriched["sector_l4"] == sector) &
            (enriched["date"] >= date_lo) &
            (enriched["date"] <= edate)
        ].copy()

        if sector_members.empty:
            continue

        # ── Rule 1: first stock to flip cloud within -10 sessions ────────────
        prev_state = enriched[
            (enriched["sector_l4"] == sector) &
            (enriched["date"] < date_lo)
        ].groupby("symbol")["cloud_bull_20_100"].last()

        first_flip_sym = None
        first_flip_date = None
        earliest = pd.Timestamp.max
        for sym, sym_grp in sector_members.groupby("symbol"):
            sym_grp = sym_grp.sort_values("date")
            was_bear = int(prev_state.get(sym, 0)) == 0
            if not was_bear:
                continue
            flip_rows = sym_grp[sym_grp["cloud_bull_20_100"] == 1]
            if flip_rows.empty:
                continue
            fd = flip_rows.iloc[0]["date"]
            if fd < earliest:
                earliest = fd
                first_flip_sym = sym
                first_flip_date = fd

        # ── Rule 2: max adv50 at event date ──────────────────────────────────
        snap = sector_members[sector_members["date"] == edate]
        max_adv50_sym = None
        if not snap.empty and "adv50" in snap.columns:
            max_adv50_sym = snap.loc[snap["adv50"].idxmax(), "symbol"]

        # ── Rule 3: top 5d return before event ───────────────────────────────
        top_ret_sym = None
        lo5 = max(0, epos - 5)
        date_lo5 = all_dates[lo5]
        window_5d = enriched[
            (enriched["sector_l4"] == sector) &
            (enriched["date"] >= date_lo5) &
            (enriched["date"] <= edate)
        ]
        if not window_5d.empty:
            ret5 = window_5d.groupby("symbol")["close"].apply(
                lambda x: x.iloc[-1] / x.iloc[0] - 1 if len(x) > 1 else 0
            )
            if not ret5.empty:
                top_ret_sym = ret5.idxmax()

        # ── Leader agreement ─────────────────────────────────────────────────
        leaders = [s for s in [first_flip_sym, max_adv50_sym, top_ret_sym] if s is not None]
        from collections import Counter
        if leaders:
            top_leader = Counter(leaders).most_common(1)[0][0]
        else:
            top_leader = None

        # Did any leader precede sector by >= LEADER_PRECEDE_SESSIONS?
        leader_before_sector = (
            first_flip_date is not None and
            first_flip_date <= edate - pd.Timedelta(days=LEADER_PRECEDE_SESSIONS)
        )

        rows.append({
            "event_id":              evt.get("event_id", ""),
            "date":                  edate,
            "sector_l4":             sector,
            "first_flip_leader":     first_flip_sym,
            "first_flip_date":       first_flip_date,
            "max_adv50_leader":      max_adv50_sym,
            "top_5d_return_leader":  top_ret_sym,
            "top_leader_by_vote":    top_leader,
            "leader_before_sector":  int(leader_before_sector),
            "n_leaders_agree":       len(set(leaders)),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        log.warning("No leader classifications produced.")
        result = pd.DataFrame(columns=["event_id", "date", "sector_l4", "top_leader_by_vote",
                                        "leader_before_sector"])
        result.to_csv(OUTPUT_DIR / "leader_vs_sector_classification.csv", index=False)
        return result

    pct_leader_before = result["leader_before_sector"].mean() * 100
    conclusion = "LEADER_DRIVEN" if pct_leader_before > 50 else "BROAD_BASED"
    log.info("Leader-before-sector: %.1f%% of events -> %s", pct_leader_before, conclusion)

    out_path = OUTPUT_DIR / "leader_vs_sector_classification.csv"
    result.to_csv(out_path, index=False)
    log.info("Leader classification saved to %s", out_path)
    return result
