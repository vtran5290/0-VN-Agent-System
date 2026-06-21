#!/usr/bin/env python3
"""
Phase A — P3 RS Ranking Test + Cash-Yield Accounting.

A2: Pre-registered RS score (40/30/20/10) replaces FIFO queue.
    Hard kill: honest MAR >= 0.27 AND 2021 capture >= 85%.
A3: Cash-yield accounting at 0%/2%/3%/4% on idle cash.

Uses canonical engine (phase_exit_sweep_core) + P0 realism harness.
DO NOT tune RS weights — this is a controlled falsification test.

Usage:
  python pp_backtest/p3_rs_cashyield.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    STRATEGY,
    binary_gate_ema20_100,
    build_a3_dp_cache,
)
from pp_backtest.portfolio_optimization_phase1 import (
    STRATEGY_CONFIGS,
    get_universe,
    load_panel,
    load_vnindex,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _annual_return,
    _build_adv50_map,
    _build_equity_adv_capped_v2,
    _tag_adv50,
)
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.p0_realism_p1_winner import (
    _build_honest_cache,
    _simulate_honest_trades,
    _metrics,
    BH_MAR_REF,
    TRAIL_MULT,
    INITIAL_STOP,
)

OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "p3_rs_cashyield"

RS_WEIGHTS = {"rs_3m": 0.40, "rs_6m": 0.30, "dist_52w_high": 0.20, "adv50_pctl": 0.10}

CASH_YIELDS = [0.00, 0.02, 0.03, 0.04]

MIN_POS_VND = 100_000


def _compute_rs_scores(panel: pd.DataFrame, trades: pd.DataFrame) -> pd.Series:
    """Compute pre-registered RS score for each trade at signal date."""
    cfg = STRATEGY_CONFIGS[STRATEGY]
    universe = get_universe(panel, cfg["universe"])
    sub = panel[panel["symbol"].isin(universe)].copy()
    sub["date"] = pd.to_datetime(sub["date"])

    px = sub.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index().ffill()
    vol_raw = sub.pivot_table(index="date", columns="symbol", values="value", aggfunc="last").sort_index().ffill()

    rs_3m = px.pct_change(63)
    rs_6m = px.pct_change(126)
    high_52w = px.rolling(252, min_periods=126).max()
    dist_52w = px / high_52w - 1.0
    adv50 = vol_raw.rolling(50, min_periods=20).mean()

    scores = []
    for idx, row in trades.iterrows():
        sym = row["symbol"]
        sig_date = pd.Timestamp(row["signal_date"])

        valid_dates = px.index[px.index <= sig_date]
        if len(valid_dates) == 0:
            scores.append(np.nan)
            continue
        d = valid_dates[-1]

        r3 = float(rs_3m.loc[d, sym]) if sym in rs_3m.columns and d in rs_3m.index else np.nan
        r6 = float(rs_6m.loc[d, sym]) if sym in rs_6m.columns and d in rs_6m.index else np.nan
        dh = float(dist_52w.loc[d, sym]) if sym in dist_52w.columns and d in dist_52w.index else np.nan

        adv_val = float(adv50.loc[d, sym]) if sym in adv50.columns and d in adv50.index else np.nan
        adv_row = adv50.loc[d].dropna() if d in adv50.index else pd.Series(dtype=float)
        if not np.isnan(adv_val) and len(adv_row) > 1:
            adv_pctl = float((adv_row < adv_val).sum()) / len(adv_row)
        else:
            adv_pctl = 0.5

        r3_rank = 0.0 if np.isnan(r3) else r3
        r6_rank = 0.0 if np.isnan(r6) else r6
        dh_rank = 0.0 if np.isnan(dh) else (1.0 + dh)

        score = (
            RS_WEIGHTS["rs_3m"] * r3_rank
            + RS_WEIGHTS["rs_6m"] * r6_rank
            + RS_WEIGHTS["dist_52w_high"] * dh_rank
            + RS_WEIGHTS["adv50_pctl"] * adv_pctl
        )
        scores.append(score)

    return pd.Series(scores, index=trades.index, name="rs_score")


def _build_equity_with_cash_yield(
    trades_df: pd.DataFrame,
    max_positions: int,
    portfolio_vnd: float,
    participation: float,
    gk_mult: float,
    rank_col: str | None,
    cash_yield_annual: float,
) -> tuple[pd.Series, dict]:
    """Equity builder with cash-yield on idle capital."""
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    base_w = 1.0 / max_positions
    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])

    is_gk = df["has_gk"].astype(bool) if "has_gk" in df.columns else pd.Series(False, index=df.index)
    tf = df["total_frac"].astype(float).fillna(1.0) if "total_frac" in df.columns else pd.Series(1.0, index=df.index)
    t1_frac = df["t1_frac"].astype(float).fillna(0.5) if "t1_frac" in df.columns else pd.Series(0.5, index=df.index)

    gk_factor = is_gk.map(lambda x: gk_mult if x else 1.0)
    target_w_full = (gk_factor * base_w).clip(upper=base_w * gk_mult)

    adv_col = "adv50_value"
    if adv_col in df.columns and (df[adv_col].fillna(0) > 0).any():
        adv_vals = df[adv_col].fillna(0).astype(float)
        max_w_full = (adv_vals * participation / portfolio_vnd).clip(lower=0, upper=base_w * gk_mult)
    else:
        max_w_full = target_w_full.copy()

    eff_w_full = np.minimum(target_w_full, max_w_full) * tf
    min_w = MIN_POS_VND / portfolio_vnd

    df["_eff_w"] = np.where(eff_w_full >= min_w, eff_w_full.values, 0.0)
    tradeable = df[df["_eff_w"] > 0].copy()

    if tradeable.empty:
        return pd.Series(dtype=float), {}

    sort_col = rank_col if rank_col and rank_col in tradeable.columns else None
    all_dates = pd.date_range(tradeable["entry_date"].min(), tradeable["exit_date"].max(), freq="B")

    by_entry = {}
    for ed, grp in tradeable.groupby("entry_date", sort=False):
        sg = grp.sort_values(sort_col, ascending=False) if sort_col else grp
        by_entry[ed] = list(sg.index)

    by_exit = {}
    for i, row in tradeable.iterrows():
        by_exit.setdefault(row["exit_date"], []).append(int(i))

    daily_yield = cash_yield_annual / 252.0
    portfolio_val = 1.0
    active: dict[int, float] = {}
    equity: dict = {}

    for dv in all_dates:
        for tid in by_exit.get(dv, []):
            if tid in active:
                w = active.pop(tid)
                portfolio_val += portfolio_val * w * float(tradeable.loc[tid, "net_return"])

        active_exp = sum(active.values())
        idle_frac = max(0.0, 1.0 - active_exp)
        portfolio_val += portfolio_val * idle_frac * daily_yield

        remaining = max_positions - len(active)
        for tid in by_entry.get(dv, []):
            if remaining <= 0:
                break
            w = float(tradeable.loc[tid, "_eff_w"])
            avail = max(0.0, 1.0 - active_exp)
            w = min(w, avail)
            if w > 1e-9:
                active[tid] = w
                active_exp += w
                remaining -= 1

        equity[dv] = portfolio_val

    eq = pd.Series(equity)
    m = portfolio_metrics(eq, tradeable) if not eq.empty else {}
    return eq, m


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading data...", flush=True)

    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)]
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)

    print("Building honest trades (P0 realism)...", flush=True)
    honest_cache = _build_honest_cache(panel)
    honest_trades = _simulate_honest_trades(honest_cache, gate, adv)

    if honest_trades.empty:
        print("ERROR: No honest trades generated.")
        return

    print(f"Honest trades: {len(honest_trades)}")

    # --- A2: RS Ranking ---
    print("Computing RS scores (pre-registered 40/30/20/10)...", flush=True)
    rs_scores = _compute_rs_scores(panel, honest_trades)
    honest_trades["rs_score"] = rs_scores

    tagged_fifo = _tag_adv50(honest_trades.copy(), adv)
    tagged_rs = _tag_adv50(honest_trades.copy(), adv)

    print("Building FIFO baseline equity...", flush=True)
    eq_fifo, m_fifo = _build_equity_with_cash_yield(
        tagged_fifo.drop(columns=["ema_dist_at_entry"], errors="ignore"),
        MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
        rank_col=None, cash_yield_annual=0.0,
    )

    print("Building RS-ranked equity...", flush=True)
    eq_rs, m_rs = _build_equity_with_cash_yield(
        tagged_rs.drop(columns=["ema_dist_at_entry"], errors="ignore"),
        MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
        rank_col="rs_score", cash_yield_annual=0.0,
    )

    mar_fifo = float(m_fifo.get("mar", np.nan))
    mar_rs = float(m_rs.get("mar", np.nan))
    cagr_fifo = float(m_fifo.get("cagr", np.nan))
    cagr_rs = float(m_rs.get("cagr", np.nan))
    maxdd_fifo = float(m_fifo.get("max_dd", np.nan))
    maxdd_rs = float(m_rs.get("max_dd", np.nan))

    y2021_fifo = _annual_return(eq_fifo, 2021) if not eq_fifo.empty else np.nan
    y2021_rs = _annual_return(eq_rs, 2021) if not eq_rs.empty else np.nan
    capture_2021 = (y2021_rs / y2021_fifo * 100) if y2021_fifo and y2021_fifo != 0 else np.nan

    kill_mar = mar_rs >= 0.27
    kill_2021 = capture_2021 >= 85.0 if not np.isnan(capture_2021) else False
    p3_pass = kill_mar and kill_2021
    p3_decision = "PASS — proceed" if p3_pass else "FAIL — freeze A3 RS ranking"

    # --- A3: Cash-yield accounting ---
    print("Running cash-yield scenarios...", flush=True)
    cy_results = []
    for cy in CASH_YIELDS:
        eq_cy, m_cy = _build_equity_with_cash_yield(
            tagged_fifo.drop(columns=["ema_dist_at_entry"], errors="ignore"),
            MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
            rank_col=None, cash_yield_annual=cy,
        )
        cy_results.append({
            "cash_yield_pct": cy * 100,
            "mar": float(m_cy.get("mar", np.nan)),
            "cagr": float(m_cy.get("cagr", np.nan)),
            "max_dd": float(m_cy.get("max_dd", np.nan)),
            "n_trades": int(m_cy.get("n_trades", 0)),
        })

    cy_df = pd.DataFrame(cy_results)
    cy_df.to_csv(OUT_DIR / "a3_cash_yield_results.csv", index=False, float_format="%.6f")

    # --- Annual returns comparison ---
    years = list(range(2012, 2027))
    annual_fifo = {yr: _annual_return(eq_fifo, yr) for yr in years}
    annual_rs = {yr: _annual_return(eq_rs, yr) for yr in years}

    # --- Summary output ---
    summary_csv = pd.DataFrame([
        {"mode": "FIFO_baseline", "mar": mar_fifo, "cagr": cagr_fifo, "max_dd": maxdd_fifo,
         "y2021": y2021_fifo, "n_trades": m_fifo.get("n_trades", 0),
         "win_rate": m_fifo.get("hit_rate", np.nan)},
        {"mode": "RS_ranked_40_30_20_10", "mar": mar_rs, "cagr": cagr_rs, "max_dd": maxdd_rs,
         "y2021": y2021_rs, "n_trades": m_rs.get("n_trades", 0),
         "win_rate": m_rs.get("hit_rate", np.nan)},
    ])
    summary_csv.to_csv(OUT_DIR / "p3_rs_vs_fifo.csv", index=False, float_format="%.6f")

    annual_rows = []
    for yr in years:
        annual_rows.append({"year": yr, "fifo": annual_fifo[yr], "rs_ranked": annual_rs[yr]})
    pd.DataFrame(annual_rows).to_csv(OUT_DIR / "p3_annual_returns.csv", index=False, float_format="%.6f")

    # --- Report ---
    annual_table = "\n".join(
        f"| {yr} | {annual_fifo[yr]:+.2%} | {annual_rs[yr]:+.2%} |"
        if not (np.isnan(annual_fifo.get(yr, np.nan)) or np.isnan(annual_rs.get(yr, np.nan)))
        else f"| {yr} | — | — |"
        for yr in years
    )

    cy_table = "\n".join(
        f"| {r['cash_yield_pct']:.0f}% | {r['mar']:.4f} | {r['cagr']:.4f} | {r['max_dd']:.4f} |"
        for _, r in cy_df.iterrows()
    )

    report = f"""# Phase A Results — P3 RS Ranking + Cash-Yield Accounting

Generated: {date.today()}

## A2: P3 RS Ranking Test

**Pre-registered formula (DO NOT TUNE):**
- 40% × 3-month RS vs liquid universe
- 30% × 6-month RS vs liquid universe
- 20% × distance to 52-week high (proximity = better)
- 10% × ADV50 liquidity percentile

### Results

| Mode | MAR | CAGR | MaxDD | 2021 Return | n_trades |
|------|-----|------|-------|-------------|----------|
| FIFO baseline | {mar_fifo:.4f} | {cagr_fifo:.4f} | {maxdd_fifo:.4f} | {y2021_fifo:+.2%} | {int(m_fifo.get('n_trades', 0))} |
| RS ranked (40/30/20/10) | {mar_rs:.4f} | {cagr_rs:.4f} | {maxdd_rs:.4f} | {y2021_rs:+.2%} | {int(m_rs.get('n_trades', 0))} |

### Kill Criteria Check

| Criterion | Required | Actual | Pass? |
|-----------|----------|--------|-------|
| Honest MAR | ≥ 0.27 | {mar_rs:.4f} | {'YES' if kill_mar else 'NO'} |
| 2021 capture | ≥ 85% | {capture_2021:.1f}% | {'YES' if kill_2021 else 'NO'} |

**Decision: {p3_decision}**

### Annual Returns

| Year | FIFO | RS Ranked |
|------|------|-----------|
{annual_table}

## A3: Cash-Yield Accounting

Cash earned on idle capital (FIFO baseline, varying deposit rate).
Label: **portfolio accounting / cash drag reduction** — not trading alpha.

| Cash Yield | MAR | CAGR | MaxDD |
|------------|-----|------|-------|
{cy_table}

VN deposit rate reference: ~5.1-6.5% for 12-24 months (VietinBank Jan 2026).
Conservative haircut applied: testing 2-4% (short-tenor proxy).

## Source

- Canonical engine: `phase_exit_sweep_core.py` (FIFO + EMA20>EMA100)
- P0 realism: `p0_realism_p1_winner.py` (next-bar fills, floor/ceiling, T+2, 0.40% RT)
- RS weights: pre-registered, not tuned
- Config: tp1=none, trail=3.5×ATR, stop=2.0×ATR
"""
    (OUT_DIR / "phase_a_report.md").write_text(report, encoding="utf-8")

    meta = {
        "generated": str(date.today()),
        "rs_weights": RS_WEIGHTS,
        "p3_decision": p3_decision,
        "mar_fifo": mar_fifo,
        "mar_rs": mar_rs,
        "capture_2021_pct": capture_2021,
        "cash_yield_results": cy_results,
    }
    (OUT_DIR / "phase_a_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    print(report)
    print(f"\nWrote results to {OUT_DIR}")


if __name__ == "__main__":
    main()
