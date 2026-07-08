#!/usr/bin/env python3
"""
Exit overlay harnesses — S20 count-only, PA-008 50d-MA stop, PA-009 2R partial exit.

All three overlays applied to A3_RS+S2@1.4x baseline.
Pre-regs:
  knowledge/backtests/2026-07-08_s20_count_only_prereg.md
  knowledge/backtests/2026-07-08_pa008_exit_prereg.md
  knowledge/backtests/2026-07-08_pa009_exit_prereg.md

RESEARCH_ONLY_NOT_PRODUCTION
Usage: python pp_backtest/cortex_exit_overlays.py
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

from pp_backtest.cortex_book1_common import OOS_WINDOW, PANEL_END, PANEL_START
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_volume_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.cortex_degeneracy_common import (
    OOS_END,
    OOS_START,
    build_symbol_panel,
    oos_entry_mask,
    rolling_sma,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    RESEARCH_LABEL,
    apply_size,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.ema_levels.indicators import compute_atr
from pp_backtest.phase_exit_sweep_core import MAX_POSITIONS
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)

OUT_DIR = REPO / "data" / "research" / "cortex_exit_overlays"

# Baseline from S2 extension recompute (2026-07-08)
S2_BASE_MULT = 1.4
NEW_BASELINE_OOS_MAR = 2.5292
REPRO_TOL = 0.050

# Gates (k=1 — new test category for each arm)
G1A_MARGIN = 0.050
G1A_THRESH = NEW_BASELINE_OOS_MAR + G1A_MARGIN   # 2.5792
G1B_THRESH = max(0.10, NEW_BASELINE_OOS_MAR * 0.50)  # 1.2646

# Cost model
COST_RT = 0.004  # 40bps round-trip (conservative)

# S20 parameters
S20_UP_FRAC = 0.70  # >= 70% up-days
S20_WINDOWS = [7, 10, 15]

# PA-008 parameters
PA008_MA_PERIOD = 50

# PA-009 parameters
PA009_INITIAL_STOP_ATR = 2.0  # R = 2.0 * ATR14


def _oos_metrics(eq: pd.Series) -> tuple[dict, dict, dict]:
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_a = slice_equity_years(eq, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_b = slice_equity_years(eq, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    return (
        _metrics_from_equity(eq_oos),
        _metrics_from_equity(eq_a),
        _metrics_from_equity(eq_b),
    )


def _gate_verdict(oos_mar: float) -> str:
    if not np.isfinite(oos_mar):
        return "PARKED"
    if oos_mar >= G1A_THRESH:
        return "ADVANCE"
    if oos_mar >= G1B_THRESH:
        return "CONDITIONAL-ADVANCE"
    return "FAIL"


def _atr14_at_entry(sp: dict, entry_i: int) -> float:
    if "atr" in sp:
        v = float(sp["atr"][entry_i])
        if np.isfinite(v) and v > 0:
            return v
    high = pd.Series(sp["high"])
    low = pd.Series(sp["low"])
    close = pd.Series(sp["close"])
    atr = compute_atr(high, low, close, 14).values
    v = float(atr[entry_i]) if entry_i < len(atr) else float("nan")
    return v if np.isfinite(v) and v > 0 else float("nan")


# ---------------------------------------------------------------------------
# Arm 1: S20 count-only exit
# ---------------------------------------------------------------------------

def _apply_s20_count_only(
    sized: pd.DataFrame,
    sym_panel: dict,
    window: int,
) -> pd.DataFrame:
    """Return modified trade dataframe where S20 count-only trigger overrides exit."""
    modified = sized.copy()
    modified["entry_date"] = pd.to_datetime(modified["entry_date"])
    modified["exit_date"] = pd.to_datetime(modified["exit_date"])

    oos_mask = oos_entry_mask(modified)
    oos_idx = modified.index[oos_mask]
    trigger_count = 0

    for idx in oos_idx:
        row = modified.loc[idx]
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            continue

        entry_price = float(row.get("blended_ep") or row.get("ep1") or 0.0)
        if entry_price <= 0:
            continue

        ei = sp["date_to_i"].get(pd.Timestamp(row["entry_date"]).normalize())
        xi = sp["date_to_i"].get(pd.Timestamp(row["exit_date"]).normalize())
        if ei is None or xi is None or xi <= ei:
            continue

        close = sp["close"]
        buffer: list[bool] = []
        triggered_i: int | None = None

        for i in range(ei + 1, xi + 1):
            if i < 1 or i >= len(close):
                continue
            prev = close[i - 1]
            if prev <= 0:
                continue
            up = close[i] > prev
            buffer.append(up)
            if len(buffer) > window:
                buffer.pop(0)
            if len(buffer) == window and sum(buffer) / window >= S20_UP_FRAC:
                triggered_i = i
                break

        if triggered_i is not None and triggered_i < len(close):
            new_price = close[triggered_i]
            if entry_price > 0 and new_price > 0:
                new_net = (new_price / entry_price) - 1.0 - COST_RT
                new_date = sp["dates"].iloc[triggered_i]
                modified.at[idx, "exit_date"] = pd.Timestamp(new_date).normalize()
                modified.at[idx, "net_return"] = new_net
                trigger_count += 1

    print(f"    S20 N={window}: {trigger_count}/{len(oos_idx)} OOS positions triggered early exit", flush=True)
    return modified


# ---------------------------------------------------------------------------
# Arm 2: PA-008 50d-MA stop exit
# ---------------------------------------------------------------------------

def _apply_pa008_ma_stop(
    sized: pd.DataFrame,
    sym_panel: dict,
) -> pd.DataFrame:
    """Return modified trade dataframe where 50d-MA stop triggers early exit."""
    modified = sized.copy()
    modified["entry_date"] = pd.to_datetime(modified["entry_date"])
    modified["exit_date"] = pd.to_datetime(modified["exit_date"])

    oos_mask = oos_entry_mask(modified)
    oos_idx = modified.index[oos_mask]
    trigger_count = 0

    for idx in oos_idx:
        row = modified.loc[idx]
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            continue

        entry_price = float(row.get("blended_ep") or row.get("ep1") or 0.0)
        if entry_price <= 0:
            continue

        ei = sp["date_to_i"].get(pd.Timestamp(row["entry_date"]).normalize())
        xi = sp["date_to_i"].get(pd.Timestamp(row["exit_date"]).normalize())
        if ei is None or xi is None or xi <= ei:
            continue

        close = sp["close"]
        be_active = False
        triggered_i: int | None = None

        for i in range(ei + 1, xi + 1):
            if i < PA008_MA_PERIOD or i >= len(close):
                continue
            sma50 = rolling_sma(close, i, PA008_MA_PERIOD)
            if not np.isfinite(sma50):
                continue
            if not be_active and sma50 >= entry_price:
                be_active = True
            if be_active and close[i] < sma50:
                triggered_i = i
                break

        if triggered_i is not None and triggered_i < len(close):
            new_price = close[triggered_i]
            if entry_price > 0 and new_price > 0:
                new_net = (new_price / entry_price) - 1.0 - COST_RT
                new_date = sp["dates"].iloc[triggered_i]
                modified.at[idx, "exit_date"] = pd.Timestamp(new_date).normalize()
                modified.at[idx, "net_return"] = new_net
                trigger_count += 1

    print(f"    PA-008: {trigger_count}/{len(oos_idx)} OOS positions stopped via 50d-MA", flush=True)
    return modified


# ---------------------------------------------------------------------------
# Arm 3: PA-009 2R partial exit (blended return approximation)
# ---------------------------------------------------------------------------

def _apply_pa009_partial_2r(
    sized: pd.DataFrame,
    sym_panel: dict,
) -> pd.DataFrame:
    """Return modified trade dataframe with blended 2R partial exit return.

    For positions that reach 2R: net_return = 0.5 * return_to_2r + 0.5 * original_return.
    For positions that don't reach 2R: unchanged.
    """
    modified = sized.copy()
    modified["entry_date"] = pd.to_datetime(modified["entry_date"])
    modified["exit_date"] = pd.to_datetime(modified["exit_date"])

    oos_mask = oos_entry_mask(modified)
    oos_idx = modified.index[oos_mask]
    trigger_count = 0

    for idx in oos_idx:
        row = modified.loc[idx]
        sym = str(row["symbol"])
        sp = sym_panel.get(sym)
        if sp is None:
            continue

        entry_price = float(row.get("blended_ep") or row.get("ep1") or 0.0)
        if entry_price <= 0:
            continue

        ei = sp["date_to_i"].get(pd.Timestamp(row["entry_date"]).normalize())
        xi = sp["date_to_i"].get(pd.Timestamp(row["exit_date"]).normalize())
        if ei is None or xi is None or xi <= ei:
            continue

        atr = _atr14_at_entry(sp, ei)
        if not np.isfinite(atr) or atr <= 0:
            continue

        r_dist = PA009_INITIAL_STOP_ATR * atr  # 1R distance
        target_2r = entry_price + 2.0 * r_dist

        hit_i: int | None = None
        for i in range(ei + 1, xi + 1):
            if i >= len(sp["high"]):
                continue
            if sp["high"][i] >= target_2r:
                hit_i = i
                break

        if hit_i is not None:
            half_return_at_2r = (target_2r / entry_price) - 1.0 - COST_RT / 2
            orig_return = float(row["net_return"])
            blended = 0.5 * half_return_at_2r + 0.5 * orig_return
            modified.at[idx, "net_return"] = blended
            trigger_count += 1

    print(f"    PA-009: {trigger_count}/{len(oos_idx)} OOS positions reached 2R (blended return applied)", flush=True)
    return modified


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(arm_name: str, results: list[dict], baseline_oos_mar: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = str(date.today())
    lines = [
        f"# Exit Overlays — {arm_name}",
        "",
        f"**Generated:** {today}",
        f"**Baseline (A3_RS+S2@1.4x):** OOS MAR = {baseline_oos_mar:.4f}",
        f"**G1a gate:** >= {G1A_THRESH:.4f}",
        f"**G1b gate:** >= {G1B_THRESH:.4f}",
        "",
        "| Candidate | OOS MAR | Delta | sub-A MAR | sub-B MAR | N_OOS | G1a | G1b | Verdict |",
        "|-----------|---------|-------|-----------|-----------|-------|-----|-----|---------|",
    ]
    for r in results:
        g1a = "PASS" if r["oos_mar"] >= G1A_THRESH else "FAIL"
        g1b = "PASS" if r["oos_mar"] >= G1B_THRESH else "FAIL"
        lines.append(
            f"| {r['label']} | {r['oos_mar']:.4f} | {r['delta']:+.4f} | "
            f"{r['sub_a_mar']:.4f} | {r['sub_b_mar']:.4f} | {r['n_oos']} | "
            f"{g1a} | {g1b} | {r['verdict']} |"
        )
    lines.append("")
    lines.append("RESEARCH_ONLY_NOT_PRODUCTION")

    slug = arm_name.lower().replace(" ", "_").replace("-", "_")
    (OUT_DIR / f"{slug}_report.md").write_text("\n".join(lines), encoding="utf-8")
    meta = {
        "generated": today,
        "arm": arm_name,
        "baseline_oos_mar": baseline_oos_mar,
        "g1a_thresh": G1A_THRESH,
        "g1b_thresh": G1B_THRESH,
        "results": results,
    }
    (OUT_DIR / f"{slug}_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"  Wrote {slug}_report.md and {slug}_meta.json", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_exit_overlays() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Exit Overlay Harnesses: S20 count-only / PA-008 / PA-009", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)
    print(f"  Baseline: A3_RS+S2@{S2_BASE_MULT}x OOS MAR = {NEW_BASELINE_OOS_MAR}", flush=True)

    # --- Step 1: Build A3_RS+S2@1.4x baseline ---
    print("\nStep 1: Building A3_RS+S2@1.4x stack...", flush=True)
    stack = build_baseline_stack()
    ctx = stack["ctx"]
    sctx = stack["sctx"]
    base_trades = stack["base_trades"]

    print("  Building volume filter map...", flush=True)
    filter_map = build_signal_filter_map(ctx.panel)
    s2_trades = apply_volume_filter(base_trades, filter_map, S2_BASE_MULT)
    sized = apply_size(s2_trades, sctx, leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    sized["entry_date"] = pd.to_datetime(sized["entry_date"])
    sized["exit_date"] = pd.to_datetime(sized["exit_date"])

    # Baseline verification
    prep_base = prepare_trades_with_size(sized, "rs_score", "_size_mult")
    eq_base, _, _ = run_capital_sim(prep_base, ctx.gate, D4_CASH_YIELD)
    m_oos, m_a, m_b = _oos_metrics(eq_base)
    baseline_oos_mar = float(m_oos["mar"])
    n_oos_base = count_oos_trades(sized, OOS_WINDOW[0], OOS_WINDOW[1])
    print(f"  A3_RS+S2@1.4x recomputed OOS MAR: {baseline_oos_mar:.4f} (expected {NEW_BASELINE_OOS_MAR})", flush=True)

    repro_ok = abs(baseline_oos_mar - NEW_BASELINE_OOS_MAR) <= REPRO_TOL
    if not repro_ok:
        print(f"  [BASELINE-DRIFT] deviation {abs(baseline_oos_mar - NEW_BASELINE_OOS_MAR):.4f} > {REPRO_TOL}", flush=True)
        print("  Halting — baseline drift detected. Investigate before proceeding.", flush=True)
        return {"halted": True, "baseline_oos_mar": baseline_oos_mar}

    print(f"  Reproducibility OK. N_OOS: {n_oos_base}", flush=True)

    # --- Step 2: Build symbol panel with ATR ---
    print("\nStep 2: Building symbol panel with ATR...", flush=True)
    sym_panel = build_symbol_panel(ctx.panel)
    for sym, sp in sym_panel.items():
        high = pd.Series(sp["high"])
        low = pd.Series(sp["low"])
        close = pd.Series(sp["close"])
        sp["atr"] = compute_atr(high, low, close, 14).values.astype(float)
    print(f"  Loaded {len(sym_panel)} symbols", flush=True)

    all_results: dict[str, Any] = {
        "baseline_oos_mar": baseline_oos_mar,
        "n_oos_base": n_oos_base,
        "arms": {},
    }

    # --- Step 3: S20 count-only ---
    print("\nStep 3: S20 count-only exit overlay...", flush=True)
    s20_results = []
    for w in S20_WINDOWS:
        label = f"s20_n{w}"
        print(f"  Window N={w}...", flush=True)
        mod = _apply_s20_count_only(sized, sym_panel, w)
        prep = prepare_trades_with_size(mod, "rs_score", "_size_mult")
        eq, _, _ = run_capital_sim(prep, ctx.gate, D4_CASH_YIELD)
        m, ma, mb = _oos_metrics(eq)
        oos_mar = float(m["mar"])
        n_oos = count_oos_trades(mod, OOS_WINDOW[0], OOS_WINDOW[1])
        verdict = _gate_verdict(oos_mar)
        print(f"    {label}: OOS MAR={oos_mar:.4f} sub-B={float(mb['mar']):.4f} verdict={verdict}", flush=True)
        s20_results.append({
            "label": label,
            "window": w,
            "oos_mar": oos_mar,
            "delta": oos_mar - baseline_oos_mar,
            "sub_a_mar": float(ma["mar"]),
            "sub_b_mar": float(mb["mar"]),
            "n_oos": n_oos,
            "verdict": verdict,
        })
    _write_report("S20_count_only", s20_results, baseline_oos_mar)
    all_results["arms"]["s20_count_only"] = s20_results

    # --- Step 4: PA-008 50d-MA stop ---
    print("\nStep 4: PA-008 50d-MA stop exit...", flush=True)
    mod_pa008 = _apply_pa008_ma_stop(sized, sym_panel)
    prep_pa008 = prepare_trades_with_size(mod_pa008, "rs_score", "_size_mult")
    eq_pa008, _, _ = run_capital_sim(prep_pa008, ctx.gate, D4_CASH_YIELD)
    m_pa008, ma_pa008, mb_pa008 = _oos_metrics(eq_pa008)
    oos_mar_pa008 = float(m_pa008["mar"])
    n_oos_pa008 = count_oos_trades(mod_pa008, OOS_WINDOW[0], OOS_WINDOW[1])
    verdict_pa008 = _gate_verdict(oos_mar_pa008)
    print(f"  PA-008: OOS MAR={oos_mar_pa008:.4f} MaxDD={float(m_pa008['max_dd']):.4f} verdict={verdict_pa008}", flush=True)
    pa008_result = [{
        "label": "pa008_ma50_stop",
        "oos_mar": oos_mar_pa008,
        "delta": oos_mar_pa008 - baseline_oos_mar,
        "sub_a_mar": float(ma_pa008["mar"]),
        "sub_b_mar": float(mb_pa008["mar"]),
        "oos_maxdd": float(m_pa008["max_dd"]),
        "n_oos": n_oos_pa008,
        "verdict": verdict_pa008,
    }]
    _write_report("PA008_MA_stop", pa008_result, baseline_oos_mar)
    all_results["arms"]["pa008_ma_stop"] = pa008_result

    # --- Step 5: PA-009 2R partial exit ---
    print("\nStep 5: PA-009 2R partial exit (blended return)...", flush=True)
    mod_pa009 = _apply_pa009_partial_2r(sized, sym_panel)
    prep_pa009 = prepare_trades_with_size(mod_pa009, "rs_score", "_size_mult")
    eq_pa009, _, _ = run_capital_sim(prep_pa009, ctx.gate, D4_CASH_YIELD)
    m_pa009, ma_pa009, mb_pa009 = _oos_metrics(eq_pa009)
    oos_mar_pa009 = float(m_pa009["mar"])
    n_oos_pa009 = count_oos_trades(mod_pa009, OOS_WINDOW[0], OOS_WINDOW[1])
    verdict_pa009 = _gate_verdict(oos_mar_pa009)
    print(f"  PA-009: OOS MAR={oos_mar_pa009:.4f} MaxDD={float(m_pa009['max_dd']):.4f} verdict={verdict_pa009}", flush=True)
    pa009_result = [{
        "label": "pa009_partial_2r",
        "oos_mar": oos_mar_pa009,
        "delta": oos_mar_pa009 - baseline_oos_mar,
        "sub_a_mar": float(ma_pa009["mar"]),
        "sub_b_mar": float(mb_pa009["mar"]),
        "oos_maxdd": float(m_pa009["max_dd"]),
        "n_oos": n_oos_pa009,
        "verdict": verdict_pa009,
    }]
    _write_report("PA009_partial_2R", pa009_result, baseline_oos_mar)
    all_results["arms"]["pa009_partial_2r"] = pa009_result

    # --- Step 6: Summary ---
    (OUT_DIR / "exit_overlays_summary.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )

    print("\n=== SUMMARY ===", flush=True)
    print(f"  Baseline (A3_RS+S2@1.4x): OOS MAR {baseline_oos_mar:.4f}", flush=True)
    for label, res in [("S20 N=7", s20_results[0]), ("S20 N=10", s20_results[1]), ("S20 N=15", s20_results[2]),
                       ("PA-008", pa008_result[0]), ("PA-009", pa009_result[0])]:
        print(f"  {label}: OOS MAR {res['oos_mar']:.4f} ({res['verdict']})", flush=True)

    return all_results


def main() -> None:
    run_exit_overlays()


if __name__ == "__main__":
    main()
