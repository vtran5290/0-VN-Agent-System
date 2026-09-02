#!/usr/bin/env python3
"""
Cortex Book #2 — S1+S2 Interaction Test.

Combined filter: S1 within_15pct (prox >= 0.85) AND S2 vol >= 1.4× on signal bar.
Baseline for gates: S1 standalone (not A3 raw).

Pre-registration: knowledge/backtests/2026-07-05_cortex_book2_s1s2_interaction_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    python pp_backtest/cortex_book2_s1s2_interaction.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

from pp_backtest.cortex_book1_common import (
    OOS_WINDOW,
    PANEL_END,
    PANEL_START,
    _fmt_pct,
)
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_proximity_filter,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    RESEARCH_LABEL,
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

OUT_DIR = REPO / "data" / "research" / "cortex_book2"
PREREG = "knowledge/backtests/2026-07-05_cortex_book2_s1s2_interaction_prereg.md"

# Locked pre-registration constants — do not modify post-run
S1_MIN_PROX = 0.85
S2_MIN_VOL = 1.4

S1_BASELINE = {
    "full_mar": 1.4435,
    "oos_mar": 1.7844,
    "oos_sub_b_mar": 0.5465,
    "n_oos": 1732,
    "n_oos_sub_a": 612,
    "n_oos_sub_b": 1120,
}

GATES = {
    "G_ia": 1.8344,
    "G_ib": 0.516,
    "G_full": 1.3935,
    "N_oos_full_min": 30,
    "N_oos_sub_min": 12,
    "severe_regression": S1_BASELINE["oos_mar"] - 0.100,
}


def apply_s1s2_combined_filter(
    trades: pd.DataFrame,
    filter_map: dict[tuple[str, pd.Timestamp], dict],
) -> pd.DataFrame:
    """S1 then S2 — intersection identical to applying both."""
    s1 = apply_proximity_filter(trades, filter_map, S1_MIN_PROX)
    return apply_volume_filter(s1, filter_map, S2_MIN_VOL)


def evaluate_interaction_gates(
    m_combined_full: dict[str, float],
    m_combined_oos: dict[str, float],
    m_s1_oos: dict[str, float],
    n_oos_full: int,
    n_oos_sub_a: int,
    n_oos_sub_b: int,
) -> tuple[list[dict[str, Any]], str]:
    oos_mar = m_combined_oos["mar"]
    full_mar = m_combined_full["mar"]
    s1_oos = m_s1_oos["mar"]

    g_ia = np.isfinite(oos_mar) and oos_mar >= GATES["G_ia"]
    g_ib = np.isfinite(oos_mar) and oos_mar >= GATES["G_ib"]
    g_full = np.isfinite(full_mar) and full_mar >= GATES["G_full"]
    n_full_ok = n_oos_full >= GATES["N_oos_full_min"]
    n_a_ok = n_oos_sub_a >= GATES["N_oos_sub_min"]
    n_b_ok = n_oos_sub_b >= GATES["N_oos_sub_min"]
    neg_cap = (
        np.isfinite(s1_oos)
        and np.isfinite(oos_mar)
        and s1_oos > 0
        and oos_mar > 0
    )
    severe = np.isfinite(oos_mar) and oos_mar < GATES["severe_regression"]

    details = [
        {
            "id": "G_ia",
            "criterion": f"combined OOS MAR >= {GATES['G_ia']:.4f} (S1 + 0.050)",
            "result": f"{oos_mar:.4f}",
            "pass": g_ia,
        },
        {
            "id": "G_ib",
            "criterion": f"combined OOS MAR >= {GATES['G_ib']:.3f}",
            "result": f"{oos_mar:.4f}",
            "pass": g_ib,
        },
        {
            "id": "G_full",
            "criterion": f"combined Full MAR >= {GATES['G_full']:.4f} (S1 Full − 0.050)",
            "result": f"{full_mar:.4f}",
            "pass": g_full,
        },
        {
            "id": "N_OOS_full",
            "criterion": f">= {GATES['N_oos_full_min']} trades full OOS",
            "result": str(n_oos_full),
            "pass": n_full_ok,
        },
        {
            "id": "N_OOS_sub_A",
            "criterion": f">= {GATES['N_oos_sub_min']} trades sub-A {OOS_SUB_WINDOW_A}",
            "result": str(n_oos_sub_a),
            "pass": n_a_ok,
        },
        {
            "id": "N_OOS_sub_B",
            "criterion": f">= {GATES['N_oos_sub_min']} trades sub-B {OOS_SUB_WINDOW_B}",
            "result": str(n_oos_sub_b),
            "pass": n_b_ok,
        },
        {
            "id": "Neg-OOS-cap",
            "criterion": "S1 baseline and combined OOS MAR positive",
            "result": "OK" if neg_cap else "FAIL",
            "pass": neg_cap,
        },
    ]

    if not n_full_ok or not n_a_ok or not n_b_ok:
        verdict = "VN-THIN"
    elif severe or (np.isfinite(oos_mar) and oos_mar < GATES["G_ib"]):
        verdict = "DEGRADING-REJECT"
    elif g_ib and g_ia and n_full_ok:
        verdict = "CALIBRATED"
    elif g_ib and n_full_ok:
        verdict = "INCONCLUSIVE-HOLD"
    else:
        verdict = "DEGRADING-REJECT"

    return details, verdict


def write_interaction_report(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    c = meta["combined"]
    gates = c["gates"]
    mech = meta["mechanism_checks"]

    lines = [
        "# Cortex Book #2 — S1+S2 Interaction Test",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Combined filter:** prox >= {S1_MIN_PROX} (within_15pct) AND vol >= {S2_MIN_VOL}×",
        "",
        f"**VERDICT: {c['verdict']}**",
        "",
        "## Reference baselines",
        "",
        "| Baseline | Full MAR | OOS MAR | N OOS | Sub-B MAR |",
        "|----------|----------|---------|-------|-----------|",
        f"| A3_RS raw | {meta['a3_baseline']['full_mar']:.4f} | "
        f"{meta['a3_baseline']['oos_mar']:.4f} | {meta['a3_baseline']['n_oos']} | — |",
        f"| S1 standalone | {S1_BASELINE['full_mar']:.4f} | "
        f"{S1_BASELINE['oos_mar']:.4f} | {S1_BASELINE['n_oos']} | "
        f"{S1_BASELINE['oos_sub_b_mar']:.4f} |",
        "",
        "## Combined candidate metrics",
        "",
        f"- Full MAR: **{c['full']['mar']:.4f}**",
        f"- OOS MAR: **{c['oos']['mar']:.4f}**",
        f"- OOS MaxDD: **{_fmt_pct(c['oos']['max_dd'])}**",
        f"- OOS CAGR: **{_fmt_pct(c['oos']['cagr'])}**",
        f"- N trades (full): **{c['n_full']}**",
        f"- N trades (OOS): **{c['n_oos']}**",
        f"- N trades (OOS sub-A): **{c['n_oos_sub_a']}**",
        f"- N trades (OOS sub-B): **{c['n_oos_sub_b']}**",
        f"- OOS sub-A MAR: **{c['oos_sub_a']['mar']:.4f}**",
        f"- OOS sub-B MAR: **{c['oos_sub_b']['mar']:.4f}**",
        "",
        "## Locked gates",
        "",
        f"- G_ia: combined OOS MAR >= **{GATES['G_ia']:.4f}**",
        f"- G_ib: combined OOS MAR >= **{GATES['G_ib']:.3f}**",
        f"- G_full: combined Full MAR >= **{GATES['G_full']:.4f}**",
        "",
        "| Gate | Criterion | Pass |",
        "|------|-----------|------|",
    ]
    for g in gates:
        lines.append(f"| {g['id']} | {g['criterion']} | {'PASS ✓' if g['pass'] else 'FAIL ✗'} |")

    lines.extend([
        "",
        "## Mechanism checks",
        "",
        f"- **M1 Fire count:** {mech['m1_pct_remaining']:.1f}% of S1 OOS signals remain "
        f"({c['n_oos']}/{meta['s1_recomputed']['n_oos']} S1 OOS trades)",
        f"- **M2 Marginal contribution:** OOS MAR delta vs S1 = "
        f"{mech['m2_oos_mar_delta']:+.4f} (need >= 0.010 for meaningful add)",
        f"- **M3 Sub-B:** combined {c['oos_sub_b']['mar']:.4f} vs S1 baseline "
        f"{S1_BASELINE['oos_sub_b_mar']:.4f} — volume filter "
        f"{'raises' if mech['m3_sub_b_higher'] else 'does not raise'} S1 sub-B",
        f"- **M4 Monotonicity:** combined Full MAR {c['full']['mar']:.4f} vs S1 "
        f"{S1_BASELINE['full_mar']:.4f} — G_full {'PASS' if mech['m4_g_full_pass'] else 'FAIL'}",
        "",
        "## Notes",
        "- Filters on signal bar; entry T+1 open. Same realism as S1/S2 standalone.",
        "- RESEARCH_ONLY_NOT_PRODUCTION",
        "",
    ])

    report_path = OUT_DIR / "s1s2_interaction_report.md"
    meta_path = OUT_DIR / "s1s2_interaction_meta.json"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {report_path}", flush=True)


def run_s1s2_interaction() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Cortex Book #2 — S1+S2 Interaction Test", flush=True)
    print(f"  S1 prox >= {S1_MIN_PROX}, S2 vol >= {S2_MIN_VOL}x", flush=True)
    print(f"  G_ia={GATES['G_ia']:.4f} G_ib={GATES['G_ib']:.3f} G_full={GATES['G_full']:.4f}", flush=True)

    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]
    eq_base = stack["eq"]

    m_a3_full = _metrics_from_equity(eq_base)
    eq_a3_oos = slice_equity_years(eq_base, OOS_WINDOW[0], OOS_WINDOW[1])
    m_a3_oos = _metrics_from_equity(eq_a3_oos)

    filter_map = build_signal_filter_map(ctx.panel)

    # S1 standalone (recomputed for apples-to-apples comparison)
    s1_trades = apply_proximity_filter(base_trades, filter_map, S1_MIN_PROX)
    sized_s1 = apply_size(s1_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_s1 = prepare_trades_with_size(sized_s1, "rs_score", "_size_mult")
    eq_s1, _, _ = run_capital_sim(prep_s1, ctx.gate, D4_CASH_YIELD)
    m_s1_full = _metrics_from_equity(eq_s1)
    eq_s1_oos = slice_equity_years(eq_s1, OOS_WINDOW[0], OOS_WINDOW[1])
    m_s1_oos = _metrics_from_equity(eq_s1_oos)
    eq_s1_a = slice_equity_years(eq_s1, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_s1_b = slice_equity_years(eq_s1, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    m_s1_oos_a = _metrics_from_equity(eq_s1_a)
    m_s1_oos_b = _metrics_from_equity(eq_s1_b)

    # Combined S1 ∩ S2
    combined_trades = apply_s1s2_combined_filter(base_trades, filter_map)
    n_combined_full = len(combined_trades)
    n_combined_oos = count_oos_trades(combined_trades, OOS_WINDOW[0], OOS_WINDOW[1])
    n_combined_a = count_oos_trades(combined_trades, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    n_combined_b = count_oos_trades(combined_trades, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    print(
        f"  Combined trades: {n_combined_full} full, {n_combined_oos} OOS, "
        f"{n_combined_a} sub-A, {n_combined_b} sub-B",
        flush=True,
    )

    sized_comb = apply_size(combined_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_comb = prepare_trades_with_size(sized_comb, "rs_score", "_size_mult")
    eq_comb, _, _ = run_capital_sim(prep_comb, ctx.gate, D4_CASH_YIELD)

    m_comb_full = _metrics_from_equity(eq_comb)
    eq_comb_oos = slice_equity_years(eq_comb, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_comb_a = slice_equity_years(eq_comb, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_comb_b = slice_equity_years(eq_comb, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    m_comb_oos = _metrics_from_equity(eq_comb_oos)
    m_comb_oos_a = _metrics_from_equity(eq_comb_a)
    m_comb_oos_b = _metrics_from_equity(eq_comb_b)

    print(f"  Combined OOS MAR={m_comb_oos['mar']:.4f}", flush=True)

    gates, verdict = evaluate_interaction_gates(
        m_comb_full, m_comb_oos, m_s1_oos,
        n_combined_oos, n_combined_a, n_combined_b,
    )
    print(f"  Verdict: {verdict}", flush=True)

    n_s1_oos = count_oos_trades(s1_trades, OOS_WINDOW[0], OOS_WINDOW[1])
    m1_pct = 100.0 * n_combined_oos / n_s1_oos if n_s1_oos else 0.0
    m2_delta = m_comb_oos["mar"] - m_s1_oos["mar"]
    m3_higher = m_comb_oos_b["mar"] > m_s1_oos_b["mar"]
    m4_pass = m_comb_full["mar"] >= GATES["G_full"]

    meta: dict[str, Any] = {
        "generated": str(date.today()),
        "test": "S1_S2_interaction",
        "panel_start": PANEL_START,
        "panel_end": PANEL_END,
        "filters": {"s1_min_prox": S1_MIN_PROX, "s2_min_vol": S2_MIN_VOL},
        "gates_locked": GATES,
        "s1_baseline_prereg": S1_BASELINE,
        "a3_baseline": {
            "full_mar": m_a3_full["mar"],
            "oos_mar": m_a3_oos["mar"],
            "n_oos": count_oos_trades(base_trades, OOS_WINDOW[0], OOS_WINDOW[1]),
        },
        "s1_recomputed": {
            "full_mar": m_s1_full["mar"],
            "oos_mar": m_s1_oos["mar"],
            "oos_sub_a_mar": m_s1_oos_a["mar"],
            "oos_sub_b_mar": m_s1_oos_b["mar"],
            "n_oos": n_s1_oos,
            "n_oos_sub_a": count_oos_trades(s1_trades, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1]),
            "n_oos_sub_b": count_oos_trades(s1_trades, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1]),
        },
        "combined": {
            "verdict": verdict,
            "full": m_comb_full,
            "oos": m_comb_oos,
            "oos_sub_a": m_comb_oos_a,
            "oos_sub_b": m_comb_oos_b,
            "n_full": n_combined_full,
            "n_oos": n_combined_oos,
            "n_oos_sub_a": n_combined_a,
            "n_oos_sub_b": n_combined_b,
            "gates": gates,
        },
        "mechanism_checks": {
            "m1_pct_remaining": m1_pct,
            "m2_oos_mar_delta": m2_delta,
            "m3_sub_b_higher": m3_higher,
            "m3_combined_sub_b_mar": m_comb_oos_b["mar"],
            "m3_s1_sub_b_mar": m_s1_oos_b["mar"],
            "m4_g_full_pass": m4_pass,
        },
    }

    write_interaction_report(meta)
    return meta


def main() -> None:
    run_s1s2_interaction()


if __name__ == "__main__":
    main()
