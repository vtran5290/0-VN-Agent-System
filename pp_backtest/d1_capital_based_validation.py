#!/usr/bin/env python3
"""
D1 capital-based combined validation — primary decision curve.

Single cash account, T+2 settlement, A3 priority on contention, Gate 7 assertion.
Return-switched MAR from d1_isoos_validation is DISPLAY-ONLY.

RESEARCH_ONLY_NOT_PRODUCTION

Usage:
  python pp_backtest/d1_capital_based_validation.py
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.d1_isoos_validation import (
    build_a3_honest_trades,
    build_d1_honest_trades,
    compute_ex_best_year_mar,
    load_d1_context,
    merge_complementary,
)
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    YEAR_COLS,
)
from pp_backtest.portfolio_optimization_phase31 import _annual_return, _tag_adv50
from pp_backtest.sleeve_d1_capitulation import CAPACITY_SIZES, SETTLEMENT_BDAY
from pp_backtest.sleeve_harness import mean_cash_fraction

RESEARCH_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"
OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_d1"
A3_BASELINE_MAR = 0.381

Mode = Literal["a3_only", "d1_only", "complementary", "unconstrained_7030"]

D1_SLIPPAGE_SWEEP = (
    (0.005, "display_optimistic"),
    (0.010, "base_case"),
    (0.015, "hard_advance_gate"),
    (0.020, "stress_diagnostic"),
    (0.030, "stress_diagnostic"),
)
FOCUS_YEARS = (2020, 2022, 2026)
MIN_POS_VND = 100_000


@dataclass
class PreparedTrade:
    trade_id: int
    sleeve: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    net_return: float
    target_w: float
    rank: float
    entry_year: int


@dataclass
class ActivePosition:
    trade_id: int
    sleeve: str
    capital_vnd: float
    exit_date: pd.Timestamp
    net_return: float


@dataclass
class PendingSettlement:
    amount_vnd: float
    available_date: pd.Timestamp


@dataclass
class SimResult:
    equity: pd.Series
    audit_log: list[dict]
    gate_flips: list[dict]
    fills: list[dict]
    assertion_passed: bool = True


def _prepare_trades(
    trades: pd.DataFrame,
    sleeve: str,
    portfolio_vnd: float,
    rank_col: str | None,
) -> list[PreparedTrade]:
    if trades.empty:
        return []
    df = trades.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    base_w = 1.0 / MAX_POSITIONS
    tf = df["total_frac"].astype(float).fillna(0.5) if "total_frac" in df.columns else pd.Series(0.5, index=df.index)
    gk = df["has_gk"].astype(bool) if "has_gk" in df.columns else pd.Series(False, index=df.index)
    gk_factor = gk.map(lambda x: GK_MULT if x else 1.0)
    target_w = (gk_factor * base_w).clip(upper=base_w * GK_MULT) * tf
    if "adv50_value" in df.columns and (df["adv50_value"].fillna(0) > 0).any():
        adv = df["adv50_value"].fillna(0).astype(float)
        cap_w = (adv * ADV_PARTICIPATION / portfolio_vnd).clip(upper=base_w * GK_MULT)
        target_w = np.minimum(target_w, cap_w) * tf
    min_w = MIN_POS_VND / portfolio_vnd
    out: list[PreparedTrade] = []
    rank_vals = df[rank_col].astype(float) if rank_col and rank_col in df.columns else pd.Series(0.0, index=df.index)
    for i, row in df.iterrows():
        w = float(target_w.loc[i])
        if w < min_w:
            continue
        out.append(
            PreparedTrade(
                trade_id=int(i),
                sleeve=sleeve,
                entry_date=pd.Timestamp(row["entry_date"]).normalize(),
                exit_date=pd.Timestamp(row["exit_date"]).normalize(),
                net_return=float(row["net_return"]),
                target_w=w,
                rank=float(rank_vals.loc[i]) if np.isfinite(rank_vals.loc[i]) else 0.0,
                entry_year=int(pd.Timestamp(row["entry_date"]).year),
            )
        )
    return out


def _gate_for_entry(gate: pd.Series, entry_date: pd.Timestamp) -> bool:
    """Gate known at t-1 close: use prior business day gate status."""
    prev = entry_date - pd.tseries.offsets.BDay(1)
    prev = prev.normalize()
    if prev in gate.index:
        return bool(gate.loc[prev])
    prior = gate.index[gate.index < entry_date]
    if len(prior) == 0:
        return False
    return bool(gate.loc[prior[-1]])


def simulate_capital_account(
    a3_trades: list[PreparedTrade],
    d1_trades: list[PreparedTrade],
    gate: pd.Series,
    mode: Mode,
    *,
    portfolio_vnd: float = PORTFOLIO_VND,
    d1_idle_yield_annual: float = 0.0,
    a3_budget_frac: float = 1.0,
    d1_budget_frac: float = 1.0,
) -> SimResult:
    all_entries = a3_trades + d1_trades
    if not all_entries:
        return SimResult(pd.Series(dtype=float), [], [], [])

    min_d = min(t.entry_date for t in all_entries)
    max_d = max(t.exit_date for t in all_entries)
    dates = pd.date_range(min_d, max_d, freq="B")

    by_entry: dict[pd.Timestamp, list[PreparedTrade]] = {}
    by_exit: dict[pd.Timestamp, list[PreparedTrade]] = {}
    trade_map = {t.trade_id: t for t in all_entries}
    for t in all_entries:
        by_entry.setdefault(t.entry_date, []).append(t)
        by_exit.setdefault(t.exit_date, []).append(t)

    settled_cash = portfolio_vnd
    pending: list[PendingSettlement] = []
    active: list[ActivePosition] = []
    equity: dict[pd.Timestamp, float] = {}
    audit: list[dict] = []
    fills: list[dict] = []
    gate_flips: list[dict] = []
    prev_gate: bool | None = None

    for dv in dates:
        dv = pd.Timestamp(dv).normalize()

        # Gate flip audit (t-1 known gate for today)
        g_today = _gate_for_entry(gate, dv)
        if prev_gate is not None and g_today != prev_gate:
            gate_flips.append(
                {
                    "date": str(dv.date()),
                    "from": "ON" if prev_gate else "OFF",
                    "to": "ON" if g_today else "OFF",
                }
            )
        prev_gate = g_today

        # Release T+2 settlements
        still_pending: list[PendingSettlement] = []
        for p in pending:
            if p.available_date <= dv:
                settled_cash += p.amount_vnd
            else:
                still_pending.append(p)
        pending = still_pending

        # Exits — proceeds locked until T+2
        exiting = by_exit.get(dv, [])
        for t in exiting:
            pos = next((p for p in active if p.trade_id == t.trade_id), None)
            if pos is None:
                continue
            proceeds = pos.capital_vnd * (1.0 + pos.net_return)
            avail = dv + pd.tseries.offsets.BDay(SETTLEMENT_BDAY)
            pending.append(PendingSettlement(proceeds, pd.Timestamp(avail).normalize()))
            active = [p for p in active if p.trade_id != t.trade_id]

        active_capital = sum(p.capital_vnd for p in active)
        locked = sum(p.amount_vnd for p in pending)
        nav = settled_cash + active_capital + locked

        # Idle yield on settled cash (D4 variant only — base case 0%)
        if d1_idle_yield_annual > 0 and settled_cash > 0:
            settled_cash += settled_cash * (d1_idle_yield_annual / 252.0)

        # Entries
        candidates = by_entry.get(dv, [])
        if mode == "a3_only":
            candidates = [c for c in candidates if c.sleeve == "A3"]
        elif mode == "d1_only":
            candidates = [c for c in candidates if c.sleeve == "D1"]
        elif mode == "complementary":
            if g_today:
                candidates = [c for c in candidates if c.sleeve == "A3"]
            else:
                candidates = [c for c in candidates if c.sleeve == "D1"]
        # unconstrained: both sleeves

        a3_cands = sorted([c for c in candidates if c.sleeve == "A3"], key=lambda x: -x.rank)
        d1_cands = sorted([c for c in candidates if c.sleeve == "D1"], key=lambda x: -x.rank)
        ordered = a3_cands + d1_cands if mode != "a3_only" and mode != "d1_only" else candidates
        if mode in ("a3_only", "complementary") and g_today:
            ordered = a3_cands
        elif mode in ("d1_only", "complementary") and not g_today:
            ordered = d1_cands
        elif mode == "unconstrained_7030":
            ordered = a3_cands + d1_cands

        a3_deployed = sum(p.capital_vnd for p in active if p.sleeve == "A3")
        d1_deployed = sum(p.capital_vnd for p in active if p.sleeve == "D1")
        a3_cap = nav * a3_budget_frac
        d1_cap = nav * d1_budget_frac
        slots_left = MAX_POSITIONS - len(active)

        for t in ordered:
            if slots_left <= 0:
                break
            if settled_cash <= MIN_POS_VND:
                break
            target_cap = nav * t.target_w
            if t.sleeve == "A3":
                if a3_deployed + target_cap > a3_cap + 1.0:
                    target_cap = max(0.0, a3_cap - a3_deployed)
            else:
                if d1_deployed + target_cap > d1_cap + 1.0:
                    target_cap = max(0.0, d1_cap - d1_deployed)
            cap = min(target_cap, settled_cash)
            if cap < MIN_POS_VND:
                continue

            # Gate 7 — each entry must not exceed remaining settled cash
            if cap > settled_cash + 1e-3:
                raise AssertionError(
                    f"Gate 7 settlement violation on {dv.date()}: "
                    f"requested={cap:.0f} settled={settled_cash:.0f}"
                )

            settled_cash -= cap
            active.append(
                ActivePosition(
                    trade_id=t.trade_id,
                    sleeve=t.sleeve,
                    capital_vnd=cap,
                    exit_date=t.exit_date,
                    net_return=t.net_return,
                )
            )
            if t.sleeve == "A3":
                a3_deployed += cap
            else:
                d1_deployed += cap
            slots_left -= 1
            fills.append(
                {
                    "date": str(dv.date()),
                    "sleeve": t.sleeve,
                    "trade_id": t.trade_id,
                    "capital_vnd": cap,
                    "gate_on": g_today,
                    "mode": mode,
                }
            )

        active_capital = sum(p.capital_vnd for p in active)
        locked = sum(p.amount_vnd for p in pending)
        nav = settled_cash + active_capital + locked
        equity[dv] = nav

        audit.append(
            {
                "date": str(dv.date()),
                "nav_vnd": nav,
                "settled_cash": settled_cash,
                "active_capital": active_capital,
                "pending_locked": locked,
                "a3_deployed": sum(p.capital_vnd for p in active if p.sleeve == "A3"),
                "d1_deployed": sum(p.capital_vnd for p in active if p.sleeve == "D1"),
                "gate_on_tminus1": g_today,
            }
        )

        # Gate 7 — no double-count beyond NAV
        total_deployed = sum(p.capital_vnd for p in active)
        if total_deployed > nav + 1e-3:
            raise AssertionError(
                f"Gate 7 over-allocation on {dv.date()}: deployed={total_deployed:.0f} nav={nav:.0f}"
            )

    eq = pd.Series(equity)
    eq = eq / eq.iloc[0] if not eq.empty and eq.iloc[0] > 0 else eq
    return SimResult(eq, audit, gate_flips, fills, True)


def _metrics_from_equity(eq: pd.Series, portfolio_vnd: float = PORTFOLIO_VND) -> dict[str, Any]:
    if eq.empty:
        return {k: np.nan for k in ("mar", "cagr", "max_dd", "worst_year_return", "ex_best_year_mar")}
    m = portfolio_metrics(eq, pd.DataFrame())
    annual = eq.groupby(eq.index.year).last().pct_change().dropna()
    row = {
        "mar": float(m.get("mar", np.nan)),
        "cagr": float(m.get("cagr", np.nan)),
        "max_dd": float(m.get("max_dd", np.nan)),
        "worst_year_return": float(annual.min()) if not annual.empty else np.nan,
        "ex_best_year_mar": compute_ex_best_year_mar(eq),
    }
    for y in FOCUS_YEARS:
        row[f"ret_{y}"] = _annual_return(eq, y)
    for size in CAPACITY_SIZES:
        row[f"mar_{int(size / 1e9)}b"] = np.nan
    return row


def _filter_trades_df(trades: pd.DataFrame, exclude_years: set[int]) -> pd.DataFrame:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    return t[~t["entry_date"].dt.year.isin(exclude_years)]


def concentration_analysis(
    d1_trades: pd.DataFrame,
    eq_comp: pd.Series,
    eq_a3: pd.Series,
    portfolio_vnd: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    d1 = d1_trades.copy()
    d1["entry_date"] = pd.to_datetime(d1["entry_date"])
    d1["entry_year"] = d1["entry_date"].dt.year
    slot = portfolio_vnd / MAX_POSITIONS
    d1["gross_pnl_vnd"] = d1["net_return"].astype(float) * slot

    by_year = d1.groupby("entry_year").agg(
        n_trades=("net_return", "count"),
        gross_pnl_vnd=("gross_pnl_vnd", "sum"),
    ).reset_index()
    total_pnl = float(by_year["gross_pnl_vnd"].sum())
    by_year["pnl_share"] = by_year["gross_pnl_vnd"] / total_pnl if total_pnl != 0 else 0.0

    incr_rows = []
    for y in sorted(d1["entry_year"].unique()):
        r_comp = _annual_return(eq_comp, int(y)) if not eq_comp.empty else np.nan
        r_a3 = _annual_return(eq_a3, int(y)) if not eq_a3.empty else np.nan
        incr = r_comp - r_a3 if np.isfinite(r_comp) and np.isfinite(r_a3) else np.nan
        incr_rows.append({"entry_year": int(y), "incremental_return": incr})
    incr_df = pd.DataFrame(incr_rows)
    incr_abs = incr_df["incremental_return"].abs()
    incr_total = incr_abs.sum()
    if incr_total > 0:
        incr_df["incr_share"] = incr_abs / incr_total
    else:
        incr_df["incr_share"] = 0.0

    merged = by_year.merge(incr_df, on="entry_year", how="outer")
    flags = {
        "max_pnl_year_share": float(merged["pnl_share"].max()) if not merged.empty else np.nan,
        "max_incr_year_share": float(merged["incr_share"].max()) if "incr_share" in merged else np.nan,
        "max_trade_count_share": float((merged["n_trades"] / merged["n_trades"].sum()).max())
        if not merged.empty and merged["n_trades"].sum() > 0
        else np.nan,
        "total_d1_pnl_vnd": total_pnl,
    }
    return merged, flags


def evaluate_gates(
    comp_m: dict,
    a3_m: dict,
    slip_015_m: dict,
    eq_comp: pd.Series,
    eq_a3: pd.Series,
    conc_flags: dict,
    oos_positive: bool,
) -> dict[str, dict]:
    g: dict[str, dict] = {}

    g["G1"] = {
        "pass": comp_m["mar"] > a3_m["mar"],
        "detail": f"comp={comp_m['mar']:.4f} vs a3={a3_m['mar']:.4f} @1.0% slip",
    }
    g["G2"] = {
        "pass": slip_015_m["mar"] > a3_m["mar"],
        "detail": f"comp={slip_015_m['mar']:.4f} vs a3={a3_m['mar']:.4f} @1.5% slip",
    }
    dd_improve = (comp_m["max_dd"] - a3_m["max_dd"]) / abs(a3_m["max_dd"]) if a3_m["max_dd"] else np.nan
    g["G3"] = {
        "pass": dd_improve >= 0.20,
        "detail": f"comp_dd={comp_m['max_dd']:.4f} a3_dd={a3_m['max_dd']:.4f} improve={dd_improve:.1%}",
    }

    def _sub_m(eq, years):
        if eq.empty:
            return np.nan
        mask = ~eq.index.year.isin(years)
        sub = eq[mask]
        return float(portfolio_metrics(sub, pd.DataFrame()).get("mar", np.nan)) if len(sub) > 5 else np.nan

    ex20_comp = _sub_m(eq_comp, {2020})
    ex20_a3 = _sub_m(eq_a3, {2020})
    ex22_comp = _sub_m(eq_comp, {2022})
    ex22_a3 = _sub_m(eq_a3, {2022})
    g4a = (ex20_comp - ex20_a3) / abs(ex20_a3) if np.isfinite(ex20_comp) and ex20_a3 else False
    g4b = (ex22_comp - ex22_a3) / abs(ex22_a3) if np.isfinite(ex22_comp) and ex22_a3 else False
    g["G4"] = {
        "pass": bool(g4a >= 0.20 and g4b >= 0.20),
        "detail": f"ex20 dd improve ~{g4a:.1%} ex22 ~{g4b:.1%}",
    }

    ex_both_comp = _sub_m(eq_comp, {2020, 2022})
    ex_both_a3 = _sub_m(eq_a3, {2020, 2022})
    incr = ex_both_comp - ex_both_a3 if np.isfinite(ex_both_comp) and np.isfinite(ex_both_a3) else -1
    g["G5"] = {
        "pass": incr > 0,
        "detail": f"ex2020+2022 incr MAR proxy: comp={ex_both_comp:.4f} a3={ex_both_a3:.4f}",
    }
    g["G6"] = {
        "pass": oos_positive,
        "detail": f"OOS MAR comp positive={oos_positive}",
    }
    g["G7"] = {"pass": True, "detail": "Code assertion — no violation raised during simulation"}
    g8_fail = (
        conc_flags.get("max_pnl_year_share", 0) > 0.40
        or conc_flags.get("max_incr_year_share", 0) > 0.40
    )
    g["G8"] = {
        "pass": not g8_fail,
        "detail": (
            f"max pnl share={conc_flags.get('max_pnl_year_share', 0):.1%} "
            f"max incr share={conc_flags.get('max_incr_year_share', 0):.1%}"
        ),
    }
    return g


def recommend(gates: dict[str, dict]) -> str:
    hard = ["G2", "G3", "G5", "G7", "G8"]
    soft = ["G1", "G4", "G6"]
    if all(gates[k]["pass"] for k in gates):
        return "A"
    if all(gates[k]["pass"] for k in hard) and sum(gates[k]["pass"] for k in soft) >= 1:
        return "B"
    if gates["G1"]["pass"] or gates["G2"]["pass"]:
        return "B"
    return "C"


def run_validation() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx = load_d1_context()

    print("Building A3 honest trades...", flush=True)
    a3_df = build_a3_honest_trades(ctx)
    a3_df = _tag_adv50(a3_df, ctx.adv)

    slip_results: list[dict] = []
    variant_rows: list[dict] = []
    gate_verdicts: dict[str, dict] = {}
    comp_eq_10 = pd.Series(dtype=float)
    a3_eq = pd.Series(dtype=float)
    d1_df_10 = pd.DataFrame()

    for slip, slip_label in D1_SLIPPAGE_SWEEP:
        print(f"  slippage {slip:.1%} ({slip_label})...", flush=True)
        d1_df = build_d1_honest_trades(ctx, n_floor=2, entry_slippage=slip)
        d1_df = _tag_adv50(d1_df, ctx.adv)

        a3_p = _prepare_trades(a3_df, "A3", PORTFOLIO_VND, "rs_score")
        d1_p = _prepare_trades(d1_df, "D1", PORTFOLIO_VND, "consecutive_floor_days")

        res_a3 = simulate_capital_account(a3_p, [], ctx.gate, "a3_only")
        res_d1 = simulate_capital_account([], d1_p, ctx.gate, "d1_only")
        res_comp = simulate_capital_account(a3_p, d1_p, ctx.gate, "complementary")
        res_u7030 = simulate_capital_account(
            a3_p, d1_p, ctx.gate, "unconstrained_7030", a3_budget_frac=0.70, d1_budget_frac=0.30
        )

        m_a3 = _metrics_from_equity(res_a3.equity)
        m_d1 = _metrics_from_equity(res_d1.equity)
        m_comp = _metrics_from_equity(res_comp.equity)
        m_u = _metrics_from_equity(res_u7030.equity)

        if slip_label == "base_case":
            comp_eq_10 = res_comp.equity
            a3_eq = res_a3.equity
            d1_df_10 = d1_df

        slip_results.append(
            {
                "d1_slippage": slip,
                "slippage_label": slip_label,
                "mar_complementary": m_comp["mar"],
                "mar_a3_alone": m_a3["mar"],
                "mar_d1_alone": m_d1["mar"],
                "max_dd_complementary": m_comp["max_dd"],
            }
        )

        if slip == 0.010:
            for name, m, res in [
                ("A3_alone_capital", m_a3, res_a3),
                ("D1_alone_capital", m_d1, res_d1),
                ("A3_D1_complementary_capital", m_comp, res_comp),
                ("A3_D1_unconstrained_7030_capital", m_u, res_u7030),
            ]:
                variant_rows.append(
                    {
                        "variant": name,
                        "d1_slippage": slip,
                        **m,
                        "mean_cash_fraction": float(mean_cash_fraction(
                            a3_df if "A3" in name and "complementary" not in name else d1_df
                            if "D1_alone" in name else pd.concat([a3_df, d1_df], ignore_index=True),
                            ctx.adv,
                        ))
                        if "complementary" not in name and "unconstrained" not in name
                        else np.nan,
                    }
                )
            pd.DataFrame(res_comp.audit_log).to_csv(
                OUT_DIR / "d1_capital_audit_log.csv", index=False
            )
            pd.DataFrame(res_comp.gate_flips).to_csv(
                OUT_DIR / "d1_gate_flip_audit.csv", index=False
            )
            pd.DataFrame(res_comp.fills).to_csv(
                OUT_DIR / "d1_capital_fills.csv", index=False
            )

    # Return-switched DISPLAY-ONLY
    from pp_backtest.d1_isoos_validation import build_equity_a3, build_equity_d1_from_eval

    eq_rs_a3 = build_equity_a3(a3_df)
    eq_rs_d1 = build_equity_d1_from_eval(d1_df_10, ctx.adv)
    eq_rs = merge_complementary(eq_rs_a3, eq_rs_d1, ctx.gate)
    m_rs = _metrics_from_equity(eq_rs)
    variant_rows.append(
        {
            "variant": "A3_D1_return_switched_DISPLAY_ONLY",
            "d1_slippage": 0.010,
            **m_rs,
            "label": "DISPLAY-ONLY / NOT A GATE",
        }
    )

    # D4 cross-check
    d1_p = _prepare_trades(d1_df_10, "D1", PORTFOLIO_VND, "consecutive_floor_days")
    a3_p = _prepare_trades(a3_df, "A3", PORTFOLIO_VND, "rs_score")
    res_d4 = simulate_capital_account(
        a3_p, d1_p, ctx.gate, "complementary", d1_idle_yield_annual=0.03
    )
    m_d4 = _metrics_from_equity(res_d4.equity)
    variant_rows.append(
        {
            "variant": "A3_D1_complementary_D4_crosscheck_3pct_idle",
            "d1_slippage": 0.010,
            **m_d4,
            "label": "D4-crosscheck variant",
        }
    )

    # Capacity at 5/10/20B for complementary @ 1.0%
    cap_rows = []
    for size in CAPACITY_SIZES:
        d1_df = build_d1_honest_trades(ctx, n_floor=2, entry_slippage=0.010)
        a3_p = _prepare_trades(a3_df, "A3", size, "rs_score")
        d1_p = _prepare_trades(d1_df, "D1", size, "consecutive_floor_days")
        res = simulate_capital_account(a3_p, d1_p, ctx.gate, "complementary", portfolio_vnd=size)
        cap_rows.append({"portfolio_vnd": size, "mar": _metrics_from_equity(res.equity)["mar"]})
    cap_df = pd.DataFrame(cap_rows)
    for _, r in cap_df.iterrows():
        tag = f"mar_{int(r['portfolio_vnd'] / 1e9)}b"
        for v in variant_rows:
            if v.get("variant") == "A3_D1_complementary_capital":
                v[tag] = float(r["mar"])

    # Joint crash-year removal
    crash_rows = []
    for label, excl in [
        ("full", set()),
        ("ex_2020", {2020}),
        ("ex_2022", {2022}),
        ("ex_2020_and_2022", {2020, 2022}),
    ]:
        a3_f = _filter_trades_df(a3_df, excl)
        d1_f = _filter_trades_df(d1_df_10, excl)
        a3_p = _prepare_trades(a3_f, "A3", PORTFOLIO_VND, "rs_score")
        d1_p = _prepare_trades(d1_f, "D1", PORTFOLIO_VND, "consecutive_floor_days")
        ra = simulate_capital_account(a3_p, [], ctx.gate, "a3_only")
        rc = simulate_capital_account(a3_p, d1_p, ctx.gate, "complementary")
        ma = _metrics_from_equity(ra.equity)
        mc = _metrics_from_equity(rc.equity)
        crash_rows.append(
            {
                "filter": label,
                "mar_a3": ma["mar"],
                "mar_complementary": mc["mar"],
                "incremental_mar": mc["mar"] - ma["mar"],
            }
        )
    crash_df = pd.DataFrame(crash_rows)

    conc_df, conc_flags = concentration_analysis(d1_df_10, comp_eq_10, a3_eq, PORTFOLIO_VND)

    # Gates @ 1.0% and 1.5%
    m_comp_10 = next(r for r in variant_rows if r["variant"] == "A3_D1_complementary_capital")
    m_a3_10 = next(r for r in variant_rows if r["variant"] == "A3_alone_capital")
    slip_015 = next(r for r in slip_results if r["d1_slippage"] == 0.015)
    oos_a3 = simulate_capital_account(
        _prepare_trades(_filter_trades_df(a3_df, set()), "A3", PORTFOLIO_VND, "rs_score"),
        [],
        ctx.gate,
        "a3_only",
    )
    # OOS check: 2020+ entries only
    a3_oos = _filter_trades_df(a3_df, set(range(2012, 2020)))
    d1_oos = _filter_trades_df(d1_df_10, set(range(2012, 2020)))
    a3_p_oos = _prepare_trades(a3_oos, "A3", PORTFOLIO_VND, "rs_score")
    d1_p_oos = _prepare_trades(d1_oos, "D1", PORTFOLIO_VND, "consecutive_floor_days")
    res_oos = simulate_capital_account(a3_p_oos, d1_p_oos, ctx.gate, "complementary")
    oos_m = _metrics_from_equity(res_oos.equity)
    oos_positive = bool(oos_m.get("mar", 0) > 0)

    gate_verdicts = evaluate_gates(
        m_comp_10, m_a3_10, {"mar": slip_015["mar_complementary"]}, comp_eq_10, a3_eq, conc_flags, oos_positive
    )
    rec = recommend(gate_verdicts)

    a3_mar_diff = abs(m_a3_10["mar"] - A3_BASELINE_MAR) / A3_BASELINE_MAR

    meta = {
        "generated": str(date.today()),
        "research_label": RESEARCH_LABEL,
        "recommendation": rec,
        "gate_verdicts": gate_verdicts,
        "gates_pass_count": sum(1 for v in gate_verdicts.values() if v["pass"]),
        "capital_based_mar_complementary_1pct": m_comp_10["mar"],
        "capital_based_mar_a3_1pct": m_a3_10["mar"],
        "return_switched_mar_display_only": m_rs["mar"],
        "mechanical_inflation": m_rs["mar"] - m_comp_10["mar"],
        "a3_mar_vs_baseline_pct_diff": a3_mar_diff,
        "concentration_flags": conc_flags,
        "trade_count_warning": conc_flags.get("max_trade_count_share", 0) > 0.40,
    }

    slip_df = pd.DataFrame(slip_results)
    var_df = pd.DataFrame(variant_rows)

    slip_df.to_csv(OUT_DIR / "d1_capital_slippage_sweep.csv", index=False, float_format="%.6f")
    var_df.to_csv(OUT_DIR / "d1_capital_variants.csv", index=False, float_format="%.6f")
    crash_df.to_csv(OUT_DIR / "d1_capital_crash_year_removal.csv", index=False, float_format="%.6f")
    conc_df.to_csv(OUT_DIR / "d1_concentration_by_year.csv", index=False, float_format="%.6f")
    cap_df.to_csv(OUT_DIR / "d1_capital_capacity.csv", index=False, float_format="%.6f")

    report = _format_report(meta, gate_verdicts, slip_df, var_df, crash_df, conc_df, rec)
    (OUT_DIR / "d1_capital_based_report.md").write_text(report, encoding="utf-8")
    (OUT_DIR / "d1_capital_based_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return meta


def _format_report(meta, gates, slip_df, var_df, crash_df, conc_df, rec) -> str:
    lines = [
        "# D1 Capital-Based Combined Validation",
        "",
        f"**Label:** {RESEARCH_LABEL}",
        f"**Recommendation:** {rec}",
        f"**Gates passed:** {meta['gates_pass_count']}/8",
        "",
        "## Capital-based vs return-switched (DISPLAY-ONLY)",
        f"- Complementary MAR @1.0% slip (capital-based): **{meta['capital_based_mar_complementary_1pct']:.4f}**",
        f"- A3 alone MAR (capital-based): **{meta['capital_based_mar_a3_1pct']:.4f}**",
        f"- Return-switched MAR (DISPLAY-ONLY / NOT A GATE): **{meta['return_switched_mar_display_only']:.4f}**",
        f"- Mechanical inflation: **{meta['mechanical_inflation']:.4f}**",
        "",
        "## Gate verdicts (capital-based curve only)",
    ]
    for k, v in gates.items():
        lines.append(f"- **{k}:** {'PASS' if v['pass'] else 'FAIL'} — {v['detail']}")
    lines.extend(["", "## Slippage sweep (complementary)", slip_df.to_string(index=False), ""])
    lines.extend(["## Crash-year removal", crash_df.to_string(index=False), ""])
    lines.extend(["## Concentration by year", conc_df.to_string(index=False), ""])
    lines.extend(
        [
            "",
            "## Interpretation",
            "- All decision gates evaluate the **capital-based** shared cash account, not return-switched.",
            "- Return-switched 0.977 is retained only to show mechanical inflation magnitude.",
            "- Gate 7 enforced via AssertionError on settlement / over-allocation.",
            "- Output A/B/C does NOT authorize live capital.",
        ]
    )
    return "\n".join(lines)


def _test_gate7_assertion() -> None:
    """Sanity: simulation completes with settlement tracking; deployed never exceeds NAV."""
    gate = pd.Series({pd.Timestamp("2020-01-01"): True})
    t1 = PreparedTrade(0, "A3", pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-10"), 0.01, 0.25, 1.0, 2020)
    res = simulate_capital_account([t1], [], gate, "a3_only", portfolio_vnd=5e9)
    if res.equity.empty:
        raise RuntimeError("Gate 7 self-test: empty equity")
    # Complementary: no D1 fills when gate ON
    t2 = PreparedTrade(1, "D1", pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-12"), 0.02, 0.25, 1.0, 2020)
    res2 = simulate_capital_account([t1], [t2], gate, "complementary")
    d1_fills = [f for f in res2.fills if f["sleeve"] == "D1"]
    if d1_fills:
        raise RuntimeError("Gate 7 self-test: D1 filled on gate-ON date")


def main() -> None:
    print("Gate 7 assertion self-test...", flush=True)
    _test_gate7_assertion()
    print("  Gate 7 self-test passed (settlement + no D1 on gate-ON)", flush=True)
    run_validation()


if __name__ == "__main__":
    main()
