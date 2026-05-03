#!/usr/bin/env python3
"""
Step 4: Matched-random baselines for EMA cloud signal evaluation.

Two baseline types:
  1. same-stock: random entry ±15 trading days of each real signal, same symbol
  2. cross-sectional: random (symbol, bar) from same calendar month + same ADV50 quartile

Run on the OOS-selected best param key only. Reports for 3 universe tracks:
  full / ex-VIC / ex-VIC+VHM+VRE

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_baselines.py
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
HORIZON_NAMES_TD = ["63d", "126d"]
VIN_SYMS = {"VIC", "VHM", "VRE", "VPL"}
BEST_PARAM = "f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30"  # OOS-selected (14/24 folds)
JITTER_BARS = 15   # ±15 trading days for same-stock baseline
N_DRAWS = 3        # draws per signal (averaged) for same-stock baseline
RNG_SEED = 42


def _forward_returns(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                     entry_t: int, entry_px: float, n: int) -> dict:
    r: dict = {}
    for h_bars, h_name in zip(HORIZON_TRADING, HORIZON_NAMES_TD):
        exit_t = min(entry_t + h_bars, n - 1)
        if exit_t <= entry_t or entry_px <= 0:
            continue
        is_trunc = int(exit_t == n - 1 and entry_t + h_bars > n - 1)
        if is_trunc:
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
    for h in HORIZON_NAMES_TD:
        ret_col = f"fwd_ret_{h}"
        sc_col = f"trade_success_{h}"
        win_col = f"win_{h}"
        if ret_col not in df.columns:
            continue
        g = df[ret_col].dropna()
        if len(g) == 0:
            continue
        out[f"n_{h}"] = len(g)
        out[f"success_rate_{h}"] = round(float(df[sc_col].mean()), 4)
        out[f"win_rate_{h}"] = round(float(df[win_col].mean()), 4)
        out[f"mean_ret_{h}"] = round(float(g.mean()), 4)
        out[f"median_ret_{h}"] = round(float(g.median()), 4)
    return out


def _universe_slices(signals: pd.DataFrame) -> dict:
    return {
        "full":             signals,
        "ex_VIC":           signals[~signals["symbol"].isin({"VIC"})],
        "ex_VIC_VHM_VRE":  signals[~signals["symbol"].isin({"VIC", "VHM", "VRE"})],
    }


def run_same_stock_baseline(signals: pd.DataFrame, panel: pd.DataFrame, rng: np.random.Generator) -> list[dict]:
    """For each signal draw N_DRAWS random entries ±JITTER_BARS on same symbol (non-signal bars)."""
    sig_bars: dict[str, set] = {}
    for _, row in signals.iterrows():
        sig_bars.setdefault(row["symbol"], set()).add(int(row["signal_bar"]))

    sym_data: dict[str, dict] = {}
    for sym, grp in panel.groupby("symbol"):
        grp = grp.sort_values("date").reset_index(drop=True)
        sym_data[sym] = {
            "close": grp["close"].values.astype(float),
            "high": grp["high"].values.astype(float),
            "low": grp["low"].values.astype(float),
            "open": grp["open"].values.astype(float),
            "n": len(grp),
        }

    rows = []
    warmup = 60
    for _, sig in signals.iterrows():
        sym = sig["symbol"]
        sb = int(sig["signal_bar"])
        d = sym_data.get(sym)
        if d is None:
            continue
        n = d["n"]
        blocked = sig_bars.get(sym, set())
        lo = max(warmup + 1, sb - JITTER_BARS)
        hi = min(n - 2, sb + JITTER_BARS)  # -2 so open[t+1] exists
        candidates = [b for b in range(lo, hi + 1) if b != sb and b not in blocked]
        if not candidates:
            continue
        chosen = rng.choice(candidates, size=min(N_DRAWS, len(candidates)), replace=False)
        for c in chosen:
            entry_t = c + 1
            entry_px = float(d["open"][entry_t])
            r = _forward_returns(d["close"], d["high"], d["low"], entry_t, entry_px, n)
            if r:
                r["symbol"] = sym
                rows.append(r)
    return rows


def run_cross_sectional_baseline(signals: pd.DataFrame, panel: pd.DataFrame, rng: np.random.Generator) -> list[dict]:
    """For each signal draw a random (sym, bar) from same month + same ADV50 quartile."""
    panel2 = panel.copy()
    panel2["date"] = pd.to_datetime(panel2["date"])
    panel2["month"] = panel2["date"].dt.to_period("M")

    # ADV50 per (symbol, month) — use pre-computed ADV50 from trades if available, else approx
    # Approximate: compute median monthly value per symbol, assign quartile
    monthly_value = (
        panel2.groupby(["symbol", "month"])["value"].median().reset_index()
        .rename(columns={"value": "med_value"})
    )
    monthly_value["quartile"] = pd.qcut(monthly_value["med_value"], 4, labels=[0, 1, 2, 3])

    # Build pool: (symbol, bar_idx, open_price, close, high, low) indexed by (month, quartile)
    sym_data: dict[str, dict] = {}
    for sym, grp in panel2.groupby("symbol"):
        grp = grp.sort_values("date").reset_index(drop=True)
        sym_data[sym] = {
            "close": grp["close"].values.astype(float),
            "high": grp["high"].values.astype(float),
            "low": grp["low"].values.astype(float),
            "open": grp["open"].values.astype(float),
            "month": grp["month"].values,
            "n": len(grp),
        }

    # Signal bars to exclude from pool
    sig_set: set[tuple] = set()
    for _, row in signals.iterrows():
        sig_set.add((row["symbol"], int(row["signal_bar"])))

    # Build pool by (month, quartile)
    from collections import defaultdict
    pool: dict[tuple, list] = defaultdict(list)
    warmup = 60
    for sym, d in sym_data.items():
        n = d["n"]
        sym_mv = monthly_value[monthly_value["symbol"] == sym].set_index("month")
        for b in range(warmup + 1, n - 1):
            if (sym, b) in sig_set:
                continue
            m = d["month"][b]
            if m not in sym_mv.index:
                continue
            q = sym_mv.loc[m, "quartile"]
            pool[(m, q)].append((sym, b))

    rows = []
    for _, sig in signals.iterrows():
        sym = sig["symbol"]
        sb = int(sig["signal_bar"])
        d = sym_data.get(sym)
        if d is None:
            continue
        m = d["month"][sb]
        sym_mv = monthly_value[monthly_value["symbol"] == sym].set_index("month")
        if m not in sym_mv.index:
            continue
        q = sym_mv.loc[m, "quartile"]
        candidates = [(s, b) for s, b in pool.get((m, q), []) if s != sym]
        if not candidates:
            continue
        idx = rng.integers(0, len(candidates))
        csym, cb = candidates[idx]
        cd = sym_data[csym]
        entry_t = cb + 1
        entry_px = float(cd["open"][entry_t])
        r = _forward_returns(cd["close"], cd["high"], cd["low"], entry_t, entry_px, cd["n"])
        if r:
            r["symbol"] = csym
            rows.append(r)
    return rows


def main():
    log.info("Loading trades and panel cache...")
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    panel = pd.read_parquet(CACHE_PARQUET)

    # Filter to best param, exclude VPL
    signals = trades[
        (trades["param_key"] == BEST_PARAM) &
        (~trades["symbol"].isin({"VPL"}))
    ].copy()
    log.info(f"Signals for best param ({BEST_PARAM}): {len(signals):,} total")

    rng = np.random.default_rng(RNG_SEED)
    panel = panel[~panel["symbol"].isin({"VPL"})].copy()

    results = []

    # ── Real signal stats ──────────────────────────────────────────────────────
    for sig_type in ["all", "breakout", "retest", "reclaim"]:
        sigs = signals if sig_type == "all" else signals[signals["signal_type"] == sig_type]
        for uname, usigs in _universe_slices(sigs).items():
            real_rows = []
            for _, row in usigs.iterrows():
                r = {}
                for h in HORIZON_NAMES_TD:
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
                    real_rows.append(r)
            s = _stats(real_rows, f"real|{sig_type}|{uname}")
            if s:
                s["baseline_type"] = "real"
                s["signal_type"] = sig_type
                s["universe"] = uname
                results.append(s)

    # ── Same-stock baseline ────────────────────────────────────────────────────
    log.info("Running same-stock baseline...")
    for sig_type in ["all", "breakout", "retest", "reclaim"]:
        sigs = signals if sig_type == "all" else signals[signals["signal_type"] == sig_type]
        for uname, usigs in _universe_slices(sigs).items():
            upanel = panel[~panel["symbol"].isin({"VIC"} if "ex_VIC" in uname else set())]
            if "ex_VIC_VHM_VRE" in uname:
                upanel = panel[~panel["symbol"].isin({"VIC", "VHM", "VRE"})]
            rows = run_same_stock_baseline(usigs, upanel, rng)
            s = _stats(rows, f"same_stock|{sig_type}|{uname}")
            if s:
                s["baseline_type"] = "same_stock"
                s["signal_type"] = sig_type
                s["universe"] = uname
                results.append(s)
        log.info(f"  same-stock {sig_type} done")

    # ── Cross-sectional baseline ───────────────────────────────────────────────
    log.info("Running cross-sectional baseline...")
    for sig_type in ["all", "breakout", "retest", "reclaim"]:
        sigs = signals if sig_type == "all" else signals[signals["signal_type"] == sig_type]
        for uname, usigs in _universe_slices(sigs).items():
            upanel = panel.copy()
            if uname == "ex_VIC":
                upanel = panel[~panel["symbol"].isin({"VIC"})]
            elif uname == "ex_VIC_VHM_VRE":
                upanel = panel[~panel["symbol"].isin({"VIC", "VHM", "VRE"})]
            rows = run_cross_sectional_baseline(usigs, upanel, rng)
            s = _stats(rows, f"cross_sec|{sig_type}|{uname}")
            if s:
                s["baseline_type"] = "cross_sectional"
                s["signal_type"] = sig_type
                s["universe"] = uname
                results.append(s)
        log.info(f"  cross-sectional {sig_type} done")

    out_df = pd.DataFrame(results)
    out_path = OUT_DIR / "baseline_comparison.csv"
    out_df.to_csv(out_path, index=False)
    log.info(f"Saved {out_path} ({len(out_df)} rows)")

    # Print summary table
    print("\n=== BASELINE COMPARISON (best param, 63d horizon) ===")
    print(f"Param: {BEST_PARAM}\n")
    cols = ["baseline_type", "signal_type", "universe", "n", "success_rate_63d", "mean_ret_63d", "win_rate_63d"]
    cols = [c for c in cols if c in out_df.columns]
    print(out_df[cols].sort_values(["signal_type", "universe", "baseline_type"]).to_string(index=False))


if __name__ == "__main__":
    main()
