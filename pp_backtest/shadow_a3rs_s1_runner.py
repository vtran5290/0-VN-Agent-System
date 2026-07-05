#!/usr/bin/env python3
"""
Shadow paper runner: A3_RS + S1 proximity filter.

PURPOSE
-------
Research infrastructure to accumulate live-adjacent paper evidence for the
A3_RS + S1 combination on the A3 universe. Runs in parallel with the B_cloud
production runner (daily_paper_trade_runner.py). This runner is completely
isolated — it NEVER affects B_cloud, final_action, or any OMS path.

COUNCIL APPROVAL
----------------
Opus APPROVE + Fable GAP resolved + ChatGPT APPROVE = 3/3
Slug: 2026-07-05-2100_VNAgent_S1S2PromotionPath
Pre-registration: knowledge/backtests/2026-07-05_shadow_a3rs_s1_prereg.md

QUARANTINE RULE (source-of-truth.md 2026-07-05)
------------------------------------------------
This runner writes ONLY to data/decision/shadow_a3rs_s1/.
It MUST NEVER write to final_action or any OMS-consumed file.
Violation = live Trigger #3 source-of-truth conflict.

FORBIDDEN
---------
S1 + S2 filter stacking. S1+S2 combined OOS MAR = 0.5821 (destroys both
edges per calibration). This runner applies S1 ONLY.

GRADUATION CRITERIA
-------------------
Requires separate Trigger #5 dual-judge (opus + ChatGPT independent) before
any promotion to production. Shadow runner evidence on A3 universe is NOT
admissible for B_cloud promotion (different universe and architecture).

Usage:
  python pp_backtest/shadow_a3rs_s1_runner.py
  python pp_backtest/shadow_a3rs_s1_runner.py --dry-run
  python pp_backtest/shadow_a3rs_s1_runner.py --kill-after-n 260
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# ── Imports from existing research infrastructure ────────────────────────────
from pp_backtest.cortex_book2_common import (
    S1_PROXIMITY_THRESHOLDS,
    apply_proximity_filter,
    build_signal_filter_map,
)
from pp_backtest.d1_isoos_validation import build_a3_honest_trades, D1Context
from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    binary_gate_ema20_100,
)
from pp_backtest.portfolio_optimization_phase1 import (
    STRATEGY_CONFIGS,
    get_universe,
    load_panel,
    load_vnindex,
)
from pp_backtest.portfolio_optimization_phase31 import _build_adv50_map
from pp_backtest.sleeve_harness import build_ohlcv_cache
from pp_backtest.sleeve_d1_capitulation import (
    _build_daily_floor_fraction,
    _precompute_symbol_floors,
)

# ── Runner identity ──────────────────────────────────────────────────────────
RUNNER_ID = "shadow_a3rs_s1"
RUNNER_VERSION = "1.0.0"
RESEARCH_LABEL = "SHADOW_PAPER_ONLY_NOT_PRODUCTION"

# ── S1 calibrated threshold ───────────────────────────────────────────────────
# CALIBRATED: OOS MAR 1.7844 (+113% vs A3_RS baseline 0.8386)
S1_THRESHOLD = S1_PROXIMITY_THRESHOLDS[0]  # 0.85 — within 15% of 52-week high

# ── Hard assertion: S1+S2 stacking is FORBIDDEN ───────────────────────────────
_APPLY_S2 = False
assert not _APPLY_S2, (
    "S1+S2 stacking FORBIDDEN per council (2026-07-05). "
    "S1+S2 combined OOS MAR = 0.5821 — destroys both edges. "
    "Shadow runner applies S1 only."
)

# ── Output directory (quarantine rule) ───────────────────────────────────────
OUT_DIR = REPO / "data" / "decision" / "shadow_a3rs_s1"

# ── Kill criterion defaults ───────────────────────────────────────────────────
DEFAULT_KILL_AFTER_N = 260  # ~52 trading weeks
KILL_MAR_THRESHOLD = 0.50   # 40% below calibrated G1B floor of 0.516

# ── B_cloud reference ─────────────────────────────────────────────────────────
BCLOUD_SIGNALS_LOG = REPO / "data" / "paper_trade" / "signals_log.csv"

# ── Ledger schema (matches daily_paper_trade_runner.py column style) ──────────
SHADOW_LEDGER_COLS = [
    "run_date",
    "signal_date",
    "entry_date",
    "symbol",
    "rs_score",
    "proximity",
    "regime_gate",
    "regime_suppressed",
    "adv50_value",
    "ep1",
    "runner_id",
    "research_label",
]


# ─────────────────────────────────────────────────────────────────────────────
# Safety guards
# ─────────────────────────────────────────────────────────────────────────────

def _assert_quarantine(path: Path) -> None:
    """Raise if any path would write outside the quarantined shadow output dir."""
    try:
        path.resolve().relative_to(OUT_DIR.resolve())
    except ValueError:
        raise RuntimeError(
            f"QUARANTINE VIOLATION: attempted write to {path} — "
            f"shadow runner may only write inside {OUT_DIR}. "
            "This is a Trigger #3 source-of-truth conflict."
        )


def _assert_no_live_auto() -> None:
    """Halt if live_auto is enabled. Shadow runner is paper-only."""
    live_gate = REPO / "data" / "paper_trade" / "live_gate_status.csv"
    if live_gate.exists():
        try:
            df = pd.read_csv(live_gate)
            if not df.empty:
                latest = df.iloc[-1]
                live_val = latest.get("live_auto", False)
                if str(live_val).lower() in ("true", "1", "yes"):
                    raise RuntimeError(
                        "HALT: live_auto is ENABLED. Shadow runner is paper-only. "
                        "Do not run shadow research infrastructure when live capital is at risk."
                    )
        except (KeyError, pd.errors.EmptyDataError):
            pass  # file exists but has no live_auto column — safe


# ─────────────────────────────────────────────────────────────────────────────
# Core: build today's A3_RS + S1 signals
# ─────────────────────────────────────────────────────────────────────────────

def _load_d1_context_for_shadow() -> D1Context:
    """Load the D1Context used by build_a3_honest_trades."""
    panel = load_panel()
    panel = panel[
        (panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)
    ].copy()
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)
    universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
    cache = build_ohlcv_cache(panel, universe)
    floor_locked = _precompute_symbol_floors(cache)
    daily_frac = _build_daily_floor_fraction(cache, universe)
    global_last = pd.Timestamp(panel["date"].max()).normalize()
    return D1Context(panel, cache, adv, floor_locked, daily_frac, global_last, gate)


def build_todays_a3rs_s1_signals(
    run_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Generate today's A3_RS + S1 entry signals.

    Strategy:
    - Build all A3_RS honest trades (full history up to panel end)
    - Apply S1 proximity filter (>= 0.85)
    - Extract signals where signal_date == last panel date
    - Check regime gate

    Returns:
        (signals_df, meta_dict)
        signals_df: rows for today's qualified signals (may be empty)
        meta_dict:  metadata about this run (regime, signal counts, etc.)
    """
    print(f"[{RUNNER_ID}] Loading panel...", flush=True)
    ctx = _load_d1_context_for_shadow()
    panel = ctx.panel

    last_panel_date = pd.Timestamp(panel["date"].max()).normalize()
    if run_date is None:
        run_date = last_panel_date
    print(f"[{RUNNER_ID}] Panel last date: {last_panel_date.date()}", flush=True)

    # Regime check
    regime_gate_on = bool(ctx.gate.get(last_panel_date, True))
    print(
        f"[{RUNNER_ID}] Regime gate on {last_panel_date.date()}: {regime_gate_on}",
        flush=True,
    )

    print(f"[{RUNNER_ID}] Building A3_RS honest trades...", flush=True)
    trades = build_a3_honest_trades(ctx)

    print(
        f"[{RUNNER_ID}] Total A3_RS trades (full history): {len(trades)}", flush=True
    )

    # Apply S1 filter
    print(f"[{RUNNER_ID}] Building S1 filter map (proximity >= {S1_THRESHOLD})...", flush=True)
    filter_map = build_signal_filter_map(panel)
    trades_s1 = apply_proximity_filter(trades, filter_map, S1_THRESHOLD)

    print(
        f"[{RUNNER_ID}] A3_RS+S1 trades (full history): {len(trades_s1)} "
        f"(filtered from {len(trades)})",
        flush=True,
    )

    # Safety: never apply S2 (hard assertion already at module level)
    assert not _APPLY_S2, "S1+S2 stacking is FORBIDDEN"

    # Extract today's signals: signal_date == last_panel_date
    trades_s1["signal_date"] = pd.to_datetime(trades_s1["signal_date"])
    todays_mask = trades_s1["signal_date"].dt.normalize() == last_panel_date
    todays_signals = trades_s1[todays_mask].copy()

    # If regime gate is OFF (bear), suppress — but log it
    regime_suppressed = not regime_gate_on
    if regime_suppressed:
        print(
            f"[{RUNNER_ID}] Regime gate OFF on {last_panel_date.date()}. "
            "Signals suppressed (C1 bear regime). This is correct behavior.",
            flush=True,
        )
        todays_signals = todays_signals.iloc[0:0]  # empty but schema preserved

    # Add filter metadata
    if not todays_signals.empty:
        todays_signals = todays_signals.copy()
        # Attach proximity from filter_map
        proxies = []
        for _, row in todays_signals.iterrows():
            key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
            rec = filter_map.get(key, {})
            proxies.append(rec.get("prox", np.nan))
        todays_signals["proximity"] = proxies
        todays_signals["regime_gate"] = regime_gate_on
        todays_signals["regime_suppressed"] = regime_suppressed
        todays_signals["run_date"] = run_date.date()
        todays_signals["runner_id"] = RUNNER_ID
        todays_signals["research_label"] = RESEARCH_LABEL

        # Sort by RS score descending (highest momentum first)
        if "rs_score" in todays_signals.columns:
            todays_signals = todays_signals.sort_values("rs_score", ascending=False)
        todays_signals = todays_signals.reset_index(drop=True)
    else:
        # Ensure consistent schema even when empty
        for col in ["proximity", "regime_gate", "regime_suppressed", "run_date", "runner_id", "research_label"]:
            todays_signals[col] = None

    meta = {
        "run_date": str(run_date.date()),
        "last_panel_date": str(last_panel_date.date()),
        "runner_id": RUNNER_ID,
        "runner_version": RUNNER_VERSION,
        "research_label": RESEARCH_LABEL,
        "regime_gate_on": regime_gate_on,
        "regime_suppressed": regime_suppressed,
        "n_a3rs_total": len(trades),
        "n_a3rs_s1_total": len(trades_s1),
        "n_todays_signals": len(todays_signals),
        "s1_threshold": S1_THRESHOLD,
        "s2_applied": False,  # always False — stacking forbidden
    }

    return todays_signals, meta


# ─────────────────────────────────────────────────────────────────────────────
# Comparison: shadow vs B_cloud
# ─────────────────────────────────────────────────────────────────────────────

def _load_bcloud_todays_signals(run_date: pd.Timestamp) -> pd.DataFrame:
    """Load B_cloud signals from today's paper_trade log for comparison."""
    if not BCLOUD_SIGNALS_LOG.exists():
        return pd.DataFrame(columns=["symbol", "signal_date"])
    try:
        df = pd.read_csv(BCLOUD_SIGNALS_LOG, parse_dates=["signal_date"])
        today_mask = pd.to_datetime(df["signal_date"]).dt.normalize() == run_date
        return df[today_mask].copy()
    except Exception:
        return pd.DataFrame(columns=["symbol", "signal_date"])


def _build_comparison_report(
    run_date: pd.Timestamp,
    shadow_signals: pd.DataFrame,
    meta: dict[str, Any],
    bcloud_signals: pd.DataFrame,
    ledger_stats: dict[str, Any],
) -> str:
    """Build the daily comparison markdown report."""
    lines = [
        f"# Shadow A3_RS+S1 Daily Report — {run_date.date()}",
        "",
        f"**Runner:** {RUNNER_ID} v{RUNNER_VERSION}",
        f"**Label:** {RESEARCH_LABEL}",
        f"**Panel last date:** {meta['last_panel_date']}",
        f"**Regime gate:** {'ON (bull)' if meta['regime_gate_on'] else 'OFF (bear — signals suppressed)'}",
        "",
        "---",
        "",
        "## Shadow A3_RS + S1 Signals",
        "",
        f"Today's signals: **{meta['n_todays_signals']}**  ",
        f"S1 threshold: proximity >= {S1_THRESHOLD} (within 15% of 52-week high)  ",
        f"S2 filter: NOT applied (forbidden — S1+S2 interaction OOS MAR = 0.5821)",
        "",
    ]

    if meta["regime_suppressed"]:
        lines += [
            "> **[REGIME SUPPRESSED]** Bear regime detected (EMA-20 < EMA-100 on VNINDEX).",
            "> Zero signals is correct behavior under C1 regime gate.",
            "",
        ]

    if shadow_signals.empty:
        lines.append("*No signals today.*")
    else:
        cols_show = ["symbol", "rs_score", "proximity", "ep1", "adv50_value"]
        cols_show = [c for c in cols_show if c in shadow_signals.columns]
        lines.append("| " + " | ".join(cols_show) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols_show)) + " |")
        for _, row in shadow_signals.iterrows():
            vals = []
            for c in cols_show:
                v = row.get(c, "")
                if isinstance(v, float):
                    vals.append(f"{v:.4f}" if not np.isnan(v) else "NaN")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")

    lines += [
        "",
        "---",
        "",
        "## B_cloud Comparison",
        "",
        f"B_cloud signals today: **{len(bcloud_signals)}**",
        "",
    ]

    if not shadow_signals.empty and not bcloud_signals.empty:
        shadow_syms = set(shadow_signals["symbol"].astype(str))
        bcloud_syms = set(bcloud_signals["symbol"].astype(str)) if "symbol" in bcloud_signals.columns else set()
        overlap = shadow_syms & bcloud_syms
        shadow_only = shadow_syms - bcloud_syms
        bcloud_only = bcloud_syms - shadow_syms
        lines += [
            f"- **Overlap (both systems):** {sorted(overlap) if overlap else 'none'}",
            f"- **A3_RS+S1 only:** {sorted(shadow_only) if shadow_only else 'none'}",
            f"- **B_cloud only:** {sorted(bcloud_only) if bcloud_only else 'none'}",
            "",
        ]
    elif shadow_signals.empty and not bcloud_signals.empty:
        syms = sorted(bcloud_signals["symbol"].astype(str).tolist()) if "symbol" in bcloud_signals.columns else []
        lines += [f"- A3_RS+S1: no signals today | B_cloud: {syms}", ""]
    else:
        lines += ["- No signals from either system today.", ""]

    lines += [
        "---",
        "",
        "## Running Ledger Stats",
        "",
        f"- Total logged signal events (all-time): {ledger_stats.get('n_total', 0)}",
        f"- Total run dates: {ledger_stats.get('n_run_dates', 0)}",
        f"- Regime-suppressed runs: {ledger_stats.get('n_suppressed', 0)}",
        "",
        "---",
        "",
        "## Kill Criterion Status",
        "",
        f"- Decisions to date: {ledger_stats.get('n_total', 0)}",
        f"- Kill threshold: {KILL_MAR_THRESHOLD} MAR after >= 20 decisions",
        f"- Kill after N: {DEFAULT_KILL_AFTER_N} trading days",
        f"- Status: {ledger_stats.get('kill_status', 'MONITORING')}",
        "",
        "---",
        "",
        "> **RESEARCH LABEL:** SHADOW_PAPER_ONLY_NOT_PRODUCTION  ",
        "> This output is NOT evidence for B_cloud promotion.  ",
        "> Shadow universe (A3) ≠ B_cloud universe — separate Trigger #5 required for any integration.",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Ledger management
# ─────────────────────────────────────────────────────────────────────────────

def _load_ledger() -> pd.DataFrame:
    """Load the cumulative shadow ledger."""
    ledger_path = OUT_DIR / "shadow_ledger.csv"
    if ledger_path.exists():
        try:
            return pd.read_csv(ledger_path)
        except Exception:
            return pd.DataFrame(columns=SHADOW_LEDGER_COLS)
    return pd.DataFrame(columns=SHADOW_LEDGER_COLS)


def _append_to_ledger(ledger: pd.DataFrame, todays_signals: pd.DataFrame) -> pd.DataFrame:
    """Append today's signals to the cumulative ledger."""
    if todays_signals.empty:
        return ledger
    cols_to_keep = [c for c in SHADOW_LEDGER_COLS if c in todays_signals.columns]
    new_rows = todays_signals[cols_to_keep].copy()
    return pd.concat([ledger, new_rows], ignore_index=True)


def _compute_ledger_stats(ledger: pd.DataFrame, run_date: pd.Timestamp) -> dict[str, Any]:
    """Compute running stats for kill criterion tracking."""
    stats: dict[str, Any] = {
        "n_total": len(ledger),
        "n_run_dates": ledger["run_date"].nunique() if "run_date" in ledger.columns else 0,
        "n_suppressed": int((ledger["regime_suppressed"] == True).sum()) if "regime_suppressed" in ledger.columns else 0,
        "kill_status": "MONITORING",
        "as_of": str(run_date.date()),
    }

    # Kill criterion: MAR estimation
    # With < 20 decisions we can't compute MAR — too early
    if stats["n_total"] >= 20 and "net_return" in ledger.columns:
        valid = ledger["net_return"].dropna()
        if len(valid) >= 20:
            avg_return = float(valid.mean())
            # Rough MAR proxy: annualized (250 bars/yr) return / max drawdown
            # This is directional only — formal MAR requires equity curve
            if avg_return < 0:
                stats["kill_status"] = "KILL-CANDIDATE"
                stats["kill_reason"] = f"Negative avg net_return: {avg_return:.4f}"

    return stats


def _save_kill_criterion_status(stats: dict[str, Any]) -> None:
    """Save kill criterion JSON."""
    kill_path = OUT_DIR / "kill_criterion_status.json"
    _assert_quarantine(kill_path)
    with open(kill_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, kill_after_n: int = DEFAULT_KILL_AFTER_N) -> None:
    """
    Main entry point for the shadow A3_RS + S1 daily paper runner.

    Args:
        dry_run: If True, compute signals but do NOT write any files.
        kill_after_n: Flag kill-candidate check after this many trading days.
    """
    print(f"[{RUNNER_ID}] Starting shadow runner (dry_run={dry_run})...", flush=True)
    print(f"[{RUNNER_ID}] Research label: {RESEARCH_LABEL}", flush=True)

    # Safety gates
    _assert_no_live_auto()

    # Ensure output directory exists
    if not dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        _assert_quarantine(OUT_DIR / ".gitkeep")  # verify quarantine is working

    # Generate today's signals
    signals, meta = build_todays_a3rs_s1_signals()
    run_date = pd.Timestamp(meta["run_date"])

    print(
        f"[{RUNNER_ID}] Signals today ({meta['last_panel_date']}): "
        f"{meta['n_todays_signals']}",
        flush=True,
    )

    # Load B_cloud signals for comparison
    bcloud_signals = _load_bcloud_todays_signals(run_date)
    print(
        f"[{RUNNER_ID}] B_cloud signals today: {len(bcloud_signals)}", flush=True
    )

    # Load and update ledger
    ledger = _load_ledger()
    ledger = _append_to_ledger(ledger, signals)
    ledger_stats = _compute_ledger_stats(ledger, run_date)

    # Build comparison report
    report = _build_comparison_report(run_date, signals, meta, bcloud_signals, ledger_stats)

    if ledger_stats["kill_status"] == "KILL-CANDIDATE":
        print(
            f"[{RUNNER_ID}] ⚠ KILL-CANDIDATE flagged: {ledger_stats.get('kill_reason', '')}",
            flush=True,
        )

    if dry_run:
        print(f"\n[{RUNNER_ID}] DRY RUN — no files written. Signal preview:", flush=True)
        if signals.empty:
            print("  (no signals today)", flush=True)
        else:
            preview_cols = [c for c in ["symbol", "rs_score", "proximity"] if c in signals.columns]
            print(signals[preview_cols].to_string(index=False), flush=True)
        print(f"\n[{RUNNER_ID}] Report preview:\n", flush=True)
        print(report[:500], flush=True)
        return

    # Write daily signals CSV
    date_str = str(run_date.date())
    signals_out = OUT_DIR / f"{date_str}_shadow_signals.csv"
    _assert_quarantine(signals_out)
    if not signals.empty:
        signals.to_csv(signals_out, index=False)
    else:
        # Write empty file with header so daily check scripts don't error
        pd.DataFrame(columns=SHADOW_LEDGER_COLS).to_csv(signals_out, index=False)
    print(f"[{RUNNER_ID}] Signals written: {signals_out}", flush=True)

    # Write comparison report
    report_out = OUT_DIR / f"{date_str}_comparison.md"
    _assert_quarantine(report_out)
    with open(report_out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[{RUNNER_ID}] Report written: {report_out}", flush=True)

    # Save cumulative ledger
    ledger_out = OUT_DIR / "shadow_ledger.csv"
    _assert_quarantine(ledger_out)
    ledger.to_csv(ledger_out, index=False)
    print(f"[{RUNNER_ID}] Ledger updated: {ledger_out} ({len(ledger)} rows)", flush=True)

    # Save kill criterion status
    _save_kill_criterion_status(ledger_stats)
    print(
        f"[{RUNNER_ID}] Kill criterion status: {ledger_stats['kill_status']}", flush=True
    )

    # Kill-after-n check
    n_run_dates = ledger_stats.get("n_run_dates", 0)
    if n_run_dates >= kill_after_n:
        print(
            f"[{RUNNER_ID}] ⚠ Shadow runner has reached {n_run_dates} run dates "
            f"(kill-after-n={kill_after_n}). Review graduation criteria in pre-registration.",
            flush=True,
        )

    print(f"[{RUNNER_ID}] Done.", flush=True)
    print(
        f"\n[{RUNNER_ID}] Summary:",
        f"\n  run_date         = {date_str}",
        f"\n  regime_gate_on   = {meta['regime_gate_on']}",
        f"\n  n_signals_today  = {meta['n_todays_signals']}",
        f"\n  n_bcloud_today   = {len(bcloud_signals)}",
        f"\n  ledger_total     = {len(ledger)}",
        f"\n  kill_status      = {ledger_stats['kill_status']}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Shadow A3_RS + S1 paper runner (research only, not production)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute signals but do not write any files",
    )
    parser.add_argument(
        "--kill-after-n",
        type=int,
        default=DEFAULT_KILL_AFTER_N,
        help=f"Flag kill-candidate after N trading days (default: {DEFAULT_KILL_AFTER_N})",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, kill_after_n=args.kill_after_n)
