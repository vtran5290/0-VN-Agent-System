#!/usr/bin/env python3
"""S16 momentum seasonality — degeneracy pre-check."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B
from pp_backtest.cortex_degeneracy_common import load_stack, oos_entry_mask, write_precheck_outputs

OUT_MD = REPO / "data" / "research" / "cortex_book7" / "s16_seasonality_precheck.md"
OUT_JSON = REPO / "data" / "research" / "cortex_book7" / "s16_seasonality_precheck_meta.json"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main() -> dict:
    print("S16 seasonality pre-check", flush=True)
    stack = load_stack()
    trades = stack["base_trades"].copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    oos = trades[oos_entry_mask(trades)].copy()
    oos["entry_month"] = oos["entry_date"].dt.month
    oos["ret"] = oos["net_return"].astype(float)

    overall_mean = float(oos["ret"].mean()) if len(oos) else 0.0
    monthly = oos.groupby("entry_month").agg(n=("ret", "count"), mean_ret=("ret", "mean"))
    monthly_stats = {}
    for m in range(1, 13):
        row = monthly.loc[m] if m in monthly.index else None
        monthly_stats[m] = {
            "n": int(row["n"]) if row is not None else 0,
            "mean_ret": float(row["mean_ret"]) if row is not None else float("nan"),
        }

    means = [monthly_stats[m]["mean_ret"] for m in range(1, 13) if monthly_stats[m]["n"] >= 10]
    months_ge10 = sum(1 for m in range(1, 13) if monthly_stats[m]["n"] >= 10)
    monthly_std = float(np.std(means)) if len(means) >= 2 else 0.0

    ranked = sorted(
        [(m, monthly_stats[m]["mean_ret"], monthly_stats[m]["n"]) for m in range(1, 13) if monthly_stats[m]["n"] > 0],
        key=lambda x: x[1] if np.isfinite(x[1]) else -999,
    )
    bottom3 = ranked[:3]
    top3 = ranked[-3:][::-1]

    jan = monthly_stats[1]
    q_end_months = [3, 6, 9, 12]
    q_end_means = [monthly_stats[m]["mean_ret"] for m in q_end_months if monthly_stats[m]["n"] >= 5]

    if months_ge10 < 10:
        verdict = "VN-THIN"
    elif monthly_std <= 0.003:
        verdict = "VN-UNKNOWN-FLAT"
    else:
        verdict = "EXPRESSIBLE"

    meta = {
        "date": str(date.today()),
        "n_oos_trades": int(len(oos)),
        "overall_mean_return": round(overall_mean, 4),
        "monthly_std_of_means_pct": round(monthly_std * 100, 3),
        "months_with_ge10_trades": months_ge10,
        "january_mean": round(jan["mean_ret"], 4) if jan["n"] else None,
        "january_n": jan["n"],
        "q_end_mean": round(float(np.mean(q_end_means)), 4) if q_end_means else None,
        "top3_months": [{"month": m, "mean": round(r, 4), "n": n} for m, r, n in top3],
        "bottom3_months": [{"month": m, "mean": round(r, 4), "n": n} for m, r, n in bottom3],
        "monthly": {str(m): monthly_stats[m] for m in range(1, 13)},
    }

    body = [
        f"- OOS trades: **{len(oos)}**",
        f"- Months with ≥10 trades: **{months_ge10}**",
        f"- Std of monthly mean returns: **{100*monthly_std:.2f}%** (gate > 0.5%)",
        f"- January mean return: **{meta['january_mean']}** (n={jan['n']})",
        f"- Q-end months mean (Mar/Jun/Sep/Dec): **{meta['q_end_mean']}**",
        "",
        "## Mean return by entry month",
        "",
        "| Month | N | Mean return |",
        "|-------|---|-------------|",
    ]
    for m in range(1, 13):
        st = monthly_stats[m]
        mr = f"{100*st['mean_ret']:.2f}%" if np.isfinite(st["mean_ret"]) else "n/a"
        body.append(f"| {MONTH_NAMES[m-1]} | {st['n']} | {mr} |")

    body += ["", "## Top / bottom months (by mean return)"]
    body.append(f"- Best: {top3}")
    body.append(f"- Worst: {bottom3}")

    write_precheck_outputs(OUT_MD, OUT_JSON, "S16 Seasonality Pre-Check", verdict, meta, body)
    print(f"  monthly_std={monthly_std:.4f} verdict={verdict}", flush=True)
    print(f"  Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
