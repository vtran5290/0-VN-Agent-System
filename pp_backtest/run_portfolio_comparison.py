#!/usr/bin/env python3
"""
Portfolio comparison: Strategy A (short-horizon) vs Strategy B (long-horizon).

Tests the best candidates from Strategy A/B signal research with portfolio
position limits, exit modes, and realistic equity curve analysis.

Strategy A candidates (short-horizon):
  - donchian_20    + partial_tp    (best OOS, 25d focus)
  - base_high      + partial_tp    (best Sharpe at 50d)
  - base_high      + trailing_2.5

Strategy B candidates (long-horizon):
  - cloud_only (21/55)  + cloud_loss_3  (most OOS-stable)
  - cloud_only (21/55)  + partial_tp
  - cloud_only (20/100) + partial_tp

Max positions: 20 (equal weight, 5% per position)
Universe: full, ex-VIN

Usage:
    .venv\\Scripts\\python.exe pp_backtest/run_portfolio_comparison.py
    .venv\\Scripts\\python.exe pp_backtest/run_portfolio_comparison.py --fast  # 30-symbol sample
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import run_portfolio, portfolio_metrics

OUT_DIR = REPO / "data" / "research" / "portfolio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
FALLBACK_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"

EX_VIN = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

MAX_POSITIONS = 20
MAX_HOLD = 250

# Strategy configs to run
CONFIGS = [
    # (label, entry_type, ema_fast, ema_slow, exit_mode, max_hold)
    # Strategy A -- short horizon
    ("A_don20_partial_tp",   "donchian_20",  10, 50,  "partial_tp",   120),
    ("A_don20_trail25",      "donchian_20",  10, 50,  "trailing_2.5", 120),
    ("A_basehigh_partial_tp","base_high",    10, 50,  "partial_tp",   120),
    ("A_basehigh_trail25",   "base_high",    10, 50,  "trailing_2.5", 120),
    # Strategy B -- long horizon
    ("B_cloud21_55_cl3",     "cloud_only",   21, 55,  "cloud_loss_3", 250),
    ("B_cloud21_55_partial", "cloud_only",   21, 55,  "partial_tp",   250),
    ("B_cloud20_100_cl3",    "cloud_only",   20, 100, "cloud_loss_3", 250),
    ("B_cloud20_100_partial","cloud_only",   20, 100, "partial_tp",   250),
]


def load_panel(panel_path: Path) -> pd.DataFrame:
    if panel_path.exists():
        df = pd.read_parquet(panel_path)
    else:
        print(f"Panel not found: {panel_path}, using fallback")
        df = pd.read_parquet(FALLBACK_PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["symbol", "date"], inplace=True)
    print(f"Loaded panel: {df['symbol'].nunique()} symbols, {len(df):,} rows, "
          f"{df['date'].min().date()} to {df['date'].max().date()}")
    return df


def get_tracks(all_symbols: list[str]) -> dict[str, list[str]]:
    full = [s for s in all_symbols if s not in EXCLUDE_ALWAYS]
    ex_vin = [s for s in full if s not in EX_VIN]
    return {"full": full, "ex_vin": ex_vin}


def run_all(panel: pd.DataFrame, tracks: dict, fast: bool = False) -> pd.DataFrame:
    results = []
    t0 = time.time()

    for track_name, symbols in tracks.items():
        sym_list = symbols[:30] if fast else symbols
        print(f"\nTrack: {track_name} ({len(sym_list)} symbols)")

        for label, entry_type, ema_fast, ema_slow, exit_mode, max_hold in CONFIGS:
            t1 = time.time()
            print(f"  {label} ...", end=" ", flush=True)

            trades_df, equity = run_portfolio(
                panel, sym_list,
                entry_type=entry_type,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                exit_mode=exit_mode,
                max_positions=MAX_POSITIONS,
                max_hold=max_hold,
            )
            m = portfolio_metrics(equity, trades_df)
            if not m:
                print("no results")
                continue

            row = {
                "track":       track_name,
                "label":       label,
                "entry_type":  entry_type,
                "ema_fast":    ema_fast,
                "ema_slow":    ema_slow,
                "exit_mode":   exit_mode,
                "max_hold":    max_hold,
                **m,
            }
            results.append(row)
            print(f"CAGR={m.get('cagr', 0):.1%}  maxDD={m.get('max_dd', 0):.1%}  "
                  f"Sharpe={m.get('sharpe', 0):.3f}  n={m.get('n_trades', 0)}  "
                  f"({time.time()-t1:.0f}s)")

            # Save equity curve
            if not equity.empty:
                eq_path = OUT_DIR / f"equity_{track_name}_{label}.csv"
                equity.to_csv(eq_path)

    print(f"\nTotal elapsed: {time.time()-t0:.0f}s")
    return pd.DataFrame(results)


def print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 100)
    print("PORTFOLIO COMPARISON SUMMARY")
    print("=" * 100)

    hdr = (f"  {'label':<30}  {'track':<8}  {'CAGR':>7}  {'maxDD':>7}  "
           f"{'Sharpe':>7}  {'MAR':>6}  {'n_tr':>6}  {'hit%':>6}  "
           f"{'avg_tr':>7}  {'oos_avg':>8}  {'yrs':>5}")
    print(hdr)
    print("  " + "-" * 96)

    df_sorted = df.sort_values(["track", "cagr"], ascending=[True, False])
    for _, r in df_sorted.iterrows():
        print(f"  {r.label:<30}  {r.track:<8}  "
              f"{r.get('cagr', 0):>7.1%}  {r.get('max_dd', 0):>7.1%}  "
              f"{r.get('sharpe', 0):>7.3f}  {r.get('mar', 0):>6.2f}  "
              f"{int(r.get('n_trades', 0)):>6}  "
              f"{r.get('hit_rate', 0):>6.1%}  "
              f"{r.get('avg_trade_ret', 0):>7.1%}  "
              f"{r.get('oos_avg_ret', 0) if r.get('oos_avg_ret') else 0:>8.1%}  "
              f"{r.get('n_years', 0):>5.1f}")

    print("\nStrategy A (short horizon) vs Strategy B (long horizon) — ex-VIN track:")
    ex = df[df["track"] == "ex_vin"].copy()
    if not ex.empty:
        strat_a = ex[ex["label"].str.startswith("A_")].sort_values("cagr", ascending=False)
        strat_b = ex[ex["label"].str.startswith("B_")].sort_values("cagr", ascending=False)
        if not strat_a.empty:
            best_a = strat_a.iloc[0]
            print(f"  Best A: {best_a.label}  CAGR={best_a.get('cagr',0):.1%}  "
                  f"maxDD={best_a.get('max_dd',0):.1%}  Sharpe={best_a.get('sharpe',0):.3f}")
        if not strat_b.empty:
            best_b = strat_b.iloc[0]
            print(f"  Best B: {best_b.label}  CAGR={best_b.get('cagr',0):.1%}  "
                  f"maxDD={best_b.get('max_dd',0):.1%}  Sharpe={best_b.get('sharpe',0):.3f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default=str(DEFAULT_PANEL))
    p.add_argument("--fast", action="store_true", help="Use 30-symbol sample for speed test")
    args = p.parse_args()

    print("=== Portfolio Comparison: Strategy A vs Strategy B ===")
    panel = load_panel(Path(args.panel))
    all_symbols = sorted(panel["symbol"].unique().tolist())
    tracks = get_tracks(all_symbols)
    print(f"Tracks: full={len(tracks['full'])}, ex_vin={len(tracks['ex_vin'])}")

    df = run_all(panel, tracks, fast=args.fast)
    if df.empty:
        print("No results.")
        return

    df.to_csv(OUT_DIR / "portfolio_comparison.csv", index=False)
    print(f"\nSaved: {OUT_DIR / 'portfolio_comparison.csv'}")
    print_summary(df)


if __name__ == "__main__":
    main()
