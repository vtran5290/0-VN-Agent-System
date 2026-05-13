#!/usr/bin/env python3
"""
Strategy A -- Short-Horizon Breakout Comparison

Horizons:  25d, 50d
Entry types compared:
  1. level_breakout  -- multi-touch resistance breakout (lb=252, cp=2%, mt=3)
  2. donchian_N      -- pure Donchian (N=20, 50, 100), no cloud filter
  3. base_high_N     -- Donchian N=50 + cloud + freshness filter
Universe:  full, ex-VIN (ex VIC/VHM/VRE), VIN-only
EMA pairs: (10,50) default; also (5,20), (10,20) for level_breakout + base_high

Usage:
    .venv\\Scripts\\python.exe pp_backtest/run_strategy_a.py
    .venv\\Scripts\\python.exe pp_backtest/run_strategy_a.py --panel data/research/ema_cloud/ohlcv_panel_ext2012.parquet
    .venv\\Scripts\\python.exe pp_backtest/run_strategy_a.py --ema-only  # skip donchian, faster
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

from pp_backtest.ema_levels.indicators import ema_cloud, rolling_resistance, pivot_highs, compute_atr
from pp_backtest.ema_levels.entry import (
    breakout_signals, donchian_breakout, base_high_breakout,
)
from pp_backtest.ema_levels.metrics import compute_metrics, composite_score

OUT_DIR = REPO / "data" / "research" / "strategy_a"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PANEL  = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
FALLBACK_PANEL = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"

EX_VIN         = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

HORIZONS = [25, 50]

# Level breakout: fixed params (best from Phase 1)
LEVEL_LB = 252
LEVEL_CP = 0.02
LEVEL_MT = 3

# EMA pairs for level_breakout and base_high variants
EMA_PAIRS_LEVEL = [(10, 50), (5, 20), (10, 20)]

# Donchian N values (no cloud filter — pure momentum benchmark)
DONCHIAN_NS = [20, 50, 100]

# Base-high N (Donchian + cloud + freshness)
BASE_HIGH_NS = [50]
EMA_PAIRS_BASEHIGH = [(10, 50)]

TRAIN_END  = "2022-12-31"
TEST_START = "2023-01-01"
COST       = 0.004

SUBPERIODS = [
    ("2012-01-01", "2016-12-31", "2012-2016"),
    ("2017-01-01", "2019-12-31", "2017-2019"),
    ("2020-01-01", "2021-12-31", "2020-2021"),
    ("2022-01-01", "2022-12-31", "2022_bear"),
    ("2023-01-01", "2030-01-01", "2023-present"),
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


def get_universe_tracks(all_symbols: list[str]) -> dict[str, list[str]]:
    full    = [s for s in all_symbols if s not in EXCLUDE_ALWAYS]
    ex_vin  = [s for s in full if s not in EX_VIN]
    vin_only = [s for s in full if s in EX_VIN]
    return {"full": full, "ex_vin": ex_vin, "vin_only": vin_only}


def forward_returns(close: pd.Series, h: int) -> pd.Series:
    entry  = close.shift(-1)
    exit_p = close.shift(-(1 + h))
    return (exit_p - entry) / entry - COST


def summarise_trades(trade_rets: pd.Series, dates: pd.Series) -> dict:
    """Compute full-period + OOS + subperiod stats for a series of trades."""
    m_full = compute_metrics(pd.DataFrame({"net_return": trade_rets}))

    train_mask = dates < TEST_START
    test_mask  = dates >= TEST_START
    m_train = compute_metrics(pd.DataFrame({"net_return": trade_rets[train_mask]}))
    m_test  = compute_metrics(pd.DataFrame({"net_return": trade_rets[test_mask]}))

    period_avgs = []
    for sp_start, sp_end, _ in SUBPERIODS:
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

    return {
        "n_trades":         m_full.get("n_trades", 0),
        "hit_rate":         m_full.get("hit_rate", np.nan),
        "avg_return":       m_full.get("avg_return", np.nan),
        "median_return":    m_full.get("median_return", np.nan),
        "std_return":       m_full.get("std_return", np.nan),
        "sharpe":           m_full.get("sharpe", np.nan),
        "max_dd":           m_full.get("max_dd", np.nan),
        "cagr":             m_full.get("cagr", np.nan),
        "train_avg_return": m_train.get("avg_return", np.nan),
        "test_avg_return":  m_test.get("avg_return", np.nan),
        "oos_deg":          oos_deg,
        "period_ret_std":   period_ret_std,
        "n_pos_periods":    n_pos_periods,
        "composite":        comp,
    }


def process_symbol(sdf: pd.DataFrame) -> list[dict]:
    """Return a list of result dicts for all entry combos × horizons for one symbol."""
    sdf   = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    high   = sdf["high"]
    volume = sdf.get("volume", pd.Series(np.ones(len(sdf)), index=sdf.index))
    symbol = sdf["symbol"].iloc[0]

    rows = []

    # Pre-compute forward returns for both horizons once
    fwd = {h: forward_returns(close, h) for h in HORIZONS}

    def add_rows(sig: pd.Series, entry_type: str, ema_fast: int, ema_slow: int,
                 extra_params: dict | None = None):
        if sig.sum() == 0:
            return
        for h in HORIZONS:
            trade_rets = fwd[h][sig].dropna()
            if len(trade_rets) < 5:
                continue
            dates = sdf.loc[trade_rets.index, "date"]
            m = summarise_trades(trade_rets, dates)
            row = {
                "symbol":     symbol,
                "entry_type": entry_type,
                "ema_fast":   ema_fast,
                "ema_slow":   ema_slow,
                "horizon":    h,
                **m,
            }
            if extra_params:
                row.update(extra_params)
            rows.append(row)

    # 1. Level breakout: lb=252, cp=2%, mt=3
    ph = pivot_highs(high, pivot_window=5)
    for ema_fast, ema_slow in EMA_PAIRS_LEVEL:
        cloud = ema_cloud(close, ema_fast, ema_slow)
        cloud_bull = cloud["cloud_bull"]
        fast_ema = cloud["ema_fast"]
        resistance, r_strength = rolling_resistance(ph, lookback=LEVEL_LB,
                                                    cluster_pct=LEVEL_CP,
                                                    min_touches=LEVEL_MT)
        sig = breakout_signals(close, volume, resistance, r_strength,
                               cloud_bull, fast_ema,
                               buffer_pct=0.005, min_touches=LEVEL_MT,
                               warmup=max(ema_slow + 5, 60))
        add_rows(sig, "level_breakout", ema_fast, ema_slow,
                 {"lb": LEVEL_LB, "cp": LEVEL_CP, "mt": LEVEL_MT})

    # 2. Donchian: pure momentum, no cloud filter
    for n in DONCHIAN_NS:
        sig = donchian_breakout(close, n=n)
        add_rows(sig, f"donchian_{n}", 0, 0, {"lb": n})

    # 3. Base-high: Donchian + cloud + freshness
    for n in BASE_HIGH_NS:
        for ema_fast, ema_slow in EMA_PAIRS_BASEHIGH:
            cloud = ema_cloud(close, ema_fast, ema_slow)
            cloud_bull = cloud["cloud_bull"]
            fast_ema = cloud["ema_fast"]
            sig = base_high_breakout(close, cloud_bull, fast_ema,
                                     n=n, fresh_window=10,
                                     warmup=max(ema_slow + 5, 60))
            add_rows(sig, "base_high", ema_fast, ema_slow, {"lb": n})

    return rows


def run_track(panel: pd.DataFrame, symbols: list[str], track_name: str) -> pd.DataFrame:
    print(f"\n  Track: {track_name} ({len(symbols)} symbols)")
    sub_panel = panel[panel["symbol"].isin(symbols)]
    all_rows = []
    t0 = time.time()
    done = 0
    for sym, sdf in sub_panel.groupby("symbol", sort=False):
        if len(sdf) < 100:
            continue
        sym_rows = process_symbol(sdf)
        for r in sym_rows:
            r["track"] = track_name
        all_rows.extend(sym_rows)
        done += 1
        if done % 50 == 0:
            print(f"    {done}/{len(symbols)} symbols  {time.time()-t0:.0f}s")
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    print(f"    Done: {len(df)} rows in {time.time()-t0:.0f}s")
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    group_cols = ["track", "entry_type", "ema_fast", "ema_slow", "horizon"]
    grp = df.groupby(group_cols)
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
    print("\n" + "=" * 90)
    print("STRATEGY A -- SHORT-HORIZON BREAKOUT COMPARISON")
    print("=" * 90)

    for track in agg["track"].unique():
        print(f"\n--- Track: {track} ---")
        sub = agg[agg["track"] == track]
        for h in HORIZONS:
            hsub = sub[sub["horizon"] == h].sort_values("composite", ascending=False)
            if hsub.empty:
                continue
            print(f"\n  Horizon {h}d (top 10 by composite):")
            hdr = (f"  {'entry_type':<20}  {'ema':>10}  {'n_tr':>6}  "
                   f"{'hit%':>6}  {'avg%':>7}  {'med%':>7}  {'sharpe':>7}  "
                   f"{'train%':>7}  {'test%':>7}  {'oos_deg':>8}  {'comp':>8}")
            print(hdr)
            for _, r in hsub.head(10).iterrows():
                ema_str = f"{int(r.ema_fast)}/{int(r.ema_slow)}" if r.ema_fast > 0 else "n/a"
                print(f"  {r.entry_type:<20}  {ema_str:>10}  "
                      f"{int(r.n_trades):>6}  {r.hit_rate:>6.1%}  "
                      f"{r.avg_return:>7.1%}  {r.median_return:>7.1%}  "
                      f"{r.sharpe:>7.3f}  {r.train_avg:>7.1%}  "
                      f"{r.test_avg:>7.1%}  {r.oos_deg:>8.3f}  {r.composite:>8.4f}")

    # Decisive comparison: level_breakout vs best Donchian vs base_high
    print("\n" + "=" * 90)
    print("BENCHMARK VERDICT: Does level_breakout outperform simpler alternatives?")
    print("=" * 90)
    for track in ["full", "ex_vin"]:
        sub = agg[agg["track"] == track]
        if sub.empty:
            continue
        print(f"\nTrack: {track}")
        for h in HORIZONS:
            hsub = sub[sub["horizon"] == h]
            if hsub.empty:
                continue
            print(f"\n  {h}d horizon:")

            # Best of each type
            for etype in ["level_breakout", "donchian_20", "donchian_50", "donchian_100",
                          "base_high"]:
                best = hsub[hsub["entry_type"] == etype].sort_values(
                    "composite", ascending=False
                ).head(1)
                if best.empty:
                    continue
                r = best.iloc[0]
                ema_str = (f"{int(r.ema_fast)}/{int(r.ema_slow)}"
                           if r.ema_fast > 0 else "n/a")
                print(f"    {r.entry_type:<20} ema={ema_str:>6}  "
                      f"avg={r.avg_return:>6.1%}  sharpe={r.sharpe:>6.3f}  "
                      f"test_avg={r.test_avg:>6.1%}  oos_deg={r.oos_deg:>7.3f}  "
                      f"comp={r.composite:>7.4f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default=str(DEFAULT_PANEL))
    args = p.parse_args()

    t_total = time.time()
    print("=== Strategy A: Short-Horizon Breakout Comparison ===")

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
    raw_df.to_parquet(OUT_DIR / "strategy_a_symbol_stats.parquet")
    print(f"Saved symbol-level stats: {OUT_DIR / 'strategy_a_symbol_stats.parquet'}")

    agg = aggregate(raw_df)
    agg.to_csv(OUT_DIR / "strategy_a_results.csv", index=False)
    print(f"Saved aggregated results: {OUT_DIR / 'strategy_a_results.csv'}")

    print_results(agg)
    print(f"\nTotal elapsed: {time.time()-t_total:.0f}s")


if __name__ == "__main__":
    main()
