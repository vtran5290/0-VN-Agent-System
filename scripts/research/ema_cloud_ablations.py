#!/usr/bin/env python3
"""
Step 5: Ablation benchmarks for EMA cloud + level breakout strategy.

Three ablations vs full model (on best OOS param key):
  A. cloud_only     — signal = first bar after N-bar cooldown where bull_cloud AND above_cloud
  B. donchian       — close > 20-bar high AND bull_cloud AND above_cloud (no clustered levels)
  C. no_cloud       — level breakout only, remove bull_cloud/above_cloud filter

Reports for: full / ex-VIC / ex-VIC+VHM+VRE
Output: data/research/ema_cloud/ablation_results.csv

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_ablations.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

OUT_DIR = REPO / "data" / "research" / "ema_cloud"
CACHE_PARQUET = OUT_DIR / "ohlcv_panel_cache.parquet"

SUCCESS_TARGET = 0.15
SUCCESS_STOP = 0.08
HORIZON_TRADING = [63, 126]
HORIZON_NAMES = ["63d", "126d"]

# Best OOS param decoded values
EMA_FAST = 10
EMA_SLOW = 50
ADV50_MIN_BN = 2.0       # 2 billion VND ADV50 filter
CLOUD_COOLDOWN = 20      # bars cooldown for cloud-only signal
DONCHIAN_LOOKBACK = 20   # bars for Donchian high
CLOSE_BUFFER = 0.003     # 0.3% close buffer for level breakout (from best param)

VIN_SYMS = {"VIC", "VHM", "VRE", "VPL"}


def _ewm(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            continue
        if np.isnan(out[i - 1]) if i > 0 else True:
            out[i] = arr[i]
        else:
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _adv50(value: np.ndarray) -> np.ndarray:
    out = np.full(len(value), np.nan)
    for i in range(49, len(value)):
        out[i] = float(np.mean(value[i - 49: i + 1])) / 1e9
    return out


def _forward_returns(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                     open_: np.ndarray, entry_t: int, n: int) -> dict:
    r: dict = {}
    entry_px = float(open_[entry_t])
    if entry_px <= 0:
        return r
    for h_bars, h_name in zip(HORIZON_TRADING, HORIZON_NAMES):
        exit_t = min(entry_t + h_bars, n - 1)
        if exit_t <= entry_t:
            continue
        if exit_t == n - 1 and entry_t + h_bars > n - 1:
            continue  # skip truncated
        fwd = close[exit_t] / entry_px - 1.0
        success = False
        for b in range(entry_t, exit_t + 1):
            if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
                success = True
                break
            if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
                break
        r[f"fwd_ret_{h_name}"] = float(fwd)
        r[f"win_{h_name}"] = int(fwd > 0)
        r[f"trade_success_{h_name}"] = int(success)
    return r


def _stats(rows: list[dict], label: str) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    out = {"label": label, "n": len(df)}
    for h in HORIZON_NAMES:
        ret_col = f"fwd_ret_{h}"
        if ret_col not in df.columns:
            continue
        g = df[ret_col].dropna()
        if len(g) == 0:
            continue
        out[f"n_{h}"] = len(g)
        out[f"success_rate_{h}"] = round(float(df[f"trade_success_{h}"].mean()), 4)
        out[f"win_rate_{h}"] = round(float(df[f"win_{h}"].mean()), 4)
        out[f"mean_ret_{h}"] = round(float(g.mean()), 4)
        out[f"median_ret_{h}"] = round(float(g.median()), 4)
    return out


def signals_cloud_only(sym_df: pd.DataFrame, cooldown: int = CLOUD_COOLDOWN) -> list[dict]:
    close = sym_df["close"].values.astype(float)
    open_ = sym_df["open"].values.astype(float)
    high = sym_df["high"].values.astype(float)
    low = sym_df["low"].values.astype(float)
    value = sym_df["value"].values.astype(float) if "value" in sym_df.columns else np.ones(len(close))
    symbol = sym_df["symbol"].iloc[0]
    n = len(sym_df)

    ema_fast = _ewm(close, EMA_FAST)
    ema_slow = _ewm(close, EMA_SLOW)
    adv = _adv50(value)
    bull_cloud = ema_fast > ema_slow
    above_cloud = close > np.maximum(ema_fast, ema_slow)

    warmup = EMA_SLOW + 10
    rows = []
    last_signal = -cooldown - 1
    for t in range(warmup, n - 1):
        if not np.isnan(adv[t]) and adv[t] < ADV50_MIN_BN:
            continue
        if not (bool(bull_cloud[t]) and bool(above_cloud[t])):
            continue
        if t - last_signal <= cooldown:
            continue
        last_signal = t
        r = _forward_returns(close, high, low, open_, t + 1, n)
        if r:
            r["symbol"] = symbol
            rows.append(r)
    return rows


def signals_donchian(sym_df: pd.DataFrame, lookback: int = DONCHIAN_LOOKBACK) -> list[dict]:
    close = sym_df["close"].values.astype(float)
    open_ = sym_df["open"].values.astype(float)
    high = sym_df["high"].values.astype(float)
    low = sym_df["low"].values.astype(float)
    value = sym_df["value"].values.astype(float) if "value" in sym_df.columns else np.ones(len(close))
    symbol = sym_df["symbol"].iloc[0]
    n = len(sym_df)

    ema_fast = _ewm(close, EMA_FAST)
    ema_slow = _ewm(close, EMA_SLOW)
    adv = _adv50(value)
    bull_cloud = ema_fast > ema_slow
    above_cloud = close > np.maximum(ema_fast, ema_slow)

    warmup = max(EMA_SLOW + 10, lookback + 1)
    rows = []
    for t in range(warmup, n - 1):
        if not np.isnan(adv[t]) and adv[t] < ADV50_MIN_BN:
            continue
        if not (bool(bull_cloud[t]) and bool(above_cloud[t])):
            continue
        don_high = float(np.max(high[t - lookback: t]))  # exclusive of bar t
        if close[t] <= don_high * (1 + CLOSE_BUFFER):
            continue
        r = _forward_returns(close, high, low, open_, t + 1, n)
        if r:
            r["symbol"] = symbol
            rows.append(r)
    return rows


def signals_no_cloud(trades_sym: pd.DataFrame) -> list[dict]:
    """Reuse level breakout signals from trades.csv but ignore cloud filter.
    Proxy: include ALL breakout signals regardless of bull_cloud/above_cloud value.
    Since trades.csv already requires cloud, this is equivalent to asking:
    'what if we had run without the cloud requirement?' — we approximate by
    comparing breakout-only row stats vs the full model breakout stats."""
    rows = []
    for _, row in trades_sym.iterrows():
        if row["signal_type"] != "breakout":
            continue
        r = {}
        for h in HORIZON_NAMES:
            tc = f"is_truncated_{h}"
            if tc in row.index and row[tc] == 1:
                continue
            rc = f"fwd_ret_{h}"
            if rc in row.index and not pd.isna(row[rc]):
                r[f"fwd_ret_{h}"] = row[rc]
                r[f"win_{h}"] = row.get(f"win_{h}", 0)
                r[f"trade_success_{h}"] = row.get(f"trade_success_{h}", 0)
                r["symbol"] = row["symbol"]
        if r:
            rows.append(r)
    return rows


def run_ablation(panel: pd.DataFrame, ablation: str) -> list[dict]:
    rows = []
    syms = panel["symbol"].unique()
    for sym in syms:
        sym_df = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if len(sym_df) < 100:
            continue
        if ablation == "cloud_only":
            rows.extend(signals_cloud_only(sym_df))
        elif ablation == "donchian":
            rows.extend(signals_donchian(sym_df))
    return rows


def _universe_filter(df_or_rows, universe: str) -> list[dict]:
    if isinstance(df_or_rows, list):
        if universe == "ex_VIC":
            return [r for r in df_or_rows if r.get("symbol") != "VIC"]
        elif universe == "ex_VIC_VHM_VRE":
            return [r for r in df_or_rows if r.get("symbol") not in {"VIC", "VHM", "VRE"}]
        return df_or_rows
    else:
        if universe == "ex_VIC":
            return df_or_rows[~df_or_rows["symbol"].isin({"VIC"})]
        elif universe == "ex_VIC_VHM_VRE":
            return df_or_rows[~df_or_rows["symbol"].isin({"VIC", "VHM", "VRE"})]
        return df_or_rows


def main():
    log.info("Loading data...")
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    panel = pd.read_parquet(CACHE_PARQUET)

    BEST_PARAM = "f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30"
    best_trades = trades[
        (trades["param_key"] == BEST_PARAM) &
        (~trades["symbol"].isin({"VPL"}))
    ].copy()
    panel = panel[~panel["symbol"].isin({"VPL"})].copy()

    universes = ["full", "ex_VIC", "ex_VIC_VHM_VRE"]
    results = []

    # ── Full model real signals (breakout only, best param) ────────────────────
    log.info("Collecting full model stats...")
    for universe in universes:
        sigs = _universe_filter(best_trades[best_trades["signal_type"] == "breakout"], universe)
        rows = []
        for _, row in (sigs.iterrows() if hasattr(sigs, "iterrows") else pd.DataFrame(sigs).iterrows()):
            r = {}
            for h in HORIZON_NAMES:
                tc = f"is_truncated_{h}"
                if tc in row.index and row[tc] == 1:
                    continue
                rc = f"fwd_ret_{h}"
                if rc in row.index and not pd.isna(row[rc]):
                    r[f"fwd_ret_{h}"] = row[rc]
                    r[f"win_{h}"] = row.get(f"win_{h}", 0)
                    r[f"trade_success_{h}"] = row.get(f"trade_success_{h}", 0)
                    r["symbol"] = row["symbol"]
            if r:
                rows.append(r)
        s = _stats(rows, f"full_model|{universe}")
        if s:
            s.update({"ablation": "full_model", "universe": universe})
            results.append(s)

    # ── Ablations ──────────────────────────────────────────────────────────────
    for ablation in ["cloud_only", "donchian"]:
        log.info(f"Running ablation: {ablation}...")
        all_rows = run_ablation(panel, ablation)
        for universe in universes:
            rows = _universe_filter(all_rows, universe)
            s = _stats(rows, f"{ablation}|{universe}")
            if s:
                s.update({"ablation": ablation, "universe": universe})
                results.append(s)
        log.info(f"  {ablation}: {len(all_rows):,} signals total")

    out_df = pd.DataFrame(results)
    out_path = OUT_DIR / "ablation_results.csv"
    out_df.to_csv(out_path, index=False)
    log.info(f"Saved {out_path}")

    print("\n=== ABLATION RESULTS (63d horizon) ===")
    cols = ["ablation", "universe", "n", "success_rate_63d", "mean_ret_63d", "win_rate_63d"]
    cols = [c for c in cols if c in out_df.columns]
    print(out_df[cols].sort_values(["universe", "ablation"]).to_string(index=False))


if __name__ == "__main__":
    main()
