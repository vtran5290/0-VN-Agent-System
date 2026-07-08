#!/usr/bin/env python3
"""
B_cloud Exit-Mode Research — Phase 1 (exit-mode sweep).

Tests whether removing partial_tp's TP1 clip lifts OOS MAR by allowing
large winners to compound. Compression hypothesis: partial_tp's TP1=+15% exit
compresses the return distribution regardless of entry quality.

B_cloud PRIMARY (EMA20/100, ex_vin3, partial_tp) baseline is recomputed fresh
for each run so exit-mode comparisons share the exact same window.

Candidates (pre-registered 2026-07-08_bcloud_exit_program_prereg.md):
  fixed_60    : exit_mode="fixed_hold", max_hold=60  (short-term, 3 months)
  fixed_120   : exit_mode="fixed_hold", max_hold=120 (decisive test, ~6 months)
  trail_only  : exit_mode="trailing_2.5", max_hold=250 (ATR trail, no TP1 clip)

Cross-architecture constraint: A3_RS evidence is NOT admissible here.
All gates are derived from B_cloud's own OOS performance.

RESEARCH_ONLY_NOT_PRODUCTION

Usage (from repo root, after activating .venv):
    python pp_backtest/cortex_book2_bcloud_exit.py

Output:
    data/research/bcloud_exit/bcloud_exit_phase1_report.md
    data/research/bcloud_exit/bcloud_exit_phase1_meta.json
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

# ── B_cloud configuration (locked) ───────────────────────────────────────────
BCLOUD_ENTRY_TYPE = "cloud_only"
BCLOUD_EMA_FAST   = 20
BCLOUD_EMA_SLOW   = 100
BCLOUD_MAX_POS    = 20
BCLOUD_COST       = 0.004  # 40 bps round-trip

EX_VIN3        = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

PANEL_PATH     = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
FALLBACK_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"

OUT_DIR = REPO / "data" / "research" / "bcloud_exit"
PREREG  = "knowledge/backtests/2026-07-08_bcloud_exit_program_prereg.md"

# ── Gate thresholds (pre-registered) ─────────────────────────────────────────
G1B_BCLOUD_SCALE    = 0.50
G1B_BCLOUD_MIN      = 0.10
N_OOS_MIN_FULL      = 30
N_OOS_MIN_SUBWINDOW = 12

# ── Baseline (locked from Phase 1+2 program, verified by recompute) ──────────
# Phase 1+2 measured partial_tp baseline OOS MAR: 0.4698
# We recompute here to confirm on the same panel version.
PHASE12_BASELINE_OOS_MAR = 0.4698

# ── Phase 1 candidates ────────────────────────────────────────────────────────
EXIT_CANDIDATES = [
    ("fixed_60",   "Fixed hold 60 bars (no TP1, no trail)",    "fixed_hold",    60),
    ("fixed_120",  "Fixed hold 120 bars (decisive test)",       "fixed_hold",   120),
    ("trail_only", "ATR trail 2.5x from entry (no TP1 clip)",  "trailing_2.5", 250),
]

# Phase 1->2 advisory gate: best Phase 1 OOS MAR must exceed baseline + 0.200
PHASE1_TO_PHASE2_ADVISORY_DELTA = 0.200


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
    m = portfolio_metrics(equity, pd.DataFrame())
    return {k: float(m.get(k, np.nan)) for k in ("mar", "cagr", "max_dd")}


def _evaluate_gates(
    base_oos_mar: float,
    cand_oos_mar: float,
    n_oos: int,
    n_oos_a: int,
    n_oos_b: int,
    g1b_threshold: float,
) -> tuple[list[dict], str]:
    g1a_thresh = base_oos_mar + G1A_MARGIN_ADJUSTED
    g1a      = (np.isfinite(cand_oos_mar) and cand_oos_mar >= g1a_thresh)
    g1b      = (np.isfinite(cand_oos_mar) and cand_oos_mar >= g1b_threshold)
    n_ok     = n_oos >= N_OOS_MIN_FULL and n_oos_a >= N_OOS_MIN_SUBWINDOW and n_oos_b >= N_OOS_MIN_SUBWINDOW
    both_neg = (np.isfinite(base_oos_mar) and np.isfinite(cand_oos_mar)
                and base_oos_mar < 0 and cand_oos_mar < 0)

    details = [
        {"gate": "G1a (binding)", "threshold": f">= {g1a_thresh:.4f}",
         "value": f"{cand_oos_mar:.4f}", "pass": g1a},
        {"gate": "G1b (advisory)", "threshold": f">= {g1b_threshold:.4f}",
         "value": f"{cand_oos_mar:.4f}", "pass": g1b},
        {"gate": "N_OOS", "threshold": f">= {N_OOS_MIN_FULL}/{N_OOS_MIN_SUBWINDOW}",
         "value": f"{n_oos}/{n_oos_a}/{n_oos_b}", "pass": n_ok},
    ]
    if both_neg:
        details.append({"gate": "neg-OOS cap", "threshold": "CONDITIONAL-ADVANCE cap",
                        "value": "both negative", "pass": False})

    if both_neg:
        verdict = "CONDITIONAL-ADVANCE"
    elif g1a and n_ok:
        verdict = "ADVANCE"
    else:
        verdict = "FAIL"

    return details, verdict


def _run_candidate(
    panel: pd.DataFrame,
    symbols: list[str],
    label: str,
    desc: str,
    exit_mode: str,
    max_hold: int,
    base_oos_mar: float,
    g1b_threshold: float,
) -> dict[str, Any]:
    print(f"\n  Running {label} ({exit_mode}, max_hold={max_hold})...", flush=True)
    try:
        trades_df = compute_all_trades(
            panel, symbols,
            entry_type=BCLOUD_ENTRY_TYPE,
            ema_fast=BCLOUD_EMA_FAST, ema_slow=BCLOUD_EMA_SLOW,
            exit_mode=exit_mode, max_hold=max_hold, cost=BCLOUD_COST,
        )
        if trades_df.empty:
            return {"label": label, "desc": desc, "error": "no trades", "verdict": "FAIL"}

        equity = build_portfolio(trades_df, BCLOUD_MAX_POS, "fifo")

        full_m   = _metrics(equity)
        oos_eq   = slice_equity_years(equity, *OOS_WINDOW)
        oos_m    = _metrics(oos_eq)
        oos_a_eq = slice_equity_years(equity, *OOS_SUB_WINDOW_A)
        oos_a_m  = _metrics(oos_a_eq)
        oos_b_eq = slice_equity_years(equity, *OOS_SUB_WINDOW_B)
        oos_b_m  = _metrics(oos_b_eq)

        n_oos   = count_oos_trades(trades_df, *OOS_WINDOW)
        n_oos_a = count_oos_trades(trades_df, *OOS_SUB_WINDOW_A)
        n_oos_b = count_oos_trades(trades_df, *OOS_SUB_WINDOW_B)

        gates, verdict = _evaluate_gates(
            base_oos_mar, oos_m["mar"], n_oos, n_oos_a, n_oos_b, g1b_threshold
        )

        delta = oos_m["mar"] - base_oos_mar

        print(f"    Full MAR={full_m['mar']:.4f}  OOS MAR={oos_m['mar']:.4f}  "
              f"delta={delta:+.4f}  sub-A={oos_a_m['mar']:.4f}  sub-B={oos_b_m['mar']:.4f}  "
              f"N_OOS={n_oos}  -> {verdict}", flush=True)

        return {
            "label": label,
            "desc": desc,
            "exit_mode": exit_mode,
            "max_hold": max_hold,
            "full_mar": full_m["mar"],
            "oos_mar": oos_m["mar"],
            "oos_cagr": oos_m["cagr"],
            "oos_maxdd": oos_m["max_dd"],
            "oos_a_mar": oos_a_m["mar"],
            "oos_b_mar": oos_b_m["mar"],
            "n_oos": n_oos,
            "n_oos_a": n_oos_a,
            "n_oos_b": n_oos_b,
            "delta": delta,
            "gates": gates,
            "verdict": verdict,
        }

    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return {"label": label, "desc": desc, "error": str(e), "verdict": "ERROR"}


# ─────────────────────────────────────────────────────────────────────────────
# Report writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_report(
    results: list[dict],
    base_oos_mar: float,
    phase12_baseline: float,
    best_delta: float,
    advisory_gate_pass: bool,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "bcloud_exit_phase1_report.md"

    lines = [
        "# B_cloud Phase 1 (Exit-Mode) — Research Report",
        "",
        f"**Generated:** {date.today()}",
        "**Research label:** RESEARCH_ONLY_NOT_PRODUCTION",
        f"**Pre-registration:** `{PREREG}`",
        "**Architecture:** B_cloud PRIMARY (EMA20/100, partial_tp baseline vs exit-mode variants)",
        "",
        "## Baseline (B_cloud PRIMARY, partial_tp — recomputed this run)",
        "",
        f"- OOS MAR (2020-2026): **{base_oos_mar:.4f}**",
        f"- Phase 1+2 program measured baseline: {phase12_baseline:.4f} "
          f"({'MATCH' if abs(base_oos_mar - phase12_baseline) < 0.005 else 'MISMATCH — flag for review'})",
        f"- G1a threshold (binding): **{base_oos_mar + G1A_MARGIN_ADJUSTED:.4f}** (= baseline + {G1A_MARGIN_ADJUSTED})",
        f"- G1b threshold (advisory): **{max(G1B_BCLOUD_MIN, base_oos_mar * G1B_BCLOUD_SCALE):.4f}**",
        "",
        "## Results by Exit Mode",
        "",
        "| Exit mode | OOS MAR | Sub-A | Sub-B | Delta vs baseline | N_OOS | Verdict |",
        "|-----------|---------|-------|-------|-------------------|-------|---------|",
    ]

    for r in results:
        if "error" in r:
            lines.append(f"| **{r['label']}** | — | — | — | — | — | **ERROR** |")
        else:
            lines.append(
                f"| **{r['label']}** | {r['oos_mar']:.4f} | {r['oos_a_mar']:.4f} | "
                f"{r['oos_b_mar']:.4f} | {r['delta']:+.4f} | {r['n_oos']} | **{r['verdict']}** |"
            )

    lines += [
        "",
        "## Detailed Results",
        "",
    ]

    for r in results:
        lines.append(f"### {r['label']} ({r.get('exit_mode', '?')}, max_hold={r.get('max_hold', '?')}) — {r['verdict']}")
        lines.append("")
        if "error" in r:
            lines.append(f"Error: {r['error']}")
        else:
            lines += [
                "| Metric | Baseline (partial_tp) | Candidate |",
                "|--------|----------------------|-----------|",
                f"| Full MAR | — | {r['full_mar']:.4f} |",
                f"| OOS MAR | {base_oos_mar:.4f} | {r['oos_mar']:.4f} |",
                f"| OOS MaxDD | — | {r['oos_maxdd']:.1%} |",
                f"| OOS CAGR | — | {r['oos_cagr']:.1%} |",
                f"| OOS sub-A MAR | — | {r['oos_a_mar']:.4f} |",
                f"| OOS sub-B MAR | — | {r['oos_b_mar']:.4f} |",
                f"| N_OOS | — | {r['n_oos']} |",
                f"| Delta vs baseline | — | {r['delta']:+.4f} |",
            ]
        lines.append("")

    lines += [
        "## Phase 1->2 Advisory Gate",
        "",
        f"Required: best Phase 1 OOS MAR delta >= +{PHASE1_TO_PHASE2_ADVISORY_DELTA:.3f}",
        f"Best achieved: {best_delta:+.4f}",
        f"Result: **{'PASS -> Phase 2 authorized' if advisory_gate_pass else 'FAIL -> CLOSED-NEGATIVE (exit-mode program ends)'}**",
        "",
        "## Conclusion",
        "",
    ]

    advance_count = sum(1 for r in results if r.get("verdict") == "ADVANCE")
    if advance_count > 0:
        lines.append(f"{advance_count} candidate(s) ADVANCE G1a gate.")
    else:
        lines.append("No candidates ADVANCE G1a gate.")

    lines += [
        f"Best delta: {best_delta:+.4f} vs Phase 1->2 advisory threshold of +{PHASE1_TO_PHASE2_ADVISORY_DELTA:.3f}.",
        "",
        "`RESEARCH_ONLY_NOT_PRODUCTION`",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written: {report_path}", flush=True)

    meta = {
        "generated": str(date.today()),
        "prereg": PREREG,
        "baseline_oos_mar": base_oos_mar,
        "phase12_baseline": phase12_baseline,
        "g1a_thresh": base_oos_mar + G1A_MARGIN_ADJUSTED,
        "best_delta": best_delta,
        "advisory_gate_pass": advisory_gate_pass,
        "results": [
            {k: v for k, v in r.items() if k != "gates"}
            for r in results
        ],
    }
    meta_path = OUT_DIR / "bcloud_exit_phase1_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Meta written: {meta_path}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70, flush=True)
    print("B_cloud Exit-Mode Research — Phase 1", flush=True)
    print(f"Pre-reg: {PREREG}", flush=True)
    print("RESEARCH_ONLY_NOT_PRODUCTION", flush=True)
    print("=" * 70, flush=True)

    panel  = _load_panel()
    syms   = _get_bcloud_symbols(panel)

    # ── Compute baseline (partial_tp, max_hold=250) ───────────────────────────
    print("\nComputing B_cloud baseline (partial_tp, max_hold=250)...", flush=True)
    base_trades = compute_all_trades(
        panel, syms,
        entry_type=BCLOUD_ENTRY_TYPE,
        ema_fast=BCLOUD_EMA_FAST, ema_slow=BCLOUD_EMA_SLOW,
        exit_mode="partial_tp", max_hold=250, cost=BCLOUD_COST,
    )
    base_equity = build_portfolio(base_trades, BCLOUD_MAX_POS, "fifo")
    base_oos_eq  = slice_equity_years(base_equity, *OOS_WINDOW)
    base_oos_mar = float(portfolio_metrics(base_oos_eq, pd.DataFrame()).get("mar", np.nan))
    g1b_threshold = max(G1B_BCLOUD_MIN, base_oos_mar * G1B_BCLOUD_SCALE)

    match_str = "MATCH" if abs(base_oos_mar - PHASE12_BASELINE_OOS_MAR) < 0.005 else "MISMATCH"
    print(f"Baseline OOS MAR: {base_oos_mar:.4f} (Phase 1+2 measured: {PHASE12_BASELINE_OOS_MAR:.4f} [{match_str}])",
          flush=True)
    print(f"G1a threshold: {base_oos_mar + G1A_MARGIN_ADJUSTED:.4f}  G1b threshold: {g1b_threshold:.4f}",
          flush=True)

    # ── Run candidates ────────────────────────────────────────────────────────
    print("\nRunning exit-mode candidates...", flush=True)
    results = []
    for label, desc, exit_mode, max_hold in EXIT_CANDIDATES:
        r = _run_candidate(
            panel, syms, label, desc, exit_mode, max_hold,
            base_oos_mar, g1b_threshold,
        )
        results.append(r)

    # ── Advisory gate check ────────────────────────────────────────────────────
    valid_mars = [r["delta"] for r in results if "delta" in r]
    best_delta = max(valid_mars) if valid_mars else float("-inf")
    advisory_gate_pass = best_delta >= PHASE1_TO_PHASE2_ADVISORY_DELTA

    # ── Write report ──────────────────────────────────────────────────────────
    _write_report(results, base_oos_mar, PHASE12_BASELINE_OOS_MAR, best_delta, advisory_gate_pass)

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70, flush=True)
    print("PHASE 1 SUMMARY", flush=True)
    print("=" * 70, flush=True)
    for r in results:
        if "error" in r:
            print(f"  {r['label']:15s}  ERROR: {r['error']}", flush=True)
        else:
            print(f"  {r['label']:15s}  OOS MAR={r['oos_mar']:.4f}  delta={r['delta']:+.4f}  "
                  f"sub-B={r['oos_b_mar']:.4f}  {r['verdict']}", flush=True)
    print(f"\nBest delta: {best_delta:+.4f} vs advisory gate +{PHASE1_TO_PHASE2_ADVISORY_DELTA:.3f}", flush=True)
    print(f"Phase 1->2 advisory gate: {'PASS' if advisory_gate_pass else 'FAIL'}", flush=True)
    if not advisory_gate_pass:
        print("-> B_cloud exit-mode program closes as CLOSED-NEGATIVE.", flush=True)
        print("-> Paper monitoring under kill criterion continues.", flush=True)
    print("\nRESEARCH_ONLY_NOT_PRODUCTION", flush=True)


if __name__ == "__main__":
    main()
