#!/usr/bin/env python3
"""S15 FIP quality momentum — degeneracy pre-check."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_degeneracy_common import iter_oos_signals, load_stack, write_precheck_outputs
from pp_backtest.p0_realism_p1_winner import _build_honest_cache

OUT_MD = REPO / "data" / "research" / "cortex_book7" / "s15_fip_precheck.md"
OUT_JSON = REPO / "data" / "research" / "cortex_book7" / "s15_fip_precheck_meta.json"
LOOKBACK = 252
LIMIT_BAND = 0.069


def _compute_fip(close: np.ndarray, pi: int) -> tuple[float, float, int]:
    """Return (fip, limit_move_rate, n_returns) for signal index pi."""
    start = pi - LOOKBACK
    if start < 1:
        return float("nan"), float("nan"), 0
    rets = close[start + 1 : pi + 1] / close[start:pi] - 1.0
    rets = rets[np.isfinite(rets)]
    if len(rets) < LOOKBACK // 2:
        return float("nan"), float("nan"), len(rets)
    pos = float((rets > 0).mean())
    neg = float((rets < 0).mean())
    past_ret = float(close[pi] / close[start] - 1.0)
    sign = 1.0 if past_ret > 0 else (-1.0 if past_ret < 0 else 0.0)
    fip = sign * (neg - pos)
    lim = float((rets <= -LIMIT_BAND).mean() + (rets >= LIMIT_BAND).mean())
    return fip, lim, len(rets)


def main() -> dict:
    print("S15 FIP pre-check", flush=True)
    stack = load_stack()
    panel = stack["ctx"].panel
    cache = _build_honest_cache(panel)

    fips: list[float] = []
    limits: list[float] = []
    for _sym, _sig, pi, sp in iter_oos_signals(panel, cache):
        fip, lim, n = _compute_fip(sp["close"], pi)
        if np.isfinite(fip):
            fips.append(fip)
            limits.append(lim)

    arr = np.array(fips)
    lim_arr = np.array(limits)
    std_fip = float(np.std(arr)) if len(arr) else 0.0
    mean_lim = float(np.mean(lim_arr)) if len(lim_arr) else 0.0
    pcts = {k: float(np.percentile(arr, q)) for k, q in zip(("p10", "p25", "p50", "p75", "p90"), (10, 25, 50, 75, 90))} if len(arr) else {}

    tercile_cut = float(np.percentile(arr, 33.33)) if len(arr) else float("nan")
    top_tercile_n = int((arr <= tercile_cut).sum()) if len(arr) else 0

    if std_fip <= 0.05 or mean_lim >= 0.30:
        verdict = "VN-SUBSUMED"
    elif top_tercile_n < 30:
        verdict = "VN-THIN"
    else:
        verdict = "EXPRESSIBLE"

    meta = {
        "date": str(date.today()),
        "n_oos_signals": len(arr),
        "std_fip": round(std_fip, 4),
        "mean_fip": round(float(np.mean(arr)), 4) if len(arr) else None,
        "fip_percentiles": {k: round(v, 4) for k, v in pcts.items()},
        "limit_move_rate": round(mean_lim, 4),
        "top_tercile_n_oos": top_tercile_n,
        "top_tercile_cutoff": round(tercile_cut, 4) if np.isfinite(tercile_cut) else None,
    }

    body = [
        f"- OOS signals with valid FIP: **{len(arr)}**",
        f"- std(FIP): **{std_fip:.4f}** (gate > 0.05)",
        f"- Mean ±7% limit-move rate: **{100*mean_lim:.1f}%** (gate < 30%)",
        f"- Top-tercile (smoothest) N_OOS: **{top_tercile_n}** (gate ≥ 30)",
        "",
        "## FIP distribution",
        "",
        "| Stat | Value |",
        "|------|-------|",
        f"| mean | {meta['mean_fip']} |",
    ]
    for k in ("p10", "p25", "p50", "p75", "p90"):
        body.append(f"| {k} | {meta['fip_percentiles'].get(k, 'n/a')} |")

    write_precheck_outputs(OUT_MD, OUT_JSON, "S15 FIP Pre-Check", verdict, meta, body)
    print(f"  std_fip={std_fip:.4f} verdict={verdict}", flush=True)
    print(f"  Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
