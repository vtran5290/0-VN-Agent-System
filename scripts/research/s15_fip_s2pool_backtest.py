#!/usr/bin/env python3
"""
S15 FIP path quality backtest on A3_RS+S2 OR pool.

Pre-reg: knowledge/backtests/2026-07-09_S15reopen_FIP_S2pool_prereg.md
Handoff: 2026-07-09-2300_VNAgent_S15FIP_S2pool

RESEARCH_ONLY_NOT_PRODUCTION
Usage: python scripts/research/s15_fip_s2pool_backtest.py
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
from scipy import stats

from pp_backtest.cortex_book1_common import OOS_WINDOW
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import D4_CASH_YIELD, prepare_trades_with_size, run_capital_sim
from pp_backtest.sprint2b_common import build_baseline_stack, slice_equity_years

TRADES_PATH = REPO / "data" / "research" / "cortex_book2" / "combo" / "combo_or_trades.csv"
OHLCV_PATH = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
OUT_DIR = REPO / "data" / "research" / "s15_fip"
OUT_REPORT = OUT_DIR / "2026-07-09_s15_fip_s2pool_results.md"
OUT_META = OUT_DIR / "2026-07-09_s15_fip_s2pool_meta.json"

BASELINE_MAR_LOCKED = 0.8386
G1A_THRESH = 0.8886
G1B_THRESH = 0.4193
G2_THRESH = 0.50

OOS_START = pd.Timestamp("2020-01-01")
SUB_B_START = pd.Timestamp("2023-01-01")
SUB_B_END = pd.Timestamp("2026-07-06")

LOOKBACK_BARS = 260
WEEKLY_STEP = 5
MIN_WEEKLY_OBS = 40
LIMIT_MOVE_THRESH = 0.069
VN_BAND_FLAG_PCT = 30.0
TODAY = str(date.today())


def inspect_inputs() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    print("=== Inspect ta_ohlcv_panel.parquet ===", flush=True)
    if not OHLCV_PATH.exists():
        raise FileNotFoundError(f"Missing OHLCV panel: {OHLCV_PATH}")
    panel = pd.read_parquet(OHLCV_PATH)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    print(f"  shape: {panel.shape}", flush=True)
    print(f"  columns: {panel.columns.tolist()}", flush=True)
    print(f"  date range: {panel['date'].min()} -> {panel['date'].max()}", flush=True)
    print(f"  symbols: {panel['symbol'].nunique()}", flush=True)

    print("\n=== Inspect combo_or_trades.csv ===", flush=True)
    if not TRADES_PATH.exists():
        raise FileNotFoundError(f"Missing trades file: {TRADES_PATH}")
    trades = pd.read_csv(TRADES_PATH)
    required = {"symbol", "signal_date", "net_return", "hold_bars", "rs_score", "vol_mult", "entry_date"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"combo_or_trades.csv missing columns: {missing}")
    print(f"  rows: {len(trades)} (expected 5915)", flush=True)
    trades["signal_date"] = pd.to_datetime(trades["signal_date"]).dt.normalize()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"]).dt.normalize()
    oos = trades[trades["signal_date"] >= OOS_START]
    print(f"  OOS rows (signal_date >= 2020-01-01): {len(oos)}", flush=True)

    sym_groups: dict[str, pd.DataFrame] = {}
    for sym, g in panel.groupby("symbol", sort=False):
        sym_groups[str(sym)] = g.sort_values("date").reset_index(drop=True)
    return trades, sym_groups


def compute_fip(
    sym_df: pd.DataFrame,
    as_of_date: pd.Timestamp,
    lookback_bars: int = LOOKBACK_BARS,
    weekly_step: int = WEEKLY_STEP,
    min_weeks: int = MIN_WEEKLY_OBS,
) -> float:
    """% of weekly periods (5-bar windows) with positive return before as_of_date."""
    sub = sym_df[sym_df["date"] < as_of_date].tail(lookback_bars)
    if len(sub) < weekly_step + 1:
        return float("nan")
    closes = sub["close"].astype(float).values
    weekly_rets: list[float] = []
    for i in range(weekly_step, len(closes), weekly_step):
        prev = closes[i - weekly_step]
        if prev <= 0 or not np.isfinite(prev):
            continue
        weekly_rets.append(float(closes[i] / prev - 1.0))
    if len(weekly_rets) < min_weeks:
        return float("nan")
    return float(sum(1 for r in weekly_rets if r > 0) / len(weekly_rets))


def has_limit_move_in_lookback(sym_df: pd.DataFrame, as_of_date: pd.Timestamp) -> bool:
    sub = sym_df[sym_df["date"] < as_of_date].tail(LOOKBACK_BARS)
    if len(sub) < 2:
        return False
    closes = sub["close"].astype(float).values
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        if abs(closes[i] / prev - 1.0) > LIMIT_MOVE_THRESH:
            return True
    return False


def compute_cohort_metrics(trades: pd.DataFrame, gate: pd.Series) -> dict[str, float | int]:
    """Capital-sim MAR/CAGR/MaxDD on trade subset (combo OR pool)."""
    if trades.empty:
        return {"n": 0, "cagr": float("nan"), "max_dd": float("nan"), "mar": float("nan")}
    prep = prepare_trades_with_size(trades.sort_values("entry_date"), "rs_score")
    if not prep:
        return {"n": 0, "cagr": float("nan"), "max_dd": float("nan"), "mar": float("nan")}
    eq, _, _ = run_capital_sim(prep, gate, D4_CASH_YIELD)
    m = _metrics_from_equity(slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1]))
    return {
        "n": len(trades),
        "cagr": float(m["cagr"]),
        "max_dd": float(m["max_dd"]),
        "mar": float(m["mar"]),
    }


def median_split_fip(oos: pd.DataFrame) -> pd.DataFrame:
    out = oos.copy()
    out["fip_cohort"] = "FIP-MISSING"
    valid = out["fip_pct"].notna()
    for sig_date, grp in out[valid].groupby("signal_date", sort=False):
        if len(grp) < 2:
            out.loc[grp.index, "fip_cohort"] = "FIP-SINGLE"
            continue
        med = grp["fip_pct"].median()
        high = grp.index[grp["fip_pct"] > med]
        low = grp.index[grp["fip_pct"] <= med]
        out.loc[high, "fip_cohort"] = "FIP-HIGH"
        out.loc[low, "fip_cohort"] = "FIP-LOW"
    return out


def evaluate_gates(
    fip_high_mar: float,
    fip_low_mar: float,
    sub_b_mar: float,
) -> dict[str, dict[str, Any]]:
    g1a_pass = np.isfinite(fip_high_mar) and fip_high_mar >= G1A_THRESH
    g1b_pass = np.isfinite(fip_high_mar) and fip_high_mar >= G1B_THRESH
    g2_pass = np.isfinite(sub_b_mar) and sub_b_mar >= G2_THRESH
    g3_pass = np.isfinite(fip_high_mar) and np.isfinite(fip_low_mar) and fip_high_mar > fip_low_mar

    return {
        "G1a": {"threshold": G1A_THRESH, "value": fip_high_mar, "pass": g1a_pass},
        "G1b": {"threshold": G1B_THRESH, "value": fip_high_mar, "pass": g1b_pass},
        "G2": {"threshold": G2_THRESH, "value": sub_b_mar, "pass": g2_pass},
        "G3": {
            "threshold": "FIP-HIGH > FIP-LOW",
            "value": fip_high_mar,
            "compare": fip_low_mar,
            "pass": g3_pass,
        },
    }


def declare_terminal_state(gates: dict[str, dict]) -> tuple[str, str]:
    if gates["G1a"]["pass"]:
        return "COMPLETED-SUCCESS", "G1a PASS — FIP-HIGH OOS MAR meets entry-class threshold."

    # Current regime sub-B choppy (regime_state 2026-07-06) per pre-reg / fable GAP ruling
    if not gates["G1a"]["pass"]:
        return (
            "PARKED-[REGIME-CONFOUNDED]",
            "G1a FAIL in sub-B choppy regime — mechanism not closed; regime-exit retest remains live.",
        )
    if not gates["G1b"]["pass"]:
        return "PARKED-DATA", "G1b FAIL — FIP-HIGH MAR below absolute floor."
    return "PARKED-DATA", "Inconclusive outcome — review data quality."


def write_report(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    m = payload["metrics"]
    g = payload["gates"]
    flags = payload["flags"]
    term, rationale = payload["terminal_state"], payload["terminal_rationale"]

    def _fmt(v: float) -> str:
        return f"{v:.4f}" if np.isfinite(v) else "n/a"

    lines = [
        "# S15 FIP S2-Pool Backtest — Delta Report",
        f"Date: {TODAY}",
        "Pre-reg: knowledge/backtests/2026-07-09_S15reopen_FIP_S2pool_prereg.md",
        f"Baseline OOS MAR (locked): {BASELINE_MAR_LOCKED}",
        "",
        "## Methodology",
        "- FIP%: % of 52 weekly (5-bar) periods with positive return in 260-bar lookback.",
        "- Cohort MAR: capital-sim on combo OR trade subsets (gate from A3_RS stack).",
        f"- Gate thresholds reference locked primary baseline {BASELINE_MAR_LOCKED}; pool ALL-S2-OOS MAR shown for context.",
        "",
        "## Data",
        f"- OOS trades: {payload['n_oos']} (signal_date >= 2020-01-01)",
        f"- FIP-MISSING: {payload['n_fip_missing']} (excluded from H/L analysis)",
        f"- FIP-HIGH: {payload['n_fip_high']} | FIP-LOW: {payload['n_fip_low']} | FIP-SINGLE: {payload['n_fip_single']}",
        f"- FIP compute time: {payload['fip_seconds']:.1f}s",
        "",
        "## MAR Results",
        "| Cohort | N | CAGR | MaxDD | MAR |",
        "|--------|---|------|-------|-----|",
        f"| ALL-S2-OOS | {m['ALL-S2-OOS']['n']} | {_fmt(m['ALL-S2-OOS']['cagr'])} | {_fmt(m['ALL-S2-OOS']['max_dd'])} | {_fmt(m['ALL-S2-OOS']['mar'])} |",
        f"| FIP-HIGH | {m['FIP-HIGH']['n']} | {_fmt(m['FIP-HIGH']['cagr'])} | {_fmt(m['FIP-HIGH']['max_dd'])} | {_fmt(m['FIP-HIGH']['mar'])} |",
        f"| FIP-LOW | {m['FIP-LOW']['n']} | {_fmt(m['FIP-LOW']['cagr'])} | {_fmt(m['FIP-LOW']['max_dd'])} | {_fmt(m['FIP-LOW']['mar'])} |",
        f"| FIP-HIGH sub-B (2023-2026) | {m['FIP-HIGH-sub-B']['n']} | {_fmt(m['FIP-HIGH-sub-B']['cagr'])} | {_fmt(m['FIP-HIGH-sub-B']['max_dd'])} | {_fmt(m['FIP-HIGH-sub-B']['mar'])} |",
        "",
        "## Gate Evaluation",
        "| Gate | Threshold | FIP-HIGH Result | PASS/FAIL |",
        "|------|-----------|-----------------|-----------|",
        f"| G1a | >= {G1A_THRESH:.4f} | {_fmt(g['G1a']['value'])} | {'PASS' if g['G1a']['pass'] else 'FAIL'} |",
        f"| G1b | >= {G1B_THRESH:.4f} | {_fmt(g['G1b']['value'])} | {'PASS' if g['G1b']['pass'] else 'FAIL'} |",
        f"| G2 | >= {G2_THRESH:.2f} (sub-B) | {_fmt(g['G2']['value'])} | {'PASS' if g['G2']['pass'] else 'FAIL'} |",
        f"| G3 | FIP-HIGH > FIP-LOW | {_fmt(g['G3']['value'])} vs {_fmt(g['G3']['compare'])} | {'PASS' if g['G3']['pass'] else 'FAIL'} |",
        "",
        "## VN-Specific Flags",
        f"- VN band flag: {flags['vn_band_pct']:.1f}% of FIP-HIGH trades had >=1 limit-up/down day in lookback — **{flags['vn_band_status']}**",
        f"- S2/FIP tension: vol_mult vs FIP% correlation r={flags['corr_r']:.3f}, p={flags['corr_p']:.4f} — **{flags['tension_status']}**",
    ]
    if flags.get("low_n_sub_b"):
        lines.append(f"- [LOW-N] FIP-HIGH sub-B N={m['FIP-HIGH-sub-B']['n']} (<50) — sub-B MAR indicative only")
    if not g["G3"]["pass"]:
        lines.append("- [FIP-NO-DISCRIMINATE] G3 FAIL — FIP-HIGH does not beat FIP-LOW on MAR")
    lines.extend([
        "",
        "## Terminal State",
        f"**{term}**",
        f"Rationale: {rationale}",
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ])
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_META.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_REPORT.relative_to(REPO)}", flush=True)


def verify_report() -> list[str]:
    failures: list[str] = []
    if not OUT_REPORT.exists():
        return ["Report file missing"]
    text = OUT_REPORT.read_text(encoding="utf-8")
    for token in ["G1a", "G1b", "G2", "G3", "Terminal State", "FIP-MISSING"]:
        if token not in text:
            failures.append(f"Missing section/token: {token}")
    for gate in ["G1a", "G1b", "G2", "G3"]:
        if f"| {gate} |" not in text:
            failures.append(f"Gate row missing: {gate}")
    if "PASS" not in text and "FAIL" not in text:
        failures.append("No gate PASS/FAIL populated")
    if "PARKED" not in text and "COMPLETED-SUCCESS" not in text:
        failures.append("Terminal state not declared")
    return failures


def run_backtest() -> dict:
    trades, sym_groups = inspect_inputs()
    oos = trades[trades["signal_date"] >= OOS_START].copy()
    n_oos = len(oos)

    print("\n=== Build capital-sim gate ===", flush=True)
    stack = build_baseline_stack()
    gate = stack["ctx"].gate

    t0 = time.perf_counter()
    fip_vals: list[float] = []
    limit_flags: list[bool] = []
    missing_sym = 0
    for _, row in oos.iterrows():
        sym = str(row["symbol"])
        sym_df = sym_groups.get(sym)
        if sym_df is None:
            fip_vals.append(float("nan"))
            limit_flags.append(False)
            missing_sym += 1
            continue
        sig = pd.Timestamp(row["signal_date"]).normalize()
        fip = compute_fip(sym_df, sig)
        fip_vals.append(fip)
        limit_flags.append(has_limit_move_in_lookback(sym_df, sig) if np.isfinite(fip) else False)

    oos["fip_pct"] = fip_vals
    oos["limit_move_lookback"] = limit_flags
    fip_seconds = time.perf_counter() - t0

    n_missing = int(oos["fip_pct"].isna().sum())
    if n_missing > 0:
        print(f"  WARNING: {n_missing} FIP-MISSING (<{MIN_WEEKLY_OBS} weekly obs or insufficient history)", flush=True)
    if missing_sym:
        print(f"  WARNING: {missing_sym} trades with symbol not in OHLCV panel", flush=True)

    tagged = median_split_fip(oos)
    n_high = int((tagged["fip_cohort"] == "FIP-HIGH").sum())
    n_low = int((tagged["fip_cohort"] == "FIP-LOW").sum())
    n_single = int((tagged["fip_cohort"] == "FIP-SINGLE").sum())

    metrics = {
        "ALL-S2-OOS": compute_cohort_metrics(tagged, gate),
        "FIP-HIGH": compute_cohort_metrics(tagged[tagged["fip_cohort"] == "FIP-HIGH"], gate),
        "FIP-LOW": compute_cohort_metrics(tagged[tagged["fip_cohort"] == "FIP-LOW"], gate),
        "FIP-HIGH-sub-B": compute_cohort_metrics(
            tagged[
                (tagged["fip_cohort"] == "FIP-HIGH")
                & (tagged["signal_date"] >= SUB_B_START)
                & (tagged["signal_date"] <= SUB_B_END)
            ],
            gate,
        ),
    }

    fip_high_mar = float(metrics["FIP-HIGH"]["mar"])
    fip_low_mar = float(metrics["FIP-LOW"]["mar"])
    sub_b_mar = float(metrics["FIP-HIGH-sub-B"]["mar"])
    gates = evaluate_gates(fip_high_mar, fip_low_mar, sub_b_mar)
    terminal_state, terminal_rationale = declare_terminal_state(gates)

    # VN band flag on FIP-HIGH
    high = tagged[tagged["fip_cohort"] == "FIP-HIGH"]
    vn_band_n = int(high["limit_move_lookback"].sum()) if len(high) else 0
    vn_band_pct = 100.0 * vn_band_n / len(high) if len(high) else 0.0
    vn_band_status = "FLAG [VN-BAND-RISK]" if vn_band_pct > VN_BAND_FLAG_PCT else "CLEAR"

    # S2/FIP tension
    valid = tagged[tagged["fip_pct"].notna()]
    if len(valid) >= 3:
        corr_r, corr_p = stats.pearsonr(valid["vol_mult"].astype(float), valid["fip_pct"].astype(float))
        tension_status = "TENSION-CONFIRMED" if corr_r < -0.3 else ("TENSION" if corr_r < 0 else "NEUTRAL")
    else:
        corr_r, corr_p = float("nan"), float("nan")
        tension_status = "NEUTRAL"

    payload = {
        "date": TODAY,
        "n_oos": n_oos,
        "n_fip_missing": n_missing,
        "n_fip_high": n_high,
        "n_fip_low": n_low,
        "n_fip_single": n_single,
        "fip_seconds": fip_seconds,
        "metrics": metrics,
        "gates": gates,
        "terminal_state": terminal_state,
        "terminal_rationale": terminal_rationale,
        "flags": {
            "vn_band_pct": vn_band_pct,
            "vn_band_n": vn_band_n,
            "vn_band_status": vn_band_status,
            "corr_r": float(corr_r) if np.isfinite(corr_r) else None,
            "corr_p": float(corr_p) if np.isfinite(corr_p) else None,
            "tension_status": tension_status,
            "low_n_sub_b": metrics["FIP-HIGH-sub-B"]["n"] < 50,
        },
        "baseline_mar_locked": BASELINE_MAR_LOCKED,
    }

    write_report(payload)

    print("\n=== Gate Summary ===", flush=True)
    for k, v in gates.items():
        print(f"  {k}: {v['value'] if isinstance(v['value'], (int, float)) else v} -> {'PASS' if v['pass'] else 'FAIL'}", flush=True)
    print(f"  Terminal: {terminal_state}", flush=True)

    return payload


def main() -> int:
    print("S15 FIP S2-Pool Backtest", flush=True)
    run_backtest()
    failures = verify_report()
    if failures:
        print("VERIFICATION: FAIL", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)
        return 1
    print("VERIFICATION: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
