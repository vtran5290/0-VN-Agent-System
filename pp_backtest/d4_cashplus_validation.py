#!/usr/bin/env python3
"""
D4 — Cash-plus / exposure-timing research (hierarchy vs D1 reference).

Level 0: A3 capital-based baseline (0% yield)
Level 1: A3 + idle settled cash yield (net-of-tax VND rates)
Level 2: A3 + VNINDEX proxy overlay during gate-OFF periods (+ placebo)
Level 3: A3+D1 reference imported from meta JSON

RESEARCH_ONLY_NOT_PRODUCTION

Usage:
  python pp_backtest/d4_cashplus_validation.py
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.d1_capital_based_validation import (
    ActivePosition,
    PendingSettlement,
    PreparedTrade,
    SimResult,
    _gate_for_entry,
    _metrics_from_equity,
    _prepare_trades,
    simulate_capital_account,
)
from pp_backtest.d1_isoos_validation import build_a3_honest_trades, load_d1_context
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.phase_exit_sweep_core import DATA_END, DATA_START, MAX_POSITIONS, PORTFOLIO_VND
from pp_backtest.portfolio_optimization_phase1 import load_vnindex
from pp_backtest.portfolio_optimization_phase31 import _tag_adv50
from pp_backtest.sleeve_d1_capitulation import SETTLEMENT_BDAY
from pp_backtest.sleeve_harness import COST_RT_P0, mean_cash_fraction

RESEARCH_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"
OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_d4"
D1_META = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_d1" / "d1_capital_based_meta.json"

A3_CAPITAL_MAR = 0.19148505804370394  # capital-based baseline from D1 validation
D1_REFERENCE_MAR = 0.22118419482626286
D1_INCREMENTAL = D1_REFERENCE_MAR - A3_CAPITAL_MAR
MAR_FLOOR = 0.21
MAXDD_FLOOR = -0.203  # A3 ~-0.1828 + 2pp
COMPLEXITY_MARGIN = 0.02
FOCUS_YEARS = (2020, 2022, 2026)
PLACEHOLDER_SEEDS = 100
ETF_SLIPPAGE = 0.003
OVERLAY_RT = COST_RT_P0 + ETF_SLIPPAGE  # per direction turnover

CASH_YIELDS = (
    (0.000, "0% baseline"),
    (0.019, "1.9% net — VND savings ~2% gross, 5% WHT"),
    (0.0285, "2.85% net — VND T-bill ~3% gross, 5% WHT"),
    (0.038, "3.8% net — VN MMF ~4% gross, 5% WHT"),
)
OVERLAY_FRACS = (0.25, 0.50, 0.75)


@dataclass
class D4SimResult:
    equity: pd.Series
    turnover_rts: float
    assertion_ok: bool


def _vnindex_daily_returns() -> pd.Series:
    vnx = load_vnindex()
    vnx = vnx[(vnx["date"] >= DATA_START) & (vnx["date"] <= DATA_END)].copy()
    vnx["date"] = pd.to_datetime(vnx["date"]).dt.normalize()
    vnx = vnx.sort_values("date")
    vnx["ret"] = vnx["close"].astype(float).pct_change()
    return vnx.set_index("date")["ret"].fillna(0.0)


def simulate_a3_with_overlay(
    a3_trades: list[PreparedTrade],
    gate: pd.Series,
    index_ret: pd.Series,
    *,
    cash_yield_annual: float = 0.0,
    overlay_frac: float = 0.0,
    expose_mask: dict[pd.Timestamp, bool] | None = None,
) -> D4SimResult:
    """A3 capital account + optional index proxy on settled idle cash during expose days."""
    if not a3_trades:
        return D4SimResult(pd.Series(dtype=float), 0.0, True)

    min_d = min(t.entry_date for t in a3_trades)
    max_d = max(t.exit_date for t in a3_trades)
    dates = pd.date_range(min_d, max_d, freq="B")

    by_entry: dict[pd.Timestamp, list[PreparedTrade]] = {}
    by_exit: dict[pd.Timestamp, list[PreparedTrade]] = {}
    for t in a3_trades:
        by_entry.setdefault(t.entry_date, []).append(t)
        by_exit.setdefault(t.exit_date, []).append(t)

    portfolio_vnd = PORTFOLIO_VND
    settled_cash = portfolio_vnd
    pending: list[PendingSettlement] = []
    active: list[ActivePosition] = []
    proxy_capital = 0.0
    equity: dict[pd.Timestamp, float] = {}
    turnover_rts = 0

    for dv in dates:
        dv = pd.Timestamp(dv).normalize()
        g_on = _gate_for_entry(gate, dv)
        want_expose = (not g_on) if expose_mask is None else expose_mask.get(dv, False)

        # Release settlements
        still: list[PendingSettlement] = []
        for p in pending:
            if p.available_date <= dv:
                settled_cash += p.amount_vnd
            else:
                still.append(p)
        pending = still

        # Index return on proxy held overnight into today
        if proxy_capital > 0:
            r = float(index_ret.get(dv, 0.0))
            proxy_capital *= 1.0 + r

        # A3 exits
        for t in by_exit.get(dv, []):
            pos = next((p for p in active if p.trade_id == t.trade_id), None)
            if pos is None:
                continue
            proceeds = pos.capital_vnd * (1.0 + pos.net_return)
            avail = pd.Timestamp(dv + pd.tseries.offsets.BDay(SETTLEMENT_BDAY)).normalize()
            pending.append(PendingSettlement(proceeds, avail))
            active = [p for p in active if p.trade_id != t.trade_id]

        # Cash yield on settled unencumbered cash (not locked in T+2 pending, not in proxy)
        if cash_yield_annual > 0 and settled_cash > 0:
            settled_cash += settled_cash * (cash_yield_annual / 252.0)

        # Overlay rebalance on OFF / expose days
        if overlay_frac > 0:
            target_proxy = overlay_frac * settled_cash if want_expose else 0.0
            delta = target_proxy - proxy_capital
            if abs(delta) > 1.0:
                if delta > 0:
                    cost = delta * OVERLAY_RT
                    spend = min(delta + cost, settled_cash)
                    if spend >= delta:
                        settled_cash -= delta + cost
                        proxy_capital += delta
                        turnover_rts += 1
                else:
                    release = -delta
                    cost = release * OVERLAY_RT
                    proxy_capital -= release
                    settled_cash += release - cost
                    turnover_rts += 1

        # A3 entries (gate ON only)
        if g_on:
            cands = sorted(by_entry.get(dv, []), key=lambda x: -x.rank)
            slots = MAX_POSITIONS - len(active)
            nav_pre = settled_cash + sum(p.capital_vnd for p in active) + sum(p.amount_vnd for p in pending) + proxy_capital
            for t in cands:
                if slots <= 0 or settled_cash <= 100_000:
                    break
                cap = min(nav_pre * t.target_w, settled_cash)
                if cap < 100_000:
                    continue
                if cap > settled_cash + 1e-3:
                    raise AssertionError(f"G5 settlement violation {dv.date()}")
                settled_cash -= cap
                active.append(
                    ActivePosition(t.trade_id, "A3", cap, t.exit_date, t.net_return)
                )
                slots -= 1

        locked = sum(p.amount_vnd for p in pending)
        active_cap = sum(p.capital_vnd for p in active)
        nav = settled_cash + active_cap + locked + proxy_capital
        equity[dv] = nav

        # G5 assertion: yield cash bounds
        if settled_cash < -1e-3 or proxy_capital < -1e-3:
            raise AssertionError(f"G5 negative cash {dv.date()}")
        if proxy_capital + settled_cash > nav + 1e-3:
            raise AssertionError(f"G5 double count {dv.date()}")

    eq = pd.Series(equity)
    eq = eq / eq.iloc[0] if not eq.empty and eq.iloc[0] > 0 else eq
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 0.1) if not eq.empty else 1
    ann_turnover = turnover_rts / years
    return D4SimResult(eq, ann_turnover, True)


def _filter_equity_ex_years(eq: pd.Series, exclude: set[int]) -> pd.Series:
    if eq.empty:
        return eq
    return eq[~eq.index.year.isin(exclude)]


def _oos_mar(eq: pd.Series) -> float:
    if eq.empty:
        return np.nan
    sub = eq[eq.index.year >= 2020]
    if len(sub) < 5:
        return np.nan
    return float(portfolio_metrics(sub, pd.DataFrame()).get("mar", np.nan))


def _make_placebo_mask(gate: pd.Series, dates: pd.DatetimeIndex, seed: int) -> dict[pd.Timestamp, bool]:
    off_count = sum(1 for d in dates if not _gate_for_entry(gate, pd.Timestamp(d)))
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(dates), size=min(off_count, len(dates)), replace=False)
    mask = {pd.Timestamp(d).normalize(): False for d in dates}
    for i in idx:
        mask[pd.Timestamp(dates[i]).normalize()] = True
    return mask


def run_validation() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx = load_d1_context()
    index_ret = _vnindex_daily_returns()

    print("Building A3 trades...", flush=True)
    a3_df = build_a3_honest_trades(ctx)
    a3_df = _tag_adv50(a3_df, ctx.adv)
    a3_p = _prepare_trades(a3_df, "A3", PORTFOLIO_VND, "rs_score")

    rows: list[dict] = []

    # Level 0
    r0 = simulate_capital_account(a3_p, [], ctx.gate, "a3_only", d1_idle_yield_annual=0.0)
    m0 = _metrics_from_equity(r0.equity)
    m0["level"] = "L0"
    m0["arm"] = "A3_alone_0pct_yield"
    m0["cash_yield_annual"] = 0.0
    rows.append(m0)

    # Level 1
    level1_rows = []
    for yld, label in CASH_YIELDS:
        res = simulate_capital_account(a3_p, [], ctx.gate, "a3_only", d1_idle_yield_annual=yld)
        m = _metrics_from_equity(res.equity)
        m.update({"level": "L1", "arm": f"cash_plus_{label}", "cash_yield_annual": yld})
        m["cash_drag_reduction_cagr"] = m["cagr"] - m0["cagr"]
        m["mean_cash_fraction"] = float(mean_cash_fraction(a3_df, ctx.adv))
        level1_rows.append(m)
        rows.append(m)
        print(f"  L1 {label}: MAR={m['mar']:.4f}", flush=True)

    level1_best = max(level1_rows, key=lambda x: x["mar"])

    # Level 2a + placebo
    level2_rows = []
    placebo_mars: dict[float, list[float]] = {f: [] for f in OVERLAY_FRACS}
    dates = r0.equity.index if not r0.equity.empty else pd.DatetimeIndex([])

    for frac in OVERLAY_FRACS:
        res = simulate_a3_with_overlay(a3_p, ctx.gate, index_ret, cash_yield_annual=0.0, overlay_frac=frac)
        m = _metrics_from_equity(res.equity)
        m.update({
            "level": "L2a",
            "arm": f"overlay_vnindex_{int(frac*100)}pct_off",
            "overlay_frac": frac,
            "annual_turnover_rts": res.turnover_rts,
        })
        level2_rows.append(m)
        rows.append(m)
        print(f"  L2a {int(frac*100)}%: MAR={m['mar']:.4f} turnover={res.turnover_rts:.1f}/yr", flush=True)

        for seed in range(PLACEHOLDER_SEEDS):
            pmask = _make_placebo_mask(ctx.gate, dates, seed)
            pres = simulate_a3_with_overlay(
                a3_p, ctx.gate, index_ret, overlay_frac=frac, expose_mask=pmask
            )
            pm = _metrics_from_equity(pres.equity)["mar"]
            placebo_mars[frac].append(float(pm))

    placebo_summary = []
    for frac in OVERLAY_FRACS:
        arr = np.array(placebo_mars[frac])
        placebo_summary.append({
            "overlay_frac": frac,
            "placebo_mean_mar": float(np.mean(arr)),
            "placebo_p5": float(np.percentile(arr, 5)),
            "placebo_p95": float(np.percentile(arr, 95)),
        })
    placebo_df = pd.DataFrame(placebo_summary)

    level2_best = max(level2_rows, key=lambda x: x["mar"])
    best_frac = level2_best["overlay_frac"]
    placebo_p95 = float(placebo_df.loc[placebo_df["overlay_frac"] == best_frac, "placebo_p95"].iloc[0])

    # Level 3 import
    d1_meta = json.loads(D1_META.read_text(encoding="utf-8"))
    rows.append({
        "level": "L3",
        "arm": "A3_D1_reference_import",
        "mar": float(d1_meta["capital_based_mar_complementary_1pct"]),
        "note": "IMPORT — not recomputed",
    })

    # Crash-year removal best L1 and L2
    crash_rows = []
    for tag, yld, frac in [
        ("L1_best", level1_best["cash_yield_annual"], 0.0),
        ("L2_best", 0.0, level2_best["overlay_frac"]),
    ]:
        for filt, excl in [
            ("full", set()),
            ("ex_2020", {2020}),
            ("ex_2022", {2022}),
            ("ex_2020_and_2022", {2020, 2022}),
        ]:
            if frac > 0:
                sim = simulate_a3_with_overlay(a3_p, ctx.gate, index_ret, overlay_frac=frac)
            else:
                sim = simulate_capital_account(
                    a3_p, [], ctx.gate, "a3_only", d1_idle_yield_annual=yld
                )
                sim = D4SimResult(sim.equity, 0.0, True)
            eq_f = _filter_equity_ex_years(sim.equity, excl)
            m = _metrics_from_equity(eq_f) if len(eq_f) > 5 else {"mar": np.nan}
            crash_rows.append({"arm": tag, "filter": filt, "mar": m.get("mar", np.nan)})

    crash_df = pd.DataFrame(crash_rows)
    ex_both_l1 = crash_df[(crash_df["arm"] == "L1_best") & (crash_df["filter"] == "ex_2020_and_2022")]["mar"].iloc[0]
    ex_both_l2 = crash_df[(crash_df["arm"] == "L2_best") & (crash_df["filter"] == "ex_2020_and_2022")]["mar"].iloc[0]
    ex_both_base = crash_df[(crash_df["arm"] == "L1_best") & (crash_df["filter"] == "full")]["mar"].iloc[0]
    # incremental vs baseline at ex-both
    baseline_ex = float(
        portfolio_metrics(
            _filter_equity_ex_years(r0.equity, {2020, 2022}), pd.DataFrame()
        ).get("mar", np.nan)
    ) if len(_filter_equity_ex_years(r0.equity, {2020, 2022})) > 5 else np.nan

    # Hierarchy winner
    l1_passes_core = level1_best["mar"] >= MAR_FLOOR and level1_best["max_dd"] >= MAXDD_FLOOR
    l2_passes_core = level2_best["mar"] >= MAR_FLOOR and level2_best["max_dd"] >= MAXDD_FLOOR
    l2_beats_l1 = level2_best["mar"] >= level1_best["mar"] + COMPLEXITY_MARGIN
    l2_beats_placebo = level2_best["mar"] > placebo_p95

    if l1_passes_core and level1_best["mar"] >= level2_best["mar"]:
        hierarchy_winner = "Level 1 (cash-plus)"
        winner_m = level1_best
    elif l2_passes_core and l2_beats_l1 and l2_beats_placebo:
        hierarchy_winner = "Level 2 (overlay)"
        winner_m = level2_best
    elif l1_passes_core:
        hierarchy_winner = "Level 1 (cash-plus)"
        winner_m = level1_best
    else:
        hierarchy_winner = "neither"
        winner_m = level1_best if level1_best["mar"] >= level2_best["mar"] else level2_best

    winner_eq = simulate_capital_account(
        a3_p, [], ctx.gate, "a3_only", d1_idle_yield_annual=winner_m.get("cash_yield_annual", 0.0)
    ).equity if "overlay" not in winner_m.get("arm", "") else simulate_a3_with_overlay(
        a3_p, ctx.gate, index_ret, overlay_frac=winner_m.get("overlay_frac", 0.5)
    ).equity

    ex_both_incr = float(
        portfolio_metrics(_filter_equity_ex_years(winner_eq, {2020, 2022}), pd.DataFrame()).get("mar", np.nan)
    ) - baseline_ex if np.isfinite(baseline_ex) else np.nan

    gates = {
        "G1": {"pass": winner_m["mar"] >= MAR_FLOOR, "detail": f"MAR={winner_m['mar']:.4f}"},
        "G2": {"pass": winner_m["max_dd"] >= MAXDD_FLOOR, "detail": f"MaxDD={winner_m['max_dd']:.4f}"},
        "G3": {"pass": ex_both_incr > 0 if np.isfinite(ex_both_incr) else False, "detail": f"incr={ex_both_incr:.4f}"},
        "G4": {"pass": _oos_mar(winner_eq) > 0, "detail": f"OOS MAR={_oos_mar(winner_eq):.4f}"},
        "G5": {"pass": True, "detail": "Settlement/cash assertions OK"},
        "G6": {"pass": level2_best["mar"] >= level1_best["mar"] + COMPLEXITY_MARGIN, "detail": f"L2-L1={level2_best['mar']-level1_best['mar']:.4f}"},
        "G7": {"pass": level2_best["mar"] > placebo_p95, "detail": f"L2={level2_best['mar']:.4f} p95={placebo_p95:.4f}"},
    }
    gates_pass = sum(1 for v in gates.values() if v["pass"])

    d4_incr = winner_m["mar"] - A3_CAPITAL_MAR
    pct_d1 = (d4_incr / D1_INCREMENTAL * 100) if D1_INCREMENTAL > 0 else np.nan

    if hierarchy_winner.startswith("Level 1") and gates["G1"]["pass"] and gates["G2"]["pass"]:
        recommendation = "A"
    elif hierarchy_winner.startswith("Level 2") and gates_pass >= 5:
        recommendation = "A"
    elif winner_m["mar"] > A3_CAPITAL_MAR:
        recommendation = "B"
    else:
        recommendation = "C"

    meta = {
        "generated": str(date.today()),
        "research_label": RESEARCH_LABEL,
        "hierarchy_winner": hierarchy_winner,
        "recommendation": recommendation,
        "gates_pass_count": gates_pass,
        "gate_verdicts": gates,
        "a3_capital_baseline_mar": A3_CAPITAL_MAR,
        "d1_reference_mar": D1_REFERENCE_MAR,
        "level0_mar": m0["mar"],
        "level1_best_mar": level1_best["mar"],
        "level2_best_mar": level2_best["mar"],
        "placebo_p95_best_overlay": placebo_p95,
        "d1_benefit_captured_pct": pct_d1,
        "level2c_skipped": "no usable breadth time series",
        "level2b_skipped": "no historical vn_liquidity series",
    }

    results_df = pd.DataFrame(rows)
    results_df.to_csv(OUT_DIR / "d4_hierarchy_results.csv", index=False, float_format="%.6f")
    placebo_df.to_csv(OUT_DIR / "d4_placebo_summary.csv", index=False, float_format="%.6f")
    crash_df.to_csv(OUT_DIR / "d4_crash_year_removal.csv", index=False, float_format="%.6f")
    (OUT_DIR / "d4_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    report = _format_report(meta, gates, results_df, placebo_df, crash_df)
    (OUT_DIR / "d4_report.md").write_text(report, encoding="utf-8")
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return meta


def _format_report(meta, gates, results, placebo, crash) -> str:
    lines = [
        "# D4 Cash-Plus / Exposure Timing Validation",
        "",
        f"**Label:** {RESEARCH_LABEL}",
        f"**Hierarchy winner:** {meta['hierarchy_winner']}",
        f"**Recommendation:** {meta['recommendation']}",
        f"**Gates passed:** {meta['gates_pass_count']}/7",
        "",
        "## Baselines (capital-based only)",
        f"- A3 alone (L0): {meta['level0_mar']:.4f} (reference {A3_CAPITAL_MAR:.4f})",
        f"- D1 reference (L3 import): {meta['d1_reference_mar']:.4f}",
        f"- D1 incremental vs A3: {D1_INCREMENTAL:.4f}",
        "",
        "## Hierarchy results",
        results[["level", "arm", "mar", "cagr", "max_dd"]].to_string(index=False),
        "",
        "## Placebo (100 seeds)",
        placebo.to_string(index=False),
        "",
        "## Gate verdicts",
    ]
    for k, v in gates.items():
        lines.append(f"- **{k}:** {'PASS' if v['pass'] else 'FAIL'} — {v['detail']}")
    lines.extend([
        "",
        f"**D1 benefit captured by D4 winner:** {meta['d1_benefit_captured_pct']:.1f}%",
        "",
        "## Crash-year removal",
        crash.to_string(index=False),
        "",
        "## Interpretation",
        "- Comparisons use capital-based A3 MAR 0.191 — NOT legacy 0.381.",
        "- Level 1 (cash-plus) is the null hypothesis; Level 2 needs +0.02 MAR vs L1 and beat placebo p95.",
        "- If cash-plus alone clears gates, that is a valid positive result (cheapest solution wins).",
    ])
    return "\n".join(lines)


def main() -> None:
    print("D4 Cash-Plus Validation", flush=True)
    run_validation()


if __name__ == "__main__":
    main()
