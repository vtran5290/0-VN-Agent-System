"""
Return-Monetization Optimization Runner
========================================

Executes Steps 1 and 2 of the frozen-strategy optimization plan.

Step 1 — Ranking / stock selection
    Sweeps 7 ranking modes × 4 anti-overextension filters for PRIMARY and SHADOW
    on ex-VIN3 (and full universe for SHADOW).
    Output: data/research/optimization/ranking_comparison.csv

Step 2 — Exit monetization (staged)
    2a: TP1 level × trail multiplier  (20 combos)
    2b: TP1 fraction × trail basis    (6 combos)
    2c: max hold × de-risk rules      (12 combos)
    All combos use the ema_dist ranking baseline.
    Output: data/research/optimization/exit_optimization.csv

Step 3 — Position sizing / exposure (separate script)
    PRIMARY + rank_mode ema_dist_mom60; sweeps max_positions, sizing_mode,
    gross_exposure; optional exit presets.
    Output: data/research/optimization/sizing_optimization_all_presets.csv (default --exit-preset all)
    Run: python pp_backtest/run_sizing_optimization.py [--exit-preset baseline|tuned_primary|tuned_shadow|all]

Usage
-----
Full run (both steps):
    python pp_backtest/run_optimization.py

Step 1 only:
    python pp_backtest/run_optimization.py --step 1

Step 2 only:
    python pp_backtest/run_optimization.py --step 2

Quick validation (30 most-liquid symbols):
    python pp_backtest/run_optimization.py --max-symbols 30

Design notes
------------
- Ranking comparison uses baseline exit (tp_pct=0.15, tp_frac=0.50,
  trail_mult=2.5, trail_basis=close, max_hold=250).
- Exit optimization uses baseline ranking (ema_dist, no anti-ext filter).
- Signals computed fresh each run; fast enough (<2 min total) without caching.
- Results are appended to CSV if file already exists (re-run-safe via overwrite).
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
    portfolio_metrics,
)
from pp_backtest.candidate_strategy_manifest import PRIMARY, SHADOW

# ── Constants ─────────────────────────────────────────────────────────────────

EX_VIN3_EXCLUDE = {"VIC", "VHM", "VRE", "VPL"}

DATA_CANDIDATES = [
    "data/research/ema_cloud/ohlcv_panel_ext2012.parquet",
    "data/fireant_ssot/ta_ohlcv_panel.parquet",
    "data/research/ema_cloud/ohlcv_panel_full.parquet",
]

OUT_DIR   = "data/research/optimization"
COST      = 0.004        # 40 bps round-trip
TEST_START = "2023-01-01"

# ── Step 1 sweep config ───────────────────────────────────────────────────────

RANK_MODES = [
    "ema_dist",         # baseline
    "mom20",
    "mom60",
    "ema_dist_mom20",
    "ema_dist_mom60",
    "ema_dist_liq",
    "mom20_liq",
]

ANTI_EXT_FILTERS = [None, 1.08, 1.12, 1.16]

BASELINE_EXIT_CFG = {
    "tp_pct":      0.15,
    "tp_frac":     0.50,
    "trail_mult":  2.5,
    "trail_basis": "close",
    "derisk_bars": None,
    "derisk_mult": None,
    "max_hold":    250,
}

# ── Step 2 sweep config ───────────────────────────────────────────────────────

# 2a: TP1 level × trail multiplier (others fixed at baseline)
STEP2A_TP_PCTS    = [0.10, 0.12, 0.15, 0.18, 0.20]
STEP2A_TRAIL_MULTS = [2.0, 2.5, 3.0, 3.5]

# 2b: TP1 fraction × trail basis (others fixed at baseline)
STEP2B_TP_FRACS    = [0.30, 0.50, 0.70]
STEP2B_TRAIL_BASES = ["close", "high"]

# 2c: max hold × de-risk rules (others fixed at baseline)
STEP2C_MAX_HOLDS = [150, 200, 250, 300]
STEP2C_DERISK    = [
    (None, None),    # no de-risk
    (100,  1.5),     # tighten to 1.5 ATR after 100 bars post-TP1
    (150,  1.5),     # tighten to 1.5 ATR after 150 bars post-TP1
]

# Strategies to test
STRATEGIES = [
    {**PRIMARY, "universe": "ex_vin3"},
    {**SHADOW,  "universe": "ex_vin3"},
    {**SHADOW,  "universe": "full"},
]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_panel(max_symbols: int | None = None) -> pd.DataFrame:
    data_path = next(
        (p for p in DATA_CANDIDATES if os.path.exists(p)), None
    )
    if data_path is None:
        raise FileNotFoundError(
            f"No OHLCV panel found. Checked: {DATA_CANDIDATES}"
        )

    print(f"Loading panel: {data_path}")
    cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
    # 'value' optional
    try:
        df = pd.read_parquet(data_path, columns=cols + ["value"])
    except Exception:
        df = pd.read_parquet(data_path, columns=cols)
        df["value"] = df["close"] * df["volume"]

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Drop thin symbols
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
          f"{df['date'].min().date()} – {df['date'].max().date()}")
    return df


def get_symbols(panel: pd.DataFrame, universe: str) -> list[str]:
    all_syms = sorted(panel["symbol"].unique())
    if universe == "ex_vin3":
        return [s for s in all_syms if s not in EX_VIN3_EXCLUDE]
    return all_syms  # "full"


# ── Core runner ───────────────────────────────────────────────────────────────

def _run_one(
    panel:              pd.DataFrame,
    symbols:            list[str],
    strat:              dict,
    exit_cfg:           dict,
    rank_mode:          str,
    anti_ext_threshold: float | None,
) -> dict:
    """Run one portfolio configuration.  Returns a metrics dict."""
    trades = compute_all_trades_v2(
        panel, symbols,
        entry_type=strat["entry_type"],
        ema_fast=strat["ema_fast"],
        ema_slow=strat["ema_slow"],
        exit_cfg=exit_cfg,
        cost=COST,
    )

    if trades.empty:
        return {
            "n_total_signals": 0, "n_trades": 0,
            "cagr": np.nan, "sharpe": np.nan, "max_dd": np.nan,
            "mar": np.nan, "hit_rate": np.nan,
            "avg_trade_ret": np.nan, "med_trade_ret": np.nan,
            "avg_hold_bars": np.nan, "fill_util": np.nan,
            "skipped_signals": 0, "oos_avg_ret": np.nan,
        }

    n_total = len(trades)

    equity, n_filled = build_portfolio_v2(
        trades,
        max_positions=strat.get("max_positions", 20),
        rank_mode=rank_mode,
        anti_ext_threshold=anti_ext_threshold,
    )

    m = portfolio_metrics(equity, trades, test_start=TEST_START)
    m["n_total_signals"] = n_total
    m["fill_util"]       = n_filled / n_total if n_total > 0 else 0.0
    m["skipped_signals"] = n_total - n_filled
    return m


# ── Step 1: ranking comparison ────────────────────────────────────────────────

def run_step1(panel: pd.DataFrame, out_dir: str) -> None:
    print("\n" + "=" * 70)
    print("STEP 1 — RANKING / STOCK SELECTION")
    print("=" * 70)

    rows = []
    t0   = time.time()
    total_runs = len(STRATEGIES) * len(RANK_MODES) * len(ANTI_EXT_FILTERS)
    run_i = 0

    for strat in STRATEGIES:
        symbols = get_symbols(panel, strat["universe"])
        label   = strat["label"]
        univ    = strat["universe"]

        for rank_mode in RANK_MODES:
            for anti_ext in ANTI_EXT_FILTERS:
                run_i += 1
                tag = f"{label} | {univ} | {rank_mode} | ext={anti_ext}"
                print(f"  [{run_i}/{total_runs}] {tag}", end="  ", flush=True)

                m = _run_one(
                    panel, symbols, strat,
                    exit_cfg=BASELINE_EXIT_CFG,
                    rank_mode=rank_mode,
                    anti_ext_threshold=anti_ext,
                )

                row = {
                    "strategy":         label,
                    "universe":         univ,
                    "rank_mode":        rank_mode,
                    "anti_ext_filter":  anti_ext if anti_ext is not None else "none",
                    "cagr":             m.get("cagr",          np.nan),
                    "sharpe":           m.get("sharpe",        np.nan),
                    "max_dd":           m.get("max_dd",        np.nan),
                    "mar":              m.get("mar",           np.nan),
                    "n_trades":         m.get("n_trades",      0),
                    "n_total_signals":  m.get("n_total_signals", 0),
                    "hit_rate":         m.get("hit_rate",      np.nan),
                    "avg_trade_ret":    m.get("avg_trade_ret", np.nan),
                    "med_trade_ret":    m.get("med_trade_ret", np.nan),
                    "avg_hold_bars":    m.get("avg_hold_bars", np.nan),
                    "fill_util":        m.get("fill_util",     np.nan),
                    "skipped_signals":  m.get("skipped_signals", 0),
                    "oos_avg_ret":      m.get("oos_avg_ret",   np.nan),
                    "oos_hit_rate":     m.get("oos_hit_rate",  np.nan),
                }
                rows.append(row)

                cagr_s  = f"{row['cagr']:.1%}" if not np.isnan(row['cagr']) else "n/a"
                sh_s    = f"{row['sharpe']:.3f}" if not np.isnan(row['sharpe']) else "n/a"
                dd_s    = f"{row['max_dd']:.1%}" if not np.isnan(row['max_dd']) else "n/a"
                print(f"CAGR={cagr_s}  Sh={sh_s}  DD={dd_s}  "
                      f"n={row['n_trades']}  fill={row['fill_util']:.0%}")

    df = pd.DataFrame(rows)
    path = os.path.join(out_dir, "ranking_comparison.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved {len(df)} rows -> {path}  ({time.time()-t0:.0f}s)")

    _print_ranking_summary(df)


def _print_ranking_summary(df: pd.DataFrame) -> None:
    sep = "-" * 70
    print(f"\n{sep}")
    print("RANKING SUMMARY — top 5 by Sharpe per strategy (no anti-ext filter)")
    print(sep)

    show = ["rank_mode", "anti_ext_filter", "cagr", "sharpe", "max_dd",
            "mar", "n_trades", "fill_util", "oos_avg_ret"]
    show = [c for c in show if c in df.columns]

    for strat_label in df["strategy"].unique():
        for univ in df[df["strategy"] == strat_label]["universe"].unique():
            sub = df[(df["strategy"] == strat_label) & (df["universe"] == univ)]
            top = sub.sort_values("sharpe", ascending=False).head(5)
            print(f"\n{strat_label} | {univ}")
            print(top[show].to_string(index=False, float_format="{:.4f}".format))


# ── Step 2: exit optimization ─────────────────────────────────────────────────

def run_step2(panel: pd.DataFrame, out_dir: str) -> None:
    print("\n" + "=" * 70)
    print("STEP 2 — EXIT MONETIZATION")
    print("=" * 70)

    rows: list[dict] = []
    t0   = time.time()

    # Only primary production strategies (ex_vin3); full-universe shadow is bonus
    core_strats = [s for s in STRATEGIES if s["universe"] == "ex_vin3"]

    # ── Stage 2a: TP1 level × trail multiplier ────────────────────────────────
    print("\n--- Stage 2a: TP1 level × trail multiplier ---")
    stage2a_combos = [
        (tp, tm)
        for tp in STEP2A_TP_PCTS
        for tm in STEP2A_TRAIL_MULTS
    ]
    total = len(core_strats) * len(stage2a_combos)
    i = 0
    for strat in core_strats:
        symbols = get_symbols(panel, strat["universe"])
        for tp_pct, trail_mult in stage2a_combos:
            i += 1
            cfg = {**BASELINE_EXIT_CFG, "tp_pct": tp_pct, "trail_mult": trail_mult}
            m   = _run_one(panel, symbols, strat, cfg, "ema_dist", None)
            rows.append(_exit_row(strat, cfg, "2a", m))
            _print_exit_progress(i, total, strat["label"], cfg, m)

    # ── Stage 2b: TP1 fraction × trail basis ─────────────────────────────────
    print("\n--- Stage 2b: TP1 fraction × trail basis ---")
    stage2b_combos = [
        (frac, basis)
        for frac  in STEP2B_TP_FRACS
        for basis in STEP2B_TRAIL_BASES
    ]
    total = len(core_strats) * len(stage2b_combos)
    i = 0
    for strat in core_strats:
        symbols = get_symbols(panel, strat["universe"])
        for tp_frac, trail_basis in stage2b_combos:
            i += 1
            cfg = {**BASELINE_EXIT_CFG, "tp_frac": tp_frac, "trail_basis": trail_basis}
            m   = _run_one(panel, symbols, strat, cfg, "ema_dist", None)
            rows.append(_exit_row(strat, cfg, "2b", m))
            _print_exit_progress(i, total, strat["label"], cfg, m)

    # ── Stage 2c: max hold × de-risk rules ───────────────────────────────────
    print("\n--- Stage 2c: max hold × de-risk rules ---")
    stage2c_combos = [
        (mh, db, dm)
        for mh         in STEP2C_MAX_HOLDS
        for (db, dm)   in STEP2C_DERISK
    ]
    total = len(core_strats) * len(stage2c_combos)
    i = 0
    for strat in core_strats:
        symbols = get_symbols(panel, strat["universe"])
        for max_hold, derisk_bars, derisk_mult in stage2c_combos:
            i += 1
            cfg = {
                **BASELINE_EXIT_CFG,
                "max_hold":    max_hold,
                "derisk_bars": derisk_bars,
                "derisk_mult": derisk_mult,
            }
            m = _run_one(panel, symbols, strat, cfg, "ema_dist", None)
            rows.append(_exit_row(strat, cfg, "2c", m))
            _print_exit_progress(i, total, strat["label"], cfg, m)

    df   = pd.DataFrame(rows)
    path = os.path.join(out_dir, "exit_optimization.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved {len(df)} rows -> {path}  ({time.time()-t0:.0f}s)")

    _print_exit_summary(df)


def _exit_row(strat: dict, cfg: dict, stage: str, m: dict) -> dict:
    return {
        "strategy":    strat["label"],
        "universe":    strat["universe"],
        "stage":       stage,
        "tp_pct":      cfg.get("tp_pct",      np.nan),
        "tp_frac":     cfg.get("tp_frac",     np.nan),
        "trail_mult":  cfg.get("trail_mult",  np.nan),
        "trail_basis": cfg.get("trail_basis", ""),
        "max_hold":    cfg.get("max_hold",    np.nan),
        "derisk_bars": cfg.get("derisk_bars") if cfg.get("derisk_bars") is not None else "none",
        "derisk_mult": cfg.get("derisk_mult") if cfg.get("derisk_mult") is not None else "none",
        "cagr":          m.get("cagr",          np.nan),
        "sharpe":        m.get("sharpe",        np.nan),
        "max_dd":        m.get("max_dd",        np.nan),
        "mar":           m.get("mar",           np.nan),
        "n_trades":      m.get("n_trades",      0),
        "hit_rate":      m.get("hit_rate",      np.nan),
        "avg_trade_ret": m.get("avg_trade_ret", np.nan),
        "med_trade_ret": m.get("med_trade_ret", np.nan),
        "avg_hold_bars": m.get("avg_hold_bars", np.nan),
        "oos_avg_ret":   m.get("oos_avg_ret",   np.nan),
        "oos_hit_rate":  m.get("oos_hit_rate",  np.nan),
    }


def _print_exit_progress(i: int, total: int, label: str, cfg: dict, m: dict) -> None:
    cagr_s = f"{m.get('cagr', float('nan')):.1%}" if not np.isnan(m.get('cagr', float('nan'))) else "n/a"
    sh_s   = f"{m.get('sharpe', float('nan')):.3f}" if not np.isnan(m.get('sharpe', float('nan'))) else "n/a"
    dd_s   = f"{m.get('max_dd', float('nan')):.1%}" if not np.isnan(m.get('max_dd', float('nan'))) else "n/a"
    print(f"  [{i}/{total}] {label} tp={cfg.get('tp_pct','?'):.0%} "
          f"frac={cfg.get('tp_frac','?'):.0%} "
          f"trail={cfg.get('trail_mult','?')} "
          f"basis={cfg.get('trail_basis','?')} "
          f"hold={cfg.get('max_hold','?')} "
          f"  CAGR={cagr_s} Sh={sh_s} DD={dd_s}")


def _print_exit_summary(df: pd.DataFrame) -> None:
    sep = "-" * 70
    print(f"\n{sep}")
    print("EXIT SUMMARY — top 5 by Sharpe per strategy × stage")
    print(sep)

    show = ["stage", "tp_pct", "tp_frac", "trail_mult", "trail_basis",
            "max_hold", "derisk_bars", "cagr", "sharpe", "max_dd", "mar",
            "avg_trade_ret", "avg_hold_bars"]
    show = [c for c in show if c in df.columns]

    for strat_label in df["strategy"].unique():
        sub = df[df["strategy"] == strat_label]
        print(f"\n{strat_label}")
        # Overall top 10 by Sharpe
        top = sub.sort_values("sharpe", ascending=False).head(10)
        print(top[show].to_string(index=False, float_format="{:.4f}".format))

    # Highlight baseline row
    base = df[
        (df["tp_pct"] == 0.15) &
        (df["tp_frac"] == 0.50) &
        (df["trail_mult"] == 2.5) &
        (df["trail_basis"] == "close") &
        (df["max_hold"] == 250) &
        (df["derisk_bars"] == "none")
    ]
    if not base.empty:
        print(f"\n{sep}")
        print("BASELINE (partial_tp default):")
        print(base[show].to_string(index=False, float_format="{:.4f}".format))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimization runner: Steps 1 (ranking) + 2 (exit)"
    )
    parser.add_argument(
        "--step", choices=["1", "2", "all"], default="all",
        help="Which step to run (default: all)",
    )
    parser.add_argument(
        "--max-symbols", type=int, default=None,
        help="Limit to N most-liquid symbols for fast validation runs",
    )
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    t_total = time.time()
    panel   = load_panel(args.max_symbols)

    if args.step in ("1", "all"):
        run_step1(panel, OUT_DIR)

    if args.step in ("2", "all"):
        run_step2(panel, OUT_DIR)

    print(f"\nTotal elapsed: {time.time() - t_total:.0f}s")
    print(f"Outputs in: {OUT_DIR}/")


if __name__ == "__main__":
    main()
