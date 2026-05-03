"""
Step 5: Ablation benchmarks.
Three ablation strategies vs the level-signal (best param):
  1. cloud_only   : bull_cloud AND above_cloud AND ADV50, 20-bar cooldown, no level
  2. donchian_20  : close > max(high[-21:-1]) AND ADV50, 20-bar cooldown, no cloud
  3. donchian_cloud: Donchian-20 AND cloud AND ADV50, 20-bar cooldown

All use EMA10/50 for cloud (same as best param). ADV50 >= 2bn. Non-truncated entries only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path("data/research/ema_cloud")
EMA_FAST = 10
EMA_SLOW = 50
ADV50_MIN_BN = 2.0
DONCHIAN_WINDOW = 20
COOLDOWN = 20
HORIZON_63 = 63
SUCCESS_TARGET = 0.15
SUCCESS_STOP = 0.08
BEST_PARAM = "f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30"
EXCLUDE_ALL = ["VPL"]
VIN_STOCKS = ["VIC", "VHM", "VRE"]
WARMUP = max(EMA_SLOW + DONCHIAN_WINDOW + 5, 70)


def compute_success(high: np.ndarray, low: np.ndarray, entry_px: float, entry_t: int, exit_t: int) -> int:
    for b in range(entry_t, exit_t + 1):
        if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
            return 1
        if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
            return 0
    return 0


def detect_strategy(
    close: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    value: np.ndarray,
    strategy: str,
) -> list[dict]:
    n = len(close)
    ema_fast = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().values
    ema_slow = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().values
    bull_cloud = ema_fast > ema_slow
    above_cloud = close > np.maximum(ema_fast, ema_slow)
    # value column is pre-computed VND turnover; adv50 in billions
    adv50 = pd.Series(value).rolling(50, min_periods=25).mean().values / 1e9

    rows = []
    last_signal_bar = -COOLDOWN - 1

    for t in range(WARMUP, n - HORIZON_63 - 1):
        if np.isnan(adv50[t]) or adv50[t] < ADV50_MIN_BN:
            continue
        if t - last_signal_bar < COOLDOWN:
            continue

        # Strategy-specific gate
        if strategy == "cloud_only":
            if not (bool(bull_cloud[t]) and bool(above_cloud[t])):
                continue
        elif strategy == "donchian_20":
            if t < DONCHIAN_WINDOW:
                continue
            don_level = float(np.max(high[t - DONCHIAN_WINDOW: t]))
            if not (close[t] > don_level):
                continue
        elif strategy == "donchian_cloud":
            if not (bool(bull_cloud[t]) and bool(above_cloud[t])):
                continue
            if t < DONCHIAN_WINDOW:
                continue
            don_level = float(np.max(high[t - DONCHIAN_WINDOW: t]))
            if not (close[t] > don_level):
                continue
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        entry_t = t + 1
        entry_px = open_[entry_t]
        if entry_px <= 0:
            continue
        exit_t = entry_t + HORIZON_63
        fwd = close[exit_t] / entry_px - 1.0
        success = compute_success(high, low, entry_px, entry_t, exit_t)
        rows.append({"signal_bar": t, "fwd_ret_63d": fwd, "trade_success_63d": success, "win_63d": int(fwd > 0)})
        last_signal_bar = t

    return rows


def agg_stats(rows: list[dict], label: str, universe: str) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    return {
        "strategy": label,
        "universe": universe,
        "n": len(df),
        "success_rate_63d": round(float(df["trade_success_63d"].mean()), 4),
        "mean_ret_63d": round(float(df["fwd_ret_63d"].mean()), 4),
        "win_rate_63d": round(float(df["win_63d"].mean()), 4),
        "median_ret_63d": round(float(df["fwd_ret_63d"].median()), 4),
    }


def main():
    print("Loading panel cache...")
    panel = pd.read_parquet(OUT_DIR / "ohlcv_panel_cache.parquet")
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    strategies = ["cloud_only", "donchian_20", "donchian_cloud"]

    # Collect rows per strategy per symbol
    strat_rows: dict[str, dict[str, list[dict]]] = {s: {} for s in strategies}

    symbols = [s for s in panel["symbol"].unique() if s not in EXCLUDE_ALL]
    print(f"Running ablations on {len(symbols)} symbols...")

    for i, symbol in enumerate(symbols):
        grp = panel[panel["symbol"] == symbol].reset_index(drop=True)
        close = grp["close"].values.astype(float)
        open_ = grp["open"].values.astype(float)
        high = grp["high"].values.astype(float)
        low = grp["low"].values.astype(float)
        value = grp["value"].values.astype(float)

        for strat in strategies:
            rows = detect_strategy(close, open_, high, low, value, strat)
            strat_rows[strat][symbol] = rows

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(symbols)} symbols done")

    print("Aggregating ablation results...")

    # Load level-signal baseline for comparison
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    trades = trades[trades["param_key"] == BEST_PARAM]
    trades = trades[~trades["symbol"].isin(EXCLUDE_ALL)]
    trades = trades[trades["is_truncated_63d"] == 0]

    records = []

    univ_filters = {
        "full": lambda sym: sym not in EXCLUDE_ALL,
        "ex-VIC": lambda sym: sym not in EXCLUDE_ALL and sym != "VIC",
        "ex-VIC/VHM/VRE": lambda sym: sym not in EXCLUDE_ALL and sym not in VIN_STOCKS,
    }

    for univ_name, sym_filter in univ_filters.items():
        # Level-signal stats (from trades.csv)
        sig_df = trades[trades["symbol"].map(sym_filter)]
        if len(sig_df) > 0:
            for sig_type in ["all", "breakout", "retest", "reclaim"]:
                sub = sig_df if sig_type == "all" else sig_df[sig_df["signal_type"] == sig_type]
                if len(sub) == 0:
                    continue
                records.append({
                    "strategy": f"level_signal_{sig_type}",
                    "universe": univ_name,
                    "n": len(sub),
                    "success_rate_63d": round(float(sub["trade_success_63d"].mean()), 4),
                    "mean_ret_63d": round(float(sub["fwd_ret_63d"].mean()), 4),
                    "win_rate_63d": round(float(sub["win_63d"].mean()), 4),
                    "median_ret_63d": round(float(sub["fwd_ret_63d"].median()), 4),
                })

        # Ablation strategy stats
        for strat in strategies:
            all_rows = [
                row
                for sym, rows in strat_rows[strat].items()
                if sym_filter(sym)
                for row in rows
            ]
            stats = agg_stats(all_rows, strat, univ_name)
            if stats:
                records.append(stats)

    result = pd.DataFrame(records)
    out_path = OUT_DIR / "ablation_results.csv"
    result.to_csv(out_path, index=False)

    print("\n=== ABLATION RESULTS (full universe, 63d) ===")
    print(result[result["universe"] == "full"].to_string(index=False))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
