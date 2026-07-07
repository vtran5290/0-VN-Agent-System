#!/usr/bin/env python3
"""
B_cloud S-Filter Research — Track B.

Tests whether S1 (52wk-high proximity) and S2 (breakout volume) filters
add value under B_cloud's exit mode (partial_tp) and portfolio constraints.

Background:
    S1 and S2 were validated on the A3_RS pipeline (cortex_book2_s1_52wkhi.py,
    cortex_book2_s2_volume.py). Those results (A3 OOS MAR 2.4804 for S2) are NOT
    valid evidence for B_cloud promotion. This script re-runs the same research on
    the B_cloud signal universe using B_cloud's exit mode.

    B_cloud PRIMARY (EMA20/100, ex_vin3, partial_tp) has IDENTICAL entry signals
    to A3_RS — so the signal filter map (prox + vol_mult at signal bars) can be
    reused as-is from cortex_book2_common.build_signal_filter_map().

    Portfolio sim uses ema_portfolio_sim (equal-weight, max_positions=20) rather
    than the D3 sector RS pipeline. This matches B_cloud's development methodology.

Pre-registration:
    knowledge/backtests/2026-07-06_cortex_book2_bcloud_s_filters_prereg.md
    (write this file BEFORE running this script)

RESEARCH_ONLY_NOT_PRODUCTION

Usage (from repo root, after activating .venv):
    python pp_backtest/cortex_book2_bcloud_s_filters.py

Output:
    data/research/cortex_book2_bcloud/bcloud_s_filters_report.md
    data/research/cortex_book2_bcloud/bcloud_s_filters_meta.json

After a successful run, update:
    data/state/s2_evidence_tracker.json
      step0_bcloud_s_filter_research_complete: true
      step0_research_results_path: "data/research/cortex_book2_bcloud/bcloud_s_filters_meta.json"
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

from pp_backtest.cortex_book2_common import (
    G1A_MARGIN_ADJUSTED,
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    S1_PROXIMITY_LABELS,
    S1_PROXIMITY_THRESHOLDS,
    S2_VOLUME_LABELS,
    S2_VOLUME_THRESHOLDS,
    apply_proximity_filter,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_book1_common import (
    IS_WINDOW,
    OOS_WINDOW,
    PANEL_END,
    PANEL_START,
)
from pp_backtest.ema_portfolio_sim import (
    build_portfolio,
    compute_all_trades,
    portfolio_metrics,
)
from pp_backtest.sprint2b_common import slice_equity_years

# ── B_cloud configuration ─────────────────────────────────────────────────────
BCLOUD_ENTRY_TYPE  = "cloud_only"
BCLOUD_EMA_FAST    = 20
BCLOUD_EMA_SLOW    = 100
BCLOUD_EXIT_MODE   = "partial_tp"
BCLOUD_MAX_POS     = 20
BCLOUD_MAX_HOLD    = 250
BCLOUD_RANK_MODE   = "fifo"
BCLOUD_COST        = 0.004  # 40 bps round-trip

EX_VIN3 = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

PANEL_PATH = (REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet")
FALLBACK_PANEL = (REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet")

OUT_DIR = REPO / "data" / "research" / "cortex_book2_bcloud"
PREREG  = "knowledge/backtests/2026-07-06_cortex_book2_bcloud_s_filters_prereg.md"

# ── Gate thresholds (pre-registered) ─────────────────────────────────────────
# G1a (binding): candidate OOS MAR >= B_cloud_baseline OOS MAR + G1A_MARGIN_ADJUSTED (0.066)
# G1b (advisory): candidate OOS MAR >= max(0.10, baseline_oos_mar * 0.50)
#   G1b is NOT binding — G1a + N_OOS + neg-OOS-cap determine ADVANCE/FAIL.
#   G1b is derived at runtime from the B_cloud baseline to avoid an unanchored absolute.
#   Pre-reg: G1b = max(0.10, baseline_oos_mar * 0.50). Reported as informational warning.
#   Rationale: pre-registering an arbitrary absolute floor for a different-pipeline baseline
#   violates verification-harness.md gate calibration rule (opus REDIRECT 2026-07-06).
G1B_BCLOUD_SCALE   = 0.50   # G1b = max(G1B_BCLOUD_MIN, baseline_oos_mar * scale)
G1B_BCLOUD_MIN     = 0.10   # absolute floor backstop
N_OOS_MIN_FULL     = 30
N_OOS_MIN_SUBWINDOW = 12

# ── S1+S2 interaction candidates (pre-registered) ────────────────────────────
# Use strongest individual thresholds as the interaction reference
S1S2_INTERACTION_S1_THRESH = 0.85  # within 15%
S1S2_INTERACTION_S2_THRESH = 1.3   # 1.3× vol


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_panel() -> pd.DataFrame:
    path = PANEL_PATH if PANEL_PATH.exists() else FALLBACK_PANEL
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["symbol", "date"], inplace=True)
    print(f"Panel loaded: {df['symbol'].nunique()} symbols, {len(df):,} rows, "
          f"{df['date'].min().date()} -> {df['date'].max().date()}", flush=True)
    return df


def _get_bcloud_symbols(panel: pd.DataFrame) -> list[str]:
    all_syms = panel["symbol"].unique().tolist()
    syms = [s for s in all_syms if s not in EX_VIN3 and s not in EXCLUDE_ALWAYS]
    print(f"B_cloud universe: {len(syms)} symbols (ex-VIN3, ex-VPL)", flush=True)
    return syms


def _metrics(equity: pd.Series) -> dict[str, float]:
    """Compute MAR, CAGR, MaxDD from a position-constrained equity series."""
    m = portfolio_metrics(equity, pd.DataFrame())
    return {k: float(m.get(k, np.nan)) for k in ("mar", "cagr", "max_dd")}


def _evaluate_gates_bcloud(
    base_oos_mar: float,
    cand_oos_mar: float,
    cand_oos_a_mar: float,
    cand_oos_b_mar: float,
    n_oos: int,
    n_oos_a: int,
    n_oos_b: int,
    g1b_threshold: float,
) -> tuple[list[dict], str]:
    """
    Evaluate pre-registered B_cloud gates.

    G1a (binding): candidate OOS MAR >= baseline OOS MAR + G1A_MARGIN_ADJUSTED (0.066)
    G1b (advisory): candidate OOS MAR >= g1b_threshold — reported but NOT binding.
    N_OOS: >= thresholds
    Neg-OOS cap: both baseline and candidate negative → CONDITIONAL-ADVANCE cap

    ADVANCE/FAIL is determined by G1a + N_OOS + neg-OOS-cap only.
    G1b failure is flagged as [G1b-WARN] in the gate output but does not change verdict.
    """
    g1a_thresh = base_oos_mar + G1A_MARGIN_ADJUSTED
    g1a = (np.isfinite(cand_oos_mar) and np.isfinite(base_oos_mar)
           and cand_oos_mar >= g1a_thresh)
    g1b = (np.isfinite(cand_oos_mar) and cand_oos_mar >= g1b_threshold)
    n_ok_full = n_oos >= N_OOS_MIN_FULL
    n_ok_a    = n_oos_a >= N_OOS_MIN_SUBWINDOW
    n_ok_b    = n_oos_b >= N_OOS_MIN_SUBWINDOW
    both_neg  = (np.isfinite(base_oos_mar) and np.isfinite(cand_oos_mar)
                 and base_oos_mar < 0 and cand_oos_mar < 0)

    details = [
        {
            "id": "G1a",
            "criterion": (f"[BINDING] OOS MAR >= baseline {base_oos_mar:.4f} + "
                          f"{G1A_MARGIN_ADJUSTED:.3f} = {g1a_thresh:.4f}"),
            "result": f"cand {cand_oos_mar:.4f}",
            "pass": g1a,
            "binding": True,
        },
        {
            "id": "G1b",
            "criterion": (f"[ADVISORY] OOS MAR >= {g1b_threshold:.4f} "
                          f"(= max({G1B_BCLOUD_MIN:.2f}, baseline×{G1B_BCLOUD_SCALE:.2f}))"),
            "result": f"{cand_oos_mar:.4f}",
            "pass": g1b,
            "binding": False,
        },
        {
            "id": "N_OOS_full",
            "criterion": f">= {N_OOS_MIN_FULL} trades in full OOS ({OOS_WINDOW[0]}–{OOS_WINDOW[1]})",
            "result": str(n_oos),
            "pass": n_ok_full,
            "binding": True,
        },
        {
            "id": "N_OOS_sub_A",
            "criterion": (f">= {N_OOS_MIN_SUBWINDOW} trades in OOS sub-A "
                          f"({OOS_SUB_WINDOW_A[0]}–{OOS_SUB_WINDOW_A[1]})"),
            "result": str(n_oos_a),
            "pass": n_ok_a,
            "binding": True,
        },
        {
            "id": "N_OOS_sub_B",
            "criterion": (f">= {N_OOS_MIN_SUBWINDOW} trades in OOS sub-B "
                          f"({OOS_SUB_WINDOW_B[0]}–{OOS_SUB_WINDOW_B[1]})"),
            "result": str(n_oos_b),
            "pass": n_ok_b,
            "binding": True,
        },
        {
            "id": "Neg-OOS-cap",
            "criterion": "Both baseline and candidate OOS MAR positive",
            "result": "BOTH NEGATIVE" if both_neg else "OK",
            "pass": not both_neg,
            "binding": True,
        },
    ]

    # Verdict based on binding gates only (G1a, N_OOS, neg-OOS-cap). G1b is advisory.
    if not n_ok_full or not n_ok_a or not n_ok_b:
        verdict = "VN-THIN"
    elif both_neg:
        verdict = "CONDITIONAL-ADVANCE" if g1a else "FAIL"
    elif g1a:
        verdict = "ADVANCE" if g1b else "ADVANCE[G1b-WARN]"
    else:
        verdict = "FAIL"

    return details, verdict


def _fmt(v: float) -> str:
    if not np.isfinite(v):
        return "N/A"
    return f"{v:.4f}"


def _fmt_pct(v: float) -> str:
    if not np.isfinite(v):
        return "N/A"
    return f"{v * 100:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# Candidate runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_candidate(
    label: str,
    filtered_trades: pd.DataFrame,
    base_oos_mar: float,
    g1b_threshold: float,
    extra: dict | None = None,
) -> dict[str, Any]:
    n_full = len(filtered_trades)
    if n_full < 10:
        print(f"    SKIP: too few trades ({n_full}) → VN-THIN", flush=True)
        return {
            "label": label,
            "verdict": "VN-THIN",
            "full": {"mar": float("nan"), "cagr": float("nan"), "max_dd": float("nan")},
            "oos":  {"mar": float("nan"), "cagr": float("nan"), "max_dd": float("nan")},
            "oos_sub_a": {"mar": float("nan"), "cagr": float("nan"), "max_dd": float("nan")},
            "oos_sub_b": {"mar": float("nan"), "cagr": float("nan"), "max_dd": float("nan")},
            "n_full": n_full, "n_oos": 0, "n_oos_sub_a": 0, "n_oos_sub_b": 0,
            "gates": [], **(extra or {}),
        }

    # Rebuild equity from filtered trade subset (reuses pre-computed trades, no re-simulation)
    eq_cand  = build_portfolio(filtered_trades, BCLOUD_MAX_POS, BCLOUD_RANK_MODE)
    eq_oos   = slice_equity_years(eq_cand, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_oos_a = slice_equity_years(eq_cand, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_oos_b = slice_equity_years(eq_cand, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])

    m_full  = _metrics(eq_cand)
    m_oos   = _metrics(eq_oos)
    m_oos_a = _metrics(eq_oos_a)
    m_oos_b = _metrics(eq_oos_b)

    n_oos   = count_oos_trades(filtered_trades, OOS_WINDOW[0], OOS_WINDOW[1])
    n_oos_a = count_oos_trades(filtered_trades, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    n_oos_b = count_oos_trades(filtered_trades, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])

    gates, verdict = _evaluate_gates_bcloud(
        base_oos_mar,
        m_oos["mar"], m_oos_a["mar"], m_oos_b["mar"],
        n_oos, n_oos_a, n_oos_b,
        g1b_threshold,
    )

    print(f"    Trades: {n_full} full, {n_oos} OOS  →  OOS MAR={_fmt(m_oos['mar'])}  verdict={verdict}",
          flush=True)

    return {
        "label":       label,
        "verdict":     verdict,
        "full":        m_full,
        "oos":         m_oos,
        "oos_sub_a":   m_oos_a,
        "oos_sub_b":   m_oos_b,
        "n_full":      n_full,
        "n_oos":       n_oos,
        "n_oos_sub_a": n_oos_a,
        "n_oos_sub_b": n_oos_b,
        "gates":       gates,
        **(extra or {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_report(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# B_cloud S-Filter Research — cortex_book2 (B_cloud pipeline)",
        "",
        f"**Generated:** {date.today()}",
        "**Research label:** RESEARCH_ONLY_NOT_PRODUCTION",
        f"**Pre-registration:** `{PREREG}`",
        f"**Architecture:** B_cloud PRIMARY (EMA{BCLOUD_EMA_FAST}/{BCLOUD_EMA_SLOW}, "
        f"{BCLOUD_EXIT_MODE}, max_pos={BCLOUD_MAX_POS}, ex_vin3)",
        "",
        "## Window",
        "",
        f"- Panel start: **{meta['panel_start']}**",
        f"- Panel end: **{meta['panel_end']}**",
        f"- Primary OOS: **{OOS_WINDOW[0]}–{OOS_WINDOW[1]}**",
        f"- OOS sub-A: **{OOS_SUB_WINDOW_A[0]}–{OOS_SUB_WINDOW_A[1]}**",
        f"- OOS sub-B: **{OOS_SUB_WINDOW_B[0]}–{OOS_SUB_WINDOW_B[1]}**",
        "",
        "## Baseline (B_cloud PRIMARY, unfiltered)",
        "",
        f"- Full MAR: **{_fmt(meta['baseline_full']['mar'])}**",
        f"- Full MaxDD: **{_fmt_pct(meta['baseline_full']['max_dd'])}**",
        f"- Full CAGR: **{_fmt_pct(meta['baseline_full']['cagr'])}**",
        f"- OOS MAR: **{_fmt(meta['baseline_oos']['mar'])}**",
        f"- OOS MaxDD: **{_fmt_pct(meta['baseline_oos']['max_dd'])}**",
        f"- Baseline N trades (full): **{meta['baseline_n_full']}**",
        f"- Baseline N trades (OOS): **{meta['baseline_n_oos']}**",
        "",
        "## Gate thresholds (pre-registered, locked before run)",
        "",
        f"- G1a [BINDING]: candidate OOS MAR >= baseline {_fmt(meta['baseline_oos']['mar'])} + 0.066 "
        f"= **{_fmt(meta['baseline_oos']['mar'] + G1A_MARGIN_ADJUSTED)}**",
        f"- G1b [ADVISORY — not binding]: OOS MAR >= **{_fmt(meta['g1b_threshold'])}** "
        f"(= max({G1B_BCLOUD_MIN:.2f}, baseline×{G1B_BCLOUD_SCALE:.2f}), runtime-derived)",
        f"- N_OOS (full): >= {N_OOS_MIN_FULL} | Sub-windows each: >= {N_OOS_MIN_SUBWINDOW}",
        f"- Filter map coverage: **{meta['filter_map_coverage_pct']}%** "
        f"({meta['filter_map_matched']}/{meta['filter_map_matched'] + meta['filter_map_missing']} signals)",
        "",
    ]

    for cand in meta["candidates"]:
        lines += [
            f"## Candidate — {cand['label']}",
            "",
            f"**Verdict: {cand['verdict']}**",
            "",
            "| Metric | Baseline | Candidate |",
            "|--------|----------|-----------|",
            f"| Full MAR | {_fmt(meta['baseline_full']['mar'])} | {_fmt(cand['full']['mar'])} |",
            f"| Full MaxDD | {_fmt_pct(meta['baseline_full']['max_dd'])} | {_fmt_pct(cand['full']['max_dd'])} |",
            f"| Full CAGR | {_fmt_pct(meta['baseline_full']['cagr'])} | {_fmt_pct(cand['full']['cagr'])} |",
            f"| OOS MAR | {_fmt(meta['baseline_oos']['mar'])} | {_fmt(cand['oos']['mar'])} |",
            f"| OOS MaxDD | {_fmt_pct(meta['baseline_oos']['max_dd'])} | {_fmt_pct(cand['oos']['max_dd'])} |",
            f"| OOS CAGR | {_fmt_pct(meta['baseline_oos']['cagr'])} | {_fmt_pct(cand['oos']['cagr'])} |",
            f"| OOS sub-A MAR | — | {_fmt(cand['oos_sub_a']['mar'])} |",
            f"| OOS sub-B MAR | — | {_fmt(cand['oos_sub_b']['mar'])} |",
            f"| N trades (full) | {meta['baseline_n_full']} | {cand['n_full']} |",
            f"| N trades (OOS) | {meta['baseline_n_oos']} | {cand['n_oos']} |",
            f"| N trades (OOS sub-A) | — | {cand['n_oos_sub_a']} |",
            f"| N trades (OOS sub-B) | — | {cand['n_oos_sub_b']} |",
            "",
        ]
        if cand.get("gates"):
            lines += [
                "| Gate | Criterion | Pass |",
                "|------|-----------|------|",
            ]
            for g in cand["gates"]:
                lines.append(f"| {g['id']} | {g['criterion']} | {'PASS ✓' if g['pass'] else 'FAIL ✗'} |")
            lines.append("")

    # Summary verdict table
    lines += [
        "## Summary",
        "",
        "| Candidate | OOS MAR | OOS sub-A | OOS sub-B | N_OOS | Verdict |",
        "|-----------|---------|-----------|-----------|-------|---------|",
        f"| **Baseline** | {_fmt(meta['baseline_oos']['mar'])} | — | — | "
        f"{meta['baseline_n_oos']} | — |",
    ]
    for cand in meta["candidates"]:
        lines.append(
            f"| {cand['label']} | {_fmt(cand['oos']['mar'])} | "
            f"{_fmt(cand['oos_sub_a']['mar'])} | {_fmt(cand['oos_sub_b']['mar'])} | "
            f"{cand['n_oos']} | **{cand['verdict']}** |"
        )

    lines += [
        "",
        "---",
        "",
        "**Cross-architecture note:** Results above are B_cloud-specific evidence.",
        "A3_RS results (OOS MAR 2.4804 for S2) were NOT used as gates here.",
        "These results feed into `data/state/s2_evidence_tracker.json` Step 0.",
        "",
        "`RESEARCH_ONLY_NOT_PRODUCTION`",
    ]

    report_path = OUT_DIR / "bcloud_s_filters_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report_path}", flush=True)

    meta_path = OUT_DIR / "bcloud_s_filters_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Meta:   {meta_path}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_bcloud_s_filters() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("B_cloud S-Filter Research", flush=True)
    print(f"  Architecture: EMA{BCLOUD_EMA_FAST}/{BCLOUD_EMA_SLOW}, {BCLOUD_EXIT_MODE}, "
          f"max_pos={BCLOUD_MAX_POS}", flush=True)
    print(f"  OOS primary: {OOS_WINDOW[0]}–{OOS_WINDOW[1]}", flush=True)
    print(f"  G1a adjusted margin: +{G1A_MARGIN_ADJUSTED:.3f}", flush=True)
    print(f"  G1b floor (B_cloud): {G1B_BCLOUD_MIN:.2f}", flush=True)
    print(f"  Pre-registration: {PREREG}", flush=True)
    print()

    # ── Step 1: load panel + symbols ─────────────────────────────────────────
    panel  = _load_panel()
    symbols = _get_bcloud_symbols(panel)

    # ── Step 2: build B_cloud baseline trades ────────────────────────────────
    print("Step 2 — Building B_cloud baseline trades (cloud_only, partial_tp)...", flush=True)
    base_trades = compute_all_trades(
        panel, symbols,
        entry_type=BCLOUD_ENTRY_TYPE,
        ema_fast=BCLOUD_EMA_FAST,
        ema_slow=BCLOUD_EMA_SLOW,
        exit_mode=BCLOUD_EXIT_MODE,
        max_hold=BCLOUD_MAX_HOLD,
        cost=BCLOUD_COST,
    )
    if base_trades.empty:
        raise RuntimeError("B_cloud baseline: no trades generated — check panel data")

    eq_base      = build_portfolio(base_trades, BCLOUD_MAX_POS, BCLOUD_RANK_MODE)
    eq_base_oos  = slice_equity_years(eq_base, OOS_WINDOW[0], OOS_WINDOW[1])

    m_base_full = _metrics(eq_base)
    m_base_oos  = _metrics(eq_base_oos)
    n_base_full = len(base_trades)
    n_base_oos  = count_oos_trades(base_trades, OOS_WINDOW[0], OOS_WINDOW[1])

    print(f"  Baseline: full MAR={_fmt(m_base_full['mar'])}  OOS MAR={_fmt(m_base_oos['mar'])}", flush=True)
    print(f"  Baseline trades: {n_base_full} full, {n_base_oos} OOS", flush=True)

    # Derive G1b at runtime from actual B_cloud baseline (pre-registered formula: max(0.10, baseline×0.50))
    g1b_threshold = max(G1B_BCLOUD_MIN, m_base_oos["mar"] * G1B_BCLOUD_SCALE)
    print(f"  G1a threshold (binding): baseline + {G1A_MARGIN_ADJUSTED:.3f} = "
          f"{_fmt(m_base_oos['mar'] + G1A_MARGIN_ADJUSTED)}", flush=True)
    print(f"  G1b threshold (advisory): max({G1B_BCLOUD_MIN:.2f}, "
          f"{_fmt(m_base_oos['mar'])}×{G1B_BCLOUD_SCALE:.2f}) = {_fmt(g1b_threshold)}", flush=True)
    print()

    # ── Step 3: build signal filter map ──────────────────────────────────────
    # Signal filter map is built from A3's honest cache (EMA20/100, cloud_only, ex_vin3).
    # B_cloud PRIMARY has identical entry params → keys will match B_cloud trade entry_dates.
    print("Step 3 — Building signal filter map...", flush=True)
    filter_map = build_signal_filter_map(panel)
    print(f"  Filter map entries: {len(filter_map)}", flush=True)

    # ── Coverage diagnostic (opus flag: report missing-key rate) ─────────────
    # Missing keys = B_cloud trades where (symbol, entry_date) not in A3 honest cache.
    # These are treated as FAIL for all filters — conservative but may bias results
    # if coverage is low. Pre-reg kill criterion: < 60% coverage → surface and flag.
    n_matched = 0
    n_missing = 0
    for _, row in base_trades.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        if key in filter_map:
            n_matched += 1
        else:
            n_missing += 1
    coverage_pct = n_matched / (n_matched + n_missing) * 100 if (n_matched + n_missing) > 0 else 0.0
    print(f"  Filter map coverage: {n_matched}/{n_matched + n_missing} B_cloud signals "
          f"({coverage_pct:.1f}%)", flush=True)
    if coverage_pct < 60.0:
        print(f"  ⚠️  COVERAGE BELOW 60% — kill criterion triggered per pre-reg §6. "
              f"Results may be invalid for Step 0. Surface to user.", flush=True)
    print()

    # Diagnostics over baseline signals
    prox_vals  = []
    vol_vals   = []
    for _, row in base_trades.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = filter_map.get(key)
        if rec:
            prox_vals.append(rec["prox"])
            vol_vals.append(rec["vol_mult"])

    if prox_vals:
        pv = np.array(prox_vals)
        pv = pv[np.isfinite(pv) & (pv > 0)]
        print(f"  Proximity (S1) distribution over B_cloud signal days:")
        for t in S1_PROXIMITY_THRESHOLDS:
            pct = (pv >= t).mean() * 100
            print(f"    >= {t:.2f}: {pct:.1f}% ({int((pv >= t).sum())}/{len(pv)} signals)")

    if vol_vals:
        vv = np.array(vol_vals)
        vv = vv[np.isfinite(vv) & (vv > 0)]
        print(f"  Volume multiple (S2) distribution over B_cloud signal days:")
        for t in S2_VOLUME_THRESHOLDS:
            pct = (vv >= t).mean() * 100
            print(f"    >= {t:.1f}×: {pct:.1f}% ({int((vv >= t).sum())}/{len(vv)} signals)")
    print()

    candidate_rows: list[dict[str, Any]] = []

    # ── Step 4a: S1 candidates ────────────────────────────────────────────────
    print("Step 4a — S1 (52wk-high proximity) candidates:", flush=True)
    for min_prox, label in zip(S1_PROXIMITY_THRESHOLDS, S1_PROXIMITY_LABELS):
        print(f"  Candidate: S1 proximity >= {min_prox:.2f} ({label})...", flush=True)
        cand_trades = apply_proximity_filter(base_trades, filter_map, min_prox)
        row = _run_candidate(
            label=f"S1_{label}",
            filtered_trades=cand_trades,
            base_oos_mar=m_base_oos["mar"],
            g1b_threshold=g1b_threshold,
            extra={"filter_type": "S1_proximity", "threshold": min_prox},
        )
        candidate_rows.append(row)

    # ── Step 4b: S2 candidates ────────────────────────────────────────────────
    print("\nStep 4b — S2 (breakout volume) candidates:", flush=True)
    for min_vol, label in zip(S2_VOLUME_THRESHOLDS, S2_VOLUME_LABELS):
        print(f"  Candidate: S2 vol >= {min_vol:.1f}× ({label})...", flush=True)
        cand_trades = apply_volume_filter(base_trades, filter_map, min_vol)
        row = _run_candidate(
            label=f"S2_{label}",
            filtered_trades=cand_trades,
            base_oos_mar=m_base_oos["mar"],
            g1b_threshold=g1b_threshold,
            extra={"filter_type": "S2_volume", "threshold": min_vol},
        )
        candidate_rows.append(row)

    # ── Step 4c: S1+S2 interaction ────────────────────────────────────────────
    # NOTE: Interaction candidates are always gated on their own G1a/G1b results.
    # There is NO auto-fail based on individual component verdicts — an AND intersection
    # can concentrate winners even when both components individually fail (the joint subset
    # may select higher-quality signals). Results are reported from the gates, not inferred.
    # Per opus REDIRECT 2026-07-06: SUPERSEDED-FAIL logic is unsound and removed.
    print("\nStep 4c — S1+S2 interaction candidates:", flush=True)

    s2_ind_result = next((c for c in candidate_rows
                          if c.get("filter_type") == "S2_volume"
                          and abs(c.get("threshold", 0) - S1S2_INTERACTION_S2_THRESH) < 0.01),
                         None)
    s1_ind_result = next((c for c in candidate_rows
                          if c.get("filter_type") == "S1_proximity"
                          and abs(c.get("threshold", 0) - S1S2_INTERACTION_S1_THRESH) < 0.01),
                         None)

    # Annotate whether individual filters passed — informational context only
    s1_verdict = s1_ind_result["verdict"] if s1_ind_result else "unknown"
    s2_verdict = s2_ind_result["verdict"] if s2_ind_result else "unknown"

    # AND combination (intersection — stricter, higher-quality subset)
    and_label = (f"S1S2_AND_s1_{S1S2_INTERACTION_S1_THRESH:.2f}_"
                 f"s2_{S1S2_INTERACTION_S2_THRESH:.1f}x")
    print(f"  Candidate: AND({and_label})...", flush=True)
    print(f"    (Individual results: S1={s1_verdict}, S2={s2_verdict} — "
          f"AND verdict determined by own gates)", flush=True)
    cand_and = apply_proximity_filter(base_trades, filter_map, S1S2_INTERACTION_S1_THRESH)
    cand_and = apply_volume_filter(cand_and, filter_map, S1S2_INTERACTION_S2_THRESH)

    row_and = _run_candidate(
        label=and_label,
        filtered_trades=cand_and,
        base_oos_mar=m_base_oos["mar"],
        g1b_threshold=g1b_threshold,
        extra={
            "filter_type":    "S1S2_AND",
            "s1_threshold":   S1S2_INTERACTION_S1_THRESH,
            "s2_threshold":   S1S2_INTERACTION_S2_THRESH,
            "s1_ind_verdict": s1_verdict,
            "s2_ind_verdict": s2_verdict,
        },
    )
    candidate_rows.append(row_and)

    # OR combination (union — looser, higher-coverage subset)
    or_label = (f"S1S2_OR_s1_{S1S2_INTERACTION_S1_THRESH:.2f}_"
                f"s2_{S1S2_INTERACTION_S2_THRESH:.1f}x")
    print(f"  Candidate: OR({or_label})...", flush=True)

    base_trades_c = base_trades.copy()
    base_trades_c["entry_date"] = pd.to_datetime(base_trades_c["entry_date"])
    or_mask = []
    for _, row in base_trades_c.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = filter_map.get(key)
        if rec is None:
            or_mask.append(False)
        else:
            s1_ok = rec["prox"] >= S1S2_INTERACTION_S1_THRESH
            s2_ok = rec["vol_mult"] >= S1S2_INTERACTION_S2_THRESH
            or_mask.append(s1_ok or s2_ok)
    cand_or = base_trades_c[or_mask].reset_index(drop=True)

    row_or = _run_candidate(
        label=or_label,
        filtered_trades=cand_or,
        base_oos_mar=m_base_oos["mar"],
        g1b_threshold=g1b_threshold,
        extra={
            "filter_type":    "S1S2_OR",
            "s1_threshold":   S1S2_INTERACTION_S1_THRESH,
            "s2_threshold":   S1S2_INTERACTION_S2_THRESH,
            "s1_ind_verdict": s1_verdict,
            "s2_ind_verdict": s2_verdict,
        },
    )
    candidate_rows.append(row_or)

    # ── Step 5: assemble meta + write report ──────────────────────────────────
    meta: dict[str, Any] = {
        "generated":       str(date.today()),
        "architecture":    "B_cloud_PRIMARY",
        "entry_type":      BCLOUD_ENTRY_TYPE,
        "ema_fast":        BCLOUD_EMA_FAST,
        "ema_slow":        BCLOUD_EMA_SLOW,
        "exit_mode":       BCLOUD_EXIT_MODE,
        "max_positions":   BCLOUD_MAX_POS,
        "panel_start":     PANEL_START,
        "panel_end":       PANEL_END,
        "oos_window":      list(OOS_WINDOW),
        "is_window":       list(IS_WINDOW),
        "oos_sub_a":       list(OOS_SUB_WINDOW_A),
        "oos_sub_b":       list(OOS_SUB_WINDOW_B),
        "g1a_margin_adjusted": G1A_MARGIN_ADJUSTED,
        "g1a_threshold":   m_base_oos["mar"] + G1A_MARGIN_ADJUSTED,
        "g1b_threshold":   g1b_threshold,  # runtime-derived from baseline
        "g1b_advisory_only": True,
        "filter_map_coverage_pct": round(coverage_pct, 1),
        "filter_map_matched":  n_matched,
        "filter_map_missing":  n_missing,
        "baseline_full":   m_base_full,
        "baseline_oos":    m_base_oos,
        "baseline_n_full": n_base_full,
        "baseline_n_oos":  n_base_oos,
        "candidates":      candidate_rows,
        "prereg":          PREREG,
    }

    _write_report(meta)

    # ── Step 6: print summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 60, flush=True)
    print(f"{'Candidate':<40} {'OOS MAR':>10} {'Verdict'}", flush=True)
    print(f"{'Baseline (unfiltered)':<40} {_fmt(m_base_oos['mar']):>10}", flush=True)
    for c in candidate_rows:
        print(f"{c['label']:<40} {_fmt(c['oos']['mar']):>10}   {c['verdict']}", flush=True)

    advances = [c for c in candidate_rows if c["verdict"] == "ADVANCE"]
    if advances:
        print(f"\n{len(advances)} candidate(s) ADVANCE:", flush=True)
        for c in advances:
            print(f"  {c['label']}: OOS MAR={_fmt(c['oos']['mar'])}", flush=True)
        print("\nNext step: update data/state/s2_evidence_tracker.json", flush=True)
        print("  step0_bcloud_s_filter_research_complete: true", flush=True)
        print("  step0_research_results_path: data/research/cortex_book2_bcloud/bcloud_s_filters_meta.json",
              flush=True)
    else:
        print("\nNo candidates ADVANCE under B_cloud pipeline.", flush=True)
        print("Update s2_evidence_tracker.json to note research complete but no filter passes.", flush=True)

    print("=" * 60, flush=True)
    return meta


def main() -> None:
    run_bcloud_s_filters()


if __name__ == "__main__":
    main()
