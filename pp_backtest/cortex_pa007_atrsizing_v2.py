#!/usr/bin/env python3
"""
PA-007 v2 — ATR sizing overlay on A3_RS+S2@1.4× base.

Pre-registration: knowledge/backtests/2026-07-08_pa007_atrsizing_s2base_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    python pp_backtest/cortex_pa007_atrsizing_v2.py
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

from pp_backtest.cortex_book1_common import OOS_WINDOW, _fmt_pct
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_volume_filter,
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

OUT_DIR = REPO / "data" / "research" / "cortex_pa007_s2base"
PREREG = "knowledge/backtests/2026-07-08_pa007_atrsizing_s2base_prereg.md"

S2_MULT = 1.4
FLAT_CAP = 1.0 / MAX_POSITIONS
MEDIAN_FLAT = 0.05

# Locked baseline (A3_RS+S2@1.4× OOS 2020-2026)
BASELINE_OOS_MAR = 2.5233
BASELINE_OOS_MAXDD = -0.0557
BASELINE_OOS_CAGR = 0.1405
REPRO_TOL = 0.050
MAXDD_TOL = 0.005

# Sizing-class gates (pre-reg locked)
G1A_THRESHOLD = BASELINE_OOS_MAR * 0.90  # 2.2710
G1B_MAXDD_THRESHOLD = BASELINE_OOS_MAXDD * 1.05  # -0.0585
G2_FILL_FLOOR = 0.80
G3_TURNOVER_CAP = 1.20
G5_2021_CAPTURE_FLOOR = 0.85
G1A_BORDERLINE = 0.020
FILL_ADV_PART = 0.07
ATR_UNDERSIZE_PCT = 0.20


def build_atr_table(panel: pd.DataFrame, windows: tuple[int, ...]) -> pd.DataFrame:
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
    return out.merge(
        atr_tbl.rename(columns={"date": "entry_date"}),
        on=["symbol", "entry_date"],
        how="left",
    )


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
    return out.dropna(subset=["_atr_w"])


def oos_mask(df: pd.DataFrame) -> pd.Series:
    ed = pd.to_datetime(df["entry_date"])
    return (ed.dt.year >= OOS_WINDOW[0]) & (ed.dt.year <= OOS_WINDOW[1])


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


def turnover_proxy(prep: list[PreparedTrade]) -> float:
    return sum(p.target_w for p in prep if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])


def pnl_contribution(trades: pd.DataFrame, weight_col: str | None) -> float:
    t = trades.copy()
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
    valid = np.isfinite(trades[atr_col]) & (trades[atr_col] > 0)
    if valid.sum() < 3:
        return pd.Series(False, index=trades.index)
    q66 = float(trades.loc[valid, atr_col].quantile(2 / 3))
    return valid & (trades[atr_col] >= q66)


def fill_realism_stats(trades: pd.DataFrame, k_val: float, atr_col: str) -> dict[str, float]:
    t = trades[oos_mask(trades)].copy()
    hv = t[high_vol_tercile_mask(t, atr_col)]
    if hv.empty:
        return {"mean_fill_fraction": float("nan"), "n_high_vol": 0}
    intended = np.minimum(FLAT_CAP, k_val / hv[atr_col].astype(float))
    if "adv50_value" in hv.columns:
        adv_cap = hv["adv50_value"].fillna(0).astype(float) * FILL_ADV_PART / PORTFOLIO_VND
        estimated = np.minimum(intended, adv_cap)
    else:
        estimated = intended
    frac = estimated / np.maximum(intended, 1e-12)
    return {"mean_fill_fraction": float(np.nanmean(frac)), "n_high_vol": int(len(hv))}


def atr_distribution_check(
    full_trades: pd.DataFrame,
    s2_trades: pd.DataFrame,
    atr_tbl: pd.DataFrame,
    atr_col: str = "atr10",
) -> dict[str, Any]:
    full_a = attach_atr(full_trades, atr_tbl, atr_col)
    s2_a = attach_atr(s2_trades, atr_tbl, atr_col)
    full_vals = full_a[atr_col].replace([np.inf, -np.inf], np.nan).dropna()
    s2_vals = s2_a[atr_col].replace([np.inf, -np.inf], np.nan).dropna()

    def _stats(s: pd.Series) -> dict[str, float]:
        if s.empty:
            return {"mean": float("nan"), "median": float("nan"), "p75": float("nan"), "n": 0}
        return {
            "mean": float(s.mean()),
            "median": float(s.median()),
            "p75": float(s.quantile(0.75)),
            "n": int(len(s)),
        }

    full_stats = _stats(full_vals)
    s2_stats = _stats(s2_vals)
    mean_ratio = s2_stats["mean"] / full_stats["mean"] if full_stats["mean"] > 0 else float("nan")
    undersize_risk = bool(np.isfinite(mean_ratio) and mean_ratio > 1.0 + ATR_UNDERSIZE_PCT)
    return {
        "atr_col": atr_col,
        "full_a3_rs": full_stats,
        "s2_surviving": s2_stats,
        "mean_ratio_s2_over_full": mean_ratio,
        "atr_undersizing_risk": undersize_risk,
        "flag": "[ATR-UNDERSIZING-RISK]" if undersize_risk else None,
    }


def evaluate_gates(
    metrics: dict[str, float],
    g2_fill: float,
    turnover_ratio: float,
    g5_ratio: float,
    flat_mar: float,
) -> dict[str, Any]:
    mar = metrics["oos_mar"]
    maxdd = metrics["oos_maxdd"]
    cagr = metrics["oos_cagr"]
    g1a_margin = mar - G1A_THRESHOLD if np.isfinite(mar) else float("nan")
    gates = {
        "G1a": np.isfinite(mar) and mar >= G1A_THRESHOLD,
        "G1b": np.isfinite(maxdd) and maxdd >= G1B_MAXDD_THRESHOLD,
        "G1c": np.isfinite(cagr) and cagr > 0.0,
        "G1d_a": np.isfinite(metrics["oos_sub_a_mar"]) and metrics["oos_sub_a_mar"] > 0.0,
        "G1d_b": np.isfinite(metrics["oos_sub_b_mar"]) and metrics["oos_sub_b_mar"] > 0.0,
        "G2_fill": np.isfinite(g2_fill) and g2_fill >= G2_FILL_FLOOR,
        "G3_turnover": np.isfinite(turnover_ratio) and turnover_ratio <= G3_TURNOVER_CAP,
        "G5_2021": np.isfinite(g5_ratio) and g5_ratio >= G5_2021_CAPTURE_FLOOR,
    }
    core = [gates["G1a"], gates["G1b"], gates["G1c"], gates["G1d_a"], gates["G1d_b"]]
    all_pass = all(core) and gates["G2_fill"] and gates["G3_turnover"] and gates["G5_2021"]
    if all_pass:
        verdict = "PASS"
    elif np.isfinite(mar) and mar < 0:
        verdict = "PARKED"
    elif np.isfinite(g1a_margin) and 0 <= g1a_margin < G1A_BORDERLINE:
        verdict = "CONDITIONAL-ADVANCE"
    elif np.isfinite(mar) and np.isfinite(flat_mar) and mar < 0 and flat_mar < 0:
        verdict = "CONDITIONAL-ADVANCE"
    else:
        verdict = "FAIL"
    return {"gates": gates, "g1a_margin": g1a_margin, "verdict": verdict}


def year_mar_table(eq: pd.Series, years: range) -> dict[int, float]:
    out: dict[int, float] = {}
    for y in years:
        sub = slice_equity_years(eq, y, y)
        out[y] = float(_metrics_from_equity(sub)["mar"]) if len(sub) >= 2 else float("nan")
    return out


def write_reports(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PA-007 v2 — ATR Sizing on A3_RS+S2@1.4×",
        "",
        f"**Generated:** {date.today()}",
        f"**Pre-reg:** `{PREREG}`",
        f"**Overall verdict:** {meta['overall_verdict']}",
        "",
        "## Baseline (A3_RS+S2@1.4× flat cap)",
        "",
        f"- OOS MAR: **{meta['baseline_mar']:.4f}** (locked {BASELINE_OOS_MAR})",
        f"- OOS MaxDD: **{_fmt_pct(meta['baseline_maxdd'])}** (locked {_fmt_pct(BASELINE_OOS_MAXDD)})",
        f"- N_OOS: **{meta['n_oos_baseline']}**",
        f"- Flags: {', '.join(meta.get('baseline_flags', [])) or 'none'}",
        "",
        "## ATR distribution check (council-mandated)",
        "",
    ]
    ad = meta["atr_distribution"]
    lines.extend([
        f"- Full A3_RS atr10 mean: **{ad['full_a3_rs']['mean']:.6f}** (n={ad['full_a3_rs']['n']})",
        f"- S2-surviving atr10 mean: **{ad['s2_surviving']['mean']:.6f}** (n={ad['s2_surviving']['n']})",
        f"- Ratio S2/full: **{ad['mean_ratio_s2_over_full']:.3f}**",
        f"- Flag: **{ad.get('flag') or 'none'}**",
        "",
        "## k calibration (S2-filtered IS only)",
        "",
        f"- k_atr20: **{meta['k_val_atr20']:.8f}** (n={meta['n_is_atr20']})",
        f"- k_atr10: **{meta['k_val_atr10']:.8f}** (n={meta['n_is_atr10']})",
        "",
    ])
    for key in ("C1_atr20_s2", "C2_atr10_s2"):
        a = meta["candidates"][key]
        g = a["gates"]
        lines.extend([
            f"## {key}",
            "",
            f"- OOS MAR: **{a['oos_mar']:.4f}** | MaxDD: **{_fmt_pct(a['oos_maxdd'])}**",
            f"- sub-A: **{a['oos_sub_a_mar']:.4f}** | sub-B: **{a['oos_sub_b_mar']:.4f}**",
            f"- G1a (>={G1A_THRESHOLD:.4f}): **{'PASS' if g['G1a'] else 'FAIL'}**",
            f"- G1b (>={G1B_MAXDD_THRESHOLD:.4f}): **{'PASS' if g['G1b'] else 'FAIL'}**",
            f"- G2 fill (>={G2_FILL_FLOOR:.0%}): **{'PASS' if g['G2_fill'] else 'FAIL'}** ({a['g2_fill']:.2%})",
            f"- G3 turnover (<={G3_TURNOVER_CAP:.0%}): **{'PASS' if g['G3_turnover'] else 'FAIL'}** ({a['turnover_ratio']:.3f})",
            f"- G5 2021 (>={G5_2021_CAPTURE_FLOOR:.0%}): **{'PASS' if g['G5_2021'] else 'FAIL'}** ({a['g5_ratio']:.3f})",
            f"- **Verdict: {a['verdict']}**",
            "",
        ])
    lines.append("RESEARCH_ONLY_NOT_PRODUCTION")
    (OUT_DIR / "pa007_atrsizing_v2_report.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT_DIR / "pa007_atrsizing_v2_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )


def run_pa007_v2() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("PA-007 v2 ATR sizing — A3_RS+S2@1.4x base", flush=True)

    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]
    filter_map = build_signal_filter_map(ctx.panel)
    s2_trades = apply_volume_filter(base_trades, filter_map, S2_MULT)
    s2_trades = _tag_adv50(s2_trades, ctx.adv)

    atr_tbl = build_atr_table(ctx.panel, (10, 20))
    atr_dist = atr_distribution_check(base_trades, s2_trades, atr_tbl, "atr10")
    print(f"  ATR dist S2/full ratio={atr_dist['mean_ratio_s2_over_full']:.3f} flag={atr_dist.get('flag')}", flush=True)

    sized_flat = apply_size(s2_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep_flat = prepare_trades_with_size(sized_flat, "rs_score", "_size_mult")
    eq_flat, _, _ = run_capital_sim(prep_flat, ctx.gate, D4_CASH_YIELD)
    flat_n = count_oos_trades(sized_flat, OOS_WINDOW[0], OOS_WINDOW[1])
    flat_metrics = run_arm_metrics(eq_flat, flat_n)

    baseline_flags: list[str] = []
    if abs(flat_metrics["oos_mar"] - BASELINE_OOS_MAR) > REPRO_TOL:
        baseline_flags.append("[BASELINE-DRIFT]")
    if abs(flat_metrics["oos_maxdd"] - BASELINE_OOS_MAXDD) > MAXDD_TOL:
        baseline_flags.append("[MAXDD-DRIFT]")

    baseline_config = {
        "baseline_configuration": "A3_RS+S2@1.4x",
        "baseline_oos_mar": flat_metrics["oos_mar"],
        "baseline_oos_maxdd": flat_metrics["oos_maxdd"],
        "baseline_oos_cagr": flat_metrics["oos_cagr"],
        "baseline_sub_a_mar": flat_metrics["oos_sub_a_mar"],
        "baseline_sub_b_mar": flat_metrics["oos_sub_b_mar"],
        "locked_mar": BASELINE_OOS_MAR,
        "locked_maxdd": BASELINE_OOS_MAXDD,
        "n_oos_trades": flat_n,
        "measured_date": str(date.today()),
        "baseline_flags": baseline_flags,
    }
    (OUT_DIR / "baseline_config.json").write_text(json.dumps(baseline_config, indent=2), encoding="utf-8")

    print(
        f"  Baseline MAR={flat_metrics['oos_mar']:.4f} MaxDD={flat_metrics['oos_maxdd']:.4f} "
        f"N_OOS={flat_n} flags={baseline_flags or 'none'}",
        flush=True,
    )
    if baseline_flags:
        meta = {
            "halted": True,
            "baseline_flags": baseline_flags,
            "baseline_mar": flat_metrics["oos_mar"],
            "overall_verdict": "PARKED",
            "atr_distribution": atr_dist,
        }
        write_reports(meta)
        return meta

    s2_atr = attach_atr(s2_trades, atr_tbl, "atr20")
    is_mask = (pd.to_datetime(s2_atr["entry_date"]) >= IS_START) & (
        pd.to_datetime(s2_atr["entry_date"]) <= IS_END
    )
    is_trades = s2_atr[is_mask]
    k_val_20, n_is_20 = derive_k_val(is_trades, "atr20")
    k_val_10, n_is_10 = derive_k_val(is_trades, "atr10")
    print(f"  k_atr20={k_val_20:.8f} (S2 IS n={n_is_20})", flush=True)
    print(f"  k_atr10={k_val_10:.8f} (S2 IS n={n_is_10})", flush=True)

    flat_turnover = turnover_proxy(prep_flat)
    candidates: dict[str, dict[str, Any]] = {}
    equities: dict[str, pd.Series] = {"flat": eq_flat}

    for key, atr_col, k_val in [
        ("C1_atr20_s2", "atr20", k_val_20),
        ("C2_atr10_s2", "atr10", k_val_10),
    ]:
        t = apply_atr_weights(s2_atr, atr_col, k_val)
        prep = prepare_trades_absolute_weight(t, "_atr_w", "rs_score")
        n_oos = sum(1 for p in prep if OOS_WINDOW[0] <= p.entry_year <= OOS_WINDOW[1])
        eq, _, _ = run_capital_sim(prep, ctx.gate, D4_CASH_YIELD)
        metrics = run_arm_metrics(eq, n_oos)
        fill_stats = fill_realism_stats(t, k_val, atr_col)
        g2_fill = fill_stats["mean_fill_fraction"]
        tvr_ratio = turnover_proxy(prep) / flat_turnover if flat_turnover > 0 else float("nan")

        hv_2021 = t[
            oos_mask(t)
            & high_vol_tercile_mask(t, "atr20")
            & (pd.to_datetime(t["entry_date"]).dt.year == 2021)
        ]
        flat_2021_hv = sized_flat[
            oos_mask(sized_flat)
            & high_vol_tercile_mask(attach_atr(sized_flat, atr_tbl, "atr20"), "atr20")
            & (pd.to_datetime(sized_flat["entry_date"]).dt.year == 2021)
        ]
        flat_pnl = pnl_contribution(flat_2021_hv, None)
        atr_pnl = pnl_contribution(hv_2021, "_atr_w")
        g5_ratio = atr_pnl / flat_pnl if abs(flat_pnl) > 1e-12 else float("nan")

        gate_eval = evaluate_gates(metrics, g2_fill, tvr_ratio, g5_ratio, flat_metrics["oos_mar"])
        candidates[key] = {
            **metrics,
            **gate_eval,
            "k_val": k_val,
            "g2_fill": g2_fill,
            "turnover_ratio": tvr_ratio,
            "g5_ratio": g5_ratio,
        }
        equities[key] = eq
        print(
            f"  {key} MAR={metrics['oos_mar']:.4f} MaxDD={metrics['oos_maxdd']:.4f} "
            f"verdict={gate_eval['verdict']}",
            flush=True,
        )

    overall = "PASS" if any(c["verdict"] == "PASS" for c in candidates.values()) else (
        "CONDITIONAL-ADVANCE"
        if any(c["verdict"] == "CONDITIONAL-ADVANCE" for c in candidates.values())
        else "FAIL"
    )

    year_mar = {k: year_mar_table(eq, range(2020, 2027)) for k, eq in equities.items()}

    meta: dict[str, Any] = {
        "test": "PA-007 v2 ATR sizing S2 base",
        "date": str(date.today()),
        "halted": False,
        "baseline_flags": baseline_flags,
        "baseline_mar": flat_metrics["oos_mar"],
        "baseline_maxdd": flat_metrics["oos_maxdd"],
        "n_oos_baseline": flat_n,
        "k_val_atr20": k_val_20,
        "k_val_atr10": k_val_10,
        "n_is_atr20": n_is_20,
        "n_is_atr10": n_is_10,
        "atr_distribution": atr_dist,
        "flat_turnover": flat_turnover,
        "overall_verdict": overall,
        "candidates": candidates,
        "year_mar": year_mar,
        "gates_locked": {
            "G1a": G1A_THRESHOLD,
            "G1b_maxdd": G1B_MAXDD_THRESHOLD,
            "G2_fill": G2_FILL_FLOOR,
            "G3_turnover": G3_TURNOVER_CAP,
            "G5_2021": G5_2021_CAPTURE_FLOOR,
        },
    }
    write_reports(meta)
    print(f"  OVERALL: {overall}", flush=True)
    return meta


def main() -> None:
    run_pa007_v2()


if __name__ == "__main__":
    main()
