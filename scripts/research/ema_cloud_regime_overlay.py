#!/usr/bin/env python3
"""
Regime overlay analysis for EMA cloud signal research.

Takes the existing trades.csv and overlays VNINDEX regime conditions
to answer: how much does a VNINDEX regime filter improve signal quality?

**Caveat (2025–2026):** cap-weighted VNINDEX EMA / cloud filters can be skewed by
Vingroup concentration — not a pure broad-market health gauge. Prefer breadth-style
proxies for conclusions; see `docs/research/VIN_EMA_CLOUD_BASELINE.md`.

Regime definitions tested:
  R1 (baseline):   no filter
  R2 (soft):       VNINDEX close > EMA50(VNINDEX)
  R3 (strict):     VNINDEX close > EMA50 AND EMA50 slope positive (EMA50[t] > EMA50[t-10])
  R4 (cloud):      VNINDEX close > max(EMA10, EMA50) — full cloud condition

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_regime_overlay.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402

OUT_DIR = REPO / "data" / "research" / "ema_cloud"
TRADES_CSV = OUT_DIR / "trades.csv"
BEST_KEY = "f10_s50_rb0_mc120_rbw120_pd0.50_mm5_cb0.30"


def fetch_vnindex() -> pd.DataFrame:
    cache = OUT_DIR / "vnindex_cache.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    client = get_client(timeout=30)
    df = client.get_ohlcv("VNINDEX", start="2023-01-01", end="2026-04-30")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df.to_parquet(cache)
    return df


def build_regime_flags(vni: pd.DataFrame) -> pd.DataFrame:
    df = vni.copy()
    df["ema10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    # EMA50 slope: positive if EMA50[t] > EMA50[t-10]
    df["ema50_slope_up"] = df["ema50"] > df["ema50"].shift(10)
    # Regime flags (computed on VNINDEX close, no leakage)
    df["R2"] = df["close"] > df["ema50"]
    df["R3"] = df["R2"] & df["ema50_slope_up"]
    df["R4"] = (df["close"] > df["ema10"]) & (df["close"] > df["ema50"])
    df["R5"] = df["R4"] & df["ema50_slope_up"]  # strictest
    return df[["date", "close", "ema50", "R2", "R3", "R4", "R5"]].rename(columns={"close": "vni_close"})


def regime_stats(df: pd.DataFrame, regime_col: str | None, label: str) -> dict:
    subset = df if regime_col is None else df[df[regime_col]]
    if subset.empty:
        return {"regime": label, "n": 0}
    row: dict = {"regime": label, "n": len(subset)}
    for h in ["63d", "126d"]:
        for metric, col in [
            ("success", f"trade_success_{h}"),
            ("win", f"win_{h}"),
            ("median", f"fwd_ret_{h}"),
            ("mean", f"fwd_ret_{h}"),
            ("p25", f"fwd_ret_{h}"),
            ("p75", f"fwd_ret_{h}"),
        ]:
            if col not in subset.columns:
                continue
            if metric == "median":
                row[f"median_{h}"] = round(float(subset[col].median()), 4)
            elif metric == "mean":
                row[f"mean_{h}"] = round(float(subset[col].mean()), 4)
            elif metric == "p25":
                row[f"p25_{h}"] = round(float(subset[col].quantile(0.25)), 4)
            elif metric == "p75":
                row[f"p75_{h}"] = round(float(subset[col].quantile(0.75)), 4)
            else:
                row[f"{metric}_{h}"] = round(float(subset[col].mean()), 4)
    return row


def main() -> None:
    print("Loading trades...")
    trades = pd.read_csv(TRADES_CSV, low_memory=False)
    trades["signal_date"] = pd.to_datetime(trades["signal_date"])

    print("Fetching VNINDEX regime...")
    vni = fetch_vnindex()
    regime = build_regime_flags(vni)

    # Join regime flags onto trades by signal_date
    df = trades.merge(regime, left_on="signal_date", right_on="date", how="left")

    # ── Analysis 1: Regime overlay on BEST single param combo ──────────────────
    best = df[df["param_key"] == BEST_KEY].copy()
    print(f"\nBest param key: {BEST_KEY}, n={len(best)} signals total")

    rows = []
    for sig_type in ["breakout", "retest", "reclaim", "all"]:
        sub = best if sig_type == "all" else best[best["signal_type"] == sig_type]
        if sub.empty:
            continue
        rows.append(regime_stats(sub, None, f"R1_no_filter") | {"signal_type": sig_type})
        for rc in ["R2", "R3", "R4", "R5"]:
            if rc in sub.columns:
                rows.append(regime_stats(sub, rc, rc) | {"signal_type": sig_type})

    regime_df = pd.DataFrame(rows)
    print("\n=== REGIME OVERLAY — Best param key, signal type breakdown ===")
    cols = ["signal_type", "regime", "n", "success_63d", "win_63d", "median_63d", "mean_63d", "success_126d", "win_126d"]
    cols = [c for c in cols if c in regime_df.columns]
    print(regime_df[regime_df["signal_type"] == "breakout"][cols].to_string(index=False))

    # ── Analysis 2: Regime overlay across ALL param combos, breakout only ──────
    brk = df[df["signal_type"] == "breakout"].copy()
    print("\n=== REGIME OVERLAY — All breakout signals (all param combos) ===")
    agg_rows = []
    for rc in [None, "R2", "R3", "R4", "R5"]:
        label = "R1_no_filter" if rc is None else rc
        r = regime_stats(brk, rc, label)
        agg_rows.append(r)
    agg = pd.DataFrame(agg_rows)
    print(agg[["regime", "n", "success_63d", "win_63d", "median_63d", "mean_63d", "success_126d"]].to_string(index=False))

    # ── Analysis 3: Monthly regime hit rate vs signal success ──────────────────
    print("\n=== MONTHLY: regime condition R3 active days + signal success ===")
    df["month"] = df["signal_date"].dt.to_period("M")
    best["month"] = best["signal_date"].dt.to_period("M")
    best_brk = best[best["signal_type"] == "breakout"].copy()
    if "trade_success_63d" in best_brk.columns and "R3" in best_brk.columns:
        monthly = (
            best_brk.groupby("month")
            .agg(
                n=("trade_success_63d", "count"),
                success_63d=("trade_success_63d", "mean"),
                r3_pct=("R3", "mean"),
                vni_close=("vni_close", "mean"),
            )
            .reset_index()
        )
        monthly["month"] = monthly["month"].astype(str)
        print(monthly.to_string(index=False))

    # ── Save ──────────────────────────────────────────────────────────────────
    out = OUT_DIR / "regime_overlay.csv"
    regime_df.to_csv(out, index=False)
    print(f"\nSaved: {out}")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n=== LIFT SUMMARY (breakout, all combos) ===")
    if "success_63d" in agg.columns:
        base = agg.loc[agg["regime"] == "R1_no_filter", "success_63d"].iloc[0]
        for _, r in agg.iterrows():
            lift = r.get("success_63d", np.nan) - base
            pct_remaining = r["n"] / agg.loc[agg["regime"] == "R1_no_filter", "n"].iloc[0] * 100
            print(
                f"  {r['regime']:15s}  n={int(r['n']):6d} ({pct_remaining:4.0f}%)  "
                f"success_63d={r.get('success_63d', np.nan):.1%}  "
                f"lift={lift:+.1%}  "
                f"win={r.get('win_63d', np.nan):.1%}"
            )


if __name__ == "__main__":
    main()
