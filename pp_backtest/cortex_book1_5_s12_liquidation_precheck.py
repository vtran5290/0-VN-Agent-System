#!/usr/bin/env python3
"""S12 Minervini institutional liquidation exit — degeneracy pre-check."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B
from pp_backtest.cortex_degeneracy_common import build_symbol_panel, load_stack, oos_entry_mask, write_precheck_outputs

OUT_MD = REPO / "data" / "research" / "cortex_book1_5" / "s12_liquidation_precheck.md"
OUT_JSON = REPO / "data" / "research" / "cortex_book1_5" / "s12_liquidation_precheck_meta.json"
LIMIT_THRESH = -0.069


def _holding_min_return(sp: dict, entry_i: int, exit_i: int) -> float:
    close = sp["close"]
    if exit_i <= entry_i or entry_i < 1:
        return float("nan")
    rets = close[entry_i : exit_i + 1] / close[entry_i - 1 : exit_i] - 1.0
    rets = rets[np.isfinite(rets)]
    return float(np.min(rets)) if len(rets) else float("nan")


def main() -> dict:
    print("S12 liquidation pre-check", flush=True)
    stack = load_stack()
    panel = stack["ctx"].panel
    sym_panel = build_symbol_panel(panel)
    trades = stack["base_trades"].copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["exit_date"] = pd.to_datetime(trades["exit_date"])
    oos = trades[oos_entry_mask(trades)]

    min_dds: list[float] = []
    hold_days: list[int] = []
    sub_a_hits: list[bool] = []
    sub_b_hits: list[bool] = []

    for _, row in oos.iterrows():
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            continue
        entry_dt = pd.Timestamp(row["entry_date"]).normalize()
        exit_dt = pd.Timestamp(row["exit_date"]).normalize()
        ei = sp["date_to_i"].get(entry_dt)
        xi = sp["date_to_i"].get(exit_dt)
        if ei is None or xi is None:
            continue
        mdd = _holding_min_return(sp, ei, xi)
        if not np.isfinite(mdd):
            continue
        min_dds.append(mdd)
        hold_days.append(max(xi - ei, 0))
        hit = mdd <= LIMIT_THRESH
        y = entry_dt.year
        if OOS_SUB_WINDOW_A[0] <= y <= OOS_SUB_WINDOW_A[1]:
            sub_a_hits.append(hit)
        if OOS_SUB_WINDOW_B[0] <= y <= OOS_SUB_WINDOW_B[1]:
            sub_b_hits.append(hit)

    arr = np.array(min_dds)
    n = len(arr)
    if n < 30:
        verdict = "VN-THIN"
    else:
        band_hit_rate = float((arr <= LIMIT_THRESH).mean())
        verdict = "VN-SUBSUMED" if band_hit_rate > 0.80 else "EXPRESSIBLE"

    band_hit_rate = float((arr <= LIMIT_THRESH).mean()) if n else 0.0
    bins = {
        "at_limit_-7pct": int((arr <= LIMIT_THRESH).sum()),
        "minus5_to_minus7": int(((arr > LIMIT_THRESH) & (arr <= -0.05)).sum()),
        "minus3_to_minus5": int(((arr > -0.05) & (arr <= -0.03)).sum()),
        "zero_to_minus3": int((arr > -0.03).sum()),
    }

    meta = {
        "date": str(date.today()),
        "n_oos_positions": n,
        "band_hit_rate": round(band_hit_rate, 4),
        "mean_holding_days": round(float(np.mean(hold_days)), 1) if hold_days else None,
        "histogram": bins,
        "sub_a_band_hit_rate": round(float(np.mean(sub_a_hits)), 4) if sub_a_hits else None,
        "sub_b_band_hit_rate": round(float(np.mean(sub_b_hits)), 4) if sub_b_hits else None,
        "stage2_proxy_note": "Entry date used as Stage 2 advance start (Minervini proxy)",
    }

    body = [
        f"- OOS positions analyzed: **{n}**",
        f"- Largest-DD-day = limit-down (−7%): **{100*band_hit_rate:.1f}%**",
        f"- Mean holding period: **{meta['mean_holding_days']}** days",
        "",
        "## Largest single-day decline distribution",
        "",
        "| Bin | Count |",
        "|-----|-------|",
        f"| ≤ −7% (limit) | {bins['at_limit_-7pct']} |",
        f"| −5% to −7% | {bins['minus5_to_minus7']} |",
        f"| −3% to −5% | {bins['minus3_to_minus5']} |",
        f"| > −3% | {bins['zero_to_minus3']} |",
        "",
        f"- Sub-A band hit rate: {meta['sub_a_band_hit_rate']}",
        f"- Sub-B band hit rate: {meta['sub_b_band_hit_rate']}",
        f"- Note: {meta['stage2_proxy_note']}",
    ]
    write_precheck_outputs(OUT_MD, OUT_JSON, "S12 Liquidation Exit Pre-Check", verdict, meta, body)
    print(f"  band_hit_rate={band_hit_rate:.3f} verdict={verdict}", flush=True)
    print(f"  Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
