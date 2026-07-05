"""Shared harness for Cortex Book #1 fixed-fractional risk-per-trade sizing test."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pp_backtest.d1_capital_based_validation import PreparedTrade, _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    RESEARCH_LABEL,
    apply_size,
    assert_frozen_a3,
    prepare_trades_with_size,
    run_capital_sim,
    signal_stream,
)
from pp_backtest.p0_realism_p1_winner import _build_honest_cache
from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
)
from pp_backtest.p3_rs_isoos_validation import WINDOWS
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_last_months,
    slice_equity_years,
)

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "research" / "cortex_book1_sizing"
PREREG = REPO / "knowledge" / "backtests" / "2026-07-04_cortex_book1_sizingrule_prereg.md"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-04_cortex_book1_sizingrule_gates_addendum.md"

INITIAL_STOP_ATR = 2.0
RISK_PCT_CANDIDATES = (0.0125, 0.0175, 0.025)
G1A_MARGIN = 0.050
G1B_FLOOR = 0.400

IS_WINDOW = WINDOWS["IS_2013_2019"]
OOS_WINDOW = WINDOWS["OOS_2020_2026"]
PANEL_START = "2012-01-03"
PANEL_END = DATA_END


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%" if np.isfinite(x) else "n/a"


def build_entry_price_atr_map(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], tuple[float, float]]:
    """Map (symbol, entry_date) -> (entry_price, atr14) from honest-trade cache."""
    cache = _build_honest_cache(panel)
    out: dict[tuple[str, pd.Timestamp], tuple[float, float]] = {}
    for sym, data in cache.items():
        dates = pd.to_datetime(data["dates"])
        close = data["close"]
        open_arr = data["open"]
        atr_arr = data["atr"]
        for si in data["sig_idxs"]:
            entry_i = si + 1
            if entry_i >= len(dates):
                continue
            entry_dt = pd.Timestamp(dates[entry_i]).normalize()
            ep1 = float(open_arr[entry_i])
            atr = float(atr_arr[entry_i])
            if ep1 <= 0 or not np.isfinite(atr) or atr <= 0:
                continue
            out[(sym, entry_dt)] = (ep1, atr)
    return out


def prepare_risk_pct_trades(
    trades: pd.DataFrame,
    price_atr_map: dict[tuple[str, pd.Timestamp], tuple[float, float]],
    risk_pct: float,
    rank_col: str = "rs_score",
) -> list[PreparedTrade]:
    """Fixed-fractional sizing: target_w = risk_pct / stop_distance_pct, capped like baseline."""
    if trades.empty:
        return []
    df = trades.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    base_w = 1.0 / MAX_POSITIONS
    tf = df["total_frac"].astype(float).fillna(0.5) if "total_frac" in df.columns else pd.Series(0.5, index=df.index)
    gk = df["has_gk"].astype(bool) if "has_gk" in df.columns else pd.Series(False, index=df.index)
    gk_factor = gk.map(lambda x: GK_MULT if x else 1.0)
    slot_cap = (gk_factor * base_w).clip(upper=base_w * GK_MULT) * tf
    min_w = 100_000 / PORTFOLIO_VND
    rank_vals = df[rank_col].astype(float) if rank_col in df.columns else pd.Series(0.0, index=df.index)
    out: list[PreparedTrade] = []
    for i, row in df.iterrows():
        sym = str(row["symbol"])
        entry_dt = pd.Timestamp(row["entry_date"]).normalize()
        px_atr = price_atr_map.get((sym, entry_dt))
        if px_atr is None:
            continue
        entry_price, atr = px_atr
        stop_price = entry_price - INITIAL_STOP_ATR * atr
        stop_dist = entry_price - stop_price
        if stop_dist <= 0 or entry_price <= 0:
            continue
        risk_w = risk_pct * entry_price / stop_dist
        w = float(min(risk_w, slot_cap.loc[i]))
        if "adv50_value" in df.columns:
            adv = float(row.get("adv50_value") or 0)
            if adv > 0:
                adv_cap = adv * ADV_PARTICIPATION / PORTFOLIO_VND
                w = min(w, adv_cap)
        w = w * float(tf.loc[i])
        if w < min_w:
            continue
        out.append(
            PreparedTrade(
                trade_id=int(i),
                sleeve="A3",
                entry_date=entry_dt,
                exit_date=pd.Timestamp(row["exit_date"]).normalize(),
                net_return=float(row["net_return"]),
                target_w=w,
                rank=float(rank_vals.loc[i]) if np.isfinite(rank_vals.loc[i]) else 0.0,
                entry_year=int(entry_dt.year),
            )
        )
    return out


def evaluate_gates(
    m_base_oos: dict[str, float],
    m_cand_oos: dict[str, float],
    frozen_ok: bool,
) -> tuple[list[dict], str]:
    g1a = (
        np.isfinite(m_cand_oos["mar"])
        and np.isfinite(m_base_oos["mar"])
        and m_cand_oos["mar"] >= m_base_oos["mar"] + G1A_MARGIN
    )
    g1b = np.isfinite(m_cand_oos["mar"]) and m_cand_oos["mar"] >= G1B_FLOOR
    both_neg = (
        np.isfinite(m_base_oos["mar"])
        and np.isfinite(m_cand_oos["mar"])
        and m_base_oos["mar"] < 0
        and m_cand_oos["mar"] < 0
    )
    details = [
        {
            "id": "G1a",
            "criterion": f"OOS MAR >= baseline OOS MAR + {G1A_MARGIN:.3f}",
            "result": f"cand {m_cand_oos['mar']:.4f} vs base {m_base_oos['mar']:.4f} (need +{G1A_MARGIN:.3f})",
            "pass": g1a,
        },
        {
            "id": "G1b",
            "criterion": f"OOS MAR >= {G1B_FLOOR:.3f} absolute floor",
            "result": f"{m_cand_oos['mar']:.4f}",
            "pass": g1b,
        },
        {
            "id": "Frozen-A3",
            "criterion": "Entry stream identical to baseline",
            "result": "match" if frozen_ok else "MISMATCH",
            "pass": frozen_ok,
        },
        {
            "id": "Neg-OOS-cap",
            "criterion": "Both baseline and candidate OOS MAR negative",
            "result": "yes" if both_neg else "no",
            "pass": not both_neg,
        },
    ]
    if both_neg:
        verdict = "CONDITIONAL-ADVANCE" if g1a and g1b and frozen_ok else "FAIL"
    elif g1a and g1b and frozen_ok:
        verdict = "ADVANCE"
    else:
        verdict = "FAIL"
    return details, verdict


def write_report(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Cortex Book #1 — Fixed-Fractional Risk-Per-Trade Sizing",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG.relative_to(REPO)}`",
        f"**Gate addendum:** `{GATES_ADDENDUM.relative_to(REPO)}`",
        "",
        "## Window",
        "",
        f"- Panel start (actual): **{PANEL_START}**",
        f"- Panel end: **{PANEL_END}**",
        f"- Primary OOS gates: **{OOS_WINDOW[0]}–{OOS_WINDOW[1]}**",
        f"- Stop rule: entry − {INITIAL_STOP_ATR}×ATR14 (P1 honest initial stop)",
        "",
        "## Baseline (A3 P1 honest + D4 + D3 @ 1.25/0.75 slot sizing)",
        "",
        f"- Full MAR **{meta['baseline_full']['mar']:.4f}**",
        f"- Full MaxDD **{_fmt_pct(meta['baseline_full']['max_dd'])}**",
        f"- Full CAGR **{_fmt_pct(meta['baseline_full']['cagr'])}**",
        f"- OOS MAR **{meta['baseline_oos']['mar']:.4f}**",
        f"- OOS MaxDD **{_fmt_pct(meta['baseline_oos']['max_dd'])}**",
        f"- OOS 12m MAR (diagnostic) **{meta['baseline_oos_12m']['mar']:.4f}**",
        "",
        "## Gate thresholds (pre-registered)",
        "",
        f"- G1a margin: **+{G1A_MARGIN:.3f}** MAR vs baseline OOS",
        f"- G1b floor: **{G1B_FLOOR:.3f}** absolute OOS MAR",
        "",
    ]
    for cand in meta["candidates"]:
        lines.extend([
            f"## Candidate — risk_pct {cand['risk_pct_label']}",
            "",
            f"**Verdict: {cand['verdict']}**",
            "",
            "| Metric | Baseline | Candidate |",
            "|--------|----------|-----------|",
            f"| Full MAR | {meta['baseline_full']['mar']:.4f} | {cand['full']['mar']:.4f} |",
            f"| Full MaxDD | {_fmt_pct(meta['baseline_full']['max_dd'])} | {_fmt_pct(cand['full']['max_dd'])} |",
            f"| Full CAGR | {_fmt_pct(meta['baseline_full']['cagr'])} | {_fmt_pct(cand['full']['cagr'])} |",
            f"| OOS MAR | {meta['baseline_oos']['mar']:.4f} | {cand['oos']['mar']:.4f} |",
            f"| OOS MaxDD | {_fmt_pct(meta['baseline_oos']['max_dd'])} | {_fmt_pct(cand['oos']['max_dd'])} |",
            f"| OOS CAGR | {_fmt_pct(meta['baseline_oos']['cagr'])} | {_fmt_pct(cand['oos']['cagr'])} |",
            "",
            "| Gate | Criterion | Pass |",
            "|------|-----------|------|",
        ])
        for g in cand["gates"]:
            lines.append(f"| {g['id']} | {g['criterion']} | {'PASS' if g['pass'] else 'FAIL'} |")
        lines.append("")
    lines.extend([
        "### Notes",
        "- Research-only simulation; does not import `sizing_policy.py`.",
        "- Baseline uses operational D3 sector slot multipliers; candidates use fixed-fractional risk-per-trade only.",
        "- Realism: P1 honest execution (T+2, floor/ceiling locks, ADV caps, 40bps RT costs).",
        "- Does not advance vn-trading-advisor session counter (CALIBRATION activity).",
        "",
    ])
    (OUT_DIR / "cortex_book1_sizing_report.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT_DIR / "cortex_book1_sizing_meta.json").write_text(
        json.dumps(meta, indent=2, default=str),
        encoding="utf-8",
    )
