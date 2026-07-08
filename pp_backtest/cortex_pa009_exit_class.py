#!/usr/bin/env python3
"""
PA-009 exit-class v2 — exact two-leg 2R partial exit on A3_RS+S2@1.4x.

Pre-registration: knowledge/backtests/2026-07-08_pa009_exit_class_prereg_v2.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    python pp_backtest/cortex_pa009_exit_class.py
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

from pp_backtest.cortex_book1_common import OOS_WINDOW, PANEL_END, PANEL_START
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_degeneracy_common import build_symbol_panel, oos_entry_mask
from pp_backtest.d1_capital_based_validation import PreparedTrade, _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    GK_MULT,
    MIN_POS_VND,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.ema_levels.indicators import compute_atr
from pp_backtest.phase_exit_sweep_core import ADV_PARTICIPATION, MAX_POSITIONS, PORTFOLIO_VND
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_pa009_exit_class"
PREREG = REPO / "knowledge" / "backtests" / "2026-07-08_pa009_exit_class_prereg_v2.md"

S2_BASE_MULT = 1.4
BASELINE_OOS_MAR_EXPECTED = 2.5292
REPRO_TOL = 0.050
COST_RT = 0.004
STOP_ATR_MULT = 2.0  # 1R = 2.0 × ATR14

G1A_EXIT_FLOOR = 0.85
G1B_EXIT_IMPROVE = 0.60
MAR_SPIKE_TOL = 0.30

VARIANTS: tuple[tuple[str, float], ...] = (
    ("pa009_v2_1r5", 1.5),
    ("pa009_v2_2r_base", 2.0),
    ("pa009_v2_2r5", 2.5),
)


def _oos_metrics(eq: pd.Series) -> tuple[dict, dict, dict]:
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_a = slice_equity_years(eq, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_b = slice_equity_years(eq, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    return (
        _metrics_from_equity(eq_oos),
        _metrics_from_equity(eq_a),
        _metrics_from_equity(eq_b),
    )


def _atr14_at_entry(sp: dict, entry_i: int) -> float:
    if "atr" in sp:
        v = float(sp["atr"][entry_i])
        if np.isfinite(v) and v > 0:
            return v
    return float("nan")


def _base_target_weight(row: pd.Series, size_mult: float) -> float:
    base_w = 1.0 / MAX_POSITIONS
    tf = float(row.get("total_frac") or 0.5)
    gk = bool(row.get("has_gk")) if "has_gk" in row.index else False
    gk_factor = GK_MULT if gk else 1.0
    target_w = min(base_w * gk_factor, base_w * GK_MULT) * tf * size_mult
    if "adv50_value" in row.index and float(row.get("adv50_value") or 0) > 0:
        adv = float(row["adv50_value"])
        cap_w = adv * ADV_PARTICIPATION / PORTFOLIO_VND
        target_w = min(target_w, cap_w)
    min_w = MIN_POS_VND / PORTFOLIO_VND
    return target_w if target_w >= min_w else float("nan")


def build_two_leg_trades(
    sized: pd.DataFrame,
    sym_panel: dict,
    r_factor: float,
) -> tuple[list[PreparedTrade], int, int]:
    """Exact split-position PA-009: two PreparedTrade rows when 2R triggers."""
    df = sized.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    oos_mask = oos_entry_mask(df)

    prepared: list[PreparedTrade] = []
    trade_id = 0
    split_count = 0
    oos_count = int(oos_mask.sum())

    for i, row in df.iterrows():
        size_mult = float(row.get("_size_mult") or 1.0)
        w = _base_target_weight(row, size_mult)
        if not np.isfinite(w):
            continue

        rank = float(row["rs_score"]) if "rs_score" in row.index and np.isfinite(row["rs_score"]) else 0.0
        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        exit_date = pd.Timestamp(row["exit_date"]).normalize()
        entry_year = int(entry_date.year)
        net_return = float(row["net_return"])

        if not bool(oos_mask.loc[i]):
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        entry_price = float(row.get("blended_ep") or row.get("ep1") or 0.0)
        if entry_price <= 0:
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        ei = sp["date_to_i"].get(entry_date)
        xi = sp["date_to_i"].get(exit_date)
        if ei is None or xi is None or xi <= ei:
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        atr = _atr14_at_entry(sp, ei)
        if not np.isfinite(atr) or atr <= 0:
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        r_dist = STOP_ATR_MULT * atr
        target_r = entry_price + r_factor * r_dist

        hit_i: int | None = None
        for j in range(ei + 1, xi + 1):
            if j >= len(sp["high"]):
                break
            if sp["high"][j] >= target_r:
                hit_i = j
                break

        if hit_i is None:
            prepared.append(
                PreparedTrade(
                    trade_id=trade_id,
                    sleeve="A3",
                    entry_date=entry_date,
                    exit_date=exit_date,
                    net_return=net_return,
                    target_w=w,
                    rank=rank,
                    entry_year=entry_year,
                )
            )
            trade_id += 1
            continue

        close_i = float(sp["close"][hit_i])
        exit_a_price = min(target_r, close_i)
        exit_b_price = entry_price * (1.0 + net_return + COST_RT)

        ret_a = (exit_a_price / entry_price) - 1.0 - COST_RT / 2
        ret_b = (exit_b_price / entry_price) - 1.0 - COST_RT / 2
        half_w = w / 2.0
        leg_a_date = pd.Timestamp(sp["dates"].iloc[hit_i]).normalize()

        prepared.append(
            PreparedTrade(
                trade_id=trade_id,
                sleeve="A3",
                entry_date=entry_date,
                exit_date=leg_a_date,
                net_return=ret_a,
                target_w=half_w,
                rank=rank,
                entry_year=entry_year,
            )
        )
        trade_id += 1
        prepared.append(
            PreparedTrade(
                trade_id=trade_id,
                sleeve="A3",
                entry_date=entry_date,
                exit_date=exit_date,
                net_return=ret_b,
                target_w=half_w,
                rank=rank,
                entry_year=entry_year,
            )
        )
        trade_id += 1
        split_count += 1

    return prepared, split_count, oos_count


def _evaluate_exit_gates(
    metrics: dict[str, float],
    *,
    baseline_mar: float,
    baseline_maxdd: float,
    g1a_thresh: float,
    g1b_thresh: float,
) -> dict[str, Any]:
    mar = metrics["oos_mar"]
    maxdd = metrics["oos_maxdd"]
    cagr = metrics["oos_cagr"]
    sub_a = metrics["oos_sub_a_mar"]
    sub_b = metrics["oos_sub_b_mar"]

    g1a = np.isfinite(mar) and mar >= g1a_thresh
    g1b = np.isfinite(maxdd) and maxdd >= g1b_thresh
    g1c = np.isfinite(cagr) and cagr > 0.0
    g1d_a = np.isfinite(sub_a) and sub_a > 0.0
    g1d_b = np.isfinite(sub_b) and sub_b > 0.0

    if np.isfinite(mar) and mar < baseline_mar * 0.50:
        verdict = "PARKED"
    elif np.isfinite(maxdd) and maxdd < baseline_maxdd:
        verdict = "PARKED"
    elif not g1d_b:
        verdict = "PARKED"
    elif g1a and g1b and g1c and g1d_a and g1d_b:
        verdict = "ADVANCE"
    else:
        verdict = "FAIL"

    return {
        "G1a_exit": g1a,
        "G1b_exit": g1b,
        "G1c_exit": g1c,
        "G1d_exit_a": g1d_a,
        "G1d_exit_b": g1d_b,
        "verdict": verdict,
    }


def _write_report(
    baseline: dict[str, float],
    gates: dict[str, float],
    results: list[dict[str, Any]],
) -> None:
    today = str(date.today())
    lines = [
        "# PA-009 Exit-Class v2 — Two-Leg Partial Exit",
        "",
        f"**Generated:** {today}",
        f"**Baseline OOS MAR:** {baseline['baseline_oos_mar']:.4f}",
        f"**Baseline OOS MaxDD:** {baseline['baseline_oos_maxdd']:.4f}",
        f"**G1a_exit (MAR >=):** {gates['g1a_exit']:.4f}",
        f"**G1b_exit (MaxDD >=):** {gates['g1b_exit']:.4f}",
        "",
        "| Variant | 2R factor | OOS MAR | OOS MaxDD | OOS CAGR | sub-A | sub-B | Trigger% | G1a | G1b | Verdict |",
        "|---------|-----------|---------|-----------|----------|-------|-------|----------|-----|-----|---------|",
    ]
    for r in results:
        lines.append(
            f"| {r['label']} | {r['r_factor']:.1f} | {r['oos_mar']:.4f} | {r['oos_maxdd']:.4f} | "
            f"{r['oos_cagr']:.4f} | {r['oos_sub_a_mar']:.4f} | {r['oos_sub_b_mar']:.4f} | "
            f"{r['trigger_rate']:.1%} | {'PASS' if r['G1a_exit'] else 'FAIL'} | "
            f"{'PASS' if r['G1b_exit'] else 'FAIL'} | {r['verdict']} |"
        )
    lines.extend(["", "RESEARCH_ONLY_NOT_PRODUCTION"])
    (OUT_DIR / "pa009_exit_class_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_pa009_exit_class() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("PA-009 Exit-Class v2 Harness", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)

    print("\nStep 1: Build A3_RS+S2@1.4x baseline...", flush=True)
    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]

    filter_map = build_signal_filter_map(ctx.panel)
    s2_trades = apply_volume_filter(base_trades, filter_map, S2_BASE_MULT)
    sized = apply_size(s2_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    sized["entry_date"] = pd.to_datetime(sized["entry_date"])
    sized["exit_date"] = pd.to_datetime(sized["exit_date"])

    prep_base = prepare_trades_with_size(sized, "rs_score", "_size_mult")
    eq_base, _, _ = run_capital_sim(prep_base, ctx.gate, D4_CASH_YIELD)
    m_oos, m_a, m_b = _oos_metrics(eq_base)
    baseline_oos_mar = float(m_oos["mar"])
    baseline_oos_maxdd = float(m_oos["max_dd"])
    baseline_oos_cagr = float(m_oos["cagr"])

    print(f"  Baseline OOS MAR: {baseline_oos_mar:.4f} (expected {BASELINE_OOS_MAR_EXPECTED})", flush=True)
    print(f"  Baseline OOS MaxDD: {baseline_oos_maxdd:.4f}", flush=True)
    print(f"  Baseline OOS CAGR: {baseline_oos_cagr:.4f}", flush=True)

    if abs(baseline_oos_mar - BASELINE_OOS_MAR_EXPECTED) > REPRO_TOL:
        print("  [BASELINE-DRIFT] halting.", flush=True)
        return {"halted": True, "baseline_oos_mar": baseline_oos_mar}

    baseline_payload = {
        "baseline_oos_mar": baseline_oos_mar,
        "baseline_oos_maxdd": baseline_oos_maxdd,
        "baseline_oos_cagr": baseline_oos_cagr,
        "baseline_sub_a_mar": float(m_a["mar"]),
        "baseline_sub_b_mar": float(m_b["mar"]),
        "window": f"{OOS_WINDOW[0]}-{OOS_WINDOW[1]}",
        "measured_date": str(date.today()),
        "n_oos_trades": count_oos_trades(sized, OOS_WINDOW[0], OOS_WINDOW[1]),
        "n_prep_trades": len(prep_base),
    }
    (OUT_DIR / "baseline_maxdd.json").write_text(
        json.dumps(baseline_payload, indent=2), encoding="utf-8"
    )
    print(f"  Wrote baseline_maxdd.json", flush=True)

    g1a_exit = baseline_oos_mar * G1A_EXIT_FLOOR
    g1b_exit = baseline_oos_maxdd * G1B_EXIT_IMPROVE
    gates = {"g1a_exit": g1a_exit, "g1b_exit": g1b_exit}

    print("\nStep 2: Build symbol panel with ATR...", flush=True)
    sym_panel = build_symbol_panel(ctx.panel)
    for sym, sp in sym_panel.items():
        high = pd.Series(sp["high"])
        low = pd.Series(sp["low"])
        close = pd.Series(sp["close"])
        sp["atr"] = compute_atr(high, low, close, 14).values.astype(float)

    print("\nStep 3: Run exit-class variants (exact two-leg)...", flush=True)
    results: list[dict[str, Any]] = []

    for label, r_factor in VARIANTS:
        prep, split_count, oos_count = build_two_leg_trades(sized, sym_panel, r_factor)
        eq, _, _ = run_capital_sim(prep, ctx.gate, D4_CASH_YIELD)
        m, ma, mb = _oos_metrics(eq)
        metrics = {
            "oos_mar": float(m["mar"]),
            "oos_maxdd": float(m["max_dd"]),
            "oos_cagr": float(m["cagr"]),
            "oos_sub_a_mar": float(ma["mar"]),
            "oos_sub_b_mar": float(mb["mar"]),
        }
        gate_eval = _evaluate_exit_gates(
            metrics,
            baseline_mar=baseline_oos_mar,
            baseline_maxdd=baseline_oos_maxdd,
            g1a_thresh=g1a_exit,
            g1b_thresh=g1b_exit,
        )
        trigger_rate = split_count / oos_count if oos_count else 0.0
        row = {
            "label": label,
            "r_factor": r_factor,
            "n_prep_trades": len(prep),
            "split_count": split_count,
            "trigger_rate": trigger_rate,
            **metrics,
            **gate_eval,
        }
        results.append(row)
        print(
            f"  {label}: MAR={row['oos_mar']:.4f} MaxDD={row['oos_maxdd']:.4f} "
            f"trigger={trigger_rate:.1%} verdict={row['verdict']}",
            flush=True,
        )

    base_mar = next(r["oos_mar"] for r in results if r["label"] == "pa009_v2_2r_base")
    sensitivity_ok = all(abs(r["oos_mar"] - base_mar) <= MAR_SPIKE_TOL for r in results)

    meta = {
        "generated": str(date.today()),
        "baseline": baseline_payload,
        "gates": {
            "g1a_exit": g1a_exit,
            "g1b_exit": g1b_exit,
            "g1a_exit_formula": f"baseline_mar * {G1A_EXIT_FLOOR}",
            "g1b_exit_formula": f"baseline_maxdd * {G1B_EXIT_IMPROVE}",
        },
        "variants": results,
        "parameter_sensitivity_ok": sensitivity_ok,
        "two_leg_dedup_check": {
            "baseline_prep_count": len(prep_base),
            "pa009_base_prep_count": next(r["n_prep_trades"] for r in results if r["label"] == "pa009_v2_2r_base"),
        },
    }
    (OUT_DIR / "pa009_exit_class_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    _write_report(baseline_payload, gates, results)

    print("\n=== PA-009 Exit-Class Summary ===", flush=True)
    print(f"  G1a_exit >= {g1a_exit:.4f} | G1b_exit >= {g1b_exit:.4f}", flush=True)
    for r in results:
        print(f"  {r['label']}: MAR {r['oos_mar']:.4f} MaxDD {r['oos_maxdd']:.4f} -> {r['verdict']}", flush=True)
    print(f"  Parameter sensitivity within {MAR_SPIKE_TOL} MAR: {sensitivity_ok}", flush=True)

    return meta


def main() -> None:
    run_pa009_exit_class()


if __name__ == "__main__":
    main()
