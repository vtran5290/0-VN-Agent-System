#!/usr/bin/env python3
"""
B_cloud Phase 2 — Ranking Mode Research.

Tests RS-proxy ranking modes (ema_dist, mom20, mom60, ema_dist_mom20,
ema_dist_mom60) against the FIFO baseline on B_cloud PRIMARY trade set.

Background:
    Phase 1 (S1/S2 filter overlays) returned RESEARCH-NEGATIVE — 8/8 candidates
    FAIL G1a on B_cloud FIFO+partial_tp. Structural explanation: FIFO ranking
    does not concentrate quality before filtering, so filters subtract quantity
    without adding quality concentration.

    Phase 2 tests whether changing the slot-allocation RANKING from FIFO to
    momentum/quality proxies improves OOS MAR. Uses the SAME trade set as
    Phase 1 (no new compute_all_trades() call) — only build_portfolio_v2()
    rank_mode varies.

Pre-registration:
    knowledge/backtests/2026-07-07_bcloud_phase2_ranking_prereg.md
    (written before this script)

RESEARCH_ONLY_NOT_PRODUCTION

Usage (from repo root):
    python pp_backtest/cortex_book2_bcloud_ranking.py

Output:
    data/research/bcloud_rs/bcloud_ranking_report.md
    data/research/bcloud_rs/bcloud_ranking_meta.json
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

from pp_backtest.cortex_book1_common import IS_WINDOW, OOS_WINDOW, PANEL_START, PANEL_END
from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B, G1A_MARGIN_ADJUSTED
from pp_backtest.ema_portfolio_sim import (
    compute_all_trades,
    build_portfolio,
    build_portfolio_v2,
    portfolio_metrics,
)
from pp_backtest.sprint2b_common import slice_equity_years

# ── B_cloud configuration (identical to Phase 1) ─────────────────────────────
BCLOUD_ENTRY_TYPE = "cloud_only"
BCLOUD_EMA_FAST   = 20
BCLOUD_EMA_SLOW   = 100
BCLOUD_EXIT_MODE  = "partial_tp"
BCLOUD_MAX_POS    = 20
BCLOUD_MAX_HOLD   = 250
BCLOUD_COST       = 0.004

EX_VIN3        = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

PANEL_PATH    = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
FALLBACK_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"
OUT_DIR       = REPO / "data" / "research" / "bcloud_rs"
PREREG        = "knowledge/backtests/2026-07-07_bcloud_phase2_ranking_prereg.md"

# ── Phase 1 baseline (pre-registered, locked) ────────────────────────────────
BASELINE_OOS_MAR = 0.4698
G1A_THRESHOLD    = BASELINE_OOS_MAR + G1A_MARGIN_ADJUSTED   # 0.5357
G1B_THRESHOLD    = max(0.10, BASELINE_OOS_MAR * 0.50)       # 0.2349
N_OOS_MIN        = 30
N_OOS_SUB_MIN    = 12

# ── Candidates (pre-registered) ──────────────────────────────────────────────
RANK_CANDIDATES = [
    ("ema_dist_mom20", "EMA distance + 20-bar momentum composite"),
    ("ema_dist_mom60", "EMA distance + 60-bar momentum composite (3m proxy)"),
    ("mom60",          "60-bar momentum (3m, closest to A3_RS 3m component)"),
    ("ema_dist",       "EMA distance (momentum quality, overextension risk)"),
    ("mom20",          "20-bar momentum (short-term, mean-revert risk with partial_tp)"),
]


def _load_panel() -> pd.DataFrame:
    path = PANEL_PATH if PANEL_PATH.exists() else FALLBACK_PATH
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["symbol", "date"], inplace=True)
    print(f"Panel: {df['symbol'].nunique()} symbols, {len(df):,} rows, "
          f"{df['date'].min().date()} -> {df['date'].max().date()}", flush=True)
    return df


def _get_symbols(panel: pd.DataFrame) -> list[str]:
    all_syms = panel["symbol"].unique().tolist()
    syms = [s for s in all_syms if s not in EX_VIN3 and s not in EXCLUDE_ALWAYS]
    print(f"Universe: {len(syms)} symbols (ex-VIN3, ex-VPL)", flush=True)
    return syms


def _fmt(v: float) -> str:
    return "N/A" if not np.isfinite(v) else f"{v:.4f}"


def _fmt_pct(v: float) -> str:
    return "N/A" if not np.isfinite(v) else f"{v * 100:.1f}%"


def _metrics(equity: pd.Series) -> dict[str, float]:
    m = portfolio_metrics(equity, pd.DataFrame())
    return {k: float(m.get(k, np.nan)) for k in ("mar", "cagr", "max_dd")}


def _count_filled(equity: pd.Series, n_filled: int,
                  start_year: int, end_year: int) -> int:
    """Approximate OOS trade count from equity index slice."""
    # n_filled from build_portfolio_v2 is total; for sub-windows we use
    # trade-level counting. Here we return n_filled as total and report separately.
    return n_filled


def _run_rank_candidate(
    label: str,
    desc: str,
    trades_df: pd.DataFrame,
    rank_mode: str,
) -> dict[str, Any]:
    print(f"  [{label}] {desc}...", flush=True)

    try:
        eq_full, n_filled = build_portfolio_v2(trades_df, BCLOUD_MAX_POS, rank_mode)
    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return {"label": label, "desc": desc, "rank_mode": rank_mode,
                "verdict": "ERROR", "error": str(e)}

    if eq_full.empty or n_filled < 10:
        print(f"    SKIP: too few filled trades ({n_filled})", flush=True)
        return {"label": label, "desc": desc, "rank_mode": rank_mode,
                "verdict": "VN-THIN", "n_filled": n_filled}

    eq_oos   = slice_equity_years(eq_full, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_oos_a = slice_equity_years(eq_full, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_oos_b = slice_equity_years(eq_full, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])

    m_full  = _metrics(eq_full)
    m_oos   = _metrics(eq_oos)
    m_oos_a = _metrics(eq_oos_a)
    m_oos_b = _metrics(eq_oos_b)

    oos_mar = m_oos["mar"]
    g1a     = np.isfinite(oos_mar) and oos_mar >= G1A_THRESHOLD
    g1b     = np.isfinite(oos_mar) and oos_mar >= G1B_THRESHOLD
    n_ok    = n_filled >= N_OOS_MIN
    both_neg = (np.isfinite(oos_mar) and oos_mar < 0 and BASELINE_OOS_MAR < 0)

    if not n_ok:
        verdict = "VN-THIN"
    elif both_neg:
        verdict = "CONDITIONAL-ADVANCE" if g1a else "FAIL"
    elif g1a:
        verdict = "ADVANCE" if g1b else "ADVANCE[G1b-WARN]"
    else:
        verdict = "FAIL"

    margin_vs_baseline = oos_mar - BASELINE_OOS_MAR
    print(f"    n_filled={n_filled}  OOS MAR={_fmt(oos_mar)} "
          f"(delta vs FIFO: {margin_vs_baseline:+.4f})  verdict={verdict}", flush=True)

    return {
        "label":      label,
        "desc":       desc,
        "rank_mode":  rank_mode,
        "verdict":    verdict,
        "full":       m_full,
        "oos":        m_oos,
        "oos_sub_a":  m_oos_a,
        "oos_sub_b":  m_oos_b,
        "n_filled":   n_filled,
        "g1a":        g1a,
        "g1b":        g1b,
        "margin_vs_baseline": float(margin_vs_baseline),
    }


def _write_report(meta: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# B_cloud Phase 2 — Ranking Mode Research",
        "",
        f"**Generated:** {date.today()}",
        "**Research label:** RESEARCH_ONLY_NOT_PRODUCTION",
        f"**Pre-registration:** `{PREREG}`",
        f"**Architecture:** B_cloud PRIMARY (EMA{BCLOUD_EMA_FAST}/{BCLOUD_EMA_SLOW}, "
        f"{BCLOUD_EXIT_MODE}, max_pos={BCLOUD_MAX_POS})",
        "",
        "## Baseline (B_cloud PRIMARY, FIFO — Phase 1 measured)",
        "",
        f"- OOS MAR (2020-2026): **{_fmt(BASELINE_OOS_MAR)}**",
        f"- G1a threshold (binding): **{_fmt(G1A_THRESHOLD)}** (= baseline + {G1A_MARGIN_ADJUSTED:.3f})",
        f"- G1b threshold (advisory): **{_fmt(G1B_THRESHOLD)}**",
        "",
        "## Results by Ranking Mode",
        "",
        "| Rank mode | OOS MAR | Sub-A | Sub-B | Delta vs FIFO | N filled | Verdict |",
        "|-----------|---------|-------|-------|---------------|----------|---------|",
        f"| **fifo (baseline)** | {_fmt(BASELINE_OOS_MAR)} | — | — | — | 7445 | — |",
    ]

    for c in meta["candidates"]:
        if "oos" not in c:
            lines.append(f"| {c['rank_mode']} | — | — | — | — | {c.get('n_filled','—')} | **{c['verdict']}** |")
            continue
        delta = c.get("margin_vs_baseline", float("nan"))
        delta_str = f"{delta:+.4f}" if np.isfinite(delta) else "—"
        lines.append(
            f"| {c['rank_mode']} | {_fmt(c['oos']['mar'])} | "
            f"{_fmt(c['oos_sub_a']['mar'])} | {_fmt(c['oos_sub_b']['mar'])} | "
            f"{delta_str} | {c.get('n_filled','—')} | **{c['verdict']}** |"
        )

    lines += [
        "",
        "## Detailed Results",
        "",
    ]

    for c in meta["candidates"]:
        lines += [f"### {c['rank_mode']} — {c['verdict']}", ""]
        if "oos" not in c:
            lines += [f"Error or skip: {c.get('error', c['verdict'])}", ""]
            continue
        lines += [
            "| Metric | Baseline (FIFO) | Candidate |",
            "|--------|-----------------|-----------|",
            f"| Full MAR | {_fmt(meta['baseline_full_mar'])} | {_fmt(c['full']['mar'])} |",
            f"| OOS MAR | {_fmt(BASELINE_OOS_MAR)} | {_fmt(c['oos']['mar'])} |",
            f"| OOS MaxDD | -27.8% | {_fmt_pct(c['oos']['max_dd'])} |",
            f"| OOS CAGR | 13.1% | {_fmt_pct(c['oos']['cagr'])} |",
            f"| OOS sub-A MAR | — | {_fmt(c['oos_sub_a']['mar'])} |",
            f"| OOS sub-B MAR | — | {_fmt(c['oos_sub_b']['mar'])} |",
            f"| N filled | 7445 (FIFO) | {c.get('n_filled','—')} |",
            "",
        ]

    lines += [
        "## Conclusion",
        "",
    ]

    advances = [c for c in meta["candidates"] if c.get("verdict") == "ADVANCE"]
    if advances:
        lines.append(f"{len(advances)} candidate(s) ADVANCE:")
        for c in advances:
            lines.append(f"- {c['rank_mode']}: OOS MAR={_fmt(c['oos']['mar'])}")
        lines += ["", "Next step: pre-register Phase 3 (ranking + filter overlay combination)."]
    else:
        best = max(
            (c for c in meta["candidates"] if "oos" in c and np.isfinite(c["oos"]["mar"])),
            key=lambda c: c["oos"]["mar"],
            default=None,
        )
        if best:
            lines.append(
                f"No candidates ADVANCE. Best: {best['rank_mode']} OOS MAR={_fmt(best['oos']['mar'])} "
                f"(delta vs FIFO: {best.get('margin_vs_baseline', float('nan')):+.4f})."
            )
        lines += [
            "Ranking overlays do not add sufficient value on B_cloud partial_tp architecture.",
            "",
            "Per program pre-reg: if no candidate achieves OOS MAR >= 2.0 after Phase 3,",
            "B_cloud research program is FAILED. Proceed to Phase 3 only if best Phase 2",
            "result shows OOS MAR >= baseline + 0.30 (advisory gate for Phase 2->3 transition).",
        ]

    lines += ["", "`RESEARCH_ONLY_NOT_PRODUCTION`"]

    rp = OUT_DIR / "bcloud_ranking_report.md"
    rp.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {rp}", flush=True)

    mp = OUT_DIR / "bcloud_ranking_meta.json"
    mp.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Meta:   {mp}", flush=True)


def run_bcloud_ranking() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("B_cloud Phase 2 — Ranking Mode Research", flush=True)
    print(f"  Baseline OOS MAR (Phase 1 FIFO): {BASELINE_OOS_MAR}", flush=True)
    print(f"  G1a threshold: {_fmt(G1A_THRESHOLD)}", flush=True)
    print(f"  Pre-registration: {PREREG}", flush=True)
    print()

    # Step 1: load panel + symbols (same as Phase 1)
    panel  = _load_panel()
    syms   = _get_symbols(panel)

    # Step 2: compute B_cloud trade set (shared across all rank modes)
    print("Step 2 — Computing B_cloud trades (cloud_only, partial_tp)...", flush=True)
    trades_df = compute_all_trades(
        panel, syms,
        entry_type=BCLOUD_ENTRY_TYPE,
        ema_fast=BCLOUD_EMA_FAST,
        ema_slow=BCLOUD_EMA_SLOW,
        exit_mode=BCLOUD_EXIT_MODE,
        max_hold=BCLOUD_MAX_HOLD,
        cost=BCLOUD_COST,
    )
    if trades_df.empty:
        raise RuntimeError("No B_cloud trades generated — check panel data")
    print(f"  {len(trades_df)} total trades generated", flush=True)

    # FIFO baseline equity (v1 API for comparability with Phase 1)
    eq_fifo     = build_portfolio(trades_df, BCLOUD_MAX_POS, "fifo")
    m_fifo_full = _metrics(eq_fifo)
    print(f"  FIFO full MAR={_fmt(m_fifo_full['mar'])}  (Phase 1 measured OOS MAR={BASELINE_OOS_MAR})",
          flush=True)
    print()

    # Step 3: test rank modes using build_portfolio_v2
    print("Step 3 — Testing ranking modes:", flush=True)
    candidate_rows: list[dict[str, Any]] = []
    for rank_mode, desc in RANK_CANDIDATES:
        row = _run_rank_candidate(rank_mode, desc, trades_df, rank_mode)
        candidate_rows.append(row)
    print()

    meta: dict[str, Any] = {
        "generated":         str(date.today()),
        "architecture":      "B_cloud_PRIMARY",
        "exit_mode":         BCLOUD_EXIT_MODE,
        "max_positions":     BCLOUD_MAX_POS,
        "panel_start":       PANEL_START,
        "panel_end":         PANEL_END,
        "oos_window":        list(OOS_WINDOW),
        "oos_sub_a":         list(OOS_SUB_WINDOW_A),
        "oos_sub_b":         list(OOS_SUB_WINDOW_B),
        "baseline_oos_mar":  BASELINE_OOS_MAR,
        "g1a_threshold":     G1A_THRESHOLD,
        "g1b_threshold":     G1B_THRESHOLD,
        "baseline_full_mar": m_fifo_full["mar"],
        "candidates":        candidate_rows,
        "prereg":            PREREG,
    }

    _write_report(meta)

    # Print summary
    print("=" * 60, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 60, flush=True)
    print(f"{'Rank mode':<25} {'OOS MAR':>10} {'Delta':>8} {'Sub-B':>8} {'Verdict'}", flush=True)
    print(f"{'fifo (baseline)':<25} {_fmt(BASELINE_OOS_MAR):>10} {'--':>8} {'--':>8}", flush=True)
    for c in candidate_rows:
        oos_mar = c["oos"]["mar"] if "oos" in c else float("nan")
        sub_b   = c["oos_sub_b"]["mar"] if "oos_sub_b" in c else float("nan")
        delta   = c.get("margin_vs_baseline", float("nan"))
        print(f"{c['rank_mode']:<25} {_fmt(oos_mar):>10} {delta:>+8.4f} {_fmt(sub_b):>8}   {c['verdict']}", flush=True)
    print("=" * 60, flush=True)

    return meta


def main() -> None:
    run_bcloud_ranking()


if __name__ == "__main__":
    main()
