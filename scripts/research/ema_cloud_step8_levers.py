#!/usr/bin/env python3
"""
Step 8: Return improvement levers on the Donchian + cloud baseline.

Baseline: close > max(high[t-20:t]) AND bull_cloud AND above_cloud, EMA(10,50), entry open[t+1]

Levers tested:
  L0  baseline          — all signals, fixed 63d exit
  L1  vol_filter        — only vol_ratio >= 1.5 (above-average volume at breakout)
  L2  strength_filter   — close > 20-bar high by >= 1% (strong breakout, not marginal)
  L3  top5_monthly      — top-5 signals per calendar month ranked by vol_ratio
  L4  dynamic_exit      — exit at first bar: close < ema_fast OR +15% target OR -8% stop
                          (else fixed 63d); return = actual exit price vs entry

Reports IS (full period) and OOS (2025+) side-by-side.
Universe tracks: full / ex_VIC / ex_VIC_VHM_VRE. VPL excluded.

Output:
  data/research/ema_cloud/step8_levers.csv
  data/research/ema_cloud/step8_levers.md
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

OUT_DIR       = REPO / "data" / "research" / "ema_cloud"
CACHE_PARQUET = OUT_DIR / "ohlcv_panel_cache.parquet"

EMA_FAST      = 10
EMA_SLOW      = 50
DON_LOOKBACK  = 20
CLOSE_BUFFER  = 0.003
ADV50_MIN_BN  = 2.0
SUCCESS_TARGET = 0.15
SUCCESS_STOP   = 0.08
FIXED_HORIZON  = 63
VOL_MA_SPAN    = 50
Z95            = 1.96

TEST_START = pd.Timestamp("2025-01-01")

UNIVERSES = {
    "full":           frozenset(),
    "ex_VIC":         frozenset({"VIC"}),
    "ex_VIC_VHM_VRE": frozenset({"VIC", "VHM", "VRE"}),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def wilson_ci(p: float, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z = Z95
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - m), 4), round(min(1.0, c + m), 4)


def _ewm(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty(len(arr)); out[:] = np.nan
    for i in range(len(arr)):
        if np.isnan(arr[i]): continue
        prev = out[i - 1] if i > 0 else np.nan
        out[i] = arr[i] if np.isnan(prev) else alpha * arr[i] + (1 - alpha) * prev
    return out


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(arr), np.nan)
    for i in range(w - 1, len(arr)):
        out[i] = float(np.mean(arr[i - w + 1: i + 1]))
    return out


def _adv50(value: np.ndarray) -> np.ndarray:
    return _rolling_mean(value, 50) / 1e9


# ── Signal generation ─────────────────────────────────────────────────────────

def generate_signals(sym_df: pd.DataFrame) -> list[dict]:
    """Generate all Donchian + cloud signals with metadata. No date filter."""
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    dates  = pd.to_datetime(sym_df["date"].values)
    close  = sym_df["close"].values.astype(float)
    open_  = sym_df["open"].values.astype(float)
    high   = sym_df["high"].values.astype(float)
    low    = sym_df["low"].values.astype(float)
    value  = sym_df["value"].values.astype(float) if "value" in sym_df.columns else np.ones(len(close))
    symbol = str(sym_df["symbol"].iloc[0])
    n      = len(sym_df)

    ema_f  = _ewm(close, EMA_FAST)
    ema_s  = _ewm(close, EMA_SLOW)
    vol_ma = _rolling_mean(value, VOL_MA_SPAN)
    adv    = _adv50(value)
    bull   = ema_f > ema_s
    above  = close > np.maximum(ema_f, ema_s)

    warmup = max(EMA_SLOW + 10, DON_LOOKBACK + 1, VOL_MA_SPAN)
    rows   = []
    for t in range(warmup, n - 1):
        if not np.isnan(adv[t]) and adv[t] < ADV50_MIN_BN:
            continue
        if not (bool(bull[t]) and bool(above[t])):
            continue
        don_high = float(np.max(high[t - DON_LOOKBACK: t]))
        if close[t] <= don_high * (1 + CLOSE_BUFFER):
            continue

        vol_ratio = float(value[t] / vol_ma[t]) if (vol_ma[t] > 0 and not np.isnan(vol_ma[t])) else 1.0
        strength  = (close[t] / don_high - 1.0) if don_high > 0 else 0.0

        entry_t  = t + 1
        entry_px = float(open_[entry_t])

        # ── Fixed-horizon forward returns (63d) ──────────────────────────────
        exit_t_fixed = min(entry_t + FIXED_HORIZON, n - 1)
        is_trunc = int(exit_t_fixed == n - 1 and entry_t + FIXED_HORIZON > n - 1)

        fwd_fixed = success_fixed = win_fixed = np.nan
        if not is_trunc and entry_px > 0:
            fwd_fixed = close[exit_t_fixed] / entry_px - 1.0
            win_fixed = int(fwd_fixed > 0)
            ok = False
            for b in range(entry_t, exit_t_fixed + 1):
                if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
                    ok = True; break
                if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
                    break
            success_fixed = int(ok)

        # ── Dynamic-exit forward return ───────────────────────────────────────
        # Exit conditions (whichever fires first within 63 bars):
        #   1. close < ema_fast  (EMA violation)
        #   2. high  >= entry_px * (1 + SUCCESS_TARGET)  (target hit)
        #   3. low   <= entry_px * (1 - SUCCESS_STOP)    (stop hit)
        #   4. fixed horizon (bar 63)
        dyn_exit_t = exit_t_fixed
        dyn_exit_reason = "horizon"
        if entry_px > 0:
            for b in range(entry_t, exit_t_fixed + 1):
                if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
                    dyn_exit_t = b; dyn_exit_reason = "target"; break
                if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
                    dyn_exit_t = b; dyn_exit_reason = "stop"; break
                if not np.isnan(ema_f[b]) and close[b] < ema_f[b]:
                    dyn_exit_t = b; dyn_exit_reason = "ema_exit"; break

        fwd_dyn = success_dyn = win_dyn = np.nan
        if not is_trunc and entry_px > 0:
            exit_px_dyn = (
                float(open_[dyn_exit_t + 1]) if (dyn_exit_reason == "ema_exit" and dyn_exit_t + 1 < n)
                else float(close[dyn_exit_t])
            )
            fwd_dyn = exit_px_dyn / entry_px - 1.0
            win_dyn = int(fwd_dyn > 0)
            success_dyn = int(fwd_dyn >= SUCCESS_TARGET)

        rows.append({
            "symbol":        symbol,
            "signal_date":   dates[t],
            "signal_bar":    t,
            "entry_px":      entry_px,
            "vol_ratio":     round(vol_ratio, 3),
            "don_strength":  round(strength, 4),
            "is_truncated":  is_trunc,
            # fixed exit
            "fwd_ret_fixed":     fwd_fixed,
            "win_fixed":         win_fixed,
            "trade_success_fixed": success_fixed,
            # dynamic exit
            "fwd_ret_dyn":       fwd_dyn,
            "win_dyn":           win_dyn,
            "trade_success_dyn": success_dyn,
            "dyn_exit_reason":   dyn_exit_reason,
        })
    return rows


# ── Stats ─────────────────────────────────────────────────────────────────────

def compute_stats(rows: list[dict], lever: str, universe: str, period: str,
                  ret_col: str = "fwd_ret_fixed",
                  sc_col: str  = "trade_success_fixed",
                  win_col: str = "win_fixed") -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows).dropna(subset=[ret_col])
    if df.empty:
        return {}
    p_sc = float(df[sc_col].mean())
    ci_lo, ci_hi = wilson_ci(p_sc, len(df))
    return {
        "lever":              lever,
        "universe":           universe,
        "period":             period,
        "n":                  len(df),
        "success_rate":       round(p_sc, 4),
        "ci95_lo":            ci_lo,
        "ci95_hi":            ci_hi,
        "win_rate":           round(float(df[win_col].mean()), 4),
        "mean_ret":           round(float(df[ret_col].mean()), 4),
        "median_ret":         round(float(df[ret_col].median()), 4),
        "p25_ret":            round(float(df[ret_col].quantile(0.25)), 4),
        "p75_ret":            round(float(df[ret_col].quantile(0.75)), 4),
    }


def apply_lever(all_sigs: list[dict], lever: str) -> list[dict]:
    df = pd.DataFrame(all_sigs)
    df = df[df["is_truncated"] == 0]

    if lever == "L0":
        return df.to_dict("records")

    if lever == "L1":
        return df[df["vol_ratio"] >= 1.5].to_dict("records")

    if lever == "L2":
        return df[df["don_strength"] >= 0.01].to_dict("records")  # >1% above 20-bar high

    if lever == "L3":
        df["month"] = pd.to_datetime(df["signal_date"]).dt.to_period("M")
        top = (
            df.sort_values("vol_ratio", ascending=False)
            .groupby("month").head(5)
        )
        return top.to_dict("records")

    return df.to_dict("records")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Loading panel cache...")
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin({"VPL"})].copy()

    log.info("Generating all Donchian signals (full history)...")
    all_signals: list[dict] = []
    for sym, grp in panel.groupby("symbol"):
        all_signals.extend(generate_signals(grp))
    log.info(f"  Total signals: {len(all_signals):,}")

    pd.DataFrame(all_signals).to_csv(OUT_DIR / "donchian_signals_full.csv", index=False)

    levers = {
        "L0": "baseline (all signals, fixed 63d)",
        "L1": "vol_filter (vol_ratio ≥ 1.5×)",
        "L2": "strength_filter (breakout > 20-bar-high by ≥1%)",
        "L3": "top5_monthly (top-5 by vol_ratio per month)",
        "L4": "dynamic_exit (EMA-violation or target/stop, else 63d)",
    }

    results = []

    for uname, excl in UNIVERSES.items():
        u_sigs = [r for r in all_signals if r["symbol"] not in excl]
        is_sigs = [r for r in u_sigs if pd.Timestamp(r["signal_date"]) < TEST_START]
        oos_sigs = [r for r in u_sigs if pd.Timestamp(r["signal_date"]) >= TEST_START]

        for lever in levers:
            is_filtered  = apply_lever(is_sigs, lever)
            oos_filtered = apply_lever(oos_sigs, lever)

            # IS stats (fixed exit)
            s = compute_stats(is_filtered, lever, uname, "IS")
            if s: results.append(s)

            # OOS stats (fixed exit)
            s = compute_stats(oos_filtered, lever, uname, "OOS")
            if s: results.append(s)

            # Dynamic exit — OOS only (L4 uses dyn columns for all levers as a separate track)
            if lever == "L4":
                s = compute_stats(
                    oos_filtered, lever + "_dyn", uname, "OOS",
                    ret_col="fwd_ret_dyn", sc_col="trade_success_dyn", win_col="win_dyn"
                )
                if s: results.append(s)

        log.info(f"  {uname}: IS={len([r for r in is_sigs if r['is_truncated']==0]):,}  "
                 f"OOS={len([r for r in oos_sigs if r['is_truncated']==0]):,}")

    out_df = pd.DataFrame(results)
    csv_path = OUT_DIR / "step8_levers.csv"
    out_df.to_csv(csv_path, index=False)
    log.info(f"Saved {csv_path}")

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        "# Step 8: Return Improvement Levers — Donchian + Cloud Baseline",
        "",
        "**Baseline:** `close > max(high[t-20:t]) AND bull_cloud AND above_cloud`, "
        "EMA(10,50), entry open[t+1], fixed 63-bar exit  ",
        f"**OOS window:** {TEST_START.date()} – latest  ",
        "**VPL excluded. CIs: Wilson 95%.**",
        "",
        "| Lever | Description |",
        "|-------|-------------|",
    ]
    for k, v in levers.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "---", ""]

    for uname in UNIVERSES:
        lines.append(f"## Universe: {uname}")
        lines.append("")
        lines.append("| lever | period | n | success | CI 95% | win | mean_ret | median_ret |")
        lines.append("|-------|--------|---|---------|--------|-----|----------|------------|")
        for lever in list(levers.keys()) + ["L4_dyn"]:
            for period in ["IS", "OOS"]:
                if lever == "L4_dyn" and period == "IS":
                    continue
                row = next((r for r in results
                            if r["lever"] == lever and r["universe"] == uname and r["period"] == period), None)
                if row is None:
                    continue
                ci = f"[{row['ci95_lo']}, {row['ci95_hi']}]"
                lines.append(
                    f"| {lever} | {period} | {row['n']} | {row['success_rate']} | {ci}"
                    f" | {row['win_rate']} | {row['mean_ret']} | {row['median_ret']} |"
                )
        lines.append("")

    lines += [
        "## Decision criteria",
        "",
        "- A lever is additive if OOS success > L0-OOS success AND mean_ret > L0-OOS mean_ret.",
        "- CI overlap with L0-OOS = statistically indistinguishable.",
        "- Dynamic exit (L4_dyn) should show higher success rate at cost of reduced n-effective.",
        "",
        "## Raw data",
        "See `step8_levers.csv`. Full signal log: `donchian_signals_full.csv`.",
    ]

    md_path = OUT_DIR / "step8_levers.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved {md_path}")

    # ── Console summary ───────────────────────────────────────────────────────
    print("\n=== STEP 8 LEVERS — FULL UNIVERSE, OOS 2025 ===\n")
    oos_full = out_df[(out_df["universe"] == "full") & (out_df["period"].isin(["OOS"]))].copy()
    cols = ["lever", "n", "success_rate", "ci95_lo", "ci95_hi", "win_rate", "mean_ret", "median_ret"]
    cols = [c for c in cols if c in oos_full.columns]
    print(oos_full[cols].sort_values("lever").to_string(index=False))

    print("\n=== STEP 8 LEVERS — FULL UNIVERSE, IS ===\n")
    is_full = out_df[(out_df["universe"] == "full") & (out_df["period"] == "IS")].copy()
    print(is_full[cols].sort_values("lever").to_string(index=False))


if __name__ == "__main__":
    main()
