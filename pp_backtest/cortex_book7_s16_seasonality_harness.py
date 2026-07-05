#!/usr/bin/env python3
"""
S16 — Gray/Vogel momentum seasonality: exclude IS bottom-2 entry months on S1+ A3_RS pool.

IS: rank calendar months by mean trade return; lock bottom K=2 as bad months.
OOS: evaluate good-months pool vs bad-months control.

Pre-reg: knowledge/backtests/2026-07-05_schwager_s16_seasonality_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_book7_s16_seasonality_harness.py
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

from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B
from pp_backtest.cortex_schwager_common import (
    G1B_FLOOR,
    IS_WINDOW,
    MIN_N_OOS,
    OOS_WINDOW,
    S16_G1A,
    S1_BASELINE_OOS_MAR,
    build_stack_with_sector,
    oos_sub_mar,
    run_filtered_sim,
    verify_s1_baseline,
    write_harness_report,
    year_mask,
)
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL

K_BAD_MONTHS = 2
MIN_IS_MONTH_N = 5
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

OUT_MD = REPO / "knowledge" / "backtests" / "s16_harness_results.md"
OUT_META = REPO / "data" / "research" / "cortex_book7" / "s16_seasonality_harness_meta.json"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s16_seasonality_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_s16_seasonality_prereg.md"


def _entry_month(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.month


def _is_month_stats(trades: pd.DataFrame) -> dict[int, dict[str, float]]:
    """Mean net_return per entry month on IS S1 trades."""
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    is_mask = year_mask(t["entry_date"], IS_WINDOW)
    is_t = t[is_mask].copy()
    is_t["entry_month"] = _entry_month(is_t["entry_date"])
    out: dict[int, dict[str, float]] = {}
    for m in range(1, 13):
        sub = is_t[is_t["entry_month"] == m]
        if len(sub) >= MIN_IS_MONTH_N:
            out[m] = {"mean_ret": float(sub["net_return"].astype(float).mean()), "n": len(sub)}
    return out


def _lock_bad_months(is_stats: dict[int, dict[str, float]], k: int = K_BAD_MONTHS) -> list[int]:
    ranked = sorted(is_stats.items(), key=lambda x: x[1]["mean_ret"])
    return [m for m, _ in ranked[:k]]


def _split_by_months(trades: pd.DataFrame, bad_months: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = trades.copy()
    t["entry_month"] = _entry_month(t["entry_date"])
    bad_set = set(bad_months)
    good = t[~t["entry_month"].isin(bad_set)].drop(columns=["entry_month"])
    bad = t[t["entry_month"].isin(bad_set)].drop(columns=["entry_month"])
    return good, bad


def _sub_window_n(trades: pd.DataFrame, window: tuple[int, int]) -> int:
    ed = pd.to_datetime(trades["entry_date"])
    return int(((ed.dt.year >= window[0]) & (ed.dt.year <= window[1])).sum())


def _oos_monthly_mean_ret(trades: pd.DataFrame) -> dict[int, dict[str, float]]:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    oos_mask = year_mask(t["entry_date"], OOS_WINDOW)
    oos = t[oos_mask].copy()
    oos["entry_month"] = _entry_month(oos["entry_date"])
    out: dict[int, dict[str, float]] = {}
    for m in range(1, 13):
        sub = oos[oos["entry_month"] == m]
        if len(sub):
            out[m] = {"mean_ret": float(sub["net_return"].astype(float).mean()), "n": len(sub)}
    return out


def _evaluate_s16(
    oos_mar_good: float,
    oos_mar_bad: float,
    s1_mar: float,
    n_good: int,
) -> tuple[dict[str, bool], str]:
    g1a = np.isfinite(oos_mar_good) and oos_mar_good >= S16_G1A
    g1b = np.isfinite(oos_mar_good) and oos_mar_good >= G1B_FLOOR
    g2 = np.isfinite(oos_mar_good) and np.isfinite(oos_mar_bad) and oos_mar_good > oos_mar_bad
    g3 = n_good >= MIN_N_OOS
    margin = oos_mar_good - S16_G1A if np.isfinite(oos_mar_good) else -999.0
    both_neg = s1_mar < 0 and np.isfinite(oos_mar_good) and oos_mar_good < 0

    gates = {"G1a": g1a, "G1b": g1b, "G2_mechanism": g2, "G3_N_OOS": g3}

    if not g3:
        return gates, "VN-THIN"
    if np.isfinite(oos_mar_good) and np.isfinite(s1_mar) and oos_mar_good < s1_mar - 0.10:
        return gates, "DEGRADING-REJECT"
    if both_neg:
        return gates, "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    if g1a and g1b and g2:
        return gates, "ADVANCE" if margin >= 0.020 else "CONDITIONAL-ADVANCE"
    return gates, "FAIL"


def main() -> dict[str, Any]:
    print("S16 seasonality harness (S1+S16 month exclusion)", flush=True)
    stack = build_stack_with_sector()

    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n} drift={drift}", flush=True)
    if drift:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 OOS MAR {s1_m['mar']:.4f} vs locked {S1_BASELINE_OOS_MAR}. Halt."
        )

    is_stats = _is_month_stats(stack["s1_trades"])
    bad_months = _lock_bad_months(is_stats, K_BAD_MONTHS)
    is_ranked = sorted(is_stats.items(), key=lambda x: x[1]["mean_ret"])

    GATES_ADDENDUM.write_text(
        "\n".join(
            [
                "# Gates Addendum: S16 Seasonality — IS month rankings (LOCKED)",
                f"# Written: {date.today()} (before OOS evaluation)",
                f"# Pre-reg: {PREREG}",
                "",
                "## Baseline verification",
                f"- S1-filtered OOS MAR: **{s1_m['mar']:.4f}** (locked ref {S1_BASELINE_OOS_MAR})",
                f"- N_OOS: **{s1_n}**",
                f"- Baseline drift flag: **{drift}**",
                "",
                f"## IS mean trade return by entry month (window {IS_WINDOW[0]}–{IS_WINDOW[1]})",
                "",
                "| Month | N (IS) | Mean return |",
                "|-------|--------|-------------|",
            ]
            + [
                f"| {MONTH_NAMES[m-1]} ({m}) | {int(st['n'])} | {100*st['mean_ret']:.2f}% |"
                for m, st in is_ranked
            ]
            + [
                "",
                f"## LOCKED bad months (bottom K={K_BAD_MONTHS} by IS mean return)",
                f"- **{', '.join(f'{MONTH_NAMES[m-1]} ({m})' for m in bad_months)}**",
                "",
                "## Locked OOS gate parameters",
                f"- G1a: good-months pool OOS MAR >= **{S16_G1A}**",
                f"- G1b: good-months pool OOS MAR >= **{G1B_FLOOR}**",
                f"- G2: good-months MAR > bad-months MAR (OOS)",
                f"- G3: N_OOS (good months) >= **{MIN_N_OOS}**",
                "- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE",
            ]
        ),
        encoding="utf-8",
    )
    print(f"  IS bad months locked: {bad_months}", flush=True)
    print(f"  Gates addendum: {GATES_ADDENDUM}", flush=True)

    good_trades, bad_trades = _split_by_months(stack["s1_trades"], bad_months)
    eq_good, m_good, n_good = run_filtered_sim(stack, good_trades)
    _, m_bad, n_bad = run_filtered_sim(stack, bad_trades)
    sub_a_mar, sub_b_mar = oos_sub_mar(eq_good)
    n_sub_a = _sub_window_n(good_trades, OOS_SUB_WINDOW_A)
    n_sub_b = _sub_window_n(good_trades, OOS_SUB_WINDOW_B)
    oos_monthly = _oos_monthly_mean_ret(stack["s1_trades"])

    gates, verdict = _evaluate_s16(m_good["mar"], m_bad["mar"], s1_m["mar"], n_good)
    print(
        f"  Good months: OOS MAR={m_good['mar']:.4f} N={n_good} | "
        f"Bad months: MAR={m_bad['mar']:.4f} N={n_bad} -> {verdict}",
        flush=True,
    )

    lines = [
        "# S16 Seasonality Month-Exclusion Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        "",
        f"**FINAL VERDICT:** {verdict}",
        "",
        f"S1 baseline OOS MAR: **{s1_m['mar']:.4f}** (locked {S1_BASELINE_OOS_MAR}) | G1a floor: **{S16_G1A}**",
        "",
        "## Baseline verification",
        f"- S1-only OOS MAR: {s1_m['mar']:.4f} | N={s1_n} | drift={drift}",
        "",
        "## IS phase — bad months (LOCKED before OOS)",
        f"- Bad months: **{', '.join(f'{MONTH_NAMES[m-1]} ({m})' for m in bad_months)}**",
        "",
        "| Month | IS N | IS mean return |",
        "|-------|------|----------------|",
    ]
    for m, st in is_ranked:
        marker = " **BAD**" if m in bad_months else ""
        lines.append(f"| {MONTH_NAMES[m-1]} | {int(st['n'])} | {100*st['mean_ret']:.2f}%{marker} |")

    lines += [
        "",
        "## OOS pools",
        "",
        "| Pool | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |",
        "|------|---------|-----------|----------|-------|",
        f"| Good months (10 months) | {m_good['mar']:.4f} | {m_good['max_dd']:.2%} | {m_good['cagr']:.2%} | {n_good} |",
        f"| Bad months (excluded) | {m_bad['mar']:.4f} | {m_bad['max_dd']:.2%} | {m_bad['cagr']:.2%} | {n_bad} |",
        "",
        "| Gate | Criterion | Pass |",
        "|------|-----------|------|",
        f"| G1a | MAR >= {S16_G1A} | {'PASS' if gates['G1a'] else 'FAIL'} |",
        f"| G1b | MAR >= {G1B_FLOOR} | {'PASS' if gates['G1b'] else 'FAIL'} |",
        f"| G2 | good > bad ({m_good['mar']:.4f} vs {m_bad['mar']:.4f}) | {'PASS' if gates['G2_mechanism'] else 'FAIL'} |",
        f"| G3 | N_OOS >= {MIN_N_OOS} | {'PASS' if gates['G3_N_OOS'] else 'FAIL'} |",
        "",
        "## Sub-window (good-months pool)",
        f"- Sub-A (2020-2022): MAR **{sub_a_mar:.4f}**, N **{n_sub_a}**",
        f"- Sub-B (2023-2026): MAR **{sub_b_mar:.4f}**, N **{n_sub_b}**",
        "",
        "## OOS diagnostic — mean trade return by entry month",
        "",
        "| Month | N | Mean return |",
        "|-------|---|-------------|",
    ]
    for m in range(1, 13):
        if m in oos_monthly:
            st = oos_monthly[m]
            tag = " (bad)" if m in bad_months else ""
            lines.append(f"| {MONTH_NAMES[m-1]} | {st['n']} | {100*st['mean_ret']:.2f}%{tag} |")

    if verdict == "ADVANCE":
        lines += [
            "",
            "## Expansion gate",
            "- S16 ADVANCE — 3rd CALIBRATED met. Mechanism Gate: 3/3 pending user approval.",
        ]

    meta: dict[str, Any] = {
        "belief_id": "S16",
        "run_date": str(date.today()),
        "baseline_verification": {
            "s1_oos_mar": s1_m["mar"],
            "s1_n_oos": s1_n,
            "baseline_drift_flag": drift,
        },
        "is_bad_months": bad_months,
        "is_month_stats": {str(m): v for m, v in is_stats.items()},
        "good_months_pool": {
            "oos_mar": m_good["mar"],
            "oos_maxdd": m_good["max_dd"],
            "oos_cagr": m_good["cagr"],
            "n_oos": n_good,
            "sub_a_mar": sub_a_mar,
            "sub_b_mar": sub_b_mar,
            "sub_a_n": n_sub_a,
            "sub_b_n": n_sub_b,
        },
        "bad_months_pool": {
            "oos_mar": m_bad["mar"],
            "n_oos": n_bad,
        },
        "oos_monthly_mean_ret": {str(m): v for m, v in oos_monthly.items()},
        "gates": {k: bool(v) for k, v in gates.items()},
        "overall_verdict": verdict,
    }

    write_harness_report(OUT_MD, "S16", lines, meta)
    OUT_META.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
