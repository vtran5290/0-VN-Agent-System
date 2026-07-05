#!/usr/bin/env python3
"""
S15 — FIP quality momentum filter on S1+ A3_RS pool.

IS: lock FIP distribution stats on S1-filtered IS pool (P50 diagnostic).
OOS: per signal_date rank by FIP ascending; keep bottom 50% (smoothest path).

Pre-reg: knowledge/backtests/2026-07-05_schwager_s15_fip_quality_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_book7_s15_fip_harness.py
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

from pp_backtest.cortex_degeneracy_common import build_symbol_panel
from pp_backtest.cortex_schwager_common import (
    G1B_FLOOR,
    IS_WINDOW,
    MIN_N_OOS,
    S15_G1A,
    S1_BASELINE_OOS_MAR,
    build_stack_with_sector,
    oos_sub_mar,
    run_filtered_sim,
    signal_date_col,
    verify_s1_baseline,
    write_harness_report,
    year_mask,
)
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL

LOOKBACK = 252
OUT_MD = REPO / "knowledge" / "backtests" / "s15_harness_results.md"
OUT_META = REPO / "data" / "research" / "cortex_book7" / "s15_fip_harness_meta.json"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s15_fip_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_s15_fip_quality_prereg.md"


def compute_fip_at_index(close: np.ndarray, pi: int, lookback: int = LOOKBACK) -> float:
    start = pi - lookback
    if start < 1 or pi >= len(close):
        return float("nan")
    rets = close[start + 1 : pi + 1] / close[start:pi] - 1.0
    rets = rets[np.isfinite(rets)]
    if len(rets) < lookback // 2:
        return float("nan")
    pct_neg = float((rets < 0).mean())
    pct_pos = float((rets > 0).mean())
    past_ret = float(close[pi] / close[start] - 1.0)
    sign = 1.0 if past_ret > 0 else (-1.0 if past_ret < 0 else 0.0)
    return sign * (pct_neg - pct_pos)


def attach_fip(trades: pd.DataFrame, sym_panel: dict[str, dict[str, Any]]) -> pd.DataFrame:
    t = trades.copy()
    t["_sig"] = signal_date_col(t)
    fips: list[float] = []
    for _, row in t.iterrows():
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            fips.append(np.nan)
            continue
        sig = pd.Timestamp(row["_sig"]).normalize()
        pi = sp["date_to_i"].get(sig)
        if pi is None:
            fips.append(np.nan)
            continue
        fips.append(compute_fip_at_index(sp["close"], pi))
    t["fip"] = fips
    return t


def split_by_fip_half(trades: pd.DataFrame, *, quality: bool) -> pd.DataFrame:
    """Per signal_date: quality=bottom 50% FIP (smoothest); lottery=top 50%."""
    t = trades.dropna(subset=["fip"]).copy()
    if t.empty:
        return t
    keep_idx: list[int] = []
    for _, grp in t.groupby("_sig"):
        if len(grp) == 1:
            if quality:
                keep_idx.extend(grp.index.tolist())
            continue
        n_q = max(1, len(grp) // 2)
        sorted_grp = grp.sort_values("fip", ascending=True)
        if quality:
            keep_idx.extend(sorted_grp.head(n_q).index.tolist())
        else:
            keep_idx.extend(sorted_grp.tail(len(grp) - n_q).index.tolist())
    out = t.loc[keep_idx].copy()
    return out.drop(columns=["_sig"], errors="ignore")


def _evaluate_s15(
    oos_mar_top: float,
    oos_mar_bottom: float,
    s1_mar: float,
    n_oos_top: int,
) -> tuple[dict[str, bool], str]:
    g1a = np.isfinite(oos_mar_top) and oos_mar_top >= S15_G1A
    g1b = np.isfinite(oos_mar_top) and oos_mar_top >= G1B_FLOOR
    g2 = np.isfinite(oos_mar_top) and np.isfinite(oos_mar_bottom) and oos_mar_top > oos_mar_bottom
    g3 = n_oos_top >= MIN_N_OOS
    margin = oos_mar_top - S15_G1A if np.isfinite(oos_mar_top) else -999.0
    both_neg = s1_mar < 0 and np.isfinite(oos_mar_top) and oos_mar_top < 0

    gates = {"G1a": g1a, "G1b": g1b, "G2_mechanism": g2, "G3_N_OOS": g3}

    if not g3:
        return gates, "VN-THIN"
    if np.isfinite(oos_mar_top) and np.isfinite(s1_mar) and oos_mar_top < s1_mar - 0.10:
        return gates, "DEGRADING-REJECT"
    if both_neg:
        return gates, "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    if g1a and g1b and g2:
        return gates, "ADVANCE" if margin >= 0.020 else "CONDITIONAL-ADVANCE"
    return gates, "FAIL"


def main() -> dict[str, Any]:
    print("S15 FIP quality momentum harness (S1+S15)", flush=True)
    stack = build_stack_with_sector()
    sym_panel = build_symbol_panel(stack["ctx"].panel)

    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n} drift={drift}", flush=True)
    if drift:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 OOS MAR {s1_m['mar']:.4f} vs locked {S1_BASELINE_OOS_MAR}. Halt."
        )

    s1_fip = attach_fip(stack["s1_trades"], sym_panel)
    is_mask = year_mask(pd.to_datetime(s1_fip["entry_date"]), IS_WINDOW)
    is_fips = s1_fip.loc[is_mask, "fip"].dropna()
    is_p50 = float(is_fips.median()) if len(is_fips) else float("nan")
    is_p25 = float(is_fips.quantile(0.25)) if len(is_fips) else float("nan")
    is_p75 = float(is_fips.quantile(0.75)) if len(is_fips) else float("nan")

    GATES_ADDENDUM.write_text(
        "\n".join(
            [
                "# Gates Addendum: S15 FIP — locked IS diagnostics",
                f"# Written: {date.today()} (before OOS evaluation)",
                f"# Pre-reg: {PREREG}",
                "",
                "## Baseline verification",
                f"- S1-filtered OOS MAR: **{s1_m['mar']:.4f}** (locked ref {S1_BASELINE_OOS_MAR})",
                f"- N_OOS: **{s1_n}**",
                f"- Baseline drift flag: **{drift}**",
                "",
                "## IS FIP distribution (S1-filtered IS pool, LOOKBACK=252)",
                f"- IS signals with valid FIP: **{len(is_fips)}**",
                f"- IS FIP P25: **{is_p25:.4f}**",
                f"- IS FIP P50 (median): **{is_p50:.4f}**",
                f"- IS FIP P75: **{is_p75:.4f}**",
                "",
                "## Locked split method (pre-reg)",
                "- Per **signal_date**: rank candidates by FIP ascending; keep **bottom 50%** (most negative = quality).",
                "- IS P50 is diagnostic only — **not** used as a universal cutoff.",
                "",
                "## Locked OOS gate parameters",
                f"- G1a: quality-half OOS MAR >= **{S15_G1A}**",
                f"- G1b: quality-half OOS MAR >= **{G1B_FLOOR}**",
                f"- G2: quality-half MAR > lottery-half MAR",
                f"- G3: N_OOS (quality half) >= **{MIN_N_OOS}**",
                "- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE",
            ]
        ),
        encoding="utf-8",
    )
    print(f"  IS FIP P50={is_p50:.4f} (locked diagnostic)", flush=True)
    print(f"  Gates addendum: {GATES_ADDENDUM}", flush=True)

    quality_trades = split_by_fip_half(s1_fip, quality=True)
    lottery_trades = split_by_fip_half(s1_fip, quality=False)

    eq_top, m_top, n_top = run_filtered_sim(stack, quality_trades)
    _, m_bottom, n_bottom = run_filtered_sim(stack, lottery_trades)
    sub_a, sub_b = oos_sub_mar(eq_top)

    gates, verdict = _evaluate_s15(m_top["mar"], m_bottom["mar"], s1_m["mar"], n_top)
    regime_split = np.isfinite(sub_a) and np.isfinite(sub_b) and sub_b > 0 and sub_a / sub_b > 2

    print(
        f"  Quality half: OOS MAR={m_top['mar']:.4f} N={n_top} | "
        f"Lottery half: MAR={m_bottom['mar']:.4f} N={n_bottom} -> {verdict}",
        flush=True,
    )

    lines = [
        "# S15 FIP Quality Momentum Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        "",
        f"**FINAL VERDICT:** {verdict}",
        "",
        f"S1 baseline OOS MAR: **{s1_m['mar']:.4f}** (locked {S1_BASELINE_OOS_MAR}) | G1a floor: **{S15_G1A}**",
        "",
        "## Baseline verification",
        f"- S1-only OOS MAR: {s1_m['mar']:.4f} | N={s1_n} | drift={drift}",
        "",
        "## IS FIP threshold (locked before OOS)",
        f"- IS FIP P50 (median): **{is_p50:.4f}** | P25={is_p25:.4f} | P75={is_p75:.4f}",
        f"- Split: per signal_date bottom 50% FIP (quality half)",
        "",
        "## OOS gate results (quality half vs lottery half)",
        "",
        "| Arm | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |",
        "|-----|---------|-----------|----------|-------|",
        f"| Quality (bottom 50% FIP) | {m_top['mar']:.4f} | {m_top['max_dd']:.2%} | {m_top['cagr']:.2%} | {n_top} |",
        f"| Lottery (top 50% FIP) | {m_bottom['mar']:.4f} | {m_bottom['max_dd']:.2%} | {m_bottom['cagr']:.2%} | {n_bottom} |",
        "",
        "| Gate | Criterion | Pass |",
        "|------|-----------|------|",
        f"| G1a | MAR >= {S15_G1A} | {'PASS' if gates['G1a'] else 'FAIL'} |",
        f"| G1b | MAR >= {G1B_FLOOR} | {'PASS' if gates['G1b'] else 'FAIL'} |",
        f"| G2 | quality MAR > lottery MAR ({m_top['mar']:.4f} vs {m_bottom['mar']:.4f}) | {'PASS' if gates['G2_mechanism'] else 'FAIL'} |",
        f"| G3 | N_OOS >= {MIN_N_OOS} | {'PASS' if gates['G3_N_OOS'] else 'FAIL'} |",
        "",
        "## Sub-window (quality half)",
        f"- Sub-A (2020-2022): **{sub_a:.4f}**",
        f"- Sub-B (2023-2026): **{sub_b:.4f}**",
    ]
    if regime_split:
        lines.append("- **[REGIME-SPLIT]** sub-B MAR materially below sub-A (>2× ratio)")

    if verdict == "ADVANCE":
        lines += [
            "",
            "## Expansion gate",
            "- S15 ADVANCE — 3rd CALIBRATED met. Mechanism Gate: 3/3 pending user approval.",
        ]

    meta: dict[str, Any] = {
        "belief_id": "S15",
        "run_date": str(date.today()),
        "baseline_verification": {
            "s1_oos_mar": s1_m["mar"],
            "s1_n_oos": s1_n,
            "baseline_drift_flag": drift,
        },
        "is_fip_p50": is_p50,
        "is_fip_p25": is_p25,
        "is_fip_p75": is_p75,
        "quality_half": {
            "oos_mar": m_top["mar"],
            "oos_maxdd": m_top["max_dd"],
            "oos_cagr": m_top["cagr"],
            "n_oos": n_top,
            "sub_a_mar": sub_a,
            "sub_b_mar": sub_b,
        },
        "lottery_half": {
            "oos_mar": m_bottom["mar"],
            "n_oos": n_bottom,
        },
        "gates": {k: bool(v) for k, v in gates.items()},
        "gate_g1a_pass": "PASS" if gates["G1a"] else "FAIL",
        "gate_g1b_pass": "PASS" if gates["G1b"] else "FAIL",
        "gate_g2_pass": "PASS" if gates["G2_mechanism"] else "FAIL",
        "gate_g3_pass": "PASS" if gates["G3_N_OOS"] else "FAIL",
        "regime_split_flag": regime_split,
        "overall_verdict": verdict,
    }

    write_harness_report(OUT_MD, "S15", lines, meta)
    OUT_META.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
