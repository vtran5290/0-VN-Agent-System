"""
Step 4: Matched-random baselines.
Compares actual level-signal entries vs two cloud-eligible baselines:
  - cloud_base_rate : all eligible bars (cloud + ADV50, non-truncated) across the signal universe
  - same_stock_cloud: per-symbol, eligible bars on the exact same stocks that generated signals

EMA settings = best param (f10/s50). ADV50 >= 2bn VND. Non-truncated (bar < n - 63).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path("data/research/ema_cloud")
EMA_FAST = 10
EMA_SLOW = 50
ADV50_MIN_BN = 2.0
HORIZON_63 = 63
SUCCESS_TARGET = 0.15
SUCCESS_STOP = 0.08
BEST_PARAM = "f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30"
EXCLUDE_ALL = ["VPL"]
VIN_STOCKS = ["VIC", "VHM", "VRE"]
WARMUP = max(EMA_SLOW + 10, 60)


def compute_success(high: np.ndarray, low: np.ndarray, entry_px: float, entry_t: int, exit_t: int) -> int:
    for b in range(entry_t, exit_t + 1):
        if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
            return 1
        if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
            return 0
    return 0


def precompute_eligible_returns(
    close: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    value: np.ndarray,
) -> dict[int, dict]:
    """Return dict of bar_idx -> {fwd_ret_63d, trade_success_63d, win_63d} for all eligible bars."""
    n = len(close)
    ema_fast = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().values
    ema_slow = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().values
    bull_cloud = ema_fast > ema_slow
    above_cloud = close > np.maximum(ema_fast, ema_slow)
    # value column is pre-computed VND turnover; adv50 in billions
    adv50 = pd.Series(value).rolling(50, min_periods=25).mean().values / 1e9

    result = {}
    for t in range(WARMUP, n - HORIZON_63 - 1):
        if not (bull_cloud[t] and above_cloud[t]):
            continue
        if np.isnan(adv50[t]) or adv50[t] < ADV50_MIN_BN:
            continue
        entry_t = t + 1
        entry_px = open_[entry_t]
        if entry_px <= 0:
            continue
        exit_t = entry_t + HORIZON_63
        fwd = close[exit_t] / entry_px - 1.0
        success = compute_success(high, low, entry_px, entry_t, exit_t)
        result[t] = {"fwd_ret_63d": fwd, "trade_success_63d": success, "win_63d": int(fwd > 0)}
    return result


def agg_stats(rows: list[dict]) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    return {
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

    print("Loading signals...")
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    trades["signal_date"] = pd.to_datetime(trades["signal_date"])
    trades = trades[trades["param_key"] == BEST_PARAM]
    trades = trades[~trades["symbol"].isin(EXCLUDE_ALL)]
    trades = trades[trades["is_truncated_63d"] == 0]
    signal_symbols = set(trades["symbol"].unique())
    print(f"  Signals: {len(trades):,} across {len(signal_symbols)} symbols")

    print("Precomputing cloud-eligible returns per symbol...")
    eligible_all: list[dict] = []   # all symbols
    eligible_sig_syms: list[dict] = []  # only symbols that had signals

    for symbol, grp in panel.groupby("symbol"):
        if symbol in EXCLUDE_ALL:
            continue
        grp = grp.reset_index(drop=True)
        close = grp["close"].values.astype(float)
        open_ = grp["open"].values.astype(float)
        high = grp["high"].values.astype(float)
        low = grp["low"].values.astype(float)
        value = grp["value"].values.astype(float)

        bar_returns = precompute_eligible_returns(close, open_, high, low, value)
        for _, ret in bar_returns.items():
            row = {"symbol": symbol, **ret}
            eligible_all.append(row)
            if symbol in signal_symbols:
                eligible_sig_syms.append(row)

    print(f"  Cloud-eligible bars (all universe): {len(eligible_all):,}")
    print(f"  Cloud-eligible bars (signal symbols only): {len(eligible_sig_syms):,}")

    # Build comparison table
    records = []

    universes = {
        "full": (
            trades,
            [r for r in eligible_all if r["symbol"] not in VIN_STOCKS + EXCLUDE_ALL],
            [r for r in eligible_sig_syms if r["symbol"] not in VIN_STOCKS + EXCLUDE_ALL],
        ),
        "ex-VIC": (
            trades[trades["symbol"] != "VIC"],
            [r for r in eligible_all if r["symbol"] != "VIC"],
            [r for r in eligible_sig_syms if r["symbol"] != "VIC"],
        ),
        "ex-VIC/VHM/VRE": (
            trades[~trades["symbol"].isin(VIN_STOCKS)],
            [r for r in eligible_all if r["symbol"] not in VIN_STOCKS],
            [r for r in eligible_sig_syms if r["symbol"] not in VIN_STOCKS],
        ),
    }
    # Redo full to include ALL symbols (not just ex-VIN), override
    universes["full"] = (
        trades,
        eligible_all,
        eligible_sig_syms,
    )

    for univ_name, (sig_df, elig_all_rows, elig_sig_rows) in universes.items():
        for sig_type in ["all", "breakout", "retest", "reclaim"]:
            if sig_type == "all":
                sig_sub = sig_df
            else:
                sig_sub = sig_df[sig_df["signal_type"] == sig_type]

            sig_stats = agg_stats(
                [{"fwd_ret_63d": r, "trade_success_63d": s, "win_63d": w}
                 for r, s, w in zip(sig_sub["fwd_ret_63d"], sig_sub["trade_success_63d"], sig_sub["win_63d"])]
            ) if len(sig_sub) > 0 else {}

            base_all_stats = agg_stats(elig_all_rows)
            base_sig_stats = agg_stats(elig_sig_rows)

            if not sig_stats:
                continue

            def make_row(baseline: str, stats: dict) -> dict:
                return {
                    "universe": univ_name,
                    "signal_type": sig_type,
                    "baseline": baseline,
                    **stats,
                    "lift_success_vs_cloud_all": round(
                        sig_stats.get("success_rate_63d", np.nan) - stats.get("success_rate_63d", np.nan), 4
                    ) if baseline != "signal" else np.nan,
                }

            records.append(make_row("signal", sig_stats))
            records.append(make_row("cloud_base_rate", base_all_stats))
            records.append(make_row("same_stock_cloud", base_sig_stats))

    result = pd.DataFrame(records)
    out_path = OUT_DIR / "baseline_comparison.csv"
    result.to_csv(out_path, index=False)

    print("\n=== SIGNAL vs CLOUD BASELINE (full universe, 63d) ===")
    disp = result[result["universe"] == "full"].pivot_table(
        index="signal_type", columns="baseline",
        values=["n", "success_rate_63d", "mean_ret_63d"],
        aggfunc="first",
    )
    print(disp.to_string())

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
