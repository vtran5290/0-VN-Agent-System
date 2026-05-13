"""
EMA Cloud + Price Levels -- Backtest Sweep
==========================================

Phase 1  (--phase 1): Forward-return analysis across entry configs.
    * Computes returns at 25/50/100/150-day horizons for every parameter combo.
    * No exit logic -- pure signal-quality test.
    * Saves:  data/research/ema_levels/phase1_trades.parquet
              data/research/ema_levels/phase1_results.csv

Phase 2  (--phase 2): Exit-mode optimisation.
    * Loads phase1 results, picks top entry configs per horizon.
    * Re-runs those entries with each exit mode and records actual trade returns.
    * Saves:  data/research/ema_levels/phase2_trades.parquet
              data/research/ema_levels/phase2_results.csv

Usage
-----
Validation (fast, ~5 min):
    python pp_backtest/run_ema_levels.py --phase 1 --max-symbols 30

Full Phase 1 sweep (~30-60 min, all symbols):
    python pp_backtest/run_ema_levels.py --phase 1

Phase 2 (requires phase 1 results):
    python pp_backtest/run_ema_levels.py --phase 2

Data
----
Primary source: data/fireant_ssot/ta_ohlcv_panel.parquet  (2017-present, 1 564 symbols)
Fallback:       data/research/ema_cloud/ohlcv_panel_full.parquet (2018-present, 272 symbols)

Limitation: data begins 2017-2018, not 2012 as requested.  Results cover ~7-8 years.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pp_backtest.ema_levels.indicators import (
    ema_cloud, pivot_highs, pivot_lows,
    rolling_resistance, rolling_support, compute_atr,
)
from pp_backtest.ema_levels.entry import (
    breakout_signals, retest_signals, reclaim_signals,
    donchian_breakout, cloud_only_entry,
)
from pp_backtest.ema_levels.sim import fixed_horizon_trades, variable_exit_trades
from pp_backtest.ema_levels.metrics import (
    compute_metrics, subperiod_metrics, composite_score,
)


# ---------------------------------------------------------------------------
# Parameter grids
# ---------------------------------------------------------------------------

EMA_PAIRS      = [(5, 20), (10, 20), (10, 50), (20, 50), (21, 55), (20, 100), (20, 150)]
LEVEL_LOOKBACKS = [60, 120, 252]
CLUSTER_PCTS   = [0.02, 0.03, 0.05]
MIN_TOUCHES    = [2, 3]
PIVOT_WINDOW   = 5
HORIZONS       = [25, 50, 100, 150]

COST_BPS     = 40    # round-trip
MIN_ADV      = 2e9   # 2 B VND ADV50
MIN_HISTORY  = 60    # bars before first signal

MAIN_ENTRY_TYPES = [
    "breakout",
    "retest",
    "reclaim",
    "breakout+retest",
    "breakout+reclaim",
]

EXIT_MODES = {
    "cloud_loss_2":   dict(exit_mode="cloud_loss",  cloud_loss_k=2,  atr_mult=2.0, trail_mult=2.5),
    "cloud_loss_3":   dict(exit_mode="cloud_loss",  cloud_loss_k=3,  atr_mult=2.0, trail_mult=2.5),
    "level_loss":     dict(exit_mode="level_loss",  cloud_loss_k=2,  atr_mult=2.0, trail_mult=2.5),
    "atr_stop_2.0":   dict(exit_mode="atr_stop",    cloud_loss_k=2,  atr_mult=2.0, trail_mult=2.5),
    "atr_stop_3.0":   dict(exit_mode="atr_stop",    cloud_loss_k=2,  atr_mult=3.0, trail_mult=2.5),
    "trailing_2.5":   dict(exit_mode="trailing",    cloud_loss_k=2,  atr_mult=2.0, trail_mult=2.5),
    "trailing_3.5":   dict(exit_mode="trailing",    cloud_loss_k=2,  atr_mult=2.0, trail_mult=3.5),
    "partial_tp":     dict(exit_mode="partial_tp",  cloud_loss_k=2,  atr_mult=2.0, trail_mult=2.5),
}

SUBPERIODS = [
    ("2018-01-01", "2020-01-01", "2018-2019"),
    ("2020-01-01", "2022-01-01", "2020-2021"),
    ("2022-01-01", "2023-01-01", "2022_bear"),
    ("2023-01-01", "2026-12-31", "2023-present"),
]

TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(data_path: str, max_symbols: int | None, start_date: str) -> pd.DataFrame:
    print(f"Loading {data_path} -")
    df = pd.read_parquet(
        data_path,
        columns=["symbol", "date", "open", "high", "low", "close", "volume", "value"],
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= start_date]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Drop symbols with too few bars
    bar_counts = df.groupby("symbol").size()
    ok_syms = bar_counts[bar_counts >= MIN_HISTORY + 50].index
    df = df[df["symbol"].isin(ok_syms)]

    if max_symbols:
        top = (
            df.groupby("symbol")["value"].sum()
            .sort_values(ascending=False)
            .head(max_symbols)
            .index
        )
        df = df[df["symbol"].isin(top)]

    print(f"  {df['symbol'].nunique()} symbols, {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# Per-symbol processing -- Phase 1
# ---------------------------------------------------------------------------

def _generate_entry_signals(
    df_sym: pd.DataFrame,
    ema_pair: tuple,
    lookback: int,
    cluster_pct: float,
    min_touch: int,
    entry_type: str,
    ph: pd.Series,
    pl: pd.Series,
) -> pd.Series | None:
    """Compute entry signal for one (symbol, param-combo)."""
    close  = df_sym["close"]
    volume = df_sym["volume"]
    high   = df_sym["high"]
    low    = df_sym["low"]
    fast, slow = ema_pair

    cloud   = ema_cloud(close, fast, slow)
    res, rs = rolling_resistance(ph, lookback, cluster_pct, min_touch)
    sup, ss = rolling_support(pl, lookback, cluster_pct, min_touch)

    def _bo():
        return breakout_signals(
            close, volume, res, rs, cloud["cloud_bull"], cloud["ema_fast"],
            min_touches=min_touch, warmup=MIN_HISTORY,
        )

    def _rt():
        return retest_signals(
            close, volume, res, rs, cloud["cloud_bull"], cloud["ema_fast"],
            min_touches=min_touch, warmup=MIN_HISTORY,
        )

    def _rc():
        return reclaim_signals(
            close, cloud["ema_fast"], cloud["ema_slow"], cloud["cloud_bull"],
            warmup=MIN_HISTORY,
        )

    if entry_type == "breakout":
        sig = _bo()
    elif entry_type == "retest":
        sig = _rt()
    elif entry_type == "reclaim":
        sig = _rc()
    elif entry_type == "breakout+retest":
        sig = _bo() | _rt()
    elif entry_type == "breakout+reclaim":
        sig = _bo() | _rc()
    elif entry_type == "retest+reclaim":
        sig = _rt() | _rc()
    else:
        return None

    return sig


def _suffix_stats(rets: pd.Series) -> dict:
    """Compute sufficient statistics from a return series (for pooling across symbols)."""
    n = len(rets.dropna())
    if n == 0:
        return {}
    r = rets.dropna()
    return {
        "n_trades":    n,
        "n_wins":      int((r > 0).sum()),
        "sum_ret":     float(r.sum()),
        "sum_sq_ret":  float((r ** 2).sum()),
        "sum_pos_ret": float(r[r > 0].sum()),
        "sum_neg_ret": float(r[r < 0].sum()),   # stored as negative value
        "min_ret":     float(r.min()),
        "max_ret":     float(r.max()),
    }


def process_symbol_phase1(
    df_sym:     pd.DataFrame,
    param_grid: list[dict],
) -> pd.DataFrame:
    """
    Run all phase-1 parameter combos for one symbol.
    Returns compact per-(combo_key, horizon, period) SUFFICIENT STATISTICS --
    NOT raw trades.  This keeps memory O(combos x horizons x periods) per symbol
    regardless of signal frequency, making the full-universe sweep tractable.

    Columns returned:
        entry_type, ema_fast, ema_slow, lookback, cluster_pct, min_touches,
        horizon, period, n_trades, n_wins, sum_ret, sum_sq_ret, min_ret, max_ret
    """
    sym   = df_sym["symbol"].iloc[0]
    close = df_sym["close"]
    high  = df_sym["high"]
    low   = df_sym["low"]
    dates = pd.to_datetime(df_sym["date"])

    ph = pivot_highs(high, PIVOT_WINDOW)
    pl = pivot_lows(low, PIVOT_WINDOW)

    # All time-range buckets we want stats for
    period_defs = [("full", "2000-01-01", "2030-12-31")] + \
                  [(lbl, s, e) for s, e, lbl in SUBPERIODS] + \
                  [("train", "2000-01-01", TRAIN_END),
                   ("test",  TEST_START,   "2030-12-31")]

    all_rows: list[dict] = []

    def _add_combo(trades: pd.DataFrame, meta: dict) -> None:
        """Aggregate trades into per-(horizon, period) rows and append."""
        if len(trades) == 0:
            return
        trades = trades.copy()
        trades["entry_date"] = dates.iloc[trades["entry_bar"].values].values
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])

        for h in HORIZONS:
            h_trades = trades[trades["horizon"] == h]
            for period_label, p_start, p_end in period_defs:
                subset = h_trades[
                    (h_trades["entry_date"] >= p_start) &
                    (h_trades["entry_date"] <= p_end)
                ]
                ss = _suffix_stats(subset["net_return"])
                if not ss:
                    continue
                row = dict(meta)
                row["horizon"] = h
                row["period"]  = period_label
                row.update(ss)
                all_rows.append(row)

    # -- Main entry types -------------------------------------------
    for p in param_grid:
        fast, slow = p["ema_pair"]
        sig = _generate_entry_signals(
            df_sym, p["ema_pair"], p["lookback"], p["cluster_pct"],
            p["min_touches"], p["entry_type"], ph, pl,
        )
        if sig is None or sig.sum() == 0:
            continue

        trades = fixed_horizon_trades(
            df_sym, sig, HORIZONS, COST_BPS, MIN_ADV, MIN_HISTORY,
        )
        _add_combo(trades, {
            "entry_type": p["entry_type"], "ema_fast": fast, "ema_slow": slow,
            "lookback": p["lookback"], "cluster_pct": p["cluster_pct"],
            "min_touches": p["min_touches"],
        })

    # -- Benchmarks: cloud-only (per EMA pair, once) ----------------
    bench_ema_done: set[tuple] = set()
    for p in param_grid:
        ep = p["ema_pair"]
        if ep in bench_ema_done:
            continue
        bench_ema_done.add(ep)
        fast, slow = ep
        cloud = ema_cloud(close, fast, slow)

        sig = cloud_only_entry(close, cloud["ema_fast"], cloud["cloud_bull"],
                               warmup=MIN_HISTORY)
        if sig.sum() > 0:
            trades = fixed_horizon_trades(df_sym, sig, HORIZONS, COST_BPS, MIN_ADV, MIN_HISTORY)
            _add_combo(trades, {
                "entry_type": "cloud_only", "ema_fast": fast, "ema_slow": slow,
                "lookback": 0, "cluster_pct": 0.0, "min_touches": 0,
            })

    # -- Benchmarks: Donchian ---------------------------------------
    for don_n in [20, 50, 100]:
        sig = donchian_breakout(close, don_n, warmup=MIN_HISTORY)
        if sig.sum() > 0:
            trades = fixed_horizon_trades(df_sym, sig, HORIZONS, COST_BPS, MIN_ADV, MIN_HISTORY)
            _add_combo(trades, {
                "entry_type": f"donchian_{don_n}", "ema_fast": don_n, "ema_slow": don_n,
                "lookback": don_n, "cluster_pct": 0.0, "min_touches": 1,
            })

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Parameter grid builder
# ---------------------------------------------------------------------------

def build_phase1_grid() -> list[dict]:
    """
    Build the Phase 1 sweep grid for main entry types.

    Optimisation: reclaim doesn't use level params -- only generate
    one reclaim config per EMA pair (skip redundant lookback/cluster/touch variants).
    """
    grid = []
    seen_reclaim: set[tuple] = set()

    for ema_pair, lb, cp, mt, et in product(
        EMA_PAIRS, LEVEL_LOOKBACKS, CLUSTER_PCTS, MIN_TOUCHES, MAIN_ENTRY_TYPES
    ):
        if et == "reclaim":
            key = (ema_pair, et)
            if key in seen_reclaim:
                continue
            seen_reclaim.add(key)

        grid.append({
            "ema_pair":    ema_pair,
            "lookback":    lb,
            "cluster_pct": cp,
            "min_touches": mt,
            "entry_type":  et,
        })

    return grid


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _pool_stats(grp: pd.DataFrame) -> dict:
    """
    Reconstruct aggregate metrics from pooled sufficient statistics.
    grp must have: n_trades, n_wins, sum_ret, sum_sq_ret, sum_pos_ret, sum_neg_ret.
    """
    n       = int(grp["n_trades"].sum())
    n_wins  = int(grp["n_wins"].sum())
    sum_r   = float(grp["sum_ret"].sum())
    sum_sq  = float(grp["sum_sq_ret"].sum())
    if n == 0:
        return {"n_trades": 0}

    avg_r = sum_r / n
    # Pooled variance: Var = (sum_sq - n * avg^2) / (n-1)
    var_r = max((sum_sq - n * avg_r ** 2) / max(n - 1, 1), 0.0)
    std_r = var_r ** 0.5

    hit_rate = n_wins / n

    # Profit factor from individual-trade positive/negative sums (correct pooling)
    pf_win  = float(grp["sum_pos_ret"].sum()) if "sum_pos_ret" in grp.columns else 0.0
    pf_loss = abs(float(grp["sum_neg_ret"].sum())) if "sum_neg_ret" in grp.columns else 1e-12
    pf      = pf_win / max(pf_loss, 1e-12)

    return {
        "n_trades":       n,
        "hit_rate":       hit_rate,
        "avg_return":     avg_r,
        "std_return":     std_r,
        "profit_factor":  pf,
    }


def aggregate_phase1(stats: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-symbol sufficient statistics into per-(combo, horizon) metrics.
    stats: output of process_symbol_phase1 concatenated across all symbols.

    For phase 1 (fixed-horizon), max_dd from sequential equity is meaningless
    (trades overlap; portfolio model not simulated).  We use only per-trade
    stats: avg_return, hit_rate, Sharpe (per-trade), OOS degradation, stability.
    """
    combo_cols = ["entry_type", "ema_fast", "ema_slow", "lookback", "cluster_pct", "min_touches"]
    group_cols = combo_cols + ["horizon"]

    rows = []
    for keys, grp in stats.groupby(group_cols):
        row = dict(zip(group_cols, keys))
        h = row["horizon"]

        # Full-sample metrics
        full = grp[grp["period"] == "full"]
        m    = _pool_stats(full)
        if m.get("n_trades", 0) < 5:
            continue
        row.update(m)

        # Sharpe: approx annualised per-trade Sharpe = (avg_ret / std_ret) * sqrt(252/h)
        if m.get("std_return", 0) > 0:
            row["sharpe"] = (m["avg_return"] / m["std_return"]) * np.sqrt(252.0 / h)
        else:
            row["sharpe"] = np.nan

        # Train / test metrics
        train_m = _pool_stats(grp[grp["period"] == "train"])
        test_m  = _pool_stats(grp[grp["period"] == "test"])
        row["train_n"]          = train_m.get("n_trades", 0)
        row["train_avg_return"] = train_m.get("avg_return", np.nan)
        row["train_sharpe"]     = (
            (train_m["avg_return"] / train_m["std_return"]) * np.sqrt(252.0 / h)
            if train_m.get("std_return", 0) > 0 else np.nan
        )
        row["test_n"]           = test_m.get("n_trades", 0)
        row["test_avg_return"]  = test_m.get("avg_return", np.nan)
        row["test_sharpe"]      = (
            (test_m["avg_return"] / test_m["std_return"]) * np.sqrt(252.0 / h)
            if test_m.get("std_return", 0) > 0 else np.nan
        )

        # OOS degradation (positive = test improves on train)
        if not (np.isnan(row.get("train_avg_return", np.nan))
                or np.isnan(row.get("test_avg_return", np.nan))):
            row["oos_deg"] = row["test_avg_return"] - row["train_avg_return"]
        else:
            row["oos_deg"] = np.nan

        # Subperiod stability
        sub_avgs = []
        for _, _, lbl in SUBPERIODS:
            sp = grp[grp["period"] == lbl]
            sm = _pool_stats(sp)
            sub_avgs.append(sm.get("avg_return", np.nan))
        valid = [x for x in sub_avgs if not np.isnan(x)]
        row["period_ret_std"] = float(np.std(valid)) if len(valid) >= 2 else np.nan
        row["n_pos_periods"]  = int(sum(x > 0 for x in valid))

        # Phase-1 composite: no max_dd penalty (not applicable to overlapping fixed-horizon)
        row["composite"] = _composite_phase1(row)
        rows.append(row)

    return pd.DataFrame(rows)


def _composite_phase1(row: dict) -> float:
    """
    Phase-1 composite score: signal quality without max_dd.
    Penalises small sample, OOS degradation, and period instability.
    """
    n       = row.get("n_trades", 0) or 0
    avg_r   = row.get("avg_return", np.nan)
    sh      = row.get("sharpe", np.nan)
    oos     = row.get("oos_deg", np.nan)
    p_std   = row.get("period_ret_std", np.nan)
    n_pos   = row.get("n_pos_periods", 0) or 0

    if n < 20 or np.isnan(avg_r):
        return -999.0

    avg_r  = float(np.clip(avg_r, -0.5,  1.5))
    sh     = float(np.clip(sh or 0,  -3.0, 10.0))
    oos    = float(oos) if not np.isnan(oos) else 0.0
    p_std  = float(p_std) if not np.isnan(p_std) else 0.1

    return_s  = avg_r   * 0.35
    sharp_s   = (sh / 5.0) * 0.30
    stab_s    = max(0.0, 0.5 - p_std * 6.0) * 0.20
    period_s  = (n_pos / max(len(SUBPERIODS), 1)) * 0.10
    size_s    = min(np.log10(max(n, 1)) / 4.0, 1.0) * 0.05

    oos_penalty = max(0.0, -oos) * 0.30   # subtract if OOS degrades

    return return_s + sharp_s + stab_s + period_s + size_s - oos_penalty


# ---------------------------------------------------------------------------
# Phase 2: exit optimisation
# ---------------------------------------------------------------------------

def run_phase2(
    all_phase1:  pd.DataFrame,
    phase1_agg:  pd.DataFrame,
    df_all:      pd.DataFrame,
    out_dir:     str,
    top_n:       int = 15,
) -> None:
    """
    For the top `top_n` entry configurations (by composite score, averaged across horizons),
    simulate trades under every exit mode.  Save results to phase2_*.
    """
    print("\n=== Phase 2: Exit Optimisation ===")

    # Pick top entry configs (exclude benchmarks for exit test)
    cfg_cols = ["entry_type", "ema_fast", "ema_slow", "lookback", "cluster_pct", "min_touches"]
    non_bench = phase1_agg[~phase1_agg["entry_type"].str.startswith(("donchian", "cloud_only"))]

    # Average composite score across horizons
    avg_score = (
        non_bench.groupby(cfg_cols)["composite"]
        .mean()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    print(f"  Top {len(avg_score)} entry configs selected for exit optimisation")

    symbols = df_all["symbol"].unique()
    all_trades: list[pd.DataFrame] = []

    for _, cfg_row in avg_score.iterrows():
        entry_type = cfg_row["entry_type"]
        fast       = int(cfg_row["ema_fast"])
        slow       = int(cfg_row["ema_slow"])
        lb         = int(cfg_row["lookback"])
        cp         = float(cfg_row["cluster_pct"])
        mt         = int(cfg_row["min_touches"])

        for exit_name, exit_kwargs in EXIT_MODES.items():
            sym_trades: list[pd.DataFrame] = []

            for sym in symbols:
                df_sym = df_all[df_all["symbol"] == sym].copy().reset_index(drop=True)
                if len(df_sym) < MIN_HISTORY + 50:
                    continue

                close  = df_sym["close"]
                high   = df_sym["high"]
                low    = df_sym["low"]
                volume = df_sym["volume"]

                ph = pivot_highs(high, PIVOT_WINDOW)
                pl = pivot_lows(low, PIVOT_WINDOW)

                cloud   = ema_cloud(close, fast, slow)
                res, rs = rolling_resistance(ph, lb, cp, mt)
                sup, ss = rolling_support(pl, lb, cp, mt)
                atr_s   = compute_atr(high, low, close, 14)

                sig = _generate_entry_signals(
                    df_sym, (fast, slow), lb, cp, mt, entry_type, ph, pl,
                )
                if sig is None or sig.sum() == 0:
                    continue

                trades = variable_exit_trades(
                    df_sym, sig,
                    ema_slow=cloud["ema_slow"],
                    support=sup,
                    atr_series=atr_s,
                    cost_bps=COST_BPS,
                    min_adv=MIN_ADV,
                    min_history=MIN_HISTORY,
                    **exit_kwargs,
                )
                if len(trades) == 0:
                    continue

                trades["symbol"]      = sym
                trades["entry_type"]  = entry_type
                trades["ema_fast"]    = fast
                trades["ema_slow"]    = slow
                trades["lookback"]    = lb
                trades["cluster_pct"] = cp
                trades["min_touches"] = mt
                trades["exit_name"]   = exit_name
                sym_trades.append(trades)

            if sym_trades:
                all_trades.append(pd.concat(sym_trades, ignore_index=True))

    if not all_trades:
        print("  No Phase 2 trades generated!")
        return

    p2 = pd.concat(all_trades, ignore_index=True)
    p2_path = os.path.join(out_dir, "phase2_trades.parquet")
    p2.to_parquet(p2_path, index=False)
    print(f"  Saved {len(p2):,} phase-2 trades -> {p2_path}")

    # Aggregate
    gcols = ["entry_type", "ema_fast", "ema_slow", "lookback", "cluster_pct", "min_touches", "exit_name"]
    p2["entry_date"] = pd.to_datetime(p2["entry_date"])
    rows = []
    for keys, grp in p2.groupby(gcols):
        m = compute_metrics(grp, "net_return")
        row = dict(zip(gcols, keys))
        row.update(m)
        row["composite"] = composite_score(m)
        rows.append(row)

    p2_agg = pd.DataFrame(rows)
    p2_agg_path = os.path.join(out_dir, "phase2_results.csv")
    p2_agg.to_csv(p2_agg_path, index=False)
    print(f"  Saved phase-2 aggregated -> {p2_agg_path}")

    # Print summary
    print("\n--- Phase 2 top exit modes (by composite) ---")
    top_exit = (
        p2_agg.sort_values("composite", ascending=False)
        .head(20)[["entry_type", "exit_name", "n_trades", "hit_rate",
                   "avg_return", "median_return", "max_dd", "sharpe", "cagr", "composite"]]
    )
    print(top_exit.to_string(index=False, float_format="{:.3f}".format))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_phase1_report(agg: pd.DataFrame) -> None:
    sep = "=" * 80

    print(f"\n{sep}")
    print("PHASE 1 -- FORWARD RETURN ANALYSIS")
    print(sep)

    show_cols = [
        "entry_type", "ema_fast", "ema_slow", "lookback", "cluster_pct", "min_touches",
        "n_trades", "hit_rate", "avg_return", "std_return", "profit_factor",
        "sharpe", "train_avg_return", "test_avg_return",
        "oos_deg", "period_ret_std", "n_pos_periods", "composite",
    ]
    show_cols = [c for c in show_cols if c in agg.columns]

    for h in HORIZONS:
        sub = agg[agg["horizon"] == h]
        top = sub.sort_values("composite", ascending=False).head(15)
        print(f"\n--- Horizon {h}d -- TOP 15 ---")
        if len(top):
            print(top[show_cols].to_string(index=False, float_format="{:.3f}".format))

    # Benchmark comparison
    print(f"\n{sep}")
    print("BENCHMARK COMPARISON (avg_return by horizon)")
    print(sep)
    bench_types = [t for t in agg["entry_type"].unique()
                   if t.startswith("donchian") or t == "cloud_only"]
    bench_sub = agg[agg["entry_type"].isin(bench_types)]
    pivot_bench = bench_sub.pivot_table(
        index="entry_type", columns="horizon",
        values="avg_return", aggfunc="mean",
    )
    print(pivot_bench.to_string(float_format="{:.4f}".format))

    # OOS degradation flag
    print(f"\n{sep}")
    print("OOS DEGRADATION CHECK  (test - train avg_return; negative = gets worse)")
    print(sep)
    worst_oos = (
        agg[~agg["entry_type"].isin(bench_types)]
        .sort_values("oos_deg")
        .head(10)[["entry_type", "ema_fast", "ema_slow", "lookback",
                   "cluster_pct", "horizon", "train_avg_return",
                   "test_avg_return", "oos_deg"]]
    )
    print(worst_oos.to_string(index=False, float_format="{:.3f}".format))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="EMA Cloud + Price Levels Backtest Sweep")
    parser.add_argument("--phase",       type=int,   default=1, choices=[1, 2])
    parser.add_argument("--data",        default="data/fireant_ssot/ta_ohlcv_panel.parquet")
    parser.add_argument("--fallback-data", default="data/research/ema_cloud/ohlcv_panel_full.parquet")
    parser.add_argument("--output",      default="data/research/ema_levels")
    parser.add_argument("--max-symbols", type=int,   default=None,
                        help="Limit to N most-liquid symbols (validation mode)")
    parser.add_argument("--start-date",  default="2018-01-01")
    parser.add_argument("--phase2-top-n", type=int,  default=15)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    t_start = time.time()

    # -- Load data ------------------------------------------------------
    data_path = args.data if os.path.exists(args.data) else args.fallback_data
    if not os.path.exists(data_path):
        print(f"ERROR: neither {args.data} nor {args.fallback_data} found.")
        sys.exit(1)

    df_all = load_data(data_path, args.max_symbols, args.start_date)
    symbols = sorted(df_all["symbol"].unique())

    if args.phase == 1:
        # -- Phase 1 ---------------------------------------------------
        param_grid = build_phase1_grid()
        n_main = sum(1 for p in param_grid if p["entry_type"] != "reclaim")
        n_reclaim = sum(1 for p in param_grid if p["entry_type"] == "reclaim")
        print(
            f"Phase 1: {len(param_grid)} combos/symbol "
            f"({n_main} level-based + {n_reclaim} reclaim) "
            f"x {len(symbols)} symbols"
        )

        all_stats: list[pd.DataFrame] = []
        n_stat_rows = 0
        for i, sym in enumerate(symbols):
            df_sym = df_all[df_all["symbol"] == sym].copy().reset_index(drop=True)
            result = process_symbol_phase1(df_sym, param_grid)
            if len(result):
                all_stats.append(result)
                n_stat_rows += len(result)

            if (i + 1) % 100 == 0 or (i + 1) == len(symbols):
                elapsed = time.time() - t_start
                print(
                    f"  {i+1}/{len(symbols)} symbols  "
                    f"{elapsed:.0f}s  "
                    f"{n_stat_rows:,} stat rows"
                )

        if not all_stats:
            print("No stats generated -- check data and parameters.")
            return

        stats_df = pd.concat(all_stats, ignore_index=True)
        stats_path = os.path.join(args.output, "phase1_stats.parquet")
        stats_df.to_parquet(stats_path, index=False)
        print(f"Saved {len(stats_df):,} stat rows -> {stats_path}")

        print("Aggregating ...")
        agg = aggregate_phase1(stats_df)
        agg_path = os.path.join(args.output, "phase1_results.csv")
        agg.to_csv(agg_path, index=False)
        print(f"Saved {len(agg):,} rows -> {agg_path}")

        print_phase1_report(agg)

    elif args.phase == 2:
        # -- Phase 2 ---------------------------------------------------
        agg_path = os.path.join(args.output, "phase1_results.csv")
        if not os.path.exists(agg_path):
            print("ERROR: run --phase 1 first to generate phase1_results.csv")
            sys.exit(1)

        phase1_agg = pd.read_csv(agg_path)
        print(f"Loaded phase1 results: {len(phase1_agg)} rows")

        run_phase2(
            all_phase1=pd.DataFrame(),   # no longer needed
            phase1_agg=phase1_agg,
            df_all=df_all,
            out_dir=args.output,
            top_n=args.phase2_top_n,
        )

    print(f"\nTotal elapsed: {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
