"""Deterministic warning states (context only)."""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd


def warning_state_row(row: pd.Series, *, breadth_ex_vin: Optional[float] = None) -> str:
    d25_raw = row.get("dist_count_25d")
    if d25_raw is None or (isinstance(d25_raw, float) and pd.isna(d25_raw)):
        return "UNKNOWN"
    d25 = float(d25_raw)
    below20 = float(row.get("close_above_ema20", 1)) < 1
    below50 = float(row.get("close_above_ema50", 1)) < 1
    if pd.isna(row.get("close")):
        return "UNKNOWN"
    if d25 <= 1:
        return "NORMAL"
    if d25 <= 3:
        return "CAUTION"
    if d25 >= 5 and below50:
        return "DOWNTREND_WARNING"
    if d25 >= 4 and (below20 or (breadth_ex_vin is not None and breadth_ex_vin < 40)):
        return "CORRECTION_RISK"
    if d25 >= 4:
        return "DISTRIBUTION_CLUSTER"
    return "CAUTION"


def vin_distortion_flag(
    raw_ret_10d: Optional[float],
    ex_ret_10d: Optional[float],
    raw_ret_25d: Optional[float],
    ex_ret_25d: Optional[float],
) -> bool:
    if raw_ret_10d is not None and ex_ret_10d is not None:
        if abs(raw_ret_10d - ex_ret_10d) >= 0.02:
            return True
    if raw_ret_25d is not None and ex_ret_25d is not None:
        if abs(raw_ret_25d - ex_ret_25d) >= 0.03:
            return True
    return False


def warning_disagreement(state_raw: str, state_ex: str) -> bool:
    risky = {"CORRECTION_RISK", "DOWNTREND_WARNING", "DISTRIBUTION_CLUSTER"}
    calm = {"NORMAL", "CAUTION"}
    return (state_raw in risky and state_ex in calm) or (state_ex in risky and state_raw in calm)


def snapshot_probabilities(
    prob_table: pd.DataFrame,
    *,
    index_view: str,
    bucket: str,
    metric: str = "dist_count_25d",
) -> dict[str, Any]:
    sub = prob_table[
        (prob_table["index_view"] == index_view)
        & (prob_table["metric"] == metric)
        & (prob_table["bucket"] == bucket)
    ]
    out: dict[str, Any] = {}
    base_rates: dict[str, float] = {}
    for _, r in sub.iterrows():
        h = int(r["horizon_d"])
        out[f"p_ret_neg_{h}d"] = r["p_ret_neg"]
        if pd.notna(r.get("base_rate_p_ret_neg")):
            base_rates[f"p_ret_neg_{h}d"] = float(r["base_rate_p_ret_neg"])
        if h == 25:
            out["p_correction_5pct_25d"] = r.get("p_max_dd_le_neg5pct")
            if pd.notna(r.get("base_rate_p_max_dd_le_neg5pct")):
                base_rates["p_correction_5pct_25d"] = float(r["base_rate_p_max_dd_le_neg5pct"])
        if h == 75:
            out["p_correction_10pct_75d"] = r.get("p_max_dd_le_neg10pct")
            if pd.notna(r.get("base_rate_p_max_dd_le_neg10pct")):
                base_rates["p_correction_10pct_75d"] = float(r["base_rate_p_max_dd_le_neg10pct"])
    if base_rates:
        out["base_rates"] = base_rates
    if sub.empty:
        out["sample_size"] = 0
        out["confidence"] = "LOW"
    else:
        out["sample_size"] = int(sub["n"].max())
        out["confidence"] = str(sub["confidence"].iloc[0])
        lifts = {}
        for _, r in sub.iterrows():
            h = int(r["horizon_d"])
            if pd.notna(r.get("lift_p_ret_neg")):
                lifts[f"lift_p_ret_neg_{h}d"] = float(r["lift_p_ret_neg"])
        if lifts:
            out["lift_vs_base"] = lifts
    return out
