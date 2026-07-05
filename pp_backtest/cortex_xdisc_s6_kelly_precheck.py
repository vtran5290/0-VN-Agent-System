#!/usr/bin/env python3
"""
Cross-Discipline S6 — Kelly fraction distribution diagnostic (pre-check).

Pre-registration: knowledge/backtests/2026-07-05_cortex_xdisc_s6_stone_kelly_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    python pp_backtest/cortex_xdisc_s6_kelly_precheck.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.phase_exit_sweep_core import ADV_PARTICIPATION, MAX_POSITIONS, PORTFOLIO_VND
from pp_backtest.sprint2b_common import build_baseline_stack

IS_START = pd.Timestamp("2012-01-01")
IS_END = pd.Timestamp("2019-12-31")
OOS_START = pd.Timestamp("2020-01-01")
OOS_END = pd.Timestamp("2026-07-03")
SLOT_CAP = 1.0 / MAX_POSITIONS  # 0.05
GATE1_MIN_FRAC = 0.15
GATE2_MIN_CV = 0.10
N_DECILES = 10
OUT_PATH = REPO / "knowledge" / "backtests" / "2026-07-05_s6_kelly_distribution_precheck.md"


def _kelly_full(p: float, w: float, l: float) -> float:
    """Full Kelly f* = (p*W - (1-p)*L) / W."""
    if w <= 0 or not np.isfinite(p):
        return np.nan
    q = 1.0 - p
    f = (p * w - q * l) / w
    return max(f, 0.0)


def _bin_stats(returns: np.ndarray) -> tuple[float, float, float]:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    p = len(wins) / len(returns) if len(returns) else 0.0
    w = float(np.mean(wins)) if len(wins) else 0.0
    l = float(np.mean(np.abs(losses))) if len(losses) else 0.0
    return p, w, l


def _apply_adv_cap(weight: float, adv50: float) -> float:
    if adv50 <= 0:
        return weight
    adv_cap = adv50 * ADV_PARTICIPATION / PORTFOLIO_VND
    return min(weight, adv_cap)


def _histogram_buckets(values: np.ndarray) -> dict[str, float]:
    """Return % in each bucket for pre-cap quarter-Kelly."""
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return {k: 0.0 for k in ["lt_1", "1_3", "3_5", "5_10", "gt_10"]}
    n = len(v)
    return {
        "lt_1": 100.0 * (v < 0.01).sum() / n,
        "1_3": 100.0 * ((v >= 0.01) & (v < 0.03)).sum() / n,
        "3_5": 100.0 * ((v >= 0.03) & (v < 0.05)).sum() / n,
        "5_10": 100.0 * ((v >= 0.05) & (v < 0.10)).sum() / n,
        "gt_10": 100.0 * (v >= 0.10).sum() / n,
    }


def run_s6_kelly_precheck() -> dict:
    print("S6 Kelly distribution pre-check", flush=True)
    stack = build_baseline_stack()
    trades = stack["base_trades"].copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["signal_date"] = pd.to_datetime(trades.get("signal_date", trades["entry_date"]))

    if "rs_score" not in trades.columns:
        raise RuntimeError("rs_score missing from baseline trades")

    # IS decile boundaries from rs_score
    is_trades = trades[
        (trades["entry_date"] >= IS_START) & (trades["entry_date"] <= IS_END)
    ].copy()
    oos_trades = trades[
        (trades["entry_date"] >= OOS_START) & (trades["entry_date"] <= OOS_END)
    ].copy()

    is_trades = is_trades[np.isfinite(is_trades["rs_score"])]
    oos_trades = oos_trades[np.isfinite(oos_trades["rs_score"])]

    # Decile edges from IS (include min/max)
    decile_edges = np.quantile(
        is_trades["rs_score"].values,
        np.linspace(0, 1, N_DECILES + 1),
    )
    # Ensure strictly increasing edges for pd.cut
    for i in range(1, len(decile_edges)):
        if decile_edges[i] <= decile_edges[i - 1]:
            decile_edges[i] = decile_edges[i - 1] + 1e-9

    def assign_decile(scores: pd.Series) -> pd.Series:
        return pd.cut(
            scores,
            bins=decile_edges,
            labels=range(N_DECILES),
            include_lowest=True,
        ).astype(float)

    is_trades["decile"] = assign_decile(is_trades["rs_score"])
    oos_trades["decile"] = assign_decile(oos_trades["rs_score"])

    # Kelly per IS decile
    bin_kelly_full: dict[int, float] = {}
    bin_kelly_quarter: dict[int, float] = {}
    for d in range(N_DECILES):
        sub = is_trades[is_trades["decile"] == d]
        if len(sub) < 5:
            bin_kelly_full[d] = np.nan
            bin_kelly_quarter[d] = np.nan
            continue
        rets = sub["net_return"].astype(float).values
        p, w, l = _bin_stats(rets)
        fk = _kelly_full(p, w, l)
        bin_kelly_full[d] = fk
        bin_kelly_quarter[d] = fk / 4.0 if np.isfinite(fk) else np.nan

    # Apply to OOS
    pre_cap_q: list[float] = []
    pre_cap_full: list[float] = []
    post_cap_weights: list[float] = []
    adv_vals = oos_trades.get("adv50_value", pd.Series(0.0, index=oos_trades.index))

    for idx, row in oos_trades.iterrows():
        d = int(row["decile"]) if np.isfinite(row["decile"]) else -1
        fq = bin_kelly_quarter.get(d, np.nan)
        ff = bin_kelly_full.get(d, np.nan)
        if not np.isfinite(fq):
            fq = 0.0
        if not np.isfinite(ff):
            ff = 0.0
        pre_cap_q.append(fq)
        pre_cap_full.append(ff)
        slot_capped = min(fq, SLOT_CAP)
        adv = float(adv_vals.loc[idx]) if idx in adv_vals.index else 0.0
        final_w = _apply_adv_cap(slot_capped, adv)
        post_cap_weights.append(final_w)

    pre_cap_q_arr = np.array(pre_cap_q)
    pre_cap_full_arr = np.array(pre_cap_full)
    post_cap_arr = np.array(post_cap_weights)

    frac_below_5_q = float((pre_cap_q_arr < SLOT_CAP).mean())
    frac_below_5_full = float((pre_cap_full_arr < SLOT_CAP).mean())
    mean_w = float(np.mean(post_cap_arr)) if len(post_cap_arr) else 0.0
    std_w = float(np.std(post_cap_arr)) if len(post_cap_arr) else 0.0
    cv = std_w / mean_w if mean_w > 0 else 0.0

    hist_q = _histogram_buckets(pre_cap_q_arr)
    hist_full = _histogram_buckets(pre_cap_full_arr)

    gate1_pass = frac_below_5_q >= GATE1_MIN_FRAC
    gate2_pass = cv > GATE2_MIN_CV

    if frac_below_5_q < 0.05:
        verdict = "VN-SUBSUMED"
    elif gate1_pass and gate2_pass:
        verdict = "EXPRESSIBLE"
    elif 0.05 <= frac_below_5_q < GATE1_MIN_FRAC:
        verdict = "BORDERLINE"
    else:
        verdict = "BORDERLINE" if frac_below_5_q >= 0.05 else "VN-SUBSUMED"

    print(f"  OOS instances: {len(oos_trades)}", flush=True)
    print(f"  Fraction pre-cap q-Kelly < 5%: {100*frac_below_5_q:.1f}%", flush=True)
    print(f"  Post-cap CV: {cv:.3f}", flush=True)
    print(f"  VERDICT: {verdict}", flush=True)

    lines = [
        "# S6 KELLY DISTRIBUTION PRE-CHECK REPORT",
        "",
        f"**Generated:** {date.today()}",
        f"**IS window (bin estimation):** {IS_START.date()} → {IS_END.date()}",
        f"**OOS window (distribution):** {OOS_START.date()} → {OOS_END.date()}",
        f"**Signal strength proxy:** rs_score decile (IS boundaries)",
        f"**Slot cap:** {SLOT_CAP:.2%} | **ADV participation:** {ADV_PARTICIPATION:.0%}",
        "",
        "```",
        "S6 KELLY DISTRIBUTION PRE-CHECK REPORT",
        f"Total OOS signal instances: {len(oos_trades)}",
        "Pre-cap quarter-Kelly distribution:",
        f"  < 1%: {hist_q['lt_1']:.1f}%",
        f"  1-3%: {hist_q['1_3']:.1f}%",
        f"  3-5%: {hist_q['3_5']:.1f}%",
        f"  5-10%: {hist_q['5_10']:.1f}%",
        f"  > 10%: {hist_q['gt_10']:.1f}%",
        f"Fraction with pre-cap quarter-Kelly < 5%: {100*frac_below_5_q:.1f}%",
        f"Post-cap weight CV: {cv:.3f}",
        f"Full-Kelly also computed: fraction < 5% = {100*frac_below_5_full:.1f}%",
        f"PRE-CHECK GATE 1 (≥15% mass below 5%): {'PASS' if gate1_pass else 'FAIL'}",
        f"PRE-CHECK GATE 2 (CV > 0.10): {'PASS' if gate2_pass else 'FAIL'}",
        f"VERDICT: {verdict}",
        "```",
        "",
        "## Full-Kelly histogram (pre-cap)",
        "",
        f"| Bucket | % |",
        f"|--------|---|",
        f"| < 1% | {hist_full['lt_1']:.1f}% |",
        f"| 1-3% | {hist_full['1_3']:.1f}% |",
        f"| 3-5% | {hist_full['3_5']:.1f}% |",
        f"| 5-10% | {hist_full['5_10']:.1f}% |",
        f"| > 10% | {hist_full['gt_10']:.1f}% |",
        "",
        "## IS decile → quarter-Kelly mapping",
        "",
        "| Decile | IS n | q-Kelly | full-Kelly |",
        "|--------|------|---------|------------|",
    ]
    for d in range(N_DECILES):
        n_is = int((is_trades["decile"] == d).sum())
        fq = bin_kelly_quarter.get(d, np.nan)
        ff = bin_kelly_full.get(d, np.nan)
        fq_s = f"{fq:.4f}" if np.isfinite(fq) else "n/a"
        ff_s = f"{ff:.4f}" if np.isfinite(ff) else "n/a"
        lines.append(f"| {d} | {n_is} | {fq_s} | {ff_s} |")

    lines.extend([
        "",
        f"**VERDICT: {verdict}**",
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {OUT_PATH}", flush=True)
    return {
        "verdict": verdict,
        "frac_below_5_q": frac_below_5_q,
        "cv": cv,
        "gate1_pass": gate1_pass,
        "gate2_pass": gate2_pass,
    }


def main() -> None:
    run_s6_kelly_precheck()


if __name__ == "__main__":
    main()
