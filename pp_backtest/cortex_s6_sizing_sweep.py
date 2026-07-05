#!/usr/bin/env python3
"""
S6 Kelly sizing sweep — quarter-Kelly (C1) vs half-Kelly (C2) vs S1 flat baseline.

Pre-registration: knowledge/backtests/2026-07-05_cortex_s6_sizing_sweep_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

# S6 Kelly Sizing Sweep — Pre-reg gates (LOCKED):
# G1a: best_oos_mar >= 1.8444
# G1b: best_oos_mar >= 0.516
# G2:  best_oos_maxdd >= -0.0940  (MaxDD <= -9.40%)
# G3:  post_cap_cv >= 0.10
# Baseline: S1 flat OOS MAR = 1.7844, N_OOS = 1732

Usage:
    python pp_backtest/cortex_s6_sizing_sweep.py
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

from pp_backtest.cortex_book1_common import OOS_WINDOW, PANEL_END, PANEL_START, _fmt_pct
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_proximity_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.d1_capital_based_validation import PreparedTrade, _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    MIN_POS_VND,
    RESEARCH_LABEL,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.phase_exit_sweep_core import ADV_PARTICIPATION, MAX_POSITIONS, PORTFOLIO_VND
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_s6"
KELLY_JSON = REPO / "data" / "research" / "cortex_xdisc" / "s6_kelly_precheck.json"
PREREG = "knowledge/backtests/2026-07-05_cortex_s6_sizing_sweep_prereg.md"

S1_MIN_PROX = 0.85
KELLY_CAP = 0.10
N_DECILES = 10

IS_START = pd.Timestamp("2012-01-01")
IS_END = pd.Timestamp("2019-12-31")

# Locked gates — do not modify post-run
G1A = 1.8444
G1B = 0.516
G2_MAXDD = -0.0940
G3_MIN_CV = 0.10
BASELINE_OOS_MAR = 1.7844
BASELINE_N_OOS = 1732
BASELINE_OOS_MAXDD = -0.0817
MAR_TOLERANCE = 0.05
N_TOLERANCE = int(BASELINE_N_OOS * 0.01)
VIN_SYMBOLS = {"VIC", "VHM", "VRE"}


def _kelly_full(p: float, w: float, l: float) -> float:
    if w <= 0 or not np.isfinite(p):
        return np.nan
    return max((p * w - (1.0 - p) * l) / w, 0.0)


def _bin_stats(returns: np.ndarray) -> tuple[float, float, float]:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    p = len(wins) / len(returns) if len(returns) else 0.0
    w = float(np.mean(wins)) if len(wins) else 0.0
    l = float(np.mean(np.abs(losses))) if len(losses) else 0.0
    return p, w, l


def export_kelly_precheck_json() -> dict[str, Any]:
    """Build locked decile Kelly table from IS estimation (same as pre-check)."""
    stack = build_baseline_stack()
    trades = stack["base_trades"].copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    is_trades = trades[
        (trades["entry_date"] >= IS_START) & (trades["entry_date"] <= IS_END)
    ].copy()
    is_trades = is_trades[np.isfinite(is_trades["rs_score"])]

    edges = np.quantile(is_trades["rs_score"].values, np.linspace(0, 1, N_DECILES + 1))
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-9

    is_trades["decile"] = pd.cut(
        is_trades["rs_score"], bins=edges, labels=range(N_DECILES), include_lowest=True
    ).astype(float)

    quarter: dict[str, float] = {}
    full: dict[str, float] = {}
    for d in range(N_DECILES):
        sub = is_trades[is_trades["decile"] == d]
        if len(sub) < 5:
            quarter[str(d)] = float("nan")
            full[str(d)] = float("nan")
            continue
        p, w, l = _bin_stats(sub["net_return"].astype(float).values)
        fk = _kelly_full(p, w, l)
        full[str(d)] = fk
        quarter[str(d)] = fk / 4.0 if np.isfinite(fk) else float("nan")

    payload = {
        "generated": str(date.today()),
        "source": "cortex_xdisc_s6_kelly_precheck methodology — IS 2012-2019",
        "decile_index": "0=lowest RS, 9=highest RS",
        "decile_edges": edges.tolist(),
        "quarter_kelly": quarter,
        "full_kelly": full,
    }
    KELLY_JSON.parent.mkdir(parents=True, exist_ok=True)
    KELLY_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_kelly_table() -> tuple[np.ndarray, dict[int, float], dict[int, float]]:
    if not KELLY_JSON.exists():
        export_kelly_precheck_json()
    data = json.loads(KELLY_JSON.read_text(encoding="utf-8"))
    edges = np.array(data["decile_edges"])
    qk = {int(k): float(v) for k, v in data["quarter_kelly"].items()}
    fk = {int(k): float(v) for k, v in data["full_kelly"].items()}
    return edges, qk, fk


def assign_decile(scores: pd.Series, edges: np.ndarray) -> pd.Series:
    return pd.cut(scores, bins=edges, labels=range(N_DECILES), include_lowest=True).astype(float)


def prepare_trades_absolute_weight(
    trades: pd.DataFrame,
    weight_col: str,
    rank_col: str = "rs_score",
) -> list[PreparedTrade]:
    """Target weight = absolute portfolio fraction in weight_col (Kelly sizing)."""
    if trades.empty:
        return []
    df = trades.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    tf = df["total_frac"].astype(float).fillna(0.5) if "total_frac" in df.columns else pd.Series(0.5, index=df.index)
    target_w = df[weight_col].astype(float) * tf
    if "adv50_value" in df.columns and (df["adv50_value"].fillna(0) > 0).any():
        adv = df["adv50_value"].fillna(0).astype(float)
        cap_w = adv * ADV_PARTICIPATION / PORTFOLIO_VND
        target_w = np.minimum(target_w, cap_w)
    min_w = MIN_POS_VND / PORTFOLIO_VND
    rank_vals = df[rank_col].astype(float) if rank_col in df.columns else pd.Series(0.0, index=df.index)
    out: list[PreparedTrade] = []
    for i, row in df.iterrows():
        w = float(target_w.loc[i])
        if w < min_w:
            continue
        out.append(
            PreparedTrade(
                trade_id=int(i),
                sleeve="A3",
                entry_date=pd.Timestamp(row["entry_date"]).normalize(),
                exit_date=pd.Timestamp(row["exit_date"]).normalize(),
                net_return=float(row["net_return"]),
                target_w=w,
                rank=float(rank_vals.loc[i]) if np.isfinite(rank_vals.loc[i]) else 0.0,
                entry_year=int(pd.Timestamp(row["entry_date"]).year),
            )
        )
    return out


def apply_kelly_weights(
    trades: pd.DataFrame,
    edges: np.ndarray,
    kelly_map: dict[int, float],
    cap: float,
) -> pd.DataFrame:
    out = trades.copy()
    out["decile"] = assign_decile(out["rs_score"].astype(float), edges)
    weights = []
    for _, row in out.iterrows():
        d = int(row["decile"]) if np.isfinite(row["decile"]) else 0
        fq = kelly_map.get(d, 0.05)
        if not np.isfinite(fq):
            fq = 0.05
        weights.append(min(fq, cap))
    out["_kelly_w"] = weights
    return out


def compute_oos_cv(trades: pd.DataFrame, weight_col: str) -> float:
    oos = trades.copy()
    oos["entry_date"] = pd.to_datetime(oos["entry_date"])
    oos = oos[(oos["entry_date"].dt.year >= OOS_WINDOW[0]) & (oos["entry_date"].dt.year <= OOS_WINDOW[1])]
    w = oos[weight_col].astype(float)
    if "adv50_value" in oos.columns:
        adv_cap = oos["adv50_value"].fillna(0).astype(float) * ADV_PARTICIPATION / PORTFOLIO_VND
        w = np.minimum(w, adv_cap)
    mean_w = float(w.mean())
    return float(w.std() / mean_w) if mean_w > 0 else 0.0


def year_mar_table(eq: pd.Series, years: range) -> dict[int, float]:
    out: dict[int, float] = {}
    for y in years:
        sub = slice_equity_years(eq, y, y)
        if len(sub) < 2:
            out[y] = float("nan")
        else:
            out[y] = float(_metrics_from_equity(sub)["mar"])
    return out


def decile_return_attribution(trades: pd.DataFrame, weight_col: str | None) -> dict[int, float]:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    oos = t[(t["entry_date"].dt.year >= OOS_WINDOW[0]) & (t["entry_date"].dt.year <= OOS_WINDOW[1])]
    if oos.empty:
        return {}
    if weight_col:
        contrib = oos["net_return"].astype(float) * oos[weight_col].astype(float)
    else:
        base_w = 1.0 / MAX_POSITIONS
        tf = oos["total_frac"].astype(float).fillna(0.5) if "total_frac" in oos.columns else 0.5
        mult = oos["_size_mult"].astype(float) if "_size_mult" in oos.columns else 1.0
        contrib = oos["net_return"].astype(float) * base_w * tf * mult
    by_dec = oos.groupby("decile", dropna=False).apply(
        lambda g: float(contrib.loc[g.index].mean()), include_groups=False
    )
    return {int(k) if np.isfinite(k) else -1: v for k, v in by_dec.items()}


def evaluate_arm_gates(oos_mar: float, oos_maxdd: float, post_cap_cv: float) -> dict[str, bool]:
    return {
        "G1a": np.isfinite(oos_mar) and oos_mar >= G1A,
        "G1b": np.isfinite(oos_mar) and oos_mar >= G1B,
        "G2": np.isfinite(oos_maxdd) and oos_maxdd >= G2_MAXDD,
        "G3": post_cap_cv >= G3_MIN_CV,
    }


def final_verdict(arms: dict[str, dict]) -> tuple[str, str]:
    best_mar = max(arms["C1"]["oos_mar"], arms["C2"]["oos_mar"])
    flat_mar = arms["flat"]["oos_mar"]
    c1_g = arms["C1"]["gates"]
    c2_g = arms["C2"]["gates"]
    c1_pass = all(c1_g.values())
    c2_pass = all(c2_g.values())
    best_g = c1_g if arms["C1"]["oos_mar"] >= arms["C2"]["oos_mar"] else c2_g

    if arms["C1"]["post_cap_cv"] < 0.05 or arms["C2"]["post_cap_cv"] < 0.05:
        return "DEGENERATE", "flat_5pct"

    if c1_pass and (not c2_pass or arms["C1"]["oos_mar"] >= arms["C2"]["oos_mar"]):
        return "BEST_PASS (C1)", "c1_qkelly"
    if c2_pass:
        return "BEST_PASS (C2)", "c2_hkelly"

    # Pre-reg: G2 fail → DEGRADING regardless of MAR
    if not best_g["G2"]:
        return "DEGRADING", "flat_5pct"
    if best_mar < G1B or (best_mar < flat_mar - 0.10):
        return "DEGRADING", "flat_5pct"
    if best_mar >= G1B and best_mar < G1A:
        return "NEUTRAL", "flat_5pct"
    return "NEUTRAL", "flat_5pct"


def write_report(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arms = meta["arms"]
    fv = meta["final_verdict"]
    rec = meta["recommended_sizing"]

    lines = [
        "# S6 Kelly Sizing Sweep Report",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Signal pool:** S1 within_15pct (prox >= {S1_MIN_PROX})",
        "",
        f"**FINAL VERDICT: {fv}**",
        f"**Recommended sizing:** {rec}",
        "",
        "## Comparison (flat vs C1 vs C2)",
        "",
        "| Arm | Full MAR | OOS MAR | OOS MaxDD | OOS CAGR | N OOS |",
        "|-----|----------|---------|-----------|----------|-------|",
    ]
    for key, label in [("flat", "flat-5%"), ("C1", "C1 q-Kelly"), ("C2", "C2 h-Kelly")]:
        a = arms[key]
        lines.append(
            f"| {label} | {a['full_mar']:.4f} | {a['oos_mar']:.4f} | "
            f"{_fmt_pct(a['oos_maxdd'])} | {_fmt_pct(a['oos_cagr'])} | {a['n_oos']} |"
        )

    lines.extend(["", "## Gate verdicts", ""])
    for key, label in [("C1", "C1 q-Kelly"), ("C2", "C2 h-Kelly")]:
        lines.append(f"### {label}")
        lines.append("| Gate | Threshold | Pass |")
        lines.append("|------|-----------|------|")
        g = arms[key]["gates"]
        lines.append(f"| G1a | >= {G1A:.4f} | {'PASS' if g['G1a'] else 'FAIL'} |")
        lines.append(f"| G1b | >= {G1B:.3f} | {'PASS' if g['G1b'] else 'FAIL'} |")
        lines.append(f"| G2 | MaxDD >= {G2_MAXDD:.4f} | {'PASS' if g['G2'] else 'FAIL'} |")
        lines.append(f"| G3 | CV >= {G3_MIN_CV:.2f} | {'PASS' if g['G3'] else 'FAIL'} |")
        lines.append("")

    lines.extend([
        "## Sub-window OOS MAR",
        "",
        "| Arm | Sub-A (2020-2022) | Sub-B (2023-2026) |",
        "|-----|-------------------|-------------------|",
    ])
    for key, label in [("flat", "flat"), ("C1", "C1"), ("C2", "C2")]:
        a = arms[key]
        lines.append(
            f"| {label} | {a['oos_sub_a_mar']:.4f} | {a['oos_sub_b_mar']:.4f} |"
        )
    lines.append("")
    lines.append(
        f"**M3 diagnostic:** C1 sub-B {arms['C1']['oos_sub_b_mar']:.4f} vs S1 flat sub-B "
        f"{arms['flat']['oos_sub_b_mar']:.4f} (baseline ref 0.5465)"
    )

    lines.extend(["", "## Year attribution (OOS MAR by year)", ""])
    lines.append("| Year | flat | C1 | C2 |")
    lines.append("|------|------|----|----|")
    for y in range(2019, 2027):
        lines.append(
            f"| {y} | {meta['year_mar']['flat'].get(y, float('nan')):.4f} | "
            f"{meta['year_mar']['C1'].get(y, float('nan')):.4f} | "
            f"{meta['year_mar']['C2'].get(y, float('nan')):.4f} |"
        )

    lines.extend(["", "## Decile attribution (mean weighted return contrib, OOS)", ""])
    lines.append("| Decile | flat | C1 | C2 |")
    lines.append("|--------|------|----|----|")
    for d in range(N_DECILES):
        lines.append(
            f"| {d} | {meta['decile_attr']['flat'].get(d, float('nan')):.6f} | "
            f"{meta['decile_attr']['C1'].get(d, float('nan')):.6f} | "
            f"{meta['decile_attr']['C2'].get(d, float('nan')):.6f} |"
        )

    lines.extend(["", "## Position-size histogram (OOS, % of trades)", ""])
    for key, label in [("flat", "flat"), ("C1", "C1"), ("C2", "C2")]:
        h = meta["histograms"][key]
        lines.append(f"**{label}:** " + ", ".join(f"{k}={v:.1f}%" for k, v in h.items()))

    lines.extend(["", "## Top-10 overweight (C1 weight > 8%)", ""])
    lines.append("| Symbol | Entry | Decile | Weight |")
    lines.append("|--------|-------|--------|--------|")
    for row in meta.get("top_overweights", [])[:10]:
        lines.append(
            f"| {row['symbol']} | {row['entry_date']} | {row['decile']} | {row['weight']:.2%} |"
        )
    if meta.get("vin_distortion_flag"):
        lines.append("")
        lines.append("**[VIN-DISTORTION-S6]** VIN symbols >40% of top-decile Kelly positions.")

    lines.extend(["", "RESEARCH_ONLY_NOT_PRODUCTION", ""])
    (OUT_DIR / "s6_sizing_sweep_report.md").write_text("\n".join(lines), encoding="utf-8")


def weight_histogram(weights: pd.Series) -> dict[str, float]:
    w = weights.astype(float)
    n = len(w)
    if n == 0:
        return {}
    return {
        "lt_3pct": 100 * (w < 0.03).sum() / n,
        "3_5pct": 100 * ((w >= 0.03) & (w < 0.05)).sum() / n,
        "5_8pct": 100 * ((w >= 0.05) & (w < 0.08)).sum() / n,
        "8_10pct": 100 * ((w >= 0.08) & (w <= 0.10)).sum() / n,
        "gt_10pct": 100 * (w > 0.10).sum() / n,
    }


def run_arm_metrics(eq: pd.Series, trades: pd.DataFrame, n_oos: int) -> dict[str, Any]:
    m_full = _metrics_from_equity(eq)
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_a = slice_equity_years(eq, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_b = slice_equity_years(eq, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    m_oos = _metrics_from_equity(eq_oos)
    return {
        "full_mar": float(m_full["mar"]),
        "oos_mar": float(m_oos["mar"]),
        "oos_maxdd": float(m_oos["max_dd"]),
        "oos_cagr": float(m_oos["cagr"]),
        "oos_sub_a_mar": float(_metrics_from_equity(eq_a)["mar"]),
        "oos_sub_b_mar": float(_metrics_from_equity(eq_b)["mar"]),
        "n_oos": n_oos,
        "equity": eq,
    }


def run_s6_sizing_sweep() -> dict[str, Any]:
    print("S6 Kelly sizing sweep", flush=True)
    print(f"  Gates: G1a={G1A} G1b={G1B} G2 MaxDD>={G2_MAXDD} G3 CV>={G3_MIN_CV}", flush=True)

    edges, qk_map, fk_map = load_kelly_table()
    half_map = {d: min(2 * v, KELLY_CAP) if np.isfinite(v) else 0.05 for d, v in qk_map.items()}

    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]
    filter_map = build_signal_filter_map(ctx.panel)

    s1_trades = apply_proximity_filter(base_trades, filter_map, S1_MIN_PROX)
    s1_trades = s1_trades.copy()
    s1_trades["decile"] = assign_decile(s1_trades["rs_score"].astype(float), edges)

    n_oos = count_oos_trades(s1_trades, OOS_WINDOW[0], OOS_WINDOW[1])
    print(f"  S1-filtered N_OOS: {n_oos} (expected {BASELINE_N_OOS})", flush=True)

    # --- Flat baseline (exact S1 pipeline) ---
    sized_flat = apply_size(s1_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_flat = prepare_trades_with_size(sized_flat, "rs_score", "_size_mult")
    eq_flat, _, _ = run_capital_sim(prep_flat, ctx.gate, D4_CASH_YIELD)
    flat_oos_n = sum(
        1 for p in prep_flat if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1]
    )
    flat_metrics = run_arm_metrics(eq_flat, sized_flat, flat_oos_n)

    print(f"  Flat OOS MAR={flat_metrics['oos_mar']:.4f} (expected {BASELINE_OOS_MAR})", flush=True)

    if abs(flat_metrics["oos_mar"] - BASELINE_OOS_MAR) > MAR_TOLERANCE:
        raise RuntimeError(
            f"BASELINE MISMATCH: flat OOS MAR {flat_metrics['oos_mar']:.4f} "
            f"vs expected {BASELINE_OOS_MAR} ± {MAR_TOLERANCE}. STOP."
        )
    if abs(flat_oos_n - BASELINE_N_OOS) > N_TOLERANCE:
        raise RuntimeError(
            f"HARNESS BUG: flat N_OOS {flat_oos_n} vs expected {BASELINE_N_OOS} ± {N_TOLERANCE}"
        )

    # --- C1 quarter-Kelly ---
    c1_trades = apply_kelly_weights(s1_trades, edges, qk_map, KELLY_CAP)
    prep_c1 = prepare_trades_absolute_weight(c1_trades, "_kelly_w", "rs_score")
    c1_oos_n = sum(1 for p in prep_c1 if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])
    if abs(c1_oos_n - BASELINE_N_OOS) > N_TOLERANCE:
        raise RuntimeError(f"HARNESS BUG: C1 N_OOS {c1_oos_n} deviates from {BASELINE_N_OOS}")
    cv_c1 = compute_oos_cv(c1_trades, "_kelly_w")
    if cv_c1 < 0.05:
        raise RuntimeError(f"DEGENERATE: C1 post-cap CV {cv_c1:.4f} < 0.05")
    eq_c1, _, _ = run_capital_sim(prep_c1, ctx.gate, D4_CASH_YIELD)
    c1_metrics = run_arm_metrics(eq_c1, c1_trades, c1_oos_n)
    c1_gates = evaluate_arm_gates(c1_metrics["oos_mar"], c1_metrics["oos_maxdd"], cv_c1)
    print(f"  C1 OOS MAR={c1_metrics['oos_mar']:.4f} CV={cv_c1:.3f}", flush=True)

    # --- C2 half-Kelly ---
    c2_trades = apply_kelly_weights(s1_trades, edges, half_map, KELLY_CAP)
    prep_c2 = prepare_trades_absolute_weight(c2_trades, "_kelly_w", "rs_score")
    c2_oos_n = sum(1 for p in prep_c2 if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])
    if abs(c2_oos_n - BASELINE_N_OOS) > N_TOLERANCE:
        raise RuntimeError(f"HARNESS BUG: C2 N_OOS {c2_oos_n} deviates from {BASELINE_N_OOS}")
    cv_c2 = compute_oos_cv(c2_trades, "_kelly_w")
    eq_c2, _, _ = run_capital_sim(prep_c2, ctx.gate, D4_CASH_YIELD)
    c2_metrics = run_arm_metrics(eq_c2, c2_trades, c2_oos_n)
    c2_gates = evaluate_arm_gates(c2_metrics["oos_mar"], c2_metrics["oos_maxdd"], cv_c2)
    print(f"  C2 OOS MAR={c2_metrics['oos_mar']:.4f} CV={cv_c2:.3f}", flush=True)

    arms = {
        "flat": {**flat_metrics, "post_cap_cv": 0.0, "gates": {}},
        "C1": {**c1_metrics, "post_cap_cv": cv_c1, "gates": c1_gates},
        "C2": {**c2_metrics, "post_cap_cv": cv_c2, "gates": c2_gates},
    }
    verdict, rec = final_verdict(arms)
    print(f"  FINAL VERDICT: {verdict}", flush=True)

    # Histograms (OOS)
    oos_mask = (
        pd.to_datetime(s1_trades["entry_date"]).dt.year >= OOS_WINDOW[0]
    ) & (pd.to_datetime(s1_trades["entry_date"]).dt.year <= OOS_WINDOW[1])
    flat_w = pd.Series([p.target_w for p in prep_flat if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1]])
    c1_w = pd.Series([p.target_w for p in prep_c1 if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1]])
    c2_w = pd.Series([p.target_w for p in prep_c2 if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1]])

    # Top overweights C1
    oos_c1 = c1_trades[oos_mask].copy()
    top_rows = []
    for _, row in oos_c1.nlargest(20, "_kelly_w").iterrows():
        if row["_kelly_w"] > 0.08:
            top_rows.append({
                "symbol": row["symbol"],
                "entry_date": str(row["entry_date"])[:10],
                "decile": int(row["decile"]) if np.isfinite(row["decile"]) else -1,
                "weight": float(row["_kelly_w"]),
            })
    top_decile = oos_c1[oos_c1["decile"] >= 7]
    vin_share = (
        top_decile["symbol"].astype(str).isin(VIN_SYMBOLS).mean()
        if len(top_decile) else 0.0
    )

    meta: dict[str, Any] = {
        "test": "S6 Kelly sizing sweep",
        "date": str(date.today()),
        "baseline_oos_mar": BASELINE_OOS_MAR,
        "baseline_n_oos": BASELINE_N_OOS,
        "flat_oos_mar_verified": flat_metrics["oos_mar"],
        "c1_qkelly_oos_mar": c1_metrics["oos_mar"],
        "c1_qkelly_maxdd": c1_metrics["oos_maxdd"],
        "c1_gate_g1a": "PASS" if c1_gates["G1a"] else "FAIL",
        "c1_gate_g1b": "PASS" if c1_gates["G1b"] else "FAIL",
        "c1_gate_g2": "PASS" if c1_gates["G2"] else "FAIL",
        "c1_gate_g3": "PASS" if c1_gates["G3"] else "FAIL",
        "c2_hkelly_oos_mar": c2_metrics["oos_mar"],
        "c2_hkelly_maxdd": c2_metrics["oos_maxdd"],
        "c2_gate_g1a": "PASS" if c2_gates["G1a"] else "FAIL",
        "c2_gate_g1b": "PASS" if c2_gates["G1b"] else "FAIL",
        "c2_gate_g2": "PASS" if c2_gates["G2"] else "FAIL",
        "c2_gate_g3": "PASS" if c2_gates["G3"] else "FAIL",
        "verdict": verdict,
        "recommended_sizing": rec,
        "s6_new_status": "TESTED" if verdict not in ("DEGENERATE",) else "DEGENERATE",
        "arms": arms,
        "year_mar": {
            "flat": year_mar_table(flat_metrics["equity"], range(2019, 2027)),
            "C1": year_mar_table(c1_metrics["equity"], range(2019, 2027)),
            "C2": year_mar_table(c2_metrics["equity"], range(2019, 2027)),
        },
        "decile_attr": {
            "flat": decile_return_attribution(sized_flat, None),
            "C1": decile_return_attribution(c1_trades, "_kelly_w"),
            "C2": decile_return_attribution(c2_trades, "_kelly_w"),
        },
        "histograms": {
            "flat": weight_histogram(flat_w),
            "C1": weight_histogram(c1_w),
            "C2": weight_histogram(c2_w),
        },
        "top_overweights": top_rows,
        "vin_distortion_flag": vin_share > 0.40,
        "kelly_json": str(KELLY_JSON),
        "final_verdict": verdict,
    }

    # Strip equity from arms for JSON serialization
    for k in arms:
        arms[k].pop("equity", None)

    write_report(meta)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "s6_sizing_sweep_meta.json").write_text(
        json.dumps({k: v for k, v in meta.items() if k not in ("arms",)}, indent=2, default=str),
        encoding="utf-8",
    )
    full_meta_path = OUT_DIR / "s6_sizing_sweep_full_meta.json"
    full_meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_DIR / 's6_sizing_sweep_report.md'}", flush=True)
    return meta


def main() -> None:
    run_s6_sizing_sweep()


if __name__ == "__main__":
    main()
