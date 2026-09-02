#!/usr/bin/env python3
"""
Cortex Book #2 — S2: O'Neil Breakout Volume Filter Backtest.

Belief: "Breakout volume must be 40%+ above 50-day average to confirm trend signal."
Source: O'Neil, How to Make Money in Stocks, Ch.2 (CAN-SLIM S = Supply/Demand)

Tests whether filtering A3_RS entry signals to those where signal-bar volume exceeds
its 50-day average by 1.2×, 1.3×, or 1.4× improves OOS MAR vs unfiltered baseline.

VN-THIN pre-check result (2026-07-05, empirical):
    ADV-qualified universe (OOS 2020-2026):
      volume >= 1.2× avg: 29.1% of stock-days → ~1,106 est. OOS filtered trades (k=3 VIABLE)
      volume >= 1.3× avg: 24.6% of stock-days → ~933 est. OOS filtered trades
      volume >= 1.4× avg: 20.8% of stock-days → ~788 est. OOS filtered trades
    All thresholds produce >>30 OOS trades. VN-THIN NOT triggered. k=3 locked.

Pre-registration: knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md
Gates addendum:   knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_gates_addendum.md
                  (write gates addendum BEFORE running this script)

RESEARCH_ONLY_NOT_PRODUCTION

Usage (from repo root, after activating .venv):
    python pp_backtest/cortex_book2_s2_volume.py

Expected runtime: ~5-10 minutes (same as S1 — shared panel load, separate filter step).

Data expected:
    data/stocks/*.csv  — per-symbol OHLCV
    data/benchmark/VNINDEX.csv — VNINDEX for regime gate
    data/master/sector_map.csv — symbol → sector mapping

Output:
    data/research/cortex_book2/s2_volume_report.md
    data/research/cortex_book2/s2_volume_report_meta.json
"""
from __future__ import annotations

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

from pp_backtest.cortex_book2_common import (
    G1A_MARGIN_ADJUSTED,
    G1A_THRESHOLD,
    G1B_ADJ,
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    S2_VOLUME_LABELS,
    S2_VOLUME_THRESHOLDS,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
    evaluate_gates_book2,
    write_book2_report,
)
from pp_backtest.cortex_book1_common import (
    IS_WINDOW,
    OOS_WINDOW,
    PANEL_END,
    PANEL_START,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
    signal_stream,
)
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_book2"
PREREG = "knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md"
GATES_ADDENDUM = "knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_gates_addendum.md"


def run_cortex_book2_s2() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Cortex Book #2 — S2: breakout volume filter", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)
    print(f"  OOS primary: {OOS_WINDOW[0]}-{OOS_WINDOW[1]}", flush=True)
    print(f"  G1a threshold (locked): OOS MAR >= {G1A_THRESHOLD:.4f}", flush=True)
    print(f"  G1b threshold (locked): OOS MAR >= {G1B_ADJ:.3f}", flush=True)
    print(f"  VN-THIN pre-check: VIABLE — k=3 locked (1.2×, 1.3×, 1.4×)", flush=True)
    print()

    # ── Step 1: build baseline ────────────────────────────────────────────────
    print("Building baseline stack (A3 P1 honest + D4 + D3)...", flush=True)
    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]
    eq_base = stack["eq"]

    m_base_full = _metrics_from_equity(eq_base)
    eq_base_oos = slice_equity_years(eq_base, OOS_WINDOW[0], OOS_WINDOW[1])
    m_base_oos = _metrics_from_equity(eq_base_oos)
    n_base_full = len(base_trades)
    n_base_oos = count_oos_trades(base_trades, OOS_WINDOW[0], OOS_WINDOW[1])
    print(f"  Baseline: full MAR={m_base_full['mar']:.4f} OOS MAR={m_base_oos['mar']:.4f}", flush=True)
    print(f"  Baseline trades: {n_base_full} full, {n_base_oos} OOS", flush=True)
    print()

    # ── Step 2: build signal filter map ──────────────────────────────────────
    # NOTE: filter_map also computes 52wk proximity (for S1), but we only use vol_mult here.
    print("Building signal-day filter map (volume multiples)...", flush=True)
    filter_map = build_signal_filter_map(ctx.panel)
    print(f"  Filter map entries: {len(filter_map)}", flush=True)

    # Diagnostic: volume multiple distribution over baseline signals
    vol_vals = []
    for _, row in base_trades.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = filter_map.get(key)
        if rec is not None:
            vol_vals.append(rec["vol_mult"])
    if vol_vals:
        vv = np.array(vol_vals)
        # Only use finite, positive values
        vv = vv[np.isfinite(vv) & (vv > 0)]
        print(f"  Volume multiple distribution over A3_RS signal days:")
        for t in S2_VOLUME_THRESHOLDS:
            pct = (vv >= t).mean() * 100
            cnt = int((vv >= t).sum())
            print(f"    >= {t:.1f}×: {pct:.1f}% ({cnt}/{len(vv)} signals)")
        print(f"  Median vol mult on signal days: {np.median(vv):.2f}×")
    print()

    # ── Step 3: run candidates ────────────────────────────────────────────────
    candidate_rows: list[dict[str, Any]] = []

    for min_vol_mult, label in zip(S2_VOLUME_THRESHOLDS, S2_VOLUME_LABELS):
        print(f"  Candidate: volume >= {min_vol_mult:.1f}× 50d avg...", flush=True)

        # Filter trade stream to volume-confirmed signals
        cand_trades = apply_volume_filter(base_trades, filter_map, min_vol_mult)

        # Verify subset constraint
        frozen_ok = all(s in signal_stream(base_trades) for s in signal_stream(cand_trades))
        n_cand_full = len(cand_trades)
        n_cand_oos = count_oos_trades(cand_trades, OOS_WINDOW[0], OOS_WINDOW[1])
        n_cand_oos_a = count_oos_trades(cand_trades, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
        n_cand_oos_b = count_oos_trades(cand_trades, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
        print(f"    Trades: {n_cand_full} full, {n_cand_oos} OOS, {n_cand_oos_a} OOS-A, {n_cand_oos_b} OOS-B", flush=True)

        if n_cand_full < 10:
            print(f"    SKIP: too few trades ({n_cand_full})", flush=True)
            candidate_rows.append({
                "label": label,
                "min_vol_mult": min_vol_mult,
                "verdict": "VN-THIN",
                "full": {"mar": float("nan"), "max_dd": float("nan"), "cagr": float("nan")},
                "oos": {"mar": float("nan"), "max_dd": float("nan"), "cagr": float("nan")},
                "n_full": n_cand_full,
                "n_oos": n_cand_oos,
                "n_oos_sub_a": n_cand_oos_a,
                "n_oos_sub_b": n_cand_oos_b,
                "gates": [],
                "frozen_subset_ok": frozen_ok,
            })
            continue

        # Apply D3 sector sizing (same as baseline)
        sized_cand = apply_size(cand_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
        prep_cand = prepare_trades_with_size(sized_cand, "rs_score", "_size_mult")

        # Run capital simulation
        eq_cand, fills_cand, ann_rt_cand = run_capital_sim(prep_cand, ctx.gate, D4_CASH_YIELD)

        # Metrics
        m_full = _metrics_from_equity(eq_cand)
        eq_oos = slice_equity_years(eq_cand, OOS_WINDOW[0], OOS_WINDOW[1])
        eq_oos_a = slice_equity_years(eq_cand, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
        eq_oos_b = slice_equity_years(eq_cand, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
        m_oos = _metrics_from_equity(eq_oos)
        m_oos_a = _metrics_from_equity(eq_oos_a)
        m_oos_b = _metrics_from_equity(eq_oos_b)

        # Gate evaluation
        gates, verdict = evaluate_gates_book2(
            m_base_oos, m_oos, m_oos_a, m_oos_b,
            n_cand_oos, n_cand_oos_a, n_cand_oos_b,
        )

        print(f"    OOS MAR={m_oos['mar']:.4f} verdict={verdict}", flush=True)

        candidate_rows.append({
            "label": label,
            "min_vol_mult": min_vol_mult,
            "verdict": verdict,
            "full": m_full,
            "oos": m_oos,
            "oos_sub_a": m_oos_a,
            "oos_sub_b": m_oos_b,
            "n_full": n_cand_full,
            "n_oos": n_cand_oos,
            "n_oos_sub_a": n_cand_oos_a,
            "n_oos_sub_b": n_cand_oos_b,
            "gates": gates,
            "frozen_subset_ok": frozen_ok,
            "annual_turnover_rts": ann_rt_cand,
        })

    # ── Step 4: write report ──────────────────────────────────────────────────
    meta: dict[str, Any] = {
        "generated": str(date.today()),
        "belief": "S2",
        "filter_type": "volume_multiple",
        "vn_thin_precheck": "VIABLE_k3",
        "vn_thin_precheck_date": "2026-07-05",
        "panel_start": PANEL_START,
        "panel_end": PANEL_END,
        "oos_window": list(OOS_WINDOW),
        "is_window": list(IS_WINDOW),
        "oos_sub_window_a": list(OOS_SUB_WINDOW_A),
        "oos_sub_window_b": list(OOS_SUB_WINDOW_B),
        "g1a_margin_adjusted": G1A_MARGIN_ADJUSTED,
        "g1a_threshold": G1A_THRESHOLD,
        "g1b_floor_adjusted": G1B_ADJ,
        "baseline_full": m_base_full,
        "baseline_oos": m_base_oos,
        "baseline_n_full": n_base_full,
        "baseline_n_oos": n_base_oos,
        "candidates": candidate_rows,
    }

    write_book2_report(
        out_dir=OUT_DIR,
        report_filename="s2_volume_report.md",
        belief_label="S2 — O'Neil Breakout Volume Filter",
        filter_kind="S2_volume_filter",
        prereg_path=PREREG,
        meta=meta,
    )
    return meta


def main() -> None:
    run_cortex_book2_s2()


if __name__ == "__main__":
    main()
