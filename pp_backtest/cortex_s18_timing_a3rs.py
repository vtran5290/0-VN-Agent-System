#!/usr/bin/env python3
"""
S18 sector persistence — timing overlay on A3_RS+S2@1.4x baseline.

Prior: S18 DEGRADING-REJECT on S1 pool (OOS MAR 0.4615 < 1.7844 baseline).
Reframe: apply as market-breadth timing filter on A3_RS+S2@1.4x trades.
Pre-reg: knowledge/backtests/2026-07-08_s18_timing_a3rs_prereg.md

RESEARCH_ONLY_NOT_PRODUCTION
Usage: python pp_backtest/cortex_s18_timing_a3rs.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_book1_common import OOS_WINDOW, PANEL_START, PANEL_END
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_schwager_common import (
    build_sector_triggers,
    build_stack_with_sector,
    filter_trades_s18,
    oos_sub_mar,
    persistence_rate,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_s18_timing_a3rs"

# Baseline from S2 extension recompute (2026-07-08)
S2_BASE_MULT = 1.4
NEW_BASELINE_OOS_MAR = 2.5292
REPRO_TOL = 0.050

# Prior S18 result (on S1 pool) — G4 sanity check
PRIOR_S18_S1_OOS_MAR = 0.4615

# Gates (k=1 — new test category on A3_RS platform)
G1A_MARGIN = 0.050
G1A_THRESH = NEW_BASELINE_OOS_MAR + G1A_MARGIN   # 2.5792
G1B_THRESH = max(0.10, NEW_BASELINE_OOS_MAR * 0.50)  # 1.2646
G2_N_OOS_MIN = 200      # minimum filtered OOS trades
G3_SUB_B_MIN = 0.50     # sub-B MAR guard
G4_PRIOR = PRIOR_S18_S1_OOS_MAR  # sanity: must beat prior degraded result

# Candidates: same k values as original S18 IS-locked params, roll=20
CANDIDATES = [
    ("s18_k075_r20", 0.75, 20),
    ("s18_k100_r20", 1.00, 20),
]


def _gate_verdict(oos_mar: float, n_oos: int, sub_b: float) -> str:
    if not np.isfinite(oos_mar):
        return "PARKED"
    if n_oos < G2_N_OOS_MIN:
        return "VN-THIN"
    if oos_mar < 0:
        return "PARKED"
    if oos_mar < G1B_THRESH:
        return "FAIL"
    if oos_mar < G1A_THRESH:
        return "CONDITIONAL-ADVANCE"
    return "ADVANCE"


def run_s18_timing() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("S18 sector persistence — A3_RS+S2@1.4x timing overlay", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)
    print(f"  Baseline: A3_RS+S2@{S2_BASE_MULT}x OOS MAR = {NEW_BASELINE_OOS_MAR}", flush=True)

    # --- Step 1: Build S2@1.4x trades via schwager stack (includes sector data) ---
    print("\nStep 1: Building stack with sector data...", flush=True)
    stack = build_stack_with_sector()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    sector_map = stack["sector_map"]
    sector_rets = stack["sector_rets"]
    filter_map = stack["filter_map"]

    print("  Applying S2@1.4x volume filter...", flush=True)
    s2_trades = apply_volume_filter(stack["base_trades"], filter_map, S2_BASE_MULT)
    s2_trades["entry_date"] = pd.to_datetime(s2_trades["entry_date"])
    s2_trades["exit_date"] = pd.to_datetime(s2_trades["exit_date"])

    # Baseline verification
    sized_base = apply_size(s2_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_base = prepare_trades_with_size(sized_base, "rs_score", "_size_mult")
    eq_base, _, _ = run_capital_sim(prep_base, ctx.gate, D4_CASH_YIELD)
    eq_oos_base = slice_equity_years(eq_base, OOS_WINDOW[0], OOS_WINDOW[1])
    baseline_oos_mar = float(_metrics_from_equity(eq_oos_base)["mar"])
    n_oos_base = count_oos_trades(sized_base, OOS_WINDOW[0], OOS_WINDOW[1])
    print(f"  A3_RS+S2@1.4x recomputed OOS MAR: {baseline_oos_mar:.4f} (expected {NEW_BASELINE_OOS_MAR})", flush=True)
    print(f"  N_OOS base: {n_oos_base}", flush=True)

    repro_ok = abs(baseline_oos_mar - NEW_BASELINE_OOS_MAR) <= REPRO_TOL
    if not repro_ok:
        drift = abs(baseline_oos_mar - NEW_BASELINE_OOS_MAR)
        print(f"  [BASELINE-DRIFT] deviation {drift:.4f} > {REPRO_TOL} — halting", flush=True)
        return {"halted": True, "baseline_oos_mar": baseline_oos_mar}

    print(f"  Reproducibility OK. Sector panel: {len(sector_rets)} sector-day rows", flush=True)
    print(f"  Sectors covered: {sector_rets['sector'].nunique()}", flush=True)

    # --- Step 2: Run candidates ---
    results: list[dict[str, Any]] = []

    for label, k, roll in CANDIDATES:
        print(f"\nStep 2: Candidate {label} (k={k}, roll={roll})...", flush=True)
        triggers = build_sector_triggers(sector_rets, k, roll=roll)

        oos_p, oos_n_trigger = persistence_rate(triggers, OOS_WINDOW)
        print(f"  OOS persistence: {oos_p:.1%}, N trigger events: {oos_n_trigger}", flush=True)

        # Filter S2@1.4x trades by sector trigger on signal date
        filt = filter_trades_s18(s2_trades, sector_map, triggers)
        print(f"  Filtered trades: {len(filt)} / {len(s2_trades)} total", flush=True)

        if filt.empty:
            print(f"  No trades passed S18 filter — VN-THIN", flush=True)
            results.append({
                "label": label, "k": k, "roll": roll,
                "oos_mar": float("nan"), "delta": float("nan"),
                "sub_a_mar": float("nan"), "sub_b_mar": float("nan"),
                "n_oos": 0, "oos_persistence": oos_p,
                "verdict": "VN-THIN",
            })
            continue

        # Size and simulate filtered trades using A3_RS context
        sized_filt = apply_size(filt, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
        prep_filt = prepare_trades_with_size(sized_filt, "rs_score", "_size_mult")
        eq_filt, _, _ = run_capital_sim(prep_filt, ctx.gate, D4_CASH_YIELD)

        eq_oos_filt = slice_equity_years(eq_filt, OOS_WINDOW[0], OOS_WINDOW[1])
        eq_a = slice_equity_years(eq_filt, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
        eq_b = slice_equity_years(eq_filt, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])

        m_oos = _metrics_from_equity(eq_oos_filt)
        m_a = _metrics_from_equity(eq_a)
        m_b = _metrics_from_equity(eq_b)

        oos_mar = float(m_oos["mar"])
        sub_a_mar = float(m_a["mar"])
        sub_b_mar = float(m_b["mar"])
        n_oos = count_oos_trades(filt, OOS_WINDOW[0], OOS_WINDOW[1])
        verdict = _gate_verdict(oos_mar, n_oos, sub_b_mar)

        # G4 sanity
        g4_pass = np.isfinite(oos_mar) and oos_mar > G4_PRIOR
        if not g4_pass:
            print(f"  [G4-FAIL] OOS MAR {oos_mar:.4f} <= prior S18-S1 {G4_PRIOR:.4f} — structural red flag", flush=True)

        print(
            f"  {label}: OOS MAR={oos_mar:.4f} sub-A={sub_a_mar:.4f} sub-B={sub_b_mar:.4f} "
            f"N_OOS={n_oos} G4={'PASS' if g4_pass else 'FAIL'} verdict={verdict}",
            flush=True,
        )
        results.append({
            "label": label,
            "k": k,
            "roll": roll,
            "oos_mar": oos_mar,
            "delta": oos_mar - baseline_oos_mar,
            "sub_a_mar": sub_a_mar,
            "sub_b_mar": sub_b_mar,
            "n_oos": n_oos,
            "oos_persistence": oos_p,
            "oos_n_trigger_events": oos_n_trigger,
            "n_filtered": len(filt),
            "n_total_s2_trades": len(s2_trades),
            "filter_rate": len(filt) / len(s2_trades) if s2_trades.shape[0] > 0 else 0.0,
            "g4_pass": g4_pass,
            "verdict": verdict,
        })

    # --- Step 3: Write report ---
    today = str(date.today())
    lines = [
        "# S18 Sector Persistence — Timing Overlay on A3_RS+S2@1.4x",
        "",
        f"**Generated:** {today}",
        f"**Baseline:** A3_RS+S2@1.4x OOS MAR = {baseline_oos_mar:.4f} (expected {NEW_BASELINE_OOS_MAR})",
        f"**G1a gate:** >= {G1A_THRESH:.4f}",
        f"**G1b gate:** >= {G1B_THRESH:.4f}",
        f"**G2 (N_OOS):** >= {G2_N_OOS_MIN}",
        f"**G3 (sub-B):** >= {G3_SUB_B_MIN}",
        f"**G4 sanity:** OOS MAR > {G4_PRIOR} (prior S18-on-S1 result)",
        "",
        "| Candidate | OOS MAR | Delta | sub-A | sub-B | N_OOS | Filter Rate | G4 | Verdict |",
        "|-----------|---------|-------|-------|-------|-------|-------------|----|---------| ",
    ]
    for r in results:
        g4 = "PASS" if r.get("g4_pass") else "FAIL"
        frate = f"{r.get('filter_rate', 0):.1%}" if r.get("filter_rate") is not None else "n/a"
        lines.append(
            f"| {r['label']} | {r['oos_mar']:.4f} | {r.get('delta', float('nan')):+.4f} | "
            f"{r['sub_a_mar']:.4f} | {r['sub_b_mar']:.4f} | {r['n_oos']} | "
            f"{frate} | {g4} | {r['verdict']} |"
        )
    lines += [
        "",
        f"**N_OOS base (unfiltered):** {n_oos_base}",
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ]

    report_path = OUT_DIR / f"{today}_s18_timing_a3rs_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "generated": today,
        "baseline_oos_mar": baseline_oos_mar,
        "g1a_thresh": G1A_THRESH,
        "g1b_thresh": G1B_THRESH,
        "g2_n_oos_min": G2_N_OOS_MIN,
        "g4_prior": G4_PRIOR,
        "n_oos_base": n_oos_base,
        "results": results,
    }
    meta_path = OUT_DIR / f"{today}_s18_timing_a3rs_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    print(f"\n  Wrote {report_path.name}", flush=True)

    # --- Summary ---
    print("\n=== SUMMARY ===", flush=True)
    print(f"  Baseline A3_RS+S2@1.4x: OOS MAR {baseline_oos_mar:.4f}", flush=True)
    for r in results:
        print(f"  {r['label']}: OOS MAR {r['oos_mar']:.4f} N_OOS={r['n_oos']} filter={r.get('filter_rate', 0):.1%} verdict={r['verdict']}", flush=True)

    return {
        "baseline_oos_mar": baseline_oos_mar,
        "results": results,
    }


def main() -> None:
    run_s18_timing()


if __name__ == "__main__":
    main()
