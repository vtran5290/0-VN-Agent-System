#!/usr/bin/env python3
"""
Strategy B -- Medium / Long Horizon Trend (Cloud-Only)

Horizons:  100d, 150d
Entry:     cloud_only (EMA cloud turns bullish)
EMA pairs: (21,55), (20,100)
Universe:  full, ex-VIN (ex VIC/VHM/VRE), VIN-only

Usage:
    .venv\\Scripts\\python.exe pp_backtest/run_strategy_b.py
    .venv\\Scripts\\python.exe pp_backtest/run_strategy_b.py --panel data/research/ema_cloud/ohlcv_panel_ext2012.parquet
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_levels.indicators import ema_cloud
from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.ema_levels.metrics import compute_metrics, composite_score

OUT_DIR = REPO / "data" / "research" / "strategy_b"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
FALLBACK_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"

EX_VIN = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

EMA_PAIRS = [(21, 55), (20, 100)]
HORIZONS  = [100, 150]

TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"

COST = 0.004  # 40 bps round-trip

SUBPERIODS = [
    ("2012-01-01", "2016-12-31", "2012-2016"),
    ("2017-01-01", "2019-12-31", "2017-2019"),
    ("2020-01-01", "2021-12-31", "2020-2021"),
    ("2022-01-01", "2022-12-31", "2022_bear"),
    ("2023-01-01", "2030-01-01", "2023-present"),
]

# For OOS: use last 2 subperiods as test, rest as train
TRAIN_PERIODS = ["2012-2016", "2017-2019", "2020-2021", "2022_bear"]
TEST_PERIODS  = ["2023-present"]


def load_panel(panel_path: Path) -> pd.DataFrame:
    if panel_path.exists():
        df = pd.read_parquet(panel_path)
    else:
        print(f"Panel not found: {panel_path}, falling back to {FALLBACK_PANEL}")
        df = pd.read_parquet(FALLBACK_PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["symbol", "date"], inplace=True)
    print(f"Loaded panel: {df['symbol'].nunique()} symbols, {len(df):,} rows, "
          f"{df['date'].min().date()} to {df['date'].max().date()}")
    return df


def get_universe_tracks(all_symbols: list[str]) -> dict[str, list[str]]:
    full = [s for s in all_symbols if s not in EXCLUDE_ALWAYS]
    ex_vin = [s for s in full if s not in EX_VIN]
    vin_only = [s for s in full if s in EX_VIN]
    return {
        "full":     full,
        "ex_vin":   ex_vin,
        "vin_only": vin_only,
    }


def forward_returns(close: pd.Series, h: int) -> pd.Series:
    """Entry at bar t+1 open (approx close[t+1]), exit at close[t+1+h]."""
    entry  = close.shift(-1)
    exit_p = close.shift(-(1 + h))
    return (exit_p - entry) / entry - COST


def process_symbol(sdf: pd.DataFrame, ema_fast: int, ema_slow: int) -> dict:
    """Compute cloud_only signals and forward returns for one symbol."""
    sdf = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    n      = len(close)

    # Indicators
    cloud = ema_cloud(close, ema_fast, ema_slow)
    fast_ema  = cloud["ema_fast"]
    cloud_bull = cloud["cloud_bull"]

    # Entry signal
    sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3, warmup=max(ema_slow + 5, 60))

    results = {}
    for h in HORIZONS:
        fwd = forward_returns(close, h)
        entry_dates = sdf.loc[sig, "date"]
        trade_rets = fwd[sig].dropna()
        if len(trade_rets) < 5:
            continue

        dates = sdf.loc[trade_rets.index, "date"]

        # Full period
        m_full = compute_metrics(pd.DataFrame({"net_return": trade_rets}))

        # Train / test split
        train_mask = dates < TEST_START
        test_mask  = dates >= TEST_START
        m_train = compute_metrics(pd.DataFrame({"net_return": trade_rets[train_mask]}))
        m_test  = compute_metrics(pd.DataFrame({"net_return": trade_rets[test_mask]}))

        # Subperiod returns
        period_avgs = []
        for sp_start, sp_end, sp_name in SUBPERIODS:
            sp_mask = (dates >= sp_start) & (dates < sp_end)
            sp_rets = trade_rets[sp_mask]
            if len(sp_rets) >= 5:
                period_avgs.append(sp_rets.mean())
        period_ret_std = float(np.std(period_avgs)) if len(period_avgs) >= 2 else np.nan
        n_pos_periods  = int(sum(a > 0 for a in period_avgs)) if period_avgs else 0

        oos_deg = (
            m_test.get("avg_return", np.nan) - m_train.get("avg_return", np.nan)
            if m_train.get("n_trades", 0) >= 5 and m_test.get("n_trades", 0) >= 5
            else np.nan
        )

        comp = composite_score(m_full, period_ret_std=period_ret_std)

        results[h] = {
            "n_trades":          m_full.get("n_trades", 0),
            "hit_rate":          m_full.get("hit_rate", np.nan),
            "avg_return":        m_full.get("avg_return", np.nan),
            "median_return":     m_full.get("median_return", np.nan),
            "std_return":        m_full.get("std_return", np.nan),
            "sharpe":            m_full.get("sharpe", np.nan),
            "max_dd":            m_full.get("max_dd", np.nan),
            "cagr":              m_full.get("cagr", np.nan),
            "train_avg_return":  m_train.get("avg_return", np.nan),
            "test_avg_return":   m_test.get("avg_return", np.nan),
            "oos_deg":           oos_deg,
            "period_ret_std":    period_ret_std,
            "n_pos_periods":     n_pos_periods,
            "composite":         comp,
        }
    return results


def run_track(panel: pd.DataFrame, symbols: list[str], track_name: str) -> pd.DataFrame:
    """Run Strategy B for one universe track."""
    print(f"\n  Track: {track_name} ({len(symbols)} symbols)")
    sub_panel = panel[panel["symbol"].isin(symbols)]

    rows = []
    t0 = time.time()
    done = 0
    for sym, sdf in sub_panel.groupby("symbol", sort=False):
        if len(sdf) < 100:
            continue
        for ema_fast, ema_slow in EMA_PAIRS:
            res = process_symbol(sdf, ema_fast, ema_slow)
            for h, m in res.items():
                rows.append({
                    "track":    track_name,
                    "ema_fast": ema_fast,
                    "ema_slow": ema_slow,
                    "horizon":  h,
                    "symbol":   sym,
                    **m,
                })
        done += 1
        if done % 50 == 0:
            print(f"    {done}/{len(symbols)} symbols  {time.time()-t0:.0f}s")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    print(f"    Done: {len(df)} rows in {time.time()-t0:.0f}s")
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Pool results across symbols."""
    if df.empty:
        return df
    grp = df.groupby(["track", "ema_fast", "ema_slow", "horizon"])
    agg = grp.agg(
        n_symbols=("symbol", "nunique"),
        n_trades=("n_trades", "sum"),
        avg_return=("avg_return", "mean"),
        median_return=("median_return", "mean"),
        hit_rate=("hit_rate", "mean"),
        sharpe=("sharpe", "mean"),
        oos_deg=("oos_deg", "mean"),
        train_avg=("train_avg_return", "mean"),
        test_avg=("test_avg_return", "mean"),
        n_pos_periods=("n_pos_periods", "mean"),
        period_ret_std=("period_ret_std", "mean"),
        composite=("composite", "mean"),
    ).reset_index()
    return agg.sort_values(["track", "horizon", "composite"], ascending=[True, True, False])


def print_results(agg: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STRATEGY B -- CLOUD-ONLY RESULTS")
    print("=" * 80)

    for track in agg["track"].unique():
        print(f"\n--- Track: {track} ---")
        sub = agg[agg["track"] == track]
        for h in HORIZONS:
            hsub = sub[sub["horizon"] == h].sort_values("composite", ascending=False)
            if hsub.empty:
                continue
            print(f"\n  Horizon {h}d:")
            hdr = f"  {'ema':>12}  {'n':>6}  {'hit%':>6}  {'avg%':>7}  {'med%':>7}  "
            hdr += f"{'sharpe':>7}  {'train%':>7}  {'test%':>7}  {'oos_deg':>8}  {'comp':>8}"
            print(hdr)
            for _, r in hsub.iterrows():
                print(f"  {r.ema_fast:>3}/{r.ema_slow:<3} (EMA)  "
                      f"{r.n_trades:>6.0f}  {r.hit_rate:>6.1%}  "
                      f"{r.avg_return:>7.1%}  {r.median_return:>7.1%}  "
                      f"{r.sharpe:>7.3f}  {r.train_avg:>7.1%}  "
                      f"{r.test_avg:>7.1%}  {r.oos_deg:>8.3f}  {r.composite:>8.4f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default=str(DEFAULT_PANEL))
    args = p.parse_args()

    t_total = time.time()
    print("=== Strategy B: Long-Horizon Cloud-Only ===")

    panel = load_panel(Path(args.panel))
    all_symbols = sorted(panel["symbol"].unique().tolist())
    tracks = get_universe_tracks(all_symbols)

    print(f"Universe tracks: full={len(tracks['full'])}, "
          f"ex_vin={len(tracks['ex_vin'])}, vin_only={len(tracks['vin_only'])}")

    all_rows = []
    for track_name, symbols in tracks.items():
        if not symbols:
            continue
        track_df = run_track(panel, symbols, track_name)
        if not track_df.empty:
            all_rows.append(track_df)

    if not all_rows:
        print("No results generated.")
        return

    raw_df = pd.concat(all_rows, ignore_index=True)
    raw_df.to_parquet(OUT_DIR / "strategy_b_symbol_stats.parquet")
    print(f"Saved symbol-level stats: {OUT_DIR / 'strategy_b_symbol_stats.parquet'}")

    agg = aggregate(raw_df)
    agg.to_csv(OUT_DIR / "strategy_b_results.csv", index=False)
    print(f"Saved aggregated results: {OUT_DIR / 'strategy_b_results.csv'}")

    print_results(agg)

    print(f"\nTotal elapsed: {time.time()-t_total:.0f}s")


if __name__ == "__main__":
    main()
