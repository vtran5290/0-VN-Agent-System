#!/usr/bin/env python3
"""
Step 7: EMA pair expansion on Donchian + cloud model.

Tests 5 EMA pairs on the same Donchian rule across 2025 OOS window.
Rule: close[t] > max(high[t-20:t]) AND bull_cloud[t] AND above_cloud[t]
Entry: open[t+1]

EMA pairs tested: (5,20), (10,50), (20,50), (20,100), (20,150)
Universe tracks: full / ex_VIC / ex_VIC_VHM_VRE
VPL excluded.

Output:
  data/research/ema_cloud/donchian_ema_expansion.csv
  data/research/ema_cloud/donchian_ema_expansion.md
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

TEST_START     = pd.Timestamp("2025-01-01")
DON_LOOKBACK   = 20
CLOSE_BUFFER   = 0.003
ADV50_MIN_BN   = 2.0
SUCCESS_TARGET = 0.15
SUCCESS_STOP   = 0.08
HORIZON_TRADING = [63, 126]
HORIZON_NAMES   = ["63d", "126d"]
Z95 = 1.96

EMA_PAIRS = [
    (5,  20),
    (10, 50),
    (20, 50),
    (20, 100),
    (20, 150),
]

UNIVERSES = {
    "full":           frozenset(),
    "ex_VIC":         frozenset({"VIC"}),
    "ex_VIC_VHM_VRE": frozenset({"VIC", "VHM", "VRE"}),
}


def wilson_ci(p: float, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z = Z95
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def _ewm(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty(len(arr))
    out[:] = np.nan
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            continue
        prev = out[i - 1] if i > 0 else np.nan
        out[i] = arr[i] if np.isnan(prev) else alpha * arr[i] + (1 - alpha) * prev
    return out


def _adv50(value: np.ndarray) -> np.ndarray:
    out = np.full(len(value), np.nan)
    for i in range(49, len(value)):
        out[i] = float(np.mean(value[i - 49: i + 1])) / 1e9
    return out


def _fwd(close, high, low, open_, entry_t, n):
    r = {}
    px = float(open_[entry_t])
    if px <= 0:
        return r
    for h_bars, h_name in zip(HORIZON_TRADING, HORIZON_NAMES):
        exit_t = min(entry_t + h_bars, n - 1)
        if exit_t <= entry_t or (exit_t == n - 1 and entry_t + h_bars > n - 1):
            continue
        fwd = close[exit_t] / px - 1.0
        ok = False
        for b in range(entry_t, exit_t + 1):
            if high[b] / px - 1.0 >= SUCCESS_TARGET:
                ok = True; break
            if low[b] / px - 1.0 <= -SUCCESS_STOP:
                break
        r[f"fwd_ret_{h_name}"]       = float(fwd)
        r[f"win_{h_name}"]           = int(fwd > 0)
        r[f"trade_success_{h_name}"] = int(ok)
    return r


def run_pair(panel: pd.DataFrame, fast: int, slow: int) -> list[dict]:
    warmup = max(slow + 10, DON_LOOKBACK + 1)
    rows: list[dict] = []
    for sym, grp in panel.groupby("symbol"):
        grp  = grp.sort_values("date").reset_index(drop=True)
        n    = len(grp)
        if n < warmup + 2:
            continue
        dates  = pd.to_datetime(grp["date"].values)
        close  = grp["close"].values.astype(float)
        open_  = grp["open"].values.astype(float)
        high   = grp["high"].values.astype(float)
        low    = grp["low"].values.astype(float)
        value  = grp["value"].values.astype(float) if "value" in grp.columns else np.ones(n)

        ema_f = _ewm(close, fast)
        ema_s = _ewm(close, slow)
        adv   = _adv50(value)
        bull  = ema_f > ema_s
        above = close > np.maximum(ema_f, ema_s)

        for t in range(warmup, n - 1):
            if dates[t] < TEST_START:
                continue
            if not np.isnan(adv[t]) and adv[t] < ADV50_MIN_BN:
                continue
            if not (bool(bull[t]) and bool(above[t])):
                continue
            don_high = float(np.max(high[t - DON_LOOKBACK: t]))
            if close[t] <= don_high * (1 + CLOSE_BUFFER):
                continue
            r = _fwd(close, high, low, open_, t + 1, n)
            if r:
                r["symbol"]      = sym
                r["signal_date"] = dates[t]
                r["ema_pair"]    = f"f{fast}_s{slow}"
                rows.append(r)
    return rows


def stats_row(rows: list[dict], ema_pair: str, universe: str) -> dict:
    if not rows:
        return {}
    df  = pd.DataFrame(rows)
    out = {"ema_pair": ema_pair, "universe": universe, "n": len(df)}
    for h in HORIZON_NAMES:
        rc = f"fwd_ret_{h}"
        sc = f"trade_success_{h}"
        wc = f"win_{h}"
        if rc not in df.columns:
            continue
        g = df[rc].dropna()
        if len(g) == 0:
            continue
        p_sc = float(df[sc].mean())
        ci_lo, ci_hi = wilson_ci(p_sc, len(g))
        out[f"n_{h}"]               = len(g)
        out[f"success_rate_{h}"]    = round(p_sc, 4)
        out[f"ci95_lo_{h}"]         = ci_lo
        out[f"ci95_hi_{h}"]         = ci_hi
        out[f"win_rate_{h}"]        = round(float(df[wc].mean()), 4)
        out[f"mean_ret_{h}"]        = round(float(g.mean()), 4)
        out[f"median_ret_{h}"]      = round(float(g.median()), 4)
        out[f"p25_ret_{h}"]         = round(float(g.quantile(0.25)), 4)
        out[f"p75_ret_{h}"]         = round(float(g.quantile(0.75)), 4)
    return out


def main():
    log.info("Loading panel cache...")
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin({"VPL"})].copy()

    all_results: list[dict] = []

    for fast, slow in EMA_PAIRS:
        pair_label = f"f{fast}_s{slow}"
        log.info(f"Running EMA({fast},{slow})...")
        rows = run_pair(panel, fast, slow)
        log.info(f"  EMA({fast},{slow}): {len(rows):,} signals in 2025")

        for uname, excl in UNIVERSES.items():
            sub = [r for r in rows if r["symbol"] not in excl]
            s   = stats_row(sub, pair_label, uname)
            if s:
                all_results.append(s)

    out_df   = pd.DataFrame(all_results)
    csv_path = OUT_DIR / "donchian_ema_expansion.csv"
    out_df.to_csv(csv_path, index=False)
    log.info(f"Saved {csv_path}")

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        "# Donchian EMA Pair Expansion — 2025 OOS",
        "",
        f"**Test window:** {TEST_START.date()} – latest  ",
        "**Rule:** `close > max(high[t-20:t]) AND bull_cloud AND above_cloud`, entry open[t+1]  ",
        "**VPL:** excluded  |  **CIs:** Wilson 95%",
        "",
        "---",
        "",
    ]

    for uname in UNIVERSES:
        lines.append(f"## {uname}")
        lines.append("")
        lines.append("| EMA pair | n | success_63d | CI 95% | win_63d | mean_63d | median_63d |")
        lines.append("|----------|---|-------------|--------|---------|----------|------------|")
        sub = [r for r in all_results if r["universe"] == uname]
        sub.sort(key=lambda x: -x.get("success_rate_63d", 0))
        for row in sub:
            pair = row["ema_pair"]
            ci   = f"[{row.get('ci95_lo_63d','?')}, {row.get('ci95_hi_63d','?')}]"
            flag = " ✓" if pair == "f10_s50" else ""
            lines.append(
                f"| {pair}{flag} | {row.get('n',0)} | {row.get('success_rate_63d','?')} | {ci}"
                f" | {row.get('win_rate_63d','?')} | {row.get('mean_ret_63d','?')}"
                f" | {row.get('median_ret_63d','?')} |"
            )
        lines.append("")

    lines += [
        "## Decision criteria",
        "",
        "- **Adopt new pair** if: success_63d materially higher than f10_s50 baseline AND CIs don't overlap.",
        "- **Keep f10_s50** if: no pair clearly dominates within CI bounds.",
        "- EMA(20,50) vs EMA(10,50): tests whether slower fast EMA changes signal quality.",
        "- EMA(20,100/150): tests whether longer slow EMA (stronger trend filter) improves precision.",
    ]

    md_path = OUT_DIR / "donchian_ema_expansion.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved {md_path}")

    # ── Console output ────────────────────────────────────────────────────────
    print("\n=== DONCHIAN EMA EXPANSION — 2025 OOS ===\n")
    cols = ["ema_pair", "universe", "n",
            "success_rate_63d", "ci95_lo_63d", "ci95_hi_63d",
            "win_rate_63d", "mean_ret_63d", "median_ret_63d"]
    cols = [c for c in cols if c in out_df.columns]
    for uname in UNIVERSES:
        print(f"--- {uname} ---")
        sub = out_df[out_df["universe"] == uname][cols].sort_values("success_rate_63d", ascending=False)
        print(sub.to_string(index=False))
        print()


if __name__ == "__main__":
    main()
