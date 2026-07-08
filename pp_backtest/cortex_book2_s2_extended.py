#!/usr/bin/env python3
"""
Cortex Book #2 — S2 Threshold Extension: 1.5× and 1.6×.

Tests whether stricter volume thresholds (1.5× and 1.6×) continue the
monotonic OOS MAR improvement observed at 1.2×/1.3×/1.4× (2.3608/2.4804/2.5447).

NEW BASELINE: S2@1.4× OOS MAR = 2.5447 (A3+S2 benchmark, recomputed live).
Gates are relative to this baseline, not the unfiltered A3_RS baseline (0.8386).

Pre-registration: knowledge/backtests/2026-07-08_s2_extended_prereg.md
Prior pre-reg:    knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md

RESEARCH_ONLY_NOT_PRODUCTION

Usage (from repo root, after activating .venv):
    python pp_backtest/cortex_book2_s2_extended.py
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

from pp_backtest.cortex_book2_common import (
    G1A_MARGIN_ADJUSTED,
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    N_OOS_MIN_FULL,
    N_OOS_MIN_SUBWINDOW,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_book1_common import (
    OOS_WINDOW,
    PANEL_START,
    PANEL_END,
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
    build_baseline_stack,
    slice_equity_years,
)

# ── Extension thresholds (k=2) ────────────────────────────────────────────────
S2_EXT_THRESHOLDS = [1.5, 1.6]
S2_EXT_LABELS = ["vol_1_5x", "vol_1_6x"]
S2_BASE_MULT = 1.4  # New baseline: S2@1.4× (prior CALIBRATED sweep max)

# ── Gate parameters (k=2 adjustment) ─────────────────────────────────────────
G1A_K2_MARGIN = 0.050 + 0.010 * np.log2(2)  # = 0.060

OUT_DIR = REPO / "data" / "research" / "cortex_book2"
PREREG = "knowledge/backtests/2026-07-08_s2_extended_prereg.md"


def _evaluate_gates_extended(
    new_baseline_oos_mar: float,
    cand_oos: dict,
    cand_oos_a: dict,
    cand_oos_b: dict,
    n_oos: int,
    n_oos_a: int,
    n_oos_b: int,
) -> tuple[list[dict], str]:
    g1a_thresh = new_baseline_oos_mar + G1A_K2_MARGIN
    g1b_thresh = max(0.10, new_baseline_oos_mar * 0.50)

    gates: list[dict] = []
    mar = cand_oos["mar"]

    if n_oos < N_OOS_MIN_FULL or n_oos_a < N_OOS_MIN_SUBWINDOW or n_oos_b < N_OOS_MIN_SUBWINDOW:
        gates.append({"name": "N_OOS", "result": "FAIL", "value": n_oos, "threshold": N_OOS_MIN_FULL})
        return gates, "VN-THIN"

    gates.append({
        "name": "G1a (relative, binding)",
        "result": "PASS" if mar >= g1a_thresh else "FAIL",
        "value": round(mar, 4),
        "threshold": round(g1a_thresh, 4),
    })
    gates.append({
        "name": "G1b (absolute floor, advisory)",
        "result": "PASS" if mar >= g1b_thresh else "FAIL",
        "value": round(mar, 4),
        "threshold": round(g1b_thresh, 4),
    })

    if mar >= g1a_thresh:
        verdict = "ADVANCE"
    elif mar >= g1b_thresh:
        verdict = "CONDITIONAL-ADVANCE"
    else:
        verdict = "RESEARCH-NEGATIVE"

    return gates, verdict


def run_s2_extended() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Cortex Book #2 — S2 Extension: 1.5× and 1.6×", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)
    print(f"  OOS primary: {OOS_WINDOW[0]}–{OOS_WINDOW[1]}", flush=True)
    print(f"  New baseline: S2@{S2_BASE_MULT}× (expected ~2.5447)", flush=True)
    print()

    # ── Step 1: Build unfiltered A3_RS stack ─────────────────────────────────
    print("Building unfiltered A3_RS baseline stack...", flush=True)
    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]

    # ── Step 2: Build signal filter map ──────────────────────────────────────
    print("Building signal-day filter map (volume multiples)...", flush=True)
    filter_map = build_signal_filter_map(ctx.panel)
    print(f"  Filter map entries: {len(filter_map)}", flush=True)
    print()

    # ── Step 3: Compute new baseline (S2@1.4×) ────────────────────────────────
    print(f"Computing new baseline: S2@{S2_BASE_MULT}×...", flush=True)
    base14_trades = apply_volume_filter(base_trades, filter_map, S2_BASE_MULT)
    n_base14_full = len(base14_trades)
    n_base14_oos = count_oos_trades(base14_trades, *OOS_WINDOW)
    n_base14_oos_a = count_oos_trades(base14_trades, *OOS_SUB_WINDOW_A)
    n_base14_oos_b = count_oos_trades(base14_trades, *OOS_SUB_WINDOW_B)

    sized_base14 = apply_size(base14_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_base14 = prepare_trades_with_size(sized_base14, "rs_score", "_size_mult")
    eq_base14, _, _ = run_capital_sim(prep_base14, ctx.gate, D4_CASH_YIELD)
    eq_base14_oos = slice_equity_years(eq_base14, OOS_WINDOW[0], OOS_WINDOW[1])
    m_base14_oos = _metrics_from_equity(eq_base14_oos)
    new_baseline_oos_mar = m_base14_oos["mar"]
    print(f"  S2@1.4× recomputed OOS MAR: {new_baseline_oos_mar:.4f} (expected ~2.5447)", flush=True)

    repro_ok = abs(new_baseline_oos_mar - 2.5447) <= 0.050
    if not repro_ok:
        print(f"  [REPRODUCIBILITY-FAIL] Deviation > 0.050 from 2.5447. Halting.", flush=True)
        return {"error": "REPRODUCIBILITY-FAIL", "recomputed_oos_mar": new_baseline_oos_mar}

    print(f"  Reproducibility OK. New G1a gate: {new_baseline_oos_mar:.4f} + {G1A_K2_MARGIN:.3f} = {new_baseline_oos_mar + G1A_K2_MARGIN:.4f}", flush=True)
    print()

    # ── Step 4: Run extension candidates ─────────────────────────────────────
    candidate_rows: list[dict[str, Any]] = []

    for min_vol_mult, label in zip(S2_EXT_THRESHOLDS, S2_EXT_LABELS):
        print(f"  Candidate: volume >= {min_vol_mult:.1f}× 50d avg...", flush=True)

        cand_trades = apply_volume_filter(base_trades, filter_map, min_vol_mult)
        n_full = len(cand_trades)
        n_oos = count_oos_trades(cand_trades, *OOS_WINDOW)
        n_oos_a = count_oos_trades(cand_trades, *OOS_SUB_WINDOW_A)
        n_oos_b = count_oos_trades(cand_trades, *OOS_SUB_WINDOW_B)
        print(f"    Trades: {n_full} full, {n_oos} OOS, {n_oos_a} OOS-A, {n_oos_b} OOS-B", flush=True)

        if n_full < 10:
            print(f"    SKIP: too few trades ({n_full})", flush=True)
            candidate_rows.append({
                "label": label,
                "min_vol_mult": min_vol_mult,
                "verdict": "VN-THIN",
                "oos": {"mar": float("nan"), "max_dd": float("nan"), "cagr": float("nan")},
                "oos_sub_a": {"mar": float("nan")},
                "oos_sub_b": {"mar": float("nan")},
                "n_full": n_full,
                "n_oos": n_oos,
                "n_oos_sub_a": n_oos_a,
                "n_oos_sub_b": n_oos_b,
                "gates": [],
            })
            continue

        sized_cand = apply_size(cand_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
        prep_cand = prepare_trades_with_size(sized_cand, "rs_score", "_size_mult")
        eq_cand, _, _ = run_capital_sim(prep_cand, ctx.gate, D4_CASH_YIELD)

        m_full = _metrics_from_equity(eq_cand)
        eq_oos = slice_equity_years(eq_cand, OOS_WINDOW[0], OOS_WINDOW[1])
        eq_oos_a = slice_equity_years(eq_cand, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
        eq_oos_b = slice_equity_years(eq_cand, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
        m_oos = _metrics_from_equity(eq_oos)
        m_oos_a = _metrics_from_equity(eq_oos_a)
        m_oos_b = _metrics_from_equity(eq_oos_b)

        gates, verdict = _evaluate_gates_extended(
            new_baseline_oos_mar, m_oos, m_oos_a, m_oos_b,
            n_oos, n_oos_a, n_oos_b,
        )

        delta = m_oos["mar"] - new_baseline_oos_mar
        print(f"    OOS MAR={m_oos['mar']:.4f} (delta={delta:+.4f} vs baseline {new_baseline_oos_mar:.4f}) verdict={verdict}", flush=True)
        print(f"    sub-A MAR={m_oos_a['mar']:.4f}  sub-B MAR={m_oos_b['mar']:.4f}", flush=True)

        candidate_rows.append({
            "label": label,
            "min_vol_mult": min_vol_mult,
            "verdict": verdict,
            "full": m_full,
            "oos": m_oos,
            "oos_sub_a": m_oos_a,
            "oos_sub_b": m_oos_b,
            "n_full": n_full,
            "n_oos": n_oos,
            "n_oos_sub_a": n_oos_a,
            "n_oos_sub_b": n_oos_b,
            "gates": gates,
            "delta_vs_baseline": round(delta, 4),
        })

    # ── Step 5: Write report ──────────────────────────────────────────────────
    meta: dict[str, Any] = {
        "generated": str(date.today()),
        "belief": "S2_extended",
        "filter_type": "volume_multiple",
        "prereg": PREREG,
        "panel_start": PANEL_START,
        "panel_end": PANEL_END,
        "oos_window": list(OOS_WINDOW),
        "oos_sub_window_a": list(OOS_SUB_WINDOW_A),
        "oos_sub_window_b": list(OOS_SUB_WINDOW_B),
        "new_baseline_s2_14x_oos_mar": round(new_baseline_oos_mar, 4),
        "new_baseline_n_full": n_base14_full,
        "new_baseline_n_oos": n_base14_oos,
        "new_baseline_n_oos_a": n_base14_oos_a,
        "new_baseline_n_oos_b": n_base14_oos_b,
        "g1a_k2_margin": round(G1A_K2_MARGIN, 3),
        "g1a_threshold": round(new_baseline_oos_mar + G1A_K2_MARGIN, 4),
        "g1b_threshold": round(max(0.10, new_baseline_oos_mar * 0.50), 4),
        "reproducibility_ok": repro_ok,
        "candidates": candidate_rows,
    }

    # Write JSON meta
    meta_path = OUT_DIR / "s2_extended_report_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"\n  Wrote meta -> {meta_path.relative_to(REPO)}", flush=True)

    # Write markdown report
    report_path = OUT_DIR / "s2_extended_report.md"
    lines: list[str] = [
        "# S2 Threshold Extension Report — 1.5× and 1.6×",
        "",
        f"**Generated:** {meta['generated']}",
        f"**Pre-reg:** {PREREG}",
        f"**New baseline (S2@1.4× recomputed):** OOS MAR = {new_baseline_oos_mar:.4f}",
        f"**G1a gate (binding):** ≥ {meta['g1a_threshold']:.4f}",
        f"**G1b gate (advisory):** ≥ {meta['g1b_threshold']:.4f}",
        "",
        "---",
        "",
        "## Results",
        "",
        "| Threshold | OOS MAR | Delta | sub-A | sub-B | N_OOS | Verdict |",
        "|-----------|---------|-------|-------|-------|-------|---------|",
    ]

    for row in candidate_rows:
        oos_mar = row["oos"].get("mar", float("nan"))
        oos_a_mar = row.get("oos_sub_a", {}).get("mar", float("nan"))
        oos_b_mar = row.get("oos_sub_b", {}).get("mar", float("nan"))
        delta = row.get("delta_vs_baseline", float("nan"))
        lines.append(
            f"| {row['min_vol_mult']:.1f}× | {oos_mar:.4f} | {delta:+.4f} | "
            f"{oos_a_mar:.4f} | {oos_b_mar:.4f} | {row['n_oos']} | {row['verdict']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Gate Details",
        "",
    ]
    for row in candidate_rows:
        lines.append(f"### {row['label']} ({row['min_vol_mult']:.1f}×)")
        for g in row.get("gates", []):
            lines.append(f"- {g['name']}: {g['result']} ({g['value']} vs threshold {g['threshold']})")
        lines.append("")

    lines += [
        "---",
        "",
        "## Interpretation",
        "",
        "| Metric | S2@1.2× | S2@1.3× | S2@1.4× (baseline) | S2@1.5× | S2@1.6× |",
        "|--------|---------|---------|---------------------|---------|---------|",
    ]
    ext_oos = {row["min_vol_mult"]: row["oos"].get("mar", float("nan")) for row in candidate_rows}
    lines.append(
        f"| OOS MAR | 2.3608 | 2.4804 | {new_baseline_oos_mar:.4f} | "
        f"{ext_oos.get(1.5, float('nan')):.4f} | {ext_oos.get(1.6, float('nan')):.4f} |"
    )

    lines += [
        "",
        "**Monotonic trend:** check whether OOS MAR continues to increase with threshold.",
        "",
        "`RESEARCH_ONLY_NOT_PRODUCTION`",
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Wrote report → {report_path.relative_to(REPO)}", flush=True)

    return meta


def main() -> None:
    result = run_s2_extended()
    if "error" in result:
        print(f"\n[ERROR] {result['error']}", flush=True)
        sys.exit(1)
    print("\n[DONE] S2 extension run complete.", flush=True)


if __name__ == "__main__":
    main()
