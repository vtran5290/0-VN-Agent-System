#!/usr/bin/env python3
"""
S19 — Intra-sector RS leader selection on S1-filtered A3_RS pool.

G1a: aggregate MAR >= 1.820 (S1 baseline x 1.02)
G2: mechanism gate — leader MAR >= laggard MAR AND mean spread > 0.20%

Pre-reg: knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_schwager_s19_buy_strongest.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_book2_common import build_signal_filter_map
from pp_backtest.cortex_schwager_common import (
    G1B_FLOOR,
    IS_WINDOW,
    MIN_N_OOS,
    OOS_WINDOW,
    S19_G1A,
    S1_BASELINE_OOS_MAR,
    apply_s19_c1_leader,
    apply_s19_c3_top_half,
    build_stack_with_sector,
    co_sector_keys,
    filter_co_sector_trades,
    run_filtered_sim,
    run_s19_c2_sim,
    verify_s1_baseline,
    write_harness_report,
    year_mask,
)
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL

OUT_MD = REPO / "knowledge" / "backtests" / "s19_harness_results.md"
OUT_META = REPO / "data" / "research" / "cortex_schwager" / "s19_harness_meta.json"
PREREG = "knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_prereg.md"

IS_SPREAD_WARN = 0.002
G2_MIN_SPREAD = 0.002
S1_MIN_PROX = 0.85


def _is_leader_laggard_spread(trades: pd.DataFrame, sector_map: dict[str, str]) -> tuple[float, str]:
    is_co = filter_co_sector_trades(trades, sector_map, IS_WINDOW)
    if is_co.empty:
        return np.nan, "NO-IS-COHORT"
    spreads: list[float] = []
    is_co = is_co.copy()
    is_co["entry_date"] = pd.to_datetime(is_co["entry_date"]).dt.normalize()
    is_co["_sec"] = is_co["symbol"].astype(str).map(sector_map)
    for (_, _), grp in is_co.groupby(["entry_date", "_sec"]):
        if len(grp) < 2:
            continue
        g = grp.sort_values("rs_score", ascending=False)
        spreads.append(float(g.iloc[0]["net_return"]) - float(g.iloc[-1]["net_return"]))
    if not spreads:
        return np.nan, "NO-IS-COHORT"
    mean_sp = float(np.mean(spreads))
    flag = "[IS-SPREAD-THIN]" if mean_sp < IS_SPREAD_WARN else "OK"
    return mean_sp, flag


def _leader_laggard_oos_mar(
    stack: dict[str, Any],
    co_trades: pd.DataFrame,
    sector_map: dict[str, str],
) -> tuple[float, float, float, int]:
    """Return leader MAR, laggard MAR, mean per-trade spread, sectors with leader>laggard."""
    t = co_trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    leader_idx: list[int] = []
    laggard_idx: list[int] = []
    spreads: list[float] = []
    sector_wins = 0
    sector_total = 0
    for (_, sec), grp in t.groupby(["entry_date", "_sec"]):
        if len(grp) < 2:
            continue
        g = grp.sort_values("rs_score", ascending=False)
        leader_idx.append(g.index[0])
        laggard_idx.append(g.index[-1])
        spreads.append(float(g.iloc[0]["net_return"]) - float(g.iloc[-1]["net_return"]))
        sector_total += 1
        if g.iloc[0]["net_return"] > g.iloc[-1]["net_return"]:
            sector_wins += 1
    if not leader_idx:
        return np.nan, np.nan, np.nan, 0
    _, m_lead, _ = run_filtered_sim(stack, t.loc[leader_idx].drop(columns=["_sec"]))
    _, m_lag, _ = run_filtered_sim(stack, t.loc[laggard_idx].drop(columns=["_sec"]))
    return m_lead["mar"], m_lag["mar"], float(np.mean(spreads)), sector_wins


def _g2_mechanism(
    leader_mar: float,
    laggard_mar: float,
    mean_spread: float,
    sector_wins: int,
) -> tuple[bool, str]:
    a = np.isfinite(leader_mar) and np.isfinite(laggard_mar) and leader_mar >= laggard_mar
    b = np.isfinite(mean_spread) and mean_spread > G2_MIN_SPREAD
    generalizes = sector_wins >= 2
    ok = a and b and generalizes
    detail = f"leader_mar={leader_mar:.4f} laggard_mar={laggard_mar:.4f} spread={mean_spread:.4f} sectors_win={sector_wins}"
    if not ok and a and b and not generalizes:
        return False, f"MECHANISM-FAIL (<2 sectors): {detail}"
    if not ok:
        return False, f"MECHANISM-FAIL: {detail}"
    return True, detail


def _evaluate_s19(
    oos_mar: float,
    s1_mar: float,
    n_oos: int,
    g2_ok: bool,
) -> tuple[dict[str, bool], str]:
    g1a = np.isfinite(oos_mar) and oos_mar >= S19_G1A
    g1b = np.isfinite(oos_mar) and oos_mar >= G1B_FLOOR
    g3 = n_oos >= MIN_N_OOS
    margin = oos_mar - S19_G1A if np.isfinite(oos_mar) else -999
    both_neg = s1_mar < 0 and oos_mar < 0

    gates = {"G1a": g1a, "G1b": g1b, "G2": g2_ok, "G3": g3}

    if not g3:
        return gates, "VN-THIN"
    if np.isfinite(oos_mar) and oos_mar < 0:
        return gates, "PARKED"
    if not g2_ok:
        return gates, "MECHANISM-FAIL"
    if both_neg:
        return gates, "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    if g1a and g1b:
        return gates, "ADVANCE"
    if g1a and margin < 0.03:
        return gates, "CONDITIONAL-ADVANCE"
    return gates, "FAIL"


def main() -> dict[str, Any]:
    print("S19 buy-strongest harness (S1+S19)", flush=True)
    stack = build_stack_with_sector()
    s1_trades = stack["s1_trades"]
    smap = stack["sector_map"]

    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n}", flush=True)
    if drift:
        print("  [BASELINE-DRIFT] warning — proceeding with locked gate 1.820", flush=True)

    is_spread, spread_flag = _is_leader_laggard_spread(s1_trades, smap)
    print(f"  IS leader-laggard spread: {is_spread:.4f} {spread_flag}", flush=True)

    co_oos = filter_co_sector_trades(s1_trades, smap, OOS_WINDOW)
    co_keys = co_sector_keys(s1_trades, smap, OOS_WINDOW)
    print(f"  Co-sector cohort days OOS (S1-filtered): {len(co_keys)}", flush=True)

    lead_mar, lag_mar, mean_spread, sec_wins = _leader_laggard_oos_mar(stack, co_oos, smap)
    g2_ok, g2_detail = _g2_mechanism(lead_mar, lag_mar, mean_spread, sec_wins)
    print(f"  G2 mechanism: {'PASS' if g2_ok else 'FAIL'} ({g2_detail})", flush=True)

    fmap = build_signal_filter_map(stack["ctx"].panel)
    leaders = apply_s19_c1_leader(co_oos, smap)
    overlap_n, overlap_d = 0, len(leaders)
    for _, row in leaders.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = fmap.get(key)
        if rec and rec.get("prox", 0) >= S1_MIN_PROX:
            overlap_n += 1
    s1_overlap = overlap_n / overlap_d if overlap_d else np.nan
    s1_flag = "HIGH-OVERLAP" if s1_overlap > 0.80 else "OK"
    print(f"  S1 overlap (leader picks): {s1_overlap:.1%} {s1_flag}", flush=True)

    candidates: list[tuple[str, Callable, Callable]] = [
        ("C1_leader_only", lambda t: apply_s19_c1_leader(t, smap), run_filtered_sim),
        ("C2_leader_weight", lambda t: t, run_s19_c2_sim),
        ("C3_exclude_laggard", lambda t: apply_s19_c3_top_half(t, smap), run_filtered_sim),
    ]

    results: list[dict[str, Any]] = []
    for label, transform, sim_fn in candidates:
        sub = transform(co_oos)
        if label == "C2_leader_weight":
            _, m, n = sim_fn(stack, sub)
        else:
            _, m, n = sim_fn(stack, sub)
        gates, verdict = _evaluate_s19(m["mar"], s1_m["mar"], n, g2_ok)
        results.append(
            {
                "label": label,
                "oos_mar": m["mar"],
                "n_oos": n,
                "gates": gates,
                "g2_detail": g2_detail,
                "verdict": verdict,
            }
        )
        print(f"  {label}: MAR={m['mar']:.4f} N={n} G2={'PASS' if g2_ok else 'FAIL'} -> {verdict}", flush=True)

    final = results[0]["verdict"] if results else "FAIL"

    lines = [
        "# S19 Buy-Strongest Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        "",
        f"**FINAL VERDICT (primary C1):** {final}",
        "",
        f"S1 baseline OOS MAR: **{s1_m['mar']:.4f}** (locked {S1_BASELINE_OOS_MAR})",
        f"G1a floor (aggregate): **{S19_G1A}**",
        f"IS leader-laggard spread: **{is_spread:.4f}** {spread_flag}",
        f"G2 mechanism: **{'PASS' if g2_ok else 'FAIL'}** — {g2_detail}",
        f"S1 overlap on leader picks: **{s1_overlap:.1%}** ({s1_flag})",
        "",
        "| Candidate | OOS MAR | N_OOS | G1a | G1b | G2 | Verdict |",
        "|-----------|---------|-------|-----|-----|----|---------|",
    ]
    for r in results:
        g = r["gates"]
        lines.append(
            f"| {r['label']} | {r['oos_mar']:.4f} | {r['n_oos']} | "
            f"{'PASS' if g['G1a'] else 'FAIL'} | {'PASS' if g['G1b'] else 'FAIL'} | "
            f"{'PASS' if g['G2'] else 'FAIL'} | {r['verdict']} |"
        )

    meta = {
        "is_spread": is_spread,
        "is_spread_flag": spread_flag,
        "s1_baseline_oos_mar": s1_m["mar"],
        "g2_mechanism": {"pass": g2_ok, "detail": g2_detail},
        "s1_overlap": s1_overlap,
        "results": results,
        "final_verdict": final,
    }
    write_harness_report(OUT_MD, "S19", lines, meta)
    OUT_META.write_text(__import__("json").dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
