#!/usr/bin/env python3
"""
S14 — Minervini Trend Template MA stack filter on S1+ A3_RS pool.

Applies pre-reg criteria 1-6 (7-8 satisfied by S1/A3_RS upstream).
G2: MA-stack pool vs non-stack (removed) pool.

Pre-reg: knowledge/backtests/2026-07-05_schwager_s14_ma_stack_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_book6_s14_ma_stack_harness.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B, count_oos_trades
from pp_backtest.cortex_degeneracy_common import build_symbol_panel, rolling_sma
from pp_backtest.cortex_schwager_common import (
    G1B_FLOOR,
    IS_WINDOW,
    MIN_N_OOS,
    OOS_WINDOW,
    S14_G1A,
    S1_BASELINE_OOS_MAR,
    build_stack_with_sector,
    oos_sub_mar,
    run_filtered_sim,
    signal_date_col,
    verify_s1_baseline,
    write_harness_report,
    year_mask,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL
from pp_backtest.sprint2b_common import slice_equity_years

TREND_CHECK_DAYS = 21
OUT_MD = REPO / "knowledge" / "backtests" / "s14_harness_results.md"
OUT_META = REPO / "data" / "research" / "cortex_book6" / "s14_ma_stack_harness_meta.json"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s14_ma_stack_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_s14_ma_stack_prereg.md"


def eval_ma_stack_criteria(sp: dict[str, Any], pi: int) -> tuple[bool, bool]:
    """Return (criteria_1_6_all_pass, evaluable). Pre-reg Trend Template criteria 1-6."""
    close = sp["close"]
    low = sp["low"]
    if pi < 199 or pi < TREND_CHECK_DAYS:
        return False, False
    px = float(close[pi])
    s50 = rolling_sma(close, pi, 50)
    s150 = rolling_sma(close, pi, 150)
    s200 = rolling_sma(close, pi, 200)
    s200_prev = rolling_sma(close, pi - TREND_CHECK_DAYS, 200)
    if not all(np.isfinite(x) for x in (s50, s150, s200, s200_prev)):
        return False, False
    lo_52w = float(np.min(low[max(0, pi - 251) : pi + 1]))
    c1 = px > s150 and px > s200
    c2 = s150 > s200
    c3 = s200 > s200_prev
    c4 = s50 > s150 and s50 > s200
    c5 = px > s50
    c6 = lo_52w > 0 and px >= 1.30 * lo_52w
    return all([c1, c2, c3, c4, c5, c6]), True


def attach_ma_stack_flag(trades: pd.DataFrame, sym_panel: dict[str, dict[str, Any]]) -> pd.DataFrame:
    t = trades.copy()
    t["_sig"] = signal_date_col(t)
    passes: list[bool] = []
    evaluable: list[bool] = []
    for _, row in t.iterrows():
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            passes.append(False)
            evaluable.append(False)
            continue
        sig = pd.Timestamp(row["_sig"]).normalize()
        pi = sp["date_to_i"].get(sig)
        if pi is None:
            passes.append(False)
            evaluable.append(False)
            continue
        ok, ev = eval_ma_stack_criteria(sp, pi)
        passes.append(ok)
        evaluable.append(ev)
    t["ma_stack_pass"] = passes
    t["ma_stack_evaluable"] = evaluable
    return t


def _sub_window_n(trades: pd.DataFrame, window: tuple[int, int]) -> int:
    ed = pd.to_datetime(trades["entry_date"])
    return int(((ed.dt.year >= window[0]) & (ed.dt.year <= window[1])).sum())


def _sub_window_mar(eq: pd.Series, window: tuple[int, int]) -> float:
    sub = slice_equity_years(eq, window[0], window[1])
    if len(sub) < 2:
        return float("nan")
    return float(_metrics_from_equity(sub)["mar"])


def _evaluate_s14(
    oos_mar_stack: float,
    oos_mar_non: float,
    s1_mar: float,
    n_stack: int,
) -> tuple[dict[str, bool], str]:
    g1a = np.isfinite(oos_mar_stack) and oos_mar_stack >= S14_G1A
    g1b = np.isfinite(oos_mar_stack) and oos_mar_stack >= G1B_FLOOR
    g2 = np.isfinite(oos_mar_stack) and np.isfinite(oos_mar_non) and oos_mar_stack > oos_mar_non
    g3 = n_stack >= MIN_N_OOS
    margin = oos_mar_stack - S14_G1A if np.isfinite(oos_mar_stack) else -999.0
    both_neg = s1_mar < 0 and np.isfinite(oos_mar_stack) and oos_mar_stack < 0

    gates = {"G1a": g1a, "G1b": g1b, "G2_mechanism": g2, "G3_N_OOS": g3}

    if not g3:
        return gates, "VN-THIN"
    if np.isfinite(oos_mar_stack) and np.isfinite(s1_mar) and oos_mar_stack < s1_mar - 0.10:
        return gates, "DEGRADING-REJECT"
    if both_neg:
        return gates, "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    if g1a and g1b and g2:
        return gates, "ADVANCE" if margin >= 0.020 else "CONDITIONAL-ADVANCE"
    return gates, "FAIL"


def main() -> dict[str, Any]:
    print("S14 MA stack harness (S1+S14)", flush=True)
    stack = build_stack_with_sector()
    sym_panel = build_symbol_panel(stack["ctx"].panel)

    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n} drift={drift}", flush=True)
    if drift:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 OOS MAR {s1_m['mar']:.4f} vs locked {S1_BASELINE_OOS_MAR}. Halt."
        )

    tagged = attach_ma_stack_flag(stack["s1_trades"], sym_panel)
    is_mask = year_mask(pd.to_datetime(tagged["entry_date"]), IS_WINDOW)
    is_eval = tagged[is_mask & tagged["ma_stack_evaluable"]]
    is_pass_rate = float(is_eval["ma_stack_pass"].mean()) if len(is_eval) else float("nan")
    is_pass_n = int(is_eval["ma_stack_pass"].sum()) if len(is_eval) else 0

    GATES_ADDENDUM.write_text(
        "\n".join(
            [
                "# Gates Addendum: S14 MA Stack — locked IS diagnostics",
                f"# Written: {date.today()} (before OOS gate evaluation)",
                f"# Pre-reg: {PREREG}",
                "",
                "## Baseline verification",
                f"- S1-filtered OOS MAR: **{s1_m['mar']:.4f}** (locked ref {S1_BASELINE_OOS_MAR})",
                f"- N_OOS: **{s1_n}**",
                f"- Baseline drift flag: **{drift}**",
                "",
                "## IS diagnostics (binary MA stack — no tunable threshold)",
                f"- IS evaluable S1 signals: **{len(is_eval)}**",
                f"- IS MA-stack pass count: **{is_pass_n}**",
                f"- IS pass rate: **{100*is_pass_rate:.2f}%**" if np.isfinite(is_pass_rate) else "- IS pass rate: n/a",
                "",
                "## Locked OOS gate parameters",
                f"- G1a: MA-stack pool OOS MAR >= **{S14_G1A}**",
                f"- G1b: MA-stack pool OOS MAR >= **{G1B_FLOOR}**",
                f"- G2: MA-stack MAR > non-stack MAR",
                f"- G3: N_OOS (MA-stack pool) >= **{MIN_N_OOS}**",
                "- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE",
                "- Sub-B N < 30: flag [SUB-B-THIN] only (not a gate fail)",
            ]
        ),
        encoding="utf-8",
    )
    print(f"  IS pass rate={100*is_pass_rate:.2f}% (n={is_pass_n})", flush=True)

    stack_trades = tagged[tagged["ma_stack_pass"]].drop(columns=["_sig", "ma_stack_pass", "ma_stack_evaluable"])
    non_stack = tagged[tagged["ma_stack_evaluable"] & ~tagged["ma_stack_pass"]].drop(
        columns=["_sig", "ma_stack_pass", "ma_stack_evaluable"]
    )

    eq_stack, m_stack, n_stack = run_filtered_sim(stack, stack_trades)
    _, m_non, n_non = run_filtered_sim(stack, non_stack)
    sub_a_mar, sub_b_mar = oos_sub_mar(eq_stack)
    n_sub_a = _sub_window_n(stack_trades, OOS_SUB_WINDOW_A)
    n_sub_b = _sub_window_n(stack_trades, OOS_SUB_WINDOW_B)
    sub_b_thin = n_sub_b < MIN_N_OOS

    gates, verdict = _evaluate_s14(m_stack["mar"], m_non["mar"], s1_m["mar"], n_stack)
    print(
        f"  MA-stack: OOS MAR={m_stack['mar']:.4f} N={n_stack} | "
        f"Non-stack: MAR={m_non['mar']:.4f} N={n_non} -> {verdict}",
        flush=True,
    )

    lines = [
        "# S14 Minervini MA Stack Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        "",
        f"**FINAL VERDICT:** {verdict}",
        "",
        f"S1 baseline OOS MAR: **{s1_m['mar']:.4f}** (locked {S1_BASELINE_OOS_MAR}) | G1a floor: **{S14_G1A}**",
        "",
        "## Baseline verification",
        f"- S1-only OOS MAR: {s1_m['mar']:.4f} | N={s1_n} | drift={drift}",
        "",
        "## Pool sizes (OOS trades)",
        f"- MA-stack pool (criteria 1-6 pass): **{n_stack}**",
        f"- Non-stack pool (removed): **{n_non}**",
        "",
        "## OOS gate results",
        "",
        "| Arm | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |",
        "|-----|---------|-----------|----------|-------|",
        f"| MA-stack | {m_stack['mar']:.4f} | {m_stack['max_dd']:.2%} | {m_stack['cagr']:.2%} | {n_stack} |",
        f"| Non-stack | {m_non['mar']:.4f} | {m_non['max_dd']:.2%} | {m_non['cagr']:.2%} | {n_non} |",
        "",
        "| Gate | Criterion | Pass |",
        "|------|-----------|------|",
        f"| G1a | MAR >= {S14_G1A} | {'PASS' if gates['G1a'] else 'FAIL'} |",
        f"| G1b | MAR >= {G1B_FLOOR} | {'PASS' if gates['G1b'] else 'FAIL'} |",
        f"| G2 | stack > non-stack ({m_stack['mar']:.4f} vs {m_non['mar']:.4f}) | {'PASS' if gates['G2_mechanism'] else 'FAIL'} |",
        f"| G3 | N_OOS >= {MIN_N_OOS} | {'PASS' if gates['G3_N_OOS'] else 'FAIL'} |",
        "",
        "## Sub-window (MA-stack pool)",
        f"- Sub-A (2020-2022): MAR **{sub_a_mar:.4f}**, N **{n_sub_a}**",
        f"- Sub-B (2023-2026): MAR **{sub_b_mar:.4f}**, N **{n_sub_b}**"
        + (" — **[SUB-B-THIN]**" if sub_b_thin else ""),
    ]

    if verdict == "ADVANCE":
        lines += [
            "",
            "## Expansion gate",
            "- S14 ADVANCE — 3rd CALIBRATED met. Mechanism Gate: 3/3 pending user approval.",
        ]

    meta: dict[str, Any] = {
        "belief_id": "S14",
        "run_date": str(date.today()),
        "baseline_verification": {
            "s1_oos_mar": s1_m["mar"],
            "s1_n_oos": s1_n,
            "baseline_drift_flag": drift,
        },
        "is_pass_rate": is_pass_rate,
        "is_pass_n": is_pass_n,
        "ma_stack_pool": {
            "oos_mar": m_stack["mar"],
            "oos_maxdd": m_stack["max_dd"],
            "oos_cagr": m_stack["cagr"],
            "n_oos": n_stack,
            "sub_a_mar": sub_a_mar,
            "sub_b_mar": sub_b_mar,
            "sub_a_n": n_sub_a,
            "sub_b_n": n_sub_b,
        },
        "non_stack_pool": {
            "oos_mar": m_non["mar"],
            "n_oos": n_non,
        },
        "gates": {k: bool(v) for k, v in gates.items()},
        "sub_b_thin_flag": sub_b_thin,
        "overall_verdict": verdict,
    }

    write_harness_report(OUT_MD, "S14", lines, meta)
    OUT_META.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
