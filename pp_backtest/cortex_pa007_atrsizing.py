#!/usr/bin/env python3
"""
PA-007 ATR-adjusted position sizing harness — S1-filtered A3_RS overlay.

Pre-registration: knowledge/backtests/2026-07-05_schwager_pa007_atrsizing_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Candidates: C1_atr20, C2_atr10
Formula: pos_size = min(1/20, k_val / ATR_Nd); k_val IS-derived before OOS.

Usage:
    python pp_backtest/cortex_pa007_atrsizing.py
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

from pp_backtest.cortex_book1_common import OOS_WINDOW, _fmt_pct
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_proximity_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_schwager_common import IS_END, IS_START
from pp_backtest.d1_capital_based_validation import PreparedTrade, _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    RESEARCH_LABEL,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.phase_exit_sweep_core import ADV_PARTICIPATION, MAX_POSITIONS, PORTFOLIO_VND
from pp_backtest.portfolio_optimization_phase31 import _tag_adv50
from pp_backtest.signals import atr
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_pa007"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_pa007_atrsizing_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_pa007_atrsizing_prereg.md"

S1_MIN_PROX = 0.85
FLAT_CAP = 1.0 / MAX_POSITIONS
MEDIAN_FLAT = 0.05

# Locked gates — do not modify post-run
S1_FLAT_OOS_MAR = 1.7844
S1_FLAT_OOS_MAXDD = -0.0817  # -8.17%
G1A_THRESHOLD = 1.8736
G1B_THRESHOLD = 0.516
G2_MAXDD_THRESHOLD = -0.08987  # -8.987%
G3_FILL_FLOOR = 0.80
G4_TURNOVER_CAP = 1.20
G5_2021_CAPTURE_FLOOR = 0.90
G1A_BORDERLINE = 0.020
MAR_TOLERANCE = 0.05
MAXDD_TOLERANCE = 0.005
BASELINE_N_OOS = 1732
N_TOLERANCE = int(BASELINE_N_OOS * 0.01)
FILL_ADV_PART = 0.07  # G3: 7% daily volume cap

SECTOR_GROUPS = (
    "Banking",
    "Real Estate",
    "Consumer",
    "Agri",
    "Securities",
    "Industrials",
)


def build_atr_table(panel: pd.DataFrame, windows: tuple[int, ...]) -> pd.DataFrame:
    """Per (symbol, date) ATR columns."""
    parts: list[pd.DataFrame] = []
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    for sym, g in p.groupby("symbol"):
        g = g.sort_values("date").copy()
        row = g[["symbol", "date"]].copy()
        for w in windows:
            row[f"atr{w}"] = atr(g, n=w).values
        parts.append(row)
    return pd.concat(parts, ignore_index=True)


def attach_atr(trades: pd.DataFrame, atr_tbl: pd.DataFrame, col: str) -> pd.DataFrame:
    out = trades.copy()
    out["entry_date"] = pd.to_datetime(out["entry_date"]).dt.normalize()
    merged = out.merge(
        atr_tbl.rename(columns={"date": "entry_date"}),
        on=["symbol", "entry_date"],
        how="left",
    )
    return merged


def derive_k_val(is_trades: pd.DataFrame, atr_col: str) -> tuple[float, int]:
    sub = is_trades[np.isfinite(is_trades[atr_col]) & (is_trades[atr_col] > 0)]
    n = len(sub)
    if n == 0:
        return float("nan"), 0
    med_atr = float(sub[atr_col].median())
    return MEDIAN_FLAT * med_atr, n


def prepare_trades_absolute_weight(
    trades: pd.DataFrame,
    weight_col: str,
    rank_col: str = "rs_score",
) -> list[PreparedTrade]:
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
    min_w = 100_000 / PORTFOLIO_VND
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


def apply_atr_weights(trades: pd.DataFrame, atr_col: str, k_val: float) -> pd.DataFrame:
    out = trades.copy()
    raw = np.where(
        np.isfinite(out[atr_col]) & (out[atr_col] > 0),
        k_val / out[atr_col].astype(float),
        np.nan,
    )
    out["_atr_w"] = np.minimum(FLAT_CAP, raw)
    out = out.dropna(subset=["_atr_w"])
    return out


def run_arm_metrics(eq: pd.Series, n_oos: int) -> dict[str, float]:
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_a = slice_equity_years(eq, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_b = slice_equity_years(eq, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    m_oos = _metrics_from_equity(eq_oos)
    return {
        "oos_mar": float(m_oos["mar"]),
        "oos_maxdd": float(m_oos["max_dd"]),
        "oos_cagr": float(m_oos["cagr"]),
        "oos_sub_a_mar": float(_metrics_from_equity(eq_a)["mar"]),
        "oos_sub_b_mar": float(_metrics_from_equity(eq_b)["mar"]),
        "n_oos": n_oos,
    }


def oos_mask(df: pd.DataFrame) -> pd.Series:
    ed = pd.to_datetime(df["entry_date"])
    return (ed.dt.year >= OOS_WINDOW[0]) & (ed.dt.year <= OOS_WINDOW[1])


def turnover_proxy(prep: list[PreparedTrade]) -> float:
    return sum(p.target_w for p in prep if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])


def pnl_contribution(trades: pd.DataFrame, weight_col: str | None, window: tuple[int, int] | None = None) -> float:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    if window:
        y0, y1 = window
        t = t[(t["entry_date"].dt.year >= y0) & (t["entry_date"].dt.year <= y1)]
    if t.empty:
        return 0.0
    if weight_col:
        w = t[weight_col].astype(float)
        tf = t["total_frac"].astype(float).fillna(0.5) if "total_frac" in t.columns else 0.5
        return float((t["net_return"].astype(float) * w * tf).sum())
    base_w = FLAT_CAP
    tf = t["total_frac"].astype(float).fillna(0.5) if "total_frac" in t.columns else 0.5
    mult = t["_size_mult"].astype(float) if "_size_mult" in t.columns else 1.0
    return float((t["net_return"].astype(float) * base_w * tf * mult).sum())


def high_vol_tercile_mask(trades: pd.DataFrame, atr_col: str = "atr20") -> pd.Series:
    t = trades.copy()
    valid = np.isfinite(t[atr_col]) & (t[atr_col] > 0)
    if valid.sum() < 3:
        return pd.Series(False, index=t.index)
    q66 = float(t.loc[valid, atr_col].quantile(2 / 3))
    return valid & (t[atr_col] >= q66)


def fill_realism_stats(trades: pd.DataFrame, k_val: float, atr_col: str = "atr20") -> dict[str, float]:
    t = trades[oos_mask(trades)].copy()
    hv = t[high_vol_tercile_mask(t, atr_col)]
    if hv.empty:
        return {"mean_fill_fraction": float("nan"), "n_high_vol": 0}
    intended = k_val / hv[atr_col].astype(float)
    intended = np.minimum(FLAT_CAP, intended)
    if "adv50_value" in hv.columns:
        adv_cap = hv["adv50_value"].fillna(0).astype(float) * FILL_ADV_PART / PORTFOLIO_VND
        estimated = np.minimum(intended, adv_cap)
    else:
        estimated = intended
    frac = estimated / np.maximum(intended, 1e-12)
    return {"mean_fill_fraction": float(np.nanmean(frac)), "n_high_vol": int(len(hv))}


def year_mar_table(eq: pd.Series, years: range) -> dict[int, float]:
    out: dict[int, float] = {}
    for y in years:
        sub = slice_equity_years(eq, y, y)
        out[y] = float(_metrics_from_equity(sub)["mar"]) if len(sub) >= 2 else float("nan")
    return out


def sector_mar_delta(
    flat_trades: pd.DataFrame,
    atr_trades: pd.DataFrame,
    sector_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    oos_flat = flat_trades[oos_mask(flat_trades)].copy()
    oos_atr = atr_trades[oos_mask(atr_trades)].copy()
    oos_flat["sector"] = oos_flat["symbol"].astype(str).map(lambda s: sector_map.get(s, "Other"))
    oos_atr["sector"] = oos_atr["symbol"].astype(str).map(lambda s: sector_map.get(s, "Other"))
    for sec in SECTOR_GROUPS:
        f = oos_flat[oos_flat["sector"] == sec]
        a = oos_atr[oos_atr["sector"] == sec]
        if len(f) < 5 or len(a) < 5:
            rows.append({"sector": sec, "flat_mar_proxy": np.nan, "atr_mar_proxy": np.nan, "delta": np.nan, "n": len(f)})
            continue
        flat_mean = float((f["net_return"] * FLAT_CAP * f.get("_size_mult", 1.0)).mean())
        atr_mean = float((a["net_return"] * a["_atr_w"]).mean())
        rows.append({"sector": sec, "flat_mar_proxy": flat_mean, "atr_mar_proxy": atr_mean, "delta": atr_mean - flat_mean, "n": len(f)})
    return rows


def evaluate_gates(
    metrics: dict[str, float],
    g3_fill: float,
    turnover_ratio: float,
    g5_ratio: float,
    flat_mar: float,
) -> dict[str, Any]:
    mar = metrics["oos_mar"]
    maxdd = metrics["oos_maxdd"]
    g1a_margin = mar - G1A_THRESHOLD if np.isfinite(mar) else float("nan")
    gates = {
        "G1a": np.isfinite(mar) and mar >= G1A_THRESHOLD,
        "G1b": np.isfinite(mar) and mar >= G1B_THRESHOLD,
        "G2": np.isfinite(maxdd) and maxdd >= G2_MAXDD_THRESHOLD,
        "G3": np.isfinite(g3_fill) and g3_fill >= G3_FILL_FLOOR,
        "G4": np.isfinite(turnover_ratio) and turnover_ratio <= G4_TURNOVER_CAP,
        "G5": np.isfinite(g5_ratio) and g5_ratio >= G5_2021_CAPTURE_FLOOR,
    }
    all_pass = all(gates.values())
    if all_pass:
        verdict = "PASS"
    elif np.isfinite(mar) and np.isfinite(flat_mar) and mar < 0 and flat_mar < 0:
        verdict = "CONDITIONAL-ADVANCE"
    elif np.isfinite(g1a_margin) and 0 <= g1a_margin < G1A_BORDERLINE:
        verdict = "CONDITIONAL-ADVANCE"
    else:
        verdict = "FAIL"
    return {"gates": gates, "g1a_margin": g1a_margin, "verdict": verdict}


def write_gates_addendum(
    k20: float,
    k10: float,
    n20: int,
    n10: int,
    baseline_pass: bool,
    baseline_mar: float,
    baseline_maxdd: float,
) -> None:
    lines = [
        "# PA-007 ATR Sizing — Gates Addendum (LOCKED)",
        "",
        "```yaml",
        "locked: true",
        f"date: {date.today()}",
        f"baseline_s1_flat_oos_mar: {S1_FLAT_OOS_MAR}",
        "baseline_s1_flat_oos_maxdd_pct: 8.17",
        f"g1a_threshold: {G1A_THRESHOLD}",
        f"g1b_threshold: {G1B_THRESHOLD}",
        "g2_maxdd_threshold_pct: 8.987",
        f"k_val_atr20: {k20:.8f}",
        f"k_val_atr10: {k10:.8f}",
        f"n_is_signal_ticker_pairs_atr20: {n20}",
        f"n_is_signal_ticker_pairs_atr10: {n10}",
        f"baseline_verification: {'PASS' if baseline_pass else 'FAIL'}",
        f"baseline_mar_observed: {baseline_mar:.4f}",
        f"baseline_maxdd_observed_pct: {baseline_maxdd * 100:.2f}",
        "```",
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ]
    GATES_ADDENDUM.parent.mkdir(parents=True, exist_ok=True)
    GATES_ADDENDUM.write_text("\n".join(lines), encoding="utf-8")


def write_reports(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arms = meta["candidates"]
    lines = [
        "# PA-007 ATR-Adjusted Position Sizing Report",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        "",
        f"**Overall verdict:** {meta['overall_verdict']}",
        "",
        "## Baseline verification (S1-flat)",
        "",
        f"- OOS MAR: **{meta['baseline_mar']:.4f}** (expected {S1_FLAT_OOS_MAR} +/- {MAR_TOLERANCE})",
        f"- OOS MaxDD: **{_fmt_pct(meta['baseline_maxdd'])}** (expected {_fmt_pct(S1_FLAT_OOS_MAXDD)} +/- 0.50%)",
        f"- Baseline flags: {', '.join(meta['baseline_flags']) or 'none'}",
        "",
        "## Locked k_val (IS-derived)",
        "",
        f"- k_val_atr20: **{meta['k_val_atr20']:.6f}** (n={meta['n_is_atr20']})",
        f"- k_val_atr10: **{meta['k_val_atr10']:.6f}** (n={meta['n_is_atr10']})",
        "",
    ]
    for key, label in [("C1_atr20", "C1_atr20"), ("C2_atr10", "C2_atr10")]:
        a = arms[key]
        g = a["gates"]
        lines.extend([
            f"## {label}",
            "",
            f"- OOS MAR: **{a['oos_mar']:.4f}** | MaxDD: **{_fmt_pct(a['oos_maxdd'])}**",
            f"- Sub-A MAR: **{a['oos_sub_a_mar']:.4f}** | Sub-B MAR: **{a['oos_sub_b_mar']:.4f}**",
            f"- G1a (>= {G1A_THRESHOLD}): **{'PASS' if g['G1a'] else 'FAIL'}** margin={a['g1a_margin']:.4f}",
            f"- G1b (>= {G1B_THRESHOLD}): **{'PASS' if g['G1b'] else 'FAIL'}**",
            f"- G2 (MaxDD >= {_fmt_pct(G2_MAXDD_THRESHOLD)}): **{'PASS' if g['G2'] else 'FAIL'}**",
            f"- G3 (fill >= {G3_FILL_FLOOR:.0%}): **{'PASS' if g['G3'] else 'FAIL'}** ({a['g3_fill']:.2%})",
            f"- G4 (turnover <= {G4_TURNOVER_CAP:.0%}): **{'PASS' if g['G4'] else 'FAIL'}** (ratio {a['turnover_ratio']:.3f})",
            f"- G5 (2021 capture >= {G5_2021_CAPTURE_FLOOR:.0%}): **{'PASS' if g['G5'] else 'FAIL'}** (ratio {a['g5_ratio']:.3f})",
            f"- **Verdict: {a['verdict']}**",
            "",
        ])
    lines.append("RESEARCH_ONLY_NOT_PRODUCTION")
    (OUT_DIR / "pa007_atrsizing_report.md").write_text("\n".join(lines), encoding="utf-8")

    attr_lines = [
        "# PA-007 Attribution Slices",
        "",
        f"**Generated:** {date.today()}",
        "",
        "## Year MAR (flat vs C1 vs C2)",
        "",
        "| Year | flat | C1_atr20 | C2_atr10 | delta_C1 | delta_C2 |",
        "|------|------|----------|----------|----------|----------|",
    ]
    ym = meta["year_mar"]
    for y in range(2019, 2027):
        f = ym["flat"].get(y, float("nan"))
        c1 = ym["C1_atr20"].get(y, float("nan"))
        c2 = ym["C2_atr10"].get(y, float("nan"))
        attr_lines.append(
            f"| {y} | {f:.4f} | {c1:.4f} | {c2:.4f} | {c1 - f:.4f} | {c2 - f:.4f} |"
        )
    attr_lines.extend(["", "## Sector attribution (mean weighted return proxy, OOS)", ""])
    attr_lines.append("| Sector | flat | C1 | delta | n |")
    attr_lines.append("|--------|------|----|-------|---|")
    for row in meta["sector_attr"]["C1_atr20"]:
        attr_lines.append(
            f"| {row['sector']} | {row['flat_mar_proxy']:.6f} | {row['atr_mar_proxy']:.6f} | "
            f"{row['delta']:.6f} | {row['n']} |"
        )
    attr_lines.extend(["", "## High-vol tercile (OOS)", ""])
    for key in ("C1_atr20", "C2_atr10"):
        hv = meta["high_vol"][key]
        attr_lines.append(
            f"- **{key}**: flat MAR-proxy={hv['flat_mar']:.4f}, ATR MAR-proxy={hv['atr_mar']:.4f}, "
            f"G3 fill={hv['g3_fill']:.2%} (n={hv['n']})"
        )
    (OUT_DIR / "pa007_atrsizing_attribution.md").write_text("\n".join(attr_lines), encoding="utf-8")

    (OUT_DIR / "pa007_atrsizing_meta.json").write_text(
        json.dumps(meta, indent=2, default=str),
        encoding="utf-8",
    )


def run_pa007() -> dict[str, Any]:
    print("PA-007 ATR sizing harness", flush=True)
    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    sector_map = stack["sector_map"]
    filter_map = build_signal_filter_map(ctx.panel)
    s1 = apply_proximity_filter(stack["base_trades"], filter_map, S1_MIN_PROX)
    s1 = _tag_adv50(s1, ctx.adv)

    # --- Step A: baseline verification ---
    sized_flat = apply_size(s1, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_flat = prepare_trades_with_size(sized_flat, "rs_score", "_size_mult")
    eq_flat, _, _ = run_capital_sim(prep_flat, ctx.gate, D4_CASH_YIELD)
    flat_n = sum(1 for p in prep_flat if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])
    flat_metrics = run_arm_metrics(eq_flat, flat_n)
    baseline_flags: list[str] = []
    if abs(flat_metrics["oos_mar"] - S1_FLAT_OOS_MAR) > MAR_TOLERANCE:
        baseline_flags.append("[BASELINE-DRIFT]")
    if abs(flat_metrics["oos_maxdd"] - S1_FLAT_OOS_MAXDD) > MAXDD_TOLERANCE:
        baseline_flags.append("[MAXDD-DRIFT]")
    if abs(flat_n - BASELINE_N_OOS) > N_TOLERANCE:
        baseline_flags.append("[N_OOS-DRIFT]")
    baseline_pass = not baseline_flags
    print(
        f"  Baseline OOS MAR={flat_metrics['oos_mar']:.4f} MaxDD={flat_metrics['oos_maxdd']:.4f} "
        f"flags={baseline_flags or 'none'}",
        flush=True,
    )
    if not baseline_pass:
        write_gates_addendum(float("nan"), float("nan"), 0, 0, False, flat_metrics["oos_mar"], flat_metrics["oos_maxdd"])
        meta = {
            "test": "PA-007 ATR sizing",
            "date": str(date.today()),
            "halted": True,
            "baseline_flags": baseline_flags,
            "baseline_mar": flat_metrics["oos_mar"],
            "baseline_maxdd": flat_metrics["oos_maxdd"],
            "overall_verdict": "PARKED",
        }
        write_reports(meta)
        return meta

    # --- Step B: IS k_val (before OOS candidate runs) ---
    atr_tbl = build_atr_table(ctx.panel, (10, 20))
    s1_atr = attach_atr(s1, atr_tbl, "atr20")
    is_mask = (pd.to_datetime(s1_atr["entry_date"]) >= IS_START) & (
        pd.to_datetime(s1_atr["entry_date"]) <= IS_END
    )
    is_trades = s1_atr[is_mask]
    k_val_20, n_is_20 = derive_k_val(is_trades, "atr20")
    k_val_10, n_is_10 = derive_k_val(is_trades, "atr10")
    print(f"  k_val_atr20={k_val_20:.6f} (n={n_is_20})", flush=True)
    print(f"  k_val_atr10={k_val_10:.6f} (n={n_is_10})", flush=True)
    write_gates_addendum(
        k_val_20, k_val_10, n_is_20, n_is_10, True, flat_metrics["oos_mar"], flat_metrics["oos_maxdd"]
    )

    flat_turnover = turnover_proxy(prep_flat)
    candidates: dict[str, dict[str, Any]] = {}

    for key, atr_col, k_val in [
        ("C1_atr20", "atr20", k_val_20),
        ("C2_atr10", "atr10", k_val_10),
    ]:
        t = apply_atr_weights(s1_atr, atr_col, k_val)
        prep = prepare_trades_absolute_weight(t, "_atr_w", "rs_score")
        n_oos = sum(1 for p in prep if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])
        eq, _, _ = run_capital_sim(prep, ctx.gate, D4_CASH_YIELD)
        metrics = run_arm_metrics(eq, n_oos)
        fill_stats = fill_realism_stats(t, k_val, atr_col)
        g3_fill = fill_stats["mean_fill_fraction"]
        tvr_ratio = turnover_proxy(prep) / flat_turnover if flat_turnover > 0 else float("nan")

        # G5: 2021 high-vol winner P&L capture
        hv_2021 = t[oos_mask(t) & high_vol_tercile_mask(t, "atr20") & (pd.to_datetime(t["entry_date"]).dt.year == 2021)]
        flat_2021_hv = sized_flat[
            oos_mask(sized_flat)
            & high_vol_tercile_mask(attach_atr(sized_flat, atr_tbl, "atr20"), "atr20")
            & (pd.to_datetime(sized_flat["entry_date"]).dt.year == 2021)
        ]
        flat_pnl = pnl_contribution(flat_2021_hv, None)
        atr_pnl = pnl_contribution(hv_2021, "_atr_w")
        g5_ratio = atr_pnl / flat_pnl if abs(flat_pnl) > 1e-12 else float("nan")

        gate_eval = evaluate_gates(metrics, g3_fill, tvr_ratio, g5_ratio, flat_metrics["oos_mar"])
        if not gate_eval["gates"]["G3"]:
            gate_eval.setdefault("flags", []).append("[G3-RISK]")

        oos_t = t[oos_mask(t)].reset_index(drop=True)
        oos_flat = sized_flat[oos_mask(sized_flat)].reset_index(drop=True)
        hv_mask = high_vol_tercile_mask(oos_t, "atr20").to_numpy()
        flat_hv = attach_atr(oos_flat, atr_tbl, "atr20")
        flat_hv_m = high_vol_tercile_mask(flat_hv, "atr20").to_numpy()

        candidates[key] = {
            **metrics,
            **gate_eval,
            "gates": gate_eval["gates"],
            "g3_fill": g3_fill,
            "turnover_ratio": tvr_ratio,
            "g5_ratio": g5_ratio,
            "equity": eq,
            "trades": t,
        }
        candidates[key]["high_vol_summary"] = {
            "flat_mar": float(oos_flat["net_return"].to_numpy()[flat_hv_m].mean()) if flat_hv_m.any() else float("nan"),
            "atr_mar": float(oos_t["net_return"].to_numpy()[hv_mask].mean()) if hv_mask.any() else float("nan"),
            "g3_fill": g3_fill,
            "n": int(hv_mask.sum()),
        }
        print(
            f"  {key} OOS MAR={metrics['oos_mar']:.4f} MaxDD={metrics['oos_maxdd']:.4f} "
            f"verdict={gate_eval['verdict']}",
            flush=True,
        )

    overall = "PASS" if any(c["verdict"] == "PASS" for c in candidates.values()) else (
        "CONDITIONAL-ADVANCE"
        if any(c["verdict"] == "CONDITIONAL-ADVANCE" for c in candidates.values())
        else "FAIL"
    )

    sector_attr = {
        "C1_atr20": sector_mar_delta(sized_flat, candidates["C1_atr20"]["trades"], sector_map),
        "C2_atr10": sector_mar_delta(sized_flat, candidates["C2_atr10"]["trades"], sector_map),
    }
    year_mar = {
        "flat": year_mar_table(eq_flat, range(2019, 2027)),
        "C1_atr20": year_mar_table(candidates["C1_atr20"]["equity"], range(2019, 2027)),
        "C2_atr10": year_mar_table(candidates["C2_atr10"]["equity"], range(2019, 2027)),
    }

    meta: dict[str, Any] = {
        "test": "PA-007 ATR sizing",
        "date": str(date.today()),
        "halted": False,
        "baseline_flags": baseline_flags,
        "baseline_mar": flat_metrics["oos_mar"],
        "baseline_maxdd": flat_metrics["oos_maxdd"],
        "k_val_atr20": k_val_20,
        "k_val_atr10": k_val_10,
        "n_is_atr20": n_is_20,
        "n_is_atr10": n_is_10,
        "flat_turnover": flat_turnover,
        "overall_verdict": overall,
        "candidates": {
            k: {kk: vv for kk, vv in v.items() if kk not in ("equity", "trades")}
            for k, v in candidates.items()
        },
        "year_mar": year_mar,
        "sector_attr": sector_attr,
        "high_vol": {k: v["high_vol_summary"] for k, v in candidates.items()},
    }
    write_reports(meta)
    print(f"  OVERALL: {overall}", flush=True)
    return meta


def main() -> None:
    run_pa007()


if __name__ == "__main__":
    main()
