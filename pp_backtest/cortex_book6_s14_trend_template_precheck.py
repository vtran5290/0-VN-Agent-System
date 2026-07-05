#!/usr/bin/env python3
"""S14 Minervini Trend Template MA stack — degeneracy pre-check."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B
from pp_backtest.cortex_degeneracy_common import (
    iter_oos_signals,
    load_stack,
    rolling_sma,
    write_precheck_outputs,
)
from pp_backtest.p0_realism_p1_winner import _build_honest_cache

OUT_MD = REPO / "data" / "research" / "cortex_book6" / "s14_trend_template_precheck.md"
OUT_JSON = REPO / "data" / "research" / "cortex_book6" / "s14_trend_template_precheck_meta.json"

CRITERIA = [
    "c1_ma_stack",
    "c2_sma50_up",
    "c3_sma150_up",
    "c4_sma200_up",
    "c5_30pct_above_52w_low",
    "c6_above_sma50",
    "c7_above_sma150",
    "c8_above_sma200",
]


def _eval_signal(sp: dict, pi: int) -> tuple[dict[str, bool], bool]:
    close = sp["close"]
    low = sp["low"]
    px = float(close[pi])
    if pi < 199:
        return {}, False
    s50 = rolling_sma(close, pi, 50)
    s150 = rolling_sma(close, pi, 150)
    s200 = rolling_sma(close, pi, 200)
    if not all(np.isfinite(x) for x in (s50, s150, s200)):
        return {}, False
    s50_20 = rolling_sma(close, pi - 20, 50)
    s150_20 = rolling_sma(close, pi - 20, 150)
    s200_20 = rolling_sma(close, pi - 20, 200)
    lo_52w = float(np.min(low[max(0, pi - 251) : pi + 1]))
    crit = {
        "c1_ma_stack": px > s50 > s150 > s200,
        "c2_sma50_up": np.isfinite(s50_20) and s50 > s50_20,
        "c3_sma150_up": np.isfinite(s150_20) and s150 > s150_20,
        "c4_sma200_up": np.isfinite(s200_20) and s200 > s200_20,
        "c5_30pct_above_52w_low": lo_52w > 0 and px >= 1.30 * lo_52w,
        "c6_above_sma50": px >= s50,
        "c7_above_sma150": px >= s150,
        "c8_above_sma200": px >= s200,
    }
    return crit, True


def main() -> dict:
    print("S14 Trend Template pre-check", flush=True)
    stack = load_stack()
    panel = stack["ctx"].panel
    cache = _build_honest_cache(panel)

    rows: list[dict] = []
    short_history = 0
    for sym, sig_dt, pi, sp in iter_oos_signals(panel, cache):
        crit, ok = _eval_signal(sp, pi)
        if not ok:
            short_history += 1
            continue
        rows.append({"symbol": sym, "signal_date": sig_dt, **crit, "all_pass": all(crit.values())})

    df = pd.DataFrame(rows)
    n = len(df)
    pass_rate = float(df["all_pass"].mean()) if n else 0.0
    exclude_rate = 1.0 - pass_rate
    fail_counts = {c: int((~df[c]).sum()) for c in CRITERIA} if n else {c: 0 for c in CRITERIA}
    binding = max(fail_counts, key=fail_counts.get) if fail_counts else "n/a"

    sub_a = df[sub_window_mask(pd.to_datetime(df["signal_date"]), OOS_SUB_WINDOW_A)] if n else df
    sub_b = df[sub_window_mask(pd.to_datetime(df["signal_date"]), OOS_SUB_WINDOW_B)] if n else df
    pass_a = float(sub_a["all_pass"].mean()) if len(sub_a) else float("nan")
    pass_b = float(sub_b["all_pass"].mean()) if len(sub_b) else float("nan")

    verdict = "EXPRESSIBLE" if pass_rate <= 0.95 else "VN-SUBSUMED"

    meta = {
        "date": str(date.today()),
        "n_oos_signals": n,
        "short_ma_history_excluded": short_history,
        "pass_rate": round(pass_rate, 4),
        "exclude_rate": round(exclude_rate, 4),
        "n_remaining_if_s14": int(df["all_pass"].sum()) if n else 0,
        "per_criterion_fail_rate": {c: round(fail_counts[c] / n, 4) if n else 0 for c in CRITERIA},
        "binding_criterion": binding,
        "sub_a_pass_rate": round(pass_a, 4) if np.isfinite(pass_a) else None,
        "sub_b_pass_rate": round(pass_b, 4) if np.isfinite(pass_b) else None,
    }

    body = [
        f"- OOS signals evaluated: **{n}** (excluded {short_history} for <200d MA history)",
        f"- All-8-criteria pass rate: **{100*pass_rate:.1f}%**",
        f"- Excluded by S14 (any fail): **{100*exclude_rate:.1f}%**",
        f"- N remaining if S14 applied: **{meta['n_remaining_if_s14']}**",
        f"- Binding criterion (most failures): **{binding}**",
        "",
        "## Per-criterion failure rate",
        "",
        "| Criterion | Fail % |",
        "|-----------|--------|",
    ]
    for c in CRITERIA:
        body.append(f"| {c} | {100*meta['per_criterion_fail_rate'][c]:.1f}% |")
    body += [
        "",
        "## Sub-windows",
        f"- Sub-A pass rate: {100*pass_a:.1f}%" if np.isfinite(pass_a) else "- Sub-A: n/a",
        f"- Sub-B pass rate: {100*pass_b:.1f}%" if np.isfinite(pass_b) else "- Sub-B: n/a",
    ]
    write_precheck_outputs(OUT_MD, OUT_JSON, "S14 Trend Template Pre-Check", verdict, meta, body)
    print(f"  pass_rate={pass_rate:.3f} verdict={verdict}", flush=True)
    print(f"  Report: {OUT_MD}", flush=True)
    return meta


def sub_window_mask(series: pd.Series, window: tuple[int, int]) -> pd.Series:
    y0, y1 = window
    return (series.dt.year >= y0) & (series.dt.year <= y1)


if __name__ == "__main__":
    main()
