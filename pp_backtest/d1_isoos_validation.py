#!/usr/bin/env python3
"""
D1 IS/OOS validation + A3+D1 combined portfolio test.

Replicates p3_rs_isoos_validation.py window structure for D1 standalone,
then tests complementary (D1 when A3 gate OFF) and unconstrained blends.

RESEARCH_ONLY_NOT_PRODUCTION

Usage:
  python pp_backtest/d1_isoos_validation.py
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.p0_realism_p1_winner import _build_honest_cache, _simulate_honest_trades
from pp_backtest.p3_rs_cashyield import _compute_rs_scores, _build_equity_with_cash_yield
from pp_backtest.p3_rs_isoos_validation import (
    WINDOWS,
    _filter_trades_by_entry_year,
    _filter_trades_excluding_years,
)
from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    YEAR_COLS,
    binary_gate_ema20_100,
)
from pp_backtest.portfolio_optimization_phase1 import load_panel, load_vnindex
from pp_backtest.portfolio_optimization_phase31 import (
    _annual_return,
    _build_adv50_map,
    _tag_adv50,
)
from pp_backtest.sleeve_harness import build_ohlcv_cache, mean_cash_fraction
from pp_backtest.sleeve_d1_capitulation import (
    CAPACITY_SIZES,
    apply_d1_p0_reprice,
    apply_slot_rationing,
    compute_ex_best_year_mar,
    evaluate_d1_trades,
    filter_events_by_cb,
    scan_raw_events_fast,
    _build_daily_floor_fraction,
    _events_to_ideal_trades,
    _precompute_symbol_floors,
)

RESEARCH_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"
OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_d1"
A3_ANN_PATH = REPO / "data" / "research" / "portfolio_optimization" / "p3_rs_cashyield" / "p3_annual_returns.csv"

D1_N_LEVELS = (2, 3)
D1_SLIPPAGES = (
    (0.005, "display_optimistic"),
    (0.010, "decision_band"),
    (0.015, "decision_band"),
)
D1_CB = 0.15
D1_EXIT = "D"
COMBINED_D1_SLIPPAGE = 0.010
ALLOC_SPLITS = ((0.70, 0.30), (0.80, 0.20), (0.60, 0.40))
FOCUS_YEARS = (2020, 2022, 2026)
MIN_IS_TRADES_N3 = 30


@dataclass
class D1Context:
    panel: pd.DataFrame
    cache: dict
    adv: dict
    floor_locked: dict
    daily_frac: dict
    global_last: pd.Timestamp
    gate: pd.Series


def load_d1_context() -> D1Context:
    from pp_backtest.portfolio_optimization_phase1 import STRATEGY_CONFIGS, get_universe

    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)].copy()
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)
    universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
    cache = build_ohlcv_cache(panel, universe)
    floor_locked = _precompute_symbol_floors(cache)
    daily_frac = _build_daily_floor_fraction(cache, universe)
    global_last = pd.Timestamp(panel["date"].max()).normalize()
    return D1Context(panel, cache, adv, floor_locked, daily_frac, global_last, gate)


def build_d1_honest_trades(
    ctx: D1Context,
    *,
    n_floor: int,
    entry_slippage: float,
) -> pd.DataFrame:
    raw = filter_events_by_cb(
        scan_raw_events_fast(ctx.cache, ctx.adv, ctx.floor_locked, n_floor),
        ctx.daily_frac,
        D1_CB,
    )
    rationed = apply_slot_rationing(raw, MAX_POSITIONS)
    ideal = _events_to_ideal_trades(rationed, ctx.cache, D1_EXIT)
    return apply_d1_p0_reprice(
        ideal,
        ctx.cache,
        ctx.adv,
        entry_slippage=entry_slippage,
        global_last=ctx.global_last,
    )


def _subset_for_window(trades: pd.DataFrame, window_name: str, year_range: tuple[int, int] | None) -> pd.DataFrame:
    if window_name == "ex_2021":
        return _filter_trades_excluding_years(trades, [2021])
    if window_name == "ex_2021_2022":
        return _filter_trades_excluding_years(trades, [2021, 2022])
    if year_range is not None:
        return _filter_trades_by_entry_year(trades, year_range[0], year_range[1])
    return trades.iloc[0:0]


def _run_d1_window(trades: pd.DataFrame, adv: dict, label: str) -> dict[str, Any]:
    m = evaluate_d1_trades(trades, adv)
    eq = m.pop("equity", pd.Series(dtype=float))
    return {
        "window": label,
        "mar": float(m.get("mar_full", np.nan)),
        "cagr": float(m.get("cagr", np.nan)),
        "max_dd": float(m.get("max_dd", np.nan)),
        "n_trades": int(m.get("n_trades", len(trades))),
        "win_rate": float(m.get("win_rate", np.nan)),
        "equity": eq,
    }


def _d1_confirmation_checks(results: pd.DataFrame) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    for check_name, window_key in [
        ("IS MAR > 0", "IS_2013_2019"),
        ("OOS MAR > 0", "OOS_2020_2026"),
        ("Ex-2021 MAR > 0", "ex_2021"),
        ("Ex-2021/2022 MAR > 0", "ex_2021_2022"),
    ]:
        sub = results[results["window"] == window_key]
        if sub.empty:
            checks.append((check_name, False, "missing window"))
            continue
        mar = float(sub.iloc[0]["mar"])
        ok = np.isfinite(mar) and mar > 0
        checks.append((check_name, ok, f"{mar:.4f}"))
    return checks


def run_d1_isoos(ctx: D1Context) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict] = []
    combo_checks: dict[str, Any] = {}

    for n_floor in D1_N_LEVELS:
        for slip, slip_label in D1_SLIPPAGES:
            print(f"  D1 trades N={n_floor} slip={slip:.1%}...", flush=True)
            trades = build_d1_honest_trades(ctx, n_floor=n_floor, entry_slippage=slip)
            window_results: list[dict] = []

            for window_name, year_range in WINDOWS.items():
                subset = _subset_for_window(trades, window_name, year_range)
                if subset.empty or len(subset) < 5:
                    print(f"    skip {window_name}: n={len(subset)}")
                    continue
                wr = _run_d1_window(subset, ctx.adv, window_name)
                wr.pop("equity", None)
                wr.update(
                    {
                        "n_floor": n_floor,
                        "entry_slippage": slip,
                        "slippage_label": slip_label,
                        "research_label": RESEARCH_LABEL,
                    }
                )
                window_results.append(wr)
                rows.append(wr)

            wr_df = pd.DataFrame(window_results)
            checks = _d1_confirmation_checks(wr_df)
            key = f"N{n_floor}_slip{slip:.3f}"
            combo_checks[key] = {
                "checks": {c[0]: {"pass": c[1], "detail": c[2]} for c in checks},
                "all_pass": all(c[1] for c in checks),
                "slippage_label": slip_label,
            }
            is_n = wr_df[wr_df["window"] == "IS_2013_2019"]
            if n_floor == 3 and not is_n.empty and int(is_n.iloc[0]["n_trades"]) < MIN_IS_TRADES_N3:
                combo_checks[key]["underpowered_is"] = True

    df = pd.DataFrame(rows)
    n_combos = len(combo_checks)
    n_pass = sum(1 for v in combo_checks.values() if v["all_pass"])
    decision_combos = [k for k, v in combo_checks.items() if v["slippage_label"] == "decision_band"]
    decision_pass = sum(1 for k in decision_combos if combo_checks[k]["all_pass"])

    if n_pass == n_combos:
        verdict = "CONFIRMED"
    elif decision_pass >= len(decision_combos):
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    meta = {
        "generated": str(date.today()),
        "research_label": RESEARCH_LABEL,
        "verdict": verdict,
        "combos_passing": n_pass,
        "combos_total": n_combos,
        "decision_band_pass": decision_pass,
        "decision_band_total": len(decision_combos),
        "combo_checks": combo_checks,
    }
    return df, meta


def build_a3_honest_trades(ctx: D1Context) -> pd.DataFrame:
    honest_cache = _build_honest_cache(ctx.panel)
    honest = _simulate_honest_trades(honest_cache, ctx.gate, ctx.adv)
    rs_scores = _compute_rs_scores(ctx.panel, honest)
    honest["rs_score"] = rs_scores
    return _tag_adv50(honest.copy(), ctx.adv)


def build_equity_a3(trades: pd.DataFrame, portfolio_vnd: float = PORTFOLIO_VND) -> pd.Series:
    t = trades.drop(columns=["ema_dist_at_entry"], errors="ignore")
    eq, _ = _build_equity_with_cash_yield(
        t,
        MAX_POSITIONS,
        portfolio_vnd,
        ADV_PARTICIPATION,
        GK_MULT,
        rank_col="rs_score",
        cash_yield_annual=0.0,
    )
    return eq


def build_equity_d1_from_eval(trades: pd.DataFrame, adv: dict, portfolio_vnd: float = PORTFOLIO_VND) -> pd.Series:
    return evaluate_d1_trades(trades, adv, portfolio_vnd=portfolio_vnd).get("equity", pd.Series(dtype=float))


def _normalize_equity(eq: pd.Series) -> pd.Series:
    if eq.empty:
        return eq
    eq = eq.sort_index()
    base = float(eq.iloc[0])
    return eq / base if base > 0 else eq


def merge_complementary(eq_a3: pd.Series, eq_d1: pd.Series, gate: pd.Series) -> pd.Series:
    idx = eq_a3.index.union(eq_d1.index).sort_values()
    a3 = _normalize_equity(eq_a3.reindex(idx).ffill().bfill())
    d1 = _normalize_equity(eq_d1.reindex(idx).ffill().bfill())
    g = gate.reindex(idx).ffill().fillna(False).astype(bool)
    ret_a3 = a3.pct_change().fillna(0.0)
    ret_d1 = d1.pct_change().fillna(0.0)
    blended = np.where(g.values, ret_a3.values, ret_d1.values)
    return pd.Series((1.0 + pd.Series(blended, index=idx)).cumprod(), index=idx)


def merge_unconstrained(eq_a3: pd.Series, eq_d1: pd.Series, w_a3: float, w_d1: float) -> pd.Series:
    idx = eq_a3.index.union(eq_d1.index).sort_values()
    a3 = _normalize_equity(eq_a3.reindex(idx).ffill().bfill())
    d1 = _normalize_equity(eq_d1.reindex(idx).ffill().bfill())
    ret = w_a3 * a3.pct_change().fillna(0.0) + w_d1 * d1.pct_change().fillna(0.0)
    return pd.Series((1.0 + ret).cumprod(), index=idx)


def equity_metrics(eq: pd.Series, trades_for_cash: pd.DataFrame | None, adv: dict, gate: pd.Series | None = None) -> dict[str, Any]:
    m = portfolio_metrics(eq, pd.DataFrame()) if not eq.empty else {}
    annual = eq.groupby(eq.index.year).last().pct_change().dropna() if not eq.empty else pd.Series(dtype=float)
    row: dict[str, Any] = {
        "mar": float(m.get("mar", np.nan)),
        "cagr": float(m.get("cagr", np.nan)),
        "max_dd": float(m.get("max_dd", np.nan)),
        "worst_year_return": float(annual.min()) if not annual.empty else np.nan,
        "ex_best_year_mar": compute_ex_best_year_mar(eq),
        "mean_cash_fraction": np.nan,
    }
    for y in FOCUS_YEARS:
        row[f"ret_{y}"] = _annual_return(eq, y) if not eq.empty else np.nan
    for size in CAPACITY_SIZES:
        row[f"mar_{int(size / 1e9)}b"] = np.nan
    if trades_for_cash is not None and not trades_for_cash.empty:
        row["mean_cash_fraction"] = float(mean_cash_fraction(trades_for_cash, adv))
    if gate is not None and not eq.empty:
        g = gate.reindex(eq.index).ffill().fillna(False)
        row["gate_on_fraction"] = float(g.mean())
    return row


def validate_a3_annual(eq_a3: pd.Series) -> dict[str, Any]:
    recomputed = {y: _annual_return(eq_a3, y) for y in YEAR_COLS if y <= 2026}
    ref = pd.read_csv(A3_ANN_PATH)
    ref = ref.set_index("year")["rs_ranked"].to_dict()
    diffs = {}
    for y, v in recomputed.items():
        if y in ref and np.isfinite(v) and np.isfinite(ref[y]):
            diffs[y] = abs(v - ref[y])
    max_diff = max(diffs.values()) if diffs else np.nan
    return {"max_abs_diff_vs_p3_annual": max_diff, "match_ok": max_diff < 0.02 if np.isfinite(max_diff) else False}


def run_combined_portfolio(ctx: D1Context, a3_trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    print("Building combined portfolio at 1.0% D1 slippage...", flush=True)
    d1_trades = build_d1_honest_trades(ctx, n_floor=2, entry_slippage=COMBINED_D1_SLIPPAGE)

    eq_a3 = build_equity_a3(a3_trades)
    eq_d1 = build_equity_d1_from_eval(d1_trades, ctx.adv)
    eq_comp = merge_complementary(eq_a3, eq_d1, ctx.gate)

    variants: dict[str, dict[str, Any]] = {}
    variants["A3_alone"] = {
        "equity": eq_a3,
        "trades": a3_trades,
        "gate": ctx.gate,
        **equity_metrics(eq_a3, a3_trades, ctx.adv, ctx.gate),
    }
    variants["D1_alone"] = {
        "equity": eq_d1,
        "trades": d1_trades,
        **equity_metrics(eq_d1, d1_trades, ctx.adv),
    }
    variants["A3_D1_complementary"] = {
        "equity": eq_comp,
        "trades": None,
        **equity_metrics(eq_comp, None, ctx.adv, ctx.gate),
    }
    gate_on = float(ctx.gate.reindex(eq_comp.index).ffill().mean())
    cf_a3 = mean_cash_fraction(a3_trades, ctx.adv)
    cf_d1 = mean_cash_fraction(d1_trades, ctx.adv)
    variants["A3_D1_complementary"]["mean_cash_fraction"] = gate_on * cf_a3 + (1.0 - gate_on) * cf_d1

    for w_a3, w_d1 in ALLOC_SPLITS:
        label = f"A3_D1_unconstrained_{int(w_a3*100)}_{int(w_d1*100)}"
        eq_blend = merge_unconstrained(eq_a3, eq_d1, w_a3, w_d1)
        variants[label] = {
            "equity": eq_blend,
            "trades": None,
            **equity_metrics(eq_blend, None, ctx.adv),
            "weight_a3": w_a3,
            "weight_d1": w_d1,
            "mean_cash_fraction": w_a3 * cf_a3 + w_d1 * cf_d1,
        }

    for size in CAPACITY_SIZES:
        eq_a3_s = build_equity_a3(a3_trades, portfolio_vnd=size)
        eq_d1_s = build_equity_d1_from_eval(d1_trades, ctx.adv, portfolio_vnd=size)
        eq_c_s = merge_complementary(eq_a3_s, eq_d1_s, ctx.gate)
        tag = f"mar_{int(size / 1e9)}b"
        variants["A3_D1_complementary"][tag] = float(
            portfolio_metrics(eq_c_s, pd.DataFrame()).get("mar", np.nan)
        )

    summary_rows = []
    annual_rows = []
    for name, v in variants.items():
        summary_rows.append({"variant": name, **{k: val for k, val in v.items() if k not in ("equity", "trades", "gate")}})
        if not v["equity"].empty:
            for y in YEAR_COLS:
                r = _annual_return(v["equity"], y)
                if np.isfinite(r):
                    annual_rows.append({"variant": name, "year": y, "annual_return": r})

    summary_df = pd.DataFrame(summary_rows)
    annual_df = pd.DataFrame(annual_rows)

    a3_mar = float(variants["A3_alone"]["mar"])
    comp_mar = float(variants["A3_D1_complementary"]["mar"])
    best_variant = "A3_D1_complementary" if comp_mar > a3_mar else "A3_alone"
    beats_a3 = comp_mar > a3_mar

    meta = {
        "generated": str(date.today()),
        "research_label": RESEARCH_LABEL,
        "d1_slippage_combined": COMBINED_D1_SLIPPAGE,
        "a3_annual_validation": validate_a3_annual(eq_a3),
        "best_variant_by_mar": best_variant,
        "complementary_beats_a3_mar": beats_a3,
        "a3_mar": a3_mar,
        "complementary_mar": comp_mar,
        "complementary_cash_fraction": variants["A3_D1_complementary"]["mean_cash_fraction"],
        "a3_cash_fraction": cf_a3,
    }
    return summary_df, annual_df, meta


def _write_isoos_report(df: pd.DataFrame, meta: dict[str, Any]) -> str:
    lines = [
        "# D1 IS/OOS Validation",
        "",
        f"**Label:** {RESEARCH_LABEL}",
        f"**Verdict:** {meta['verdict']} ({meta['combos_passing']}/{meta['combos_total']} combos all-check pass; "
        f"decision-band {meta['decision_band_pass']}/{meta['decision_band_total']})",
        "",
        "## Confirmation checks (IS/OOS/ex-2021/ex-2021+2022 MAR > 0)",
        "",
    ]
    for key, val in meta["combo_checks"].items():
        flag = " [underpowered IS]" if val.get("underpowered_is") else ""
        slip_note = " (display-only optimistic)" if val["slippage_label"] == "display_optimistic" else " (decision band)"
        lines.append(f"### {key}{slip_note}{flag}")
        for ck, cv in val["checks"].items():
            lines.append(f"- {ck}: {'PASS' if cv['pass'] else 'FAIL'} ({cv['detail']})")
        lines.append("")
    lines.extend(["## Window results", ""])
    if not df.empty:
        lines.append(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    lines.extend(
        [
            "",
            "## Interpretation",
            "- 0.5% entry slippage is display-only optimistic; verdicts reference 1.0% and 1.5% decision bands.",
            "- D1 checks replace RS vs FIFO with positive MAR across IS/OOS and ex-bull-year windows.",
            "- N=3 IS window with <30 trades should be treated as underpowered.",
        ]
    )
    return "\n".join(lines)


def _write_combined_report(summary: pd.DataFrame, meta: dict[str, Any]) -> str:
    a3v = meta["a3_annual_validation"]
    lines = [
        "# D1 + A3 Combined Portfolio",
        "",
        f"**Label:** {RESEARCH_LABEL}",
        f"**D1 slippage (combined test):** {meta['d1_slippage_combined']:.1%}",
        f"**A3 annual recompute vs p3_annual_returns.csv:** {'OK' if a3v['match_ok'] else 'CHECK'} "
        f"(max abs diff {a3v.get('max_abs_diff_vs_p3_annual', 'n/a')})",
        "",
        f"**Complementary beats A3 MAR alone:** {meta['complementary_beats_a3_mar']} "
        f"(A3={meta['a3_mar']:.4f}, complementary={meta['complementary_mar']:.4f})",
        "",
        "## Variant summary",
        "",
    ]
    cols = ["variant", "mar", "cagr", "max_dd", "worst_year_return", "ex_best_year_mar", "mean_cash_fraction"]
    cols += [f"ret_{y}" for y in FOCUS_YEARS]
    cols = [c for c in cols if c in summary.columns]
    lines.append(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    lines.extend(
        [
            "",
            "## Interpretation",
            "- **A3_D1_complementary** is the primary diversification case (D1 only when EMA20<EMA100 gate OFF).",
            "- Unconstrained splits are sensitivity only (70/30, 80/20, 60/40).",
            "- Focus years 2020/2022/2026 are A3-weak periods where D1 should add value if diversification is real.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("D1 IS/OOS + Combined Portfolio Validation", flush=True)
    print("Loading context...", flush=True)
    ctx = load_d1_context()

    print("Part 1 — D1 standalone IS/OOS...", flush=True)
    isoos_df, isoos_meta = run_d1_isoos(ctx)
    isoos_df.to_csv(OUT_DIR / "d1_isoos_validation.csv", index=False, float_format="%.6f")
    (OUT_DIR / "d1_isoos_validation_report.md").write_text(
        _write_isoos_report(isoos_df, isoos_meta), encoding="utf-8"
    )
    (OUT_DIR / "d1_isoos_validation_meta.json").write_text(
        json.dumps(isoos_meta, indent=2, default=str), encoding="utf-8"
    )
    print(f"  IS/OOS verdict: {isoos_meta['verdict']}", flush=True)

    print("Part 2 — A3 + D1 combined...", flush=True)
    a3_trades = build_a3_honest_trades(ctx)
    combined_summary, combined_annual, combined_meta = run_combined_portfolio(ctx, a3_trades)
    combined_summary.to_csv(OUT_DIR / "d1_combined_portfolio.csv", index=False, float_format="%.6f")
    combined_annual.to_csv(OUT_DIR / "d1_combined_portfolio_annual.csv", index=False, float_format="%.6f")
    (OUT_DIR / "d1_combined_portfolio_report.md").write_text(
        _write_combined_report(combined_summary, combined_meta), encoding="utf-8"
    )
    (OUT_DIR / "d1_combined_portfolio_meta.json").write_text(
        json.dumps(combined_meta, indent=2, default=str), encoding="utf-8"
    )

    nan_mar = isoos_df["mar"].isna().sum() if not isoos_df.empty else 0
    nan_combined = combined_summary["mar"].isna().sum() if not combined_summary.empty else 0
    print(f"  Combined best: {combined_meta['best_variant_by_mar']} MAR={combined_meta['complementary_mar']:.4f}")
    print(f"  NaN MAR isoos={nan_mar} combined={nan_combined}")
    print(f"Wrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
