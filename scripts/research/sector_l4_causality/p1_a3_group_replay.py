"""
P1 Test 4 — A3 ledger replay for L3/flag/theme group gates. Research only.
Does NOT modify the original A3 ledger.
Uses trade-level MAR proxy (mean/abs(worst)) — NOT portfolio NAV.
Output: a3_group_gate_replay.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .p1_config import (
    P1_GATE_THRESHOLDS, P1_RECENT_TURN_WINDOWS, P1_MIN_EVENTS,
    P1_A3_REPLAY_PATH,
)

log = logging.getLogger(__name__)


def _trade_stats(df: pd.DataFrame, ret_col: str) -> tuple[float, float, float]:
    """Returns (mean_return, worst_trade, trade_mar_proxy)."""
    if df.empty or ret_col not in df.columns:
        return np.nan, np.nan, np.nan
    rets = df[ret_col].dropna()
    if rets.empty:
        return np.nan, np.nan, np.nan
    mean_ret = float(rets.mean())
    worst    = float(rets.min())
    tmar     = mean_ret / max(abs(worst), 1e-6)
    return mean_ret, worst, tmar


def run_a3_group_gate_replay(
    enriched_ledger: pd.DataFrame,
    tall_breadth_df: pd.DataFrame,
    group_turn_events: pd.DataFrame,
    group_sym_map: dict,
    recent_turn_flags: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each eligible group and each rule, replay A3 entry gate.
    Uses asof merge to match group breadth on A3 entry date.
    """
    if enriched_ledger is None or enriched_ledger.empty:
        log.warning("No enriched ledger; skipping A3 group replay.")
        return pd.DataFrame()
    if tall_breadth_df.empty:
        log.warning("No group breadth data; skipping A3 group replay.")
        return pd.DataFrame()

    ledger = enriched_ledger.copy()
    ledger.columns = ledger.columns.str.strip().str.lower()

    date_col = next((c for c in ledger.columns if "entry" in c or c == "date"), None)
    ret_col  = next((c for c in ledger.columns if c in ("net_return", "gross_return", "ret", "return")), None)
    sym_col  = next((c for c in ledger.columns if c == "symbol"), None)

    if date_col is None or ret_col is None or sym_col is None:
        log.warning("Cannot find required columns in enriched ledger. Cols: %s", list(ledger.columns))
        return pd.DataFrame()

    ledger["_entry_date"] = pd.to_datetime(ledger[date_col])
    ledger = ledger.sort_values("_entry_date").reset_index(drop=True)

    primary_events = group_turn_events[group_turn_events["definition"] == "primary_40_35"]
    event_counts   = primary_events.groupby(["grouping_layer", "group_name"]).size()
    eligible_groups = set(event_counts[event_counts >= P1_MIN_EVENTS].index.tolist())

    # Baseline stats (all trades)
    base_mean, base_worst, base_tmar = _trade_stats(ledger, ret_col)
    n_base = len(ledger)

    rows = []

    for (layer, name), symbols in group_sym_map.items():
        if (layer, name) not in eligible_groups:
            continue

        # Subset ledger to trades whose symbol is in this group
        grp_ledger = ledger[ledger[sym_col].isin(symbols)].copy()
        if grp_ledger.empty:
            continue

        n_grp_base = len(grp_ledger)
        grp_base_mean, grp_base_worst, grp_base_tmar = _trade_stats(grp_ledger, ret_col)

        # Attach group breadth via asof merge
        bdf = tall_breadth_df[
            (tall_breadth_df["grouping_layer"] == layer) &
            (tall_breadth_df["group_name"]     == name)
        ][["date", "breadth_ew", "breadth_liq"]].copy()
        bdf["date"] = pd.to_datetime(bdf["date"])
        bdf = bdf.drop_duplicates("date").sort_values("date")

        grp_ledger = pd.merge_asof(
            grp_ledger.sort_values("_entry_date"),
            bdf.rename(columns={"date": "_bdate", "breadth_ew": "_bew", "breadth_liq": "_bliq"}),
            left_on="_entry_date", right_on="_bdate",
            direction="backward",
        )
        if "_bew" not in grp_ledger.columns:
            grp_ledger["_bew"] = np.nan
        if "_bliq" not in grp_ledger.columns:
            grp_ledger["_bliq"] = np.nan

        # Attach recent turn flags
        if recent_turn_flags is not None and not recent_turn_flags.empty:
            rtf = recent_turn_flags[
                (recent_turn_flags["grouping_layer"] == layer) &
                (recent_turn_flags["group_name"]     == name)
            ].copy()
            rtf["date"] = pd.to_datetime(rtf["date"])
            turn_cols = [c for c in rtf.columns if c.startswith("recent_turn_")]
            if turn_cols:
                grp_ledger = pd.merge_asof(
                    grp_ledger.sort_values("_entry_date"),
                    rtf[["date"] + turn_cols].sort_values("date"),
                    left_on="_entry_date", right_on="date",
                    direction="backward",
                )
                for c in turn_cols:
                    grp_ledger[c] = grp_ledger[c].fillna(0)

        # Build rules
        rules = [("no_gate", None, None)]
        for thresh in P1_GATE_THRESHOLDS:
            rules.append((f"breadth_ew_ge_{int(thresh*100)}",  "_bew",  thresh))
            rules.append((f"breadth_liq_ge_{int(thresh*100)}", "_bliq", thresh))
        for win in P1_RECENT_TURN_WINDOWS:
            col = f"recent_turn_{win}d"
            if col in grp_ledger.columns:
                rules.append((f"turned_last_{win}d", col, 1))

        for rule_id, gate_col, gate_val in rules:
            if gate_col is None:
                allowed = grp_ledger
                blocked = grp_ledger.iloc[0:0]
            elif gate_col.startswith("recent_"):
                allowed = grp_ledger[grp_ledger[gate_col].fillna(0) >= gate_val]
                blocked = grp_ledger[grp_ledger[gate_col].fillna(0) < gate_val]
            elif gate_col in grp_ledger.columns:
                allowed = grp_ledger[grp_ledger[gate_col].fillna(0) >= gate_val]
                blocked = grp_ledger[grp_ledger[gate_col].fillna(0) < gate_val]
            else:
                continue

            n_trades  = len(allowed)
            n_blocked = len(blocked)
            ret_pct   = n_trades / max(n_grp_base, 1)

            blk_win = int((blocked[ret_col].fillna(0) > 0).sum()) if not blocked.empty else 0
            blk_los = int((blocked[ret_col].fillna(0) < 0).sum()) if not blocked.empty else 0
            bl_ratio = blk_los / max(blk_win, 1)

            mean_ret, worst_ret, tmar = _trade_stats(allowed, ret_col)
            d_tmar = tmar - grp_base_tmar if not np.isnan(tmar) and not np.isnan(grp_base_tmar) else np.nan

            if rule_id == "no_gate":
                gate_pass = "N/A"
                note = "Baseline — group trades only"
            else:
                passes = (
                    not np.isnan(d_tmar) and d_tmar >= 0.05 and
                    bl_ratio >= 1.2 and ret_pct >= 0.85
                )
                gate_pass = int(passes)
                note = f"d_tmar={d_tmar:.4f}, bl_ratio={bl_ratio:.2f}, ret={ret_pct:.3f}"

            rows.append({
                "grouping_layer":              layer,
                "group_name":                  name,
                "rule_id":                     rule_id,
                "n_trades":                    n_trades,
                "n_blocked":                   n_blocked,
                "retention_pct":               round(ret_pct, 4),
                "blocked_winners":             blk_win,
                "blocked_losers":              blk_los,
                "blocked_loser_winner_ratio":  round(bl_ratio, 4),
                "mean_trade_return":           round(mean_ret, 6) if not np.isnan(mean_ret) else np.nan,
                "worst_trade_return":          round(worst_ret, 6) if not np.isnan(worst_ret) else np.nan,
                "trade_level_mar_proxy":       round(tmar, 6) if not np.isnan(tmar) else np.nan,
                "delta_trade_level_mar_proxy": round(d_tmar, 6) if not np.isnan(d_tmar) else np.nan,
                "gate_pass":                   gate_pass,
                "note":                        note,
            })

    result = pd.DataFrame(rows)
    result.to_csv(P1_A3_REPLAY_PATH, index=False)
    log.info("A3 group gate replay: %d rows saved to %s", len(result), P1_A3_REPLAY_PATH)
    return result
