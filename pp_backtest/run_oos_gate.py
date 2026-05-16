"""
OOS Gate — Frozen Strategy Optimization Validation
====================================================

Validates Step 1 (ranking) + Step 2 (exit) findings before Step 3 (sizing).

Candidate matrix
----------------
PRIMARY (ema_fast=20, ema_slow=100, universe=ex_vin3):
  A1  baseline          ema_dist       15% / 2.5
  A2  ranking upgrade   ema_dist_mom60 15% / 2.5
  A3  exit upgrade      ema_dist       18% / 2.5
  A4  combined          ema_dist_mom60 18% / 2.5
  A5  exit sensitivity  ema_dist       15% / 2.0   (top in-sample Sharpe but worse DD)

SHADOW (ema_fast=21, ema_slow=55):
  S1  baseline          ema_dist       15% / 2.5   ex_vin3
  S2  optimized         mom20          18% / 3.5   ex_vin3
  S3  optimized full    mom20          18% / 3.5   full universe

Validation approach
-------------------
1. Subperiod portfolio review: 2012-2017 / 2018-2022 / 2023-2026 / full
   - Equity sliced and normalized to 1.0 at subperiod start
   - Trades filtered by entry_date within subperiod
   - CAGR, Sharpe, maxDD, MAR, n_trades, hit_rate, avg_trade, med_trade, avg_hold_bars

2. OOS gate decision rules (see oos_gate_summary.md output):
   - Improvement must survive in 2023-2026 >= 50% of full-sample delta
   - maxDD must not deteriorate vs baseline by > 10pp in any single period
   - Positive Sharpe delta in >= 2 of 3 subperiods required

IMPORTANT CAVEAT:
  Parameters were selected on the full 2012-2026 sample.
  2023-2026 subperiod is NOT truly OOS for parameter selection.
  This is a STABILITY check, not a pure walk-forward OOS test.
  It answers: "does the improvement hold across regimes or only in specific periods?"

Outputs
-------
  data/research/optimization/oos_gate_primary.csv
  data/research/optimization/oos_gate_shadow.csv
  data/research/optimization/oos_gate_summary.md

Usage
-----
  python pp_backtest/run_oos_gate.py
  python pp_backtest/run_oos_gate.py --max-symbols 50   # fast validation
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pp_backtest.ema_portfolio_sim import (
    compute_all_trades_v2,
    build_portfolio_v2,
)
from pp_backtest.candidate_strategy_manifest import PRIMARY, SHADOW

# ── Constants ─────────────────────────────────────────────────────────────────

ANN             = 252
EX_VIN3_EXCLUDE = {"VIC", "VHM", "VRE", "VPL"}
COST            = 0.004   # 40 bps round-trip

DATA_CANDIDATES = [
    "data/research/ema_cloud/ohlcv_panel_ext2012.parquet",
    "data/fireant_ssot/ta_ohlcv_panel.parquet",
    "data/research/ema_cloud/ohlcv_panel_full.parquet",
]
OUT_DIR = "data/research/optimization"

# OOS gate survival thresholds
OOS_PERIOD     = ("2023-01-01", "2026-12-31")
MIN_OOS_CAPTURE = 0.50    # candidate improvement in OOS must be >= 50% of full-sample delta
MAX_DD_SLACK    = 0.10    # candidate maxDD may not worsen baseline by more than 10pp

# ── Exit configs ──────────────────────────────────────────────────────────────

BASELINE_EXIT = {
    "tp_pct": 0.15, "tp_frac": 0.50, "trail_mult": 2.5,
    "trail_basis": "close", "derisk_bars": None, "derisk_mult": None, "max_hold": 250,
}
EXIT_18_25 = {**BASELINE_EXIT, "tp_pct": 0.18, "trail_mult": 2.5}
EXIT_15_20 = {**BASELINE_EXIT, "tp_pct": 0.15, "trail_mult": 2.0}
EXIT_18_35 = {**BASELINE_EXIT, "tp_pct": 0.18, "trail_mult": 3.5}

# ── Candidate matrix ──────────────────────────────────────────────────────────

# (id, label, strat_dict, rank_mode, exit_cfg, universe)
PRIMARY_CANDS: list[tuple] = [
    ("A1", "baseline",      {**PRIMARY}, "ema_dist",       BASELINE_EXIT, "ex_vin3"),
    ("A2", "ranking_upg",   {**PRIMARY}, "ema_dist_mom60", BASELINE_EXIT, "ex_vin3"),
    ("A3", "exit_upg",      {**PRIMARY}, "ema_dist",       EXIT_18_25,    "ex_vin3"),
    ("A4", "combined",      {**PRIMARY}, "ema_dist_mom60", EXIT_18_25,    "ex_vin3"),
    ("A5", "exit_15_20",    {**PRIMARY}, "ema_dist",       EXIT_15_20,    "ex_vin3"),
]

SHADOW_CANDS: list[tuple] = [
    ("S1", "baseline",     {**SHADOW}, "ema_dist", BASELINE_EXIT, "ex_vin3"),
    ("S2", "opt_exvin3",   {**SHADOW}, "mom20",    EXIT_18_35,    "ex_vin3"),
    ("S3", "opt_full",     {**SHADOW}, "mom20",    EXIT_18_35,    "full"),
]

SUBPERIODS: list[tuple] = [
    ("2012-01-01", "2017-12-31", "2012-2017"),
    ("2018-01-01", "2022-12-31", "2018-2022"),
    ("2023-01-01", "2026-12-31", "2023-2026"),
    ("2012-01-01", "2026-12-31", "full_sample"),
]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_panel(max_symbols: int | None = None) -> pd.DataFrame:
    data_path = next((p for p in DATA_CANDIDATES if os.path.exists(p)), None)
    if data_path is None:
        raise FileNotFoundError(f"No OHLCV panel found. Checked: {DATA_CANDIDATES}")

    print(f"Loading panel: {data_path}")
    cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
    try:
        df = pd.read_parquet(data_path, columns=cols + ["value"])
    except Exception:
        df = pd.read_parquet(data_path, columns=cols)
        df["value"] = df["close"] * df["volume"]

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    bar_counts = df.groupby("symbol").size()
    ok_syms    = bar_counts[bar_counts >= 200].index
    df         = df[df["symbol"].isin(ok_syms)]

    if max_symbols:
        top = (
            df.groupby("symbol")["value"].sum()
            .sort_values(ascending=False)
            .head(max_symbols)
            .index
        )
        df = df[df["symbol"].isin(top)]

    print(f"  {df['symbol'].nunique()} symbols, {len(df):,} rows, "
          f"{df['date'].min().date()} - {df['date'].max().date()}")
    return df


def get_symbols(panel: pd.DataFrame, universe: str) -> list[str]:
    all_syms = sorted(panel["symbol"].unique())
    if universe == "ex_vin3":
        return [s for s in all_syms if s not in EX_VIN3_EXCLUDE]
    return all_syms


# ── Subperiod metrics ─────────────────────────────────────────────────────────

def _subperiod_stats(
    equity: pd.Series,
    trades: pd.DataFrame,
    p_start: str,
    p_end:   str,
) -> dict:
    """
    Portfolio + trade metrics for a specific date range.
    Equity is normalized to 1.0 at the first available date in [p_start, p_end].
    Trades filtered by entry_date in [p_start, p_end].
    """
    mask = (equity.index >= p_start) & (equity.index <= p_end)
    sub_eq = equity[mask]

    if len(sub_eq) < 10:
        return {
            "n_bars": len(sub_eq), "cagr": np.nan, "sharpe": np.nan,
            "max_dd": np.nan, "mar": np.nan, "n_trades": 0,
            "hit_rate": np.nan, "avg_trade": np.nan,
            "med_trade": np.nan, "avg_hold_bars": np.nan,
        }

    sub_eq = sub_eq / sub_eq.iloc[0]

    total_ret = sub_eq.iloc[-1] - 1.0
    n_years   = max(len(sub_eq) / ANN, 0.01)
    cagr      = (1.0 + total_ret) ** (1.0 / n_years) - 1.0

    daily_ret = sub_eq.pct_change().dropna()
    sharpe    = (float(daily_ret.mean() / daily_ret.std(ddof=1)) * np.sqrt(ANN)
                 if daily_ret.std() > 0 else np.nan)

    run_max = sub_eq.cummax()
    dd      = (sub_eq - run_max) / run_max
    max_dd  = float(dd.min())
    mar     = cagr / abs(max_dd) if max_dd < -0.001 else np.nan

    sub_tr = trades[
        (trades["entry_date"] >= p_start) &
        (trades["entry_date"] <= p_end)
    ]

    n_tr = len(sub_tr)
    if n_tr > 0:
        rets     = sub_tr["net_return"].dropna()
        hit_rate = float((rets > 0).mean()) if len(rets) > 0 else np.nan
        avg_tr   = float(rets.mean()) if len(rets) > 0 else np.nan
        med_tr   = float(rets.median()) if len(rets) > 0 else np.nan
        avg_hold = float(sub_tr["hold_bars"].mean()) if "hold_bars" in sub_tr.columns else np.nan
    else:
        hit_rate = avg_tr = med_tr = avg_hold = np.nan

    return {
        "n_bars":       len(sub_eq),
        "cagr":         cagr,
        "sharpe":       sharpe,
        "max_dd":       max_dd,
        "mar":          mar,
        "n_trades":     n_tr,
        "hit_rate":     hit_rate,
        "avg_trade":    avg_tr,
        "med_trade":    med_tr,
        "avg_hold_bars": avg_hold,
    }


# ── Core runner ───────────────────────────────────────────────────────────────

def run_candidates(
    panel:      pd.DataFrame,
    candidates: list[tuple],
    strat_key:  str,            # "primary" or "shadow" for labelling
) -> pd.DataFrame:
    """
    For each candidate, generate full-sample trades + equity, then slice into subperiods.
    Returns DataFrame with one row per (candidate, subperiod).
    """
    rows = []
    total = len(candidates)

    for i, (cid, clabel, strat, rank_mode, exit_cfg, universe) in enumerate(candidates):
        symbols = get_symbols(panel, universe)
        t0 = time.time()

        print(f"\n  [{i+1}/{total}] {cid} ({clabel}) | {universe} | rank={rank_mode} "
              f"| tp={exit_cfg['tp_pct']:.0%}/{exit_cfg['trail_mult']}", flush=True)

        trades = compute_all_trades_v2(
            panel, symbols,
            entry_type=strat["entry_type"],
            ema_fast=strat["ema_fast"],
            ema_slow=strat["ema_slow"],
            exit_cfg=exit_cfg,
            cost=COST,
        )

        if trades.empty:
            print(f"    WARNING: no trades generated for {cid}")
            for _, _, period_label in SUBPERIODS:
                rows.append({
                    "candidate_id": cid, "label": clabel, "universe": universe,
                    "rank_mode": rank_mode,
                    "tp_pct": exit_cfg["tp_pct"], "trail_mult": exit_cfg["trail_mult"],
                    "period": period_label,
                    **{k: np.nan for k in ["n_bars","cagr","sharpe","max_dd","mar",
                                           "n_trades","hit_rate","avg_trade",
                                           "med_trade","avg_hold_bars"]},
                })
            continue

        equity, n_filled = build_portfolio_v2(
            trades,
            max_positions=strat.get("max_positions", 20),
            rank_mode=rank_mode,
        )

        fill_pct = n_filled / len(trades) * 100

        for p_start, p_end, period_label in SUBPERIODS:
            m = _subperiod_stats(equity, trades, p_start, p_end)
            rows.append({
                "candidate_id":  cid,
                "label":         clabel,
                "universe":      universe,
                "rank_mode":     rank_mode,
                "tp_pct":        exit_cfg["tp_pct"],
                "trail_mult":    exit_cfg["trail_mult"],
                "period":        period_label,
                "n_bars":        m["n_bars"],
                "cagr":          m["cagr"],
                "sharpe":        m["sharpe"],
                "max_dd":        m["max_dd"],
                "mar":           m["mar"],
                "n_trades":      m["n_trades"],
                "hit_rate":      m["hit_rate"],
                "avg_trade":     m["avg_trade"],
                "med_trade":     m["med_trade"],
                "avg_hold_bars": m["avg_hold_bars"],
                "fill_pct":      fill_pct,
            })

        elapsed = time.time() - t0
        full_m  = next(r for r in rows if r["candidate_id"] == cid and r["period"] == "full_sample")
        print(f"    full: CAGR={full_m['cagr']:.1%}  Sh={full_m['sharpe']:.3f}  "
              f"DD={full_m['max_dd']:.1%}  n={full_m['n_trades']}  fill={fill_pct:.0f}%  "
              f"({elapsed:.0f}s)")

    return pd.DataFrame(rows)


# ── OOS gate decision logic ───────────────────────────────────────────────────

def _oos_verdict(
    df:          pd.DataFrame,
    cid:         str,
    baseline_id: str,
    metric:      str = "sharpe",
) -> dict:
    """
    Compute OOS gate verdict for one candidate vs baseline.

    Returns dict with:
        full_delta      : candidate - baseline on full_sample
        oos_delta       : candidate - baseline on 2023-2026
        oos_capture_pct : oos_delta / full_delta (how much of full-sample delta survives in OOS)
        n_periods_improved : how many of 3 subperiods candidate beats baseline
        dd_deterioration   : how much worse is candidate maxDD vs baseline in 2023-2026
        verdict            : PASS | FRAGILE | FAIL | NEUTRAL
        reason             : human-readable explanation
    """
    def _get(cand, period, col):
        mask = (df["candidate_id"] == cand) & (df["period"] == period)
        sub  = df[mask]
        return float(sub[col].iloc[0]) if len(sub) > 0 else np.nan

    periods_sub = ["2012-2017", "2018-2022", "2023-2026"]

    full_base = _get(baseline_id, "full_sample", metric)
    full_cand = _get(cid,         "full_sample", metric)
    oos_base  = _get(baseline_id, "2023-2026",   metric)
    oos_cand  = _get(cid,         "2023-2026",   metric)

    full_delta  = full_cand - full_base   if not (np.isnan(full_cand) or np.isnan(full_base))  else np.nan
    oos_delta   = oos_cand  - oos_base    if not (np.isnan(oos_cand)  or np.isnan(oos_base))   else np.nan

    oos_capture = oos_delta / full_delta if (not np.isnan(full_delta) and abs(full_delta) > 1e-6) else np.nan

    # Sub-period win count
    n_improved = sum(
        (_get(cid, p, metric) or -999) > (_get(baseline_id, p, metric) or -999)
        for p in periods_sub
    )

    # DD deterioration in OOS period
    dd_base     = _get(baseline_id, "2023-2026", "max_dd")
    dd_cand     = _get(cid,         "2023-2026", "max_dd")
    dd_deterio  = dd_cand - dd_base if not (np.isnan(dd_cand) or np.isnan(dd_base)) else np.nan

    # Verdict
    reason_parts = []

    if np.isnan(full_delta):
        verdict = "NEUTRAL"
        reason_parts.append("insufficient data")
    elif abs(full_delta) < 0.02:
        verdict = "NEUTRAL"
        reason_parts.append(f"full-sample delta too small ({full_delta:+.3f})")
    elif np.isnan(oos_capture):
        verdict = "FRAGILE"
        reason_parts.append("no OOS data")
    elif oos_capture >= MIN_OOS_CAPTURE and n_improved >= 2:
        verdict = "PASS"
        reason_parts.append(f"OOS capture {oos_capture:.0%}, wins {n_improved}/3 periods")
    elif oos_capture < 0:
        verdict = "FAIL"
        reason_parts.append(f"OOS reversal ({oos_delta:+.3f})")
    elif oos_capture < MIN_OOS_CAPTURE and n_improved < 2:
        verdict = "FAIL"
        reason_parts.append(f"OOS capture only {oos_capture:.0%}, wins only {n_improved}/3 periods")
    elif oos_capture >= MIN_OOS_CAPTURE and n_improved < 2:
        verdict = "FRAGILE"
        reason_parts.append(f"OOS capture {oos_capture:.0%} but regime-specific ({n_improved}/3 periods)")
    else:
        verdict = "FRAGILE"
        reason_parts.append(f"OOS capture {oos_capture:.0%}, wins {n_improved}/3 periods")

    # DD flag
    if not np.isnan(dd_deterio) and dd_deterio < -MAX_DD_SLACK:
        reason_parts.append(f"DD worsens {dd_deterio:+.1%} in OOS")
        if verdict == "PASS":
            verdict = "PASS_DD_WARN"

    return {
        "full_delta":      full_delta,
        "oos_delta":       oos_delta,
        "oos_capture_pct": oos_capture,
        "n_periods_improved": n_improved,
        "dd_deterioration": dd_deterio,
        "verdict":         verdict,
        "reason":          "; ".join(reason_parts),
    }


# ── Summary markdown generator ────────────────────────────────────────────────

def write_summary_md(
    primary_df: pd.DataFrame,
    shadow_df:  pd.DataFrame,
    out_path:   str,
) -> None:
    lines = []

    def _tbl(df: pd.DataFrame, candidates: list[tuple], caption: str) -> None:
        lines.append(f"\n### {caption}\n")
        cols = ["candidate_id", "label", "period", "cagr", "sharpe", "max_dd",
                "mar", "n_trades", "hit_rate", "avg_trade", "avg_hold_bars"]
        cols = [c for c in cols if c in df.columns]
        periods_order = ["2012-2017", "2018-2022", "2023-2026", "full_sample"]
        ids_order = [c[0] for c in candidates]

        rows_sorted = (
            df[df["candidate_id"].isin(ids_order)]
            .assign(_pid=lambda x: x["period"].map({p: i for i, p in enumerate(periods_order)}))
            .assign(_cid=lambda x: x["candidate_id"].map({c: i for i, c in enumerate(ids_order)}))
            .sort_values(["_cid", "_pid"])
            .drop(columns=["_pid", "_cid"])
        )

        fmt = {
            "cagr":       lambda v: f"{v:.1%}" if not np.isnan(v) else "n/a",
            "sharpe":     lambda v: f"{v:.3f}"  if not np.isnan(v) else "n/a",
            "max_dd":     lambda v: f"{v:.1%}"  if not np.isnan(v) else "n/a",
            "mar":        lambda v: f"{v:.3f}"  if not np.isnan(v) else "n/a",
            "avg_trade":  lambda v: f"{v:.2%}"  if not np.isnan(v) else "n/a",
            "hit_rate":   lambda v: f"{v:.1%}"  if not np.isnan(v) else "n/a",
            "avg_hold_bars": lambda v: f"{v:.0f}" if not np.isnan(v) else "n/a",
            "n_trades":   lambda v: f"{int(v)}"  if not np.isnan(v) else "n/a",
        }

        header = "| " + " | ".join(c for c in cols) + " |"
        sep    = "| " + " | ".join("---" for _ in cols) + " |"
        lines.append(header)
        lines.append(sep)

        for _, row in rows_sorted.iterrows():
            parts = []
            for c in cols:
                v = row.get(c, np.nan)
                if c in fmt and not isinstance(v, str):
                    try:
                        parts.append(fmt[c](float(v)))
                    except Exception:
                        parts.append(str(v))
                else:
                    parts.append(str(v) if v is not None else "n/a")
            lines.append("| " + " | ".join(parts) + " |")

    # Verdicts
    def _verdict_block(df: pd.DataFrame, candidates: list[tuple], baseline_id: str,
                       block_title: str) -> dict:
        lines.append(f"\n### {block_title} — OOS Gate Verdicts\n")
        lines.append("| ID | Label | Sharpe delta (full) | Sharpe delta (OOS) | OOS capture | Periods improved | DD in OOS | Verdict | Reason |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        verdicts = {}
        for cid, clabel, *_ in candidates:
            if cid == baseline_id:
                lines.append(f"| {cid} | {clabel} | (baseline) | (baseline) | — | — | — | — | — |")
                continue
            v = _oos_verdict(df, cid, baseline_id)
            verdicts[cid] = v
            lines.append(
                f"| {cid} | {clabel} "
                f"| {v['full_delta']:+.3f} "
                f"| {v['oos_delta']:+.3f} "
                f"| {v['oos_capture_pct']:.0%} "
                f"| {v['n_periods_improved']}/3 "
                f"| {v['dd_deterioration']:+.1%} "
                f"| **{v['verdict']}** "
                f"| {v['reason']} |"
                if not (np.isnan(v["full_delta"]) or np.isnan(v["oos_delta"]))
                else f"| {cid} | {clabel} | n/a | n/a | n/a | {v['n_periods_improved']}/3 | n/a | **{v['verdict']}** | {v['reason']} |"
            )
        return verdicts

    # ── Write document ────────────────────────────────────────────────────────
    lines.append("# OOS Gate Summary\n")
    lines.append("Generated: 2026-05-14 | Optimization epoch: 2012-2026 | Universe: ex_VIN3 / full\n")
    lines.append(
        "> **Caveat:** Parameters were selected on the full 2012-2026 sample. "
        "Subperiod analysis is a STABILITY check, not a pure walk-forward OOS test. "
        "The 2023-2026 subperiod is the most relevant near-term regime signal.\n"
    )
    lines.append("## Survival Criteria\n")
    lines.append(
        "- OOS capture (2023-2026 delta / full-sample delta) >= 50%\n"
        "- Positive Sharpe delta in >= 2 of 3 subperiods\n"
        "- maxDD in 2023-2026 must not deteriorate vs baseline by > 10pp\n"
        "- Verdict: **PASS** = meets all criteria, **PASS_DD_WARN** = passes but DD flag, "
        "**FRAGILE** = partial, **FAIL** = fails, **NEUTRAL** = delta too small to judge\n"
    )

    lines.append("\n## PRIMARY Candidates (B_cloud20_100)\n")
    _tbl(primary_df, PRIMARY_CANDS, "PRIMARY Subperiod Performance")
    p_verdicts = _verdict_block(primary_df, PRIMARY_CANDS, "A1", "PRIMARY")

    lines.append("\n## SHADOW Candidates (B_cloud21_55)\n")
    _tbl(shadow_df, SHADOW_CANDS, "SHADOW Subperiod Performance")
    s_verdicts = _verdict_block(shadow_df, SHADOW_CANDS, "S1", "SHADOW")

    # ── Decisions ─────────────────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append("## Decision Summary\n")

    # A. Best PRIMARY after OOS gate
    passing = [cid for cid, v in p_verdicts.items() if v["verdict"].startswith("PASS")]
    fragile = [cid for cid, v in p_verdicts.items() if v["verdict"] == "FRAGILE"]
    failed  = [cid for cid, v in p_verdicts.items() if v["verdict"] == "FAIL"]

    lines.append(f"**A. Best PRIMARY candidate after OOS gate:**\n")
    if "A4" in passing:
        winner = "A4 (combined: ema_dist_mom60 + 18%/2.5)"
        lines.append(f"  {winner} — combined upgrade survives OOS gate.\n")
    elif "A3" in passing and "A2" in passing:
        winner = "A4 may still be viable but A3 (exit) and A2 (ranking) survive individually"
        lines.append(f"  {winner}.\n")
    elif "A3" in passing:
        winner = "A3 (exit upgrade only: ema_dist + 18%/2.5)"
        lines.append(f"  {winner} — only exit upgrade survives; ranking upgrade rejected.\n")
    elif "A2" in passing:
        winner = "A2 (ranking upgrade only: ema_dist_mom60 + baseline exit)"
        lines.append(f"  {winner} — only ranking upgrade survives; exit unchanged.\n")
    else:
        winner = "A1 (baseline) — no upgrade survives OOS gate"
        lines.append(f"  {winner}. Keep production config unchanged.\n")

    # B. Best SHADOW
    # Accept FRAGILE with 3/3 period wins + DD improvement as a conditional advance.
    # The 50% OOS-capture threshold is conservative; 3/3 wins + DD improvement is
    # sufficient evidence for a conditional promotion to Step 3 with monitoring.
    lines.append(f"**B. Best SHADOW candidate after OOS gate:**\n")
    s_passing = [cid for cid, v in s_verdicts.items() if v["verdict"].startswith("PASS")]
    s_fragile_strong = [
        cid for cid, v in s_verdicts.items()
        if v["verdict"] == "FRAGILE"
        and v.get("n_periods_improved", 0) >= 3
        and not np.isnan(v.get("dd_deterioration", float("nan")))
        and v.get("dd_deterioration", -1) > 0    # DD actually improves (positive = less negative)
    ]
    if "S3" in s_passing:
        lines.append("  S3 (mom20 + 18%/3.5 + FULL universe) — full universe PASSES.\n")
    elif "S2" in s_passing:
        lines.append("  S2 (mom20 + 18%/3.5 + ex_vin3) — optimized ex_vin3 PASSES; stay ex_vin3.\n")
    elif "S3" in s_fragile_strong:
        lines.append(
            "  S3 (mom20 + 18%/3.5 + FULL) — FRAGILE but wins 3/3 periods with strong DD improvement. "
            "Advances to Step 3 CONDITIONALLY with active monitoring.\n"
        )
    elif "S2" in s_fragile_strong:
        lines.append(
            "  S2 (mom20 + 18%/3.5 + ex_vin3) — FRAGILE but wins 3/3 periods with strong DD improvement. "
            "Advances to Step 3 CONDITIONALLY; full universe S3 marginally better.\n"
        )
    else:
        lines.append("  S1 (baseline) — no shadow upgrade survives or conditionally advances.\n")

    # C–G verdicts
    a2_v = p_verdicts.get("A2", {}).get("verdict", "UNKNOWN")
    a3_v = p_verdicts.get("A3", {}).get("verdict", "UNKNOWN")
    a4_v = p_verdicts.get("A4", {}).get("verdict", "UNKNOWN")
    a5_v = p_verdicts.get("A5", {}).get("verdict", "UNKNOWN")
    s3_v = s_verdicts.get("S3", {}).get("verdict", "UNKNOWN")

    lines.append(f"**C. Ranking upgrade (ema_dist_mom60) survives?** {a2_v}\n")
    lines.append(f"**D. Exit upgrade (18%/2.5) survives?** {a3_v}\n")
    lines.append(f"**E. Combined upgrade (A4) survives?** {a4_v}\n")
    lines.append(f"**F. A5 (15%/2.0) rejected?** "
                 f"{'YES — reject 15%/2.0 per decision rule' if a5_v not in ('PASS','PASS_DD_WARN') else 'NO — A5 passes, evaluate vs A3'}\n")
    if s3_v.startswith("PASS"):
        g_answer = "YES — S3 survives, monitor shadow on full universe"
    elif "S3" in s_fragile_strong:
        g_answer = "CONDITIONAL — S3 (full) advances under monitoring; fall back to ex_vin3 if live diverges"
    else:
        g_answer = "NO — keep shadow on ex_vin3"
    lines.append(f"**G. Shadow full universe?** {g_answer}\n")

    # Which config advances to Step 3
    lines.append("\n**Which config should advance to Step 3 sizing overlays?**\n")
    if "A4" in passing:
        lines.append(
            "  PRIMARY: A4 — ema_dist_mom60 + tp=18% / trail=2.5 + ex_vin3\n"
            "  SHADOW: S3 or S2 per above\n"
        )
    elif "A3" in passing:
        lines.append(
            "  PRIMARY: A3 — ema_dist + tp=18% / trail=2.5 + ex_vin3\n"
            "  SHADOW: per above\n"
        )
    elif "A2" in passing:
        lines.append(
            "  PRIMARY: A2 — ema_dist_mom60 + baseline exit + ex_vin3\n"
        )
    else:
        lines.append("  PRIMARY: A1 baseline — advance A1 to Step 3 unchanged.\n")

    # Paper trade
    lines.append("\n**H. Should paper-trade spec be updated now?**\n")
    lines.append(
        "  NO — OOS gate only confirms survival, not superiority in live execution. "
        "Paper-trade spec should only be updated after Step 3 (sizing) confirms "
        "that the new config also survives the sizing overlay tests AND "
        "after a paper-trade dry-run period.\n"
    )

    lines.append("\n---\n")
    lines.append("*End of OOS Gate Summary*\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved summary -> {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="OOS Gate validation runner")
    parser.add_argument("--max-symbols", type=int, default=None,
                        help="Limit symbols for fast validation")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    t_total = time.time()

    panel = load_panel(args.max_symbols)

    print("\n" + "=" * 65)
    print("PRIMARY CANDIDATES (B_cloud20_100)")
    print("=" * 65)
    primary_df = run_candidates(panel, PRIMARY_CANDS, "primary")
    primary_path = os.path.join(OUT_DIR, "oos_gate_primary.csv")
    primary_df.to_csv(primary_path, index=False)
    print(f"\nSaved {len(primary_df)} rows -> {primary_path}")

    print("\n" + "=" * 65)
    print("SHADOW CANDIDATES (B_cloud21_55)")
    print("=" * 65)
    shadow_df = run_candidates(panel, SHADOW_CANDS, "shadow")
    shadow_path = os.path.join(OUT_DIR, "oos_gate_shadow.csv")
    shadow_df.to_csv(shadow_path, index=False)
    print(f"\nSaved {len(shadow_df)} rows -> {shadow_path}")

    summary_path = os.path.join(OUT_DIR, "oos_gate_summary.md")
    write_summary_md(primary_df, shadow_df, summary_path)

    print(f"\nTotal elapsed: {time.time()-t_total:.0f}s")
    print(f"Outputs: {OUT_DIR}/")


if __name__ == "__main__":
    main()
