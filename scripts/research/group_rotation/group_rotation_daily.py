"""
Group Rotation Dashboard — daily snapshot builder.
DASHBOARD FEATURE ONLY. No A3/OMS/Phase36/DNSE/S3 changes.
execution_allowed_flag = false for every row, always.

Output: 21-column DataFrame with one row per group.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_P1_DIR    = _REPO_ROOT / "data/research/sector_l4_causality"

_BREADTH_PANEL_PATH   = _P1_DIR / "p1_group_breadth_panels.parquet"
_TURN_EVENTS_PATH     = _P1_DIR / "group_breadth_turn_events.csv"
_LEAD_LAG_PATH        = _P1_DIR / "group_stock_lead_lag_summary.csv"
_FILTER_VALUE_PATH    = _P1_DIR / "group_filter_value_ablation.csv"
_A3_REPLAY_PATH       = _P1_DIR / "a3_group_gate_replay.csv"
_LEADER_CLF_PATH      = _P1_DIR / "group_leader_follower_classification.csv"
_STOCK_PANEL_PATH     = _P1_DIR / "stock_daily_cloud_panel.parquet"

_SCORE_BANDS = [
    (1.5,  "GROUP_STRONG_ROTATION"),
    (1.0,  "GROUP_MODERATE_ROTATION"),
    (0.5,  "GROUP_WEAK_ROTATION"),
    (0.0,  "GROUP_NO_SIGNAL"),
]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _assign_badge(score: float) -> str:
    for threshold, label in _SCORE_BANDS:
        if score >= threshold:
            return label
    return "GROUP_NO_SIGNAL"


def _assign_tier(classification: str, delta_hit_rate: float) -> str:
    """
    A: BROAD_BASED + G2 pass (delta_hit_rate >= 0.03)
    B: COINCIDENT  + G2 pass
    C: LEADER_DRIVEN + G2 pass
    D: anything else
    """
    g2 = (not np.isnan(delta_hit_rate)) and (delta_hit_rate >= 0.03)
    if classification == "BROAD_BASED" and g2:
        return "A"
    if classification == "COINCIDENT" and g2:
        return "B"
    if classification == "LEADER_DRIVEN" and g2:
        return "C"
    return "D"


def _compute_stock_cloud_turns_5d(
    stock_panel: pd.DataFrame,
    group_sym_map: dict[tuple[str, str], frozenset],
    snapshot_date: pd.Timestamp,
    all_dates: list[pd.Timestamp],
    n_sessions: int = 5,
) -> dict[tuple[str, str], int]:
    """
    Count group member symbols that transitioned cloud_bull_20_100 from 0 to 1
    in the last n_sessions trading sessions ending on snapshot_date.
    """
    # Get the last n_sessions+1 dates to detect transitions
    pos = next((i for i, d in enumerate(all_dates) if d == snapshot_date), len(all_dates) - 1)
    window_start_pos = max(0, pos - n_sessions)
    window_dates = set(all_dates[window_start_pos: pos + 1])

    # Compute per-symbol turn dates: cloud flips 0->1
    sp = stock_panel[stock_panel["date"].isin(window_dates)].copy()
    sp = sp.sort_values(["symbol", "date"])

    turn_counts: dict[tuple[str, str], int] = {}
    if sp.empty:
        return {k: 0 for k in group_sym_map}

    # Mark 0->1 transitions
    sp["_prev_bull"] = sp.groupby("symbol")["cloud_bull_20_100"].shift(1)
    sp["_is_turn"]   = (sp["_prev_bull"] == 0) & (sp["cloud_bull_20_100"] == 1)
    # Exclude the window_start date itself (it has NaN prev)
    cutoff = all_dates[min(pos - n_sessions + 1, pos)]
    turn_syms = set(sp[(sp["_is_turn"]) & (sp["date"] >= cutoff)]["symbol"].unique())

    for (layer, name), symbols in group_sym_map.items():
        turn_counts[(layer, name)] = len(symbols & turn_syms)

    return turn_counts


def _compute_sessions_since_turn(
    primary_events: pd.DataFrame,
    snapshot_date: pd.Timestamp,
    all_dates: list[pd.Timestamp],
) -> dict[tuple[str, str], tuple[int, Optional[pd.Timestamp]]]:
    """
    Returns {(layer, name): (sessions_since_turn, last_turn_date)}.
    sessions_since_turn = -1 if no prior turn found.
    """
    date_pos = {d: i for i, d in enumerate(all_dates)}
    snap_pos = date_pos.get(snapshot_date, len(all_dates) - 1)

    result: dict[tuple[str, str], tuple[int, Optional[pd.Timestamp]]] = {}

    for (layer, name), grp in primary_events.groupby(["grouping_layer", "group_name"]):
        past = grp[grp["date"] <= snapshot_date].sort_values("date", ascending=False)
        if past.empty:
            result[(layer, name)] = (-1, None)
            continue
        last_turn = pd.Timestamp(past["date"].iloc[0])
        last_pos  = date_pos.get(last_turn, -1)
        if last_pos < 0:
            result[(layer, name)] = (-1, last_turn)
        else:
            result[(layer, name)] = (snap_pos - last_pos, last_turn)

    return result


def build_group_rotation_snapshot(snapshot_date: Optional[str] = None) -> pd.DataFrame:
    """
    Build a one-row-per-group snapshot DataFrame with group rotation scores.

    Parameters
    ----------
    snapshot_date : str or None
        ISO date string (e.g. "2026-05-25"). Defaults to latest date in breadth panel.

    Returns
    -------
    pd.DataFrame with 26 columns; execution_allowed_flag = False always.
    """
    # ── Load data ─────────────────────────────────────────────────────────────
    log.info("Loading P1 output files ...")
    breadth  = pd.read_parquet(_BREADTH_PANEL_PATH)
    turns    = pd.read_csv(_TURN_EVENTS_PATH)
    lead_lag = pd.read_csv(_LEAD_LAG_PATH)
    fv       = pd.read_csv(_FILTER_VALUE_PATH)
    a3       = pd.read_csv(_A3_REPLAY_PATH)
    clf      = pd.read_csv(_LEADER_CLF_PATH)
    stock_pn = pd.read_parquet(_STOCK_PANEL_PATH)

    breadth["date"]  = pd.to_datetime(breadth["date"])
    turns["date"]    = pd.to_datetime(turns["date"])
    stock_pn["date"] = pd.to_datetime(stock_pn["date"])

    # ── Snapshot date ─────────────────────────────────────────────────────────
    all_dates = sorted(breadth["date"].unique().tolist())
    if snapshot_date:
        snap_ts = pd.Timestamp(snapshot_date)
    else:
        snap_ts = all_dates[-1]

    log.info("Snapshot date: %s", snap_ts.date())

    # ── Build group_sym_map from breadth panel group list ─────────────────────
    grp_list = breadth[["grouping_layer", "group_name"]].drop_duplicates()
    # Build approximate symbol map from stock_panel + sector_map data
    # We reconstruct it from the stock_daily_cloud_panel using sector_l4_causality io
    from scripts.research.sector_l4_causality.io import load_sector_map
    from scripts.research.sector_l4_causality.p1_group_breadth import build_group_symbol_map

    sector_map = load_sector_map()
    group_sym_map = build_group_symbol_map(sector_map)

    # ── Latest breadth per group ──────────────────────────────────────────────
    latest_breadth = (
        breadth[breadth["date"] <= snap_ts]
        .sort_values("date")
        .groupby(["grouping_layer", "group_name"])
        .last()
        .reset_index()
        [["grouping_layer", "group_name", "date", "breadth_ew", "breadth_liq", "n_active"]]
    )
    latest_breadth.rename(columns={
        "date":        "breadth_date",
        "breadth_ew":  "breadth_equal_weight",
        "breadth_liq": "breadth_liquidity_weighted",
    }, inplace=True)

    # ── Primary turn events ───────────────────────────────────────────────────
    primary = turns[turns["definition"] == "primary_40_35"].copy()

    # sessions_since_turn and last_turn_date
    sst_map = _compute_sessions_since_turn(primary, snap_ts, all_dates)

    # ── stock_cloud_turns_5d ──────────────────────────────────────────────────
    log.info("Computing stock cloud turns in last 5 sessions ...")
    cloud5d_map = _compute_stock_cloud_turns_5d(stock_pn, group_sym_map, snap_ts, all_dates)

    # ── Leader classification (one row per group, take latest) ───────────────
    grp_clf = (
        clf[["grouping_layer", "group_name", "group_classification"]]
        .drop_duplicates(["grouping_layer", "group_name"])
        .set_index(["grouping_layer", "group_name"])
    )

    # ── Filter value: breadth_ew_ge_40, horizon=60 ───────────────────────────
    fv60 = (
        fv[(fv["rule_id"] == "breadth_ew_ge_40") & (fv["horizon"] == 60)]
        [["grouping_layer", "group_name", "delta_hit_rate", "delta_mean"]]
        .set_index(["grouping_layer", "group_name"])
    )

    # ── A3 replay: breadth_ew_ge_40 ───────────────────────────────────────────
    a3_gate = (
        a3[a3["rule_id"] == "breadth_ew_ge_40"]
        [["grouping_layer", "group_name", "gate_pass"]]
        .set_index(["grouping_layer", "group_name"])
    )

    # ── Lead/lag: excess_turn_pct ─────────────────────────────────────────────
    ll_idx = (
        lead_lag[["grouping_layer", "group_name", "excess_turn_pct_t1_t10"]]
        .set_index(["grouping_layer", "group_name"])
    )

    # ── Assemble snapshot ─────────────────────────────────────────────────────
    rows = []
    for _, row in latest_breadth.iterrows():
        key = (row["grouping_layer"], row["group_name"])

        # Breadth values
        bew  = float(row["breadth_equal_weight"])
        bliq = float(row["breadth_liquidity_weighted"]) if not pd.isna(row["breadth_liquidity_weighted"]) else np.nan
        n_sym = len(group_sym_map.get(key, frozenset()))

        # Leader classification
        clf_val = grp_clf.loc[key, "group_classification"] if key in grp_clf.index else "UNKNOWN"

        # Filter value
        dhr60  = float(fv60.loc[key, "delta_hit_rate"]) if key in fv60.index else np.nan
        dmn60  = float(fv60.loc[key, "delta_mean"])     if key in fv60.index else np.nan

        # A3 gate pass
        a3_gp = int(a3_gate.loc[key, "gate_pass"]) if key in a3_gate.index else 0

        # Lead/lag
        exc_pct = float(ll_idx.loc[key, "excess_turn_pct_t1_t10"]) if key in ll_idx.index else np.nan

        # sessions_since_turn, last_turn_date
        sst, ltt = sst_map.get(key, (-1, None))

        # stock_cloud_turns_5d
        sc5d = cloud5d_map.get(key, 0)

        # ── Score components ─────────────────────────────────────────────────
        breadth_score = _clamp(bew / 0.60, 0.0, 1.0)

        if sst != -1 and sst <= 5:
            turn_recency_score = 0.50
        elif sst != -1 and sst <= 10:
            turn_recency_score = 0.30
        elif sst != -1 and sst <= 20:
            turn_recency_score = 0.15
        else:
            turn_recency_score = 0.00

        # Fix 2: corrected follower_score formula
        follower_score = min(sc5d / 3, 1.0) * 0.30

        if clf_val == "LEADER_DRIVEN":
            leader_drag_penalty = 0.50
        elif clf_val == "COINCIDENT":
            leader_drag_penalty = 0.20
        else:
            leader_drag_penalty = 0.00

        score = breadth_score + turn_recency_score + follower_score - leader_drag_penalty

        tier  = _assign_tier(clf_val, dhr60)
        badge = _assign_badge(score)
        # Fix 1: Tier D groups must not surface as normal rotation signals
        if tier == "D":
            badge = "GROUP_RESEARCH_ONLY" if score >= 0.5 else "GROUP_NO_SIGNAL"

        # Fix 3: operator note by tier
        _OPERATOR_NOTES = {
            "A": "Broad-based validated group; review A3 candidates first when signal active.",
            "B": "Coincident confirmation; useful context, not lead signal.",
            "C": "Leader-driven; inspect leader first, be careful with followers.",
            "D": "Research-only / not validated enough for ranking priority.",
        }
        operator_note = _OPERATOR_NOTES.get(tier, "")

        a3_gate_status = "GATE_PASS" if a3_gp == 1 else "GATE_FAIL"

        rows.append({
            # Core identifiers
            "grouping_layer":              row["grouping_layer"],
            "group_name":                  row["group_name"],
            "tier":                        tier,
            "group_tier":                  tier,           # Fix 3: alias
            "group_classification":        clf_val,
            "n_symbols":                   n_sym,
            # Breadth
            "breadth_equal_weight":        round(bew, 4),
            "breadth_liquidity_weighted":  round(bliq, 4) if not np.isnan(bliq) else None,
            # Score components
            "breadth_score":               round(breadth_score, 4),
            "turn_recency_score":          turn_recency_score,
            "follower_score":              round(follower_score, 4),
            "leader_drag_penalty":         leader_drag_penalty,
            "group_rotation_score":        round(score, 4),
            # Badges
            "signal_badge":                badge,
            "dashboard_badge":             badge,          # Fix 3: alias
            # Recency / followers
            "sessions_since_turn":         sst,
            "last_turn_date":              ltt.strftime("%Y-%m-%d") if ltt is not None else None,
            "stock_cloud_turns_5d":        sc5d,
            # Research evidence
            "delta_hit_rate_60d":          round(dhr60, 4) if not np.isnan(dhr60) else None,
            "delta_mean_60d":              round(dmn60, 4) if not np.isnan(dmn60) else None,  # Fix 3
            "a3_gate_pass":                a3_gp,
            "a3_gate_status":              a3_gate_status, # Fix 3: derived label
            "excess_turn_pct":             round(exc_pct, 4) if not np.isnan(exc_pct) else None,
            # Operator guidance
            "operator_note":               operator_note,  # Fix 3
            # Meta
            "snapshot_date":               snap_ts.strftime("%Y-%m-%d"),
            "execution_allowed_flag":      False,
        })

    result = pd.DataFrame(rows)
    result = result.sort_values("group_rotation_score", ascending=False).reset_index(drop=True)

    # Safety: confirm no row has execution_allowed_flag != False
    assert (result["execution_allowed_flag"] == False).all(), \
        "CRITICAL: execution_allowed_flag must be False for all rows"

    log.info(
        "Group rotation snapshot: %d groups, snapshot=%s, "
        "strong=%d, moderate=%d, weak=%d, research_only=%d, no_signal=%d",
        len(result),
        snap_ts.date(),
        (result["signal_badge"] == "GROUP_STRONG_ROTATION").sum(),
        (result["signal_badge"] == "GROUP_MODERATE_ROTATION").sum(),
        (result["signal_badge"] == "GROUP_WEAK_ROTATION").sum(),
        (result["signal_badge"] == "GROUP_RESEARCH_ONLY").sum(),
        (result["signal_badge"] == "GROUP_NO_SIGNAL").sum(),
    )
    return result
