#!/usr/bin/env python3
"""
Donchian + cloud model vs level-breakout model — head-to-head on 2025 OOS window.

Donchian rule (no params to select, applied directly to test period):
  signal = close[t] > max(high[t-20 : t]) AND bull_cloud[t] AND above_cloud[t]
  entry  = open[t+1]

Level model: uses best OOS param (f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30),
  breakout signals only, from trades.csv.

Both evaluated on 2025-01-01 onwards, same 3 universe tracks.
VPL excluded entirely.

Output:
  data/research/ema_cloud/donchian_vs_level_oos.csv
  data/research/ema_cloud/donchian_vs_level_oos.md
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

OUT_DIR   = REPO / "data" / "research" / "ema_cloud"
CACHE_PARQUET = OUT_DIR / "ohlcv_panel_cache.parquet"

TEST_START    = pd.Timestamp("2025-01-01")
EMA_FAST      = 10
EMA_SLOW      = 50
DON_LOOKBACK  = 20
CLOSE_BUFFER  = 0.003
ADV50_MIN_BN  = 2.0
SUCCESS_TARGET = 0.15
SUCCESS_STOP   = 0.08
HORIZON_TRADING = [63, 126]
HORIZON_NAMES   = ["63d", "126d"]
BEST_LEVEL_PARAM = "f10_s50_rb1_mc240_rbw80_pd0.30_mm3_cb0.30"
Z95 = 1.96

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


def _fwd_returns(close, high, low, open_, entry_t, n):
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
        r[f"fwd_ret_{h_name}"]      = float(fwd)
        r[f"win_{h_name}"]          = int(fwd > 0)
        r[f"trade_success_{h_name}"] = int(ok)
    return r


def run_donchian_on_symbol(sym_df: pd.DataFrame) -> list[dict]:
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    dates  = pd.to_datetime(sym_df["date"].values)
    close  = sym_df["close"].values.astype(float)
    open_  = sym_df["open"].values.astype(float)
    high   = sym_df["high"].values.astype(float)
    low    = sym_df["low"].values.astype(float)
    value  = sym_df["value"].values.astype(float) if "value" in sym_df.columns else np.ones(len(close))
    symbol = str(sym_df["symbol"].iloc[0])
    n = len(sym_df)

    ema_f = _ewm(close, EMA_FAST)
    ema_s = _ewm(close, EMA_SLOW)
    adv   = _adv50(value)
    bull  = ema_f > ema_s
    above = close > np.maximum(ema_f, ema_s)

    warmup = max(EMA_SLOW + 10, DON_LOOKBACK + 1)
    rows = []
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
        r = _fwd_returns(close, high, low, open_, t + 1, n)
        if r:
            r["symbol"]      = symbol
            r["signal_date"] = dates[t]
            r["model"]       = "donchian"
            rows.append(r)
    return rows


def stats_row(rows: list[dict], model: str, universe: str) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    out = {"model": model, "universe": universe, "n": len(df)}
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
        out[f"n_{h}"]                 = len(g)
        out[f"success_rate_{h}"]      = round(p_sc, 4)
        out[f"success_ci95_lo_{h}"]   = ci_lo
        out[f"success_ci95_hi_{h}"]   = ci_hi
        out[f"win_rate_{h}"]          = round(float(df[wc].mean()), 4)
        out[f"mean_ret_{h}"]          = round(float(g.mean()), 4)
        out[f"median_ret_{h}"]        = round(float(g.median()), 4)
        out[f"p25_ret_{h}"]           = round(float(g.quantile(0.25)), 4)
        out[f"p75_ret_{h}"]           = round(float(g.quantile(0.75)), 4)
    return out


def main():
    log.info("Loading data...")
    panel  = pd.read_parquet(CACHE_PARQUET)
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    trades["signal_date"] = pd.to_datetime(trades["signal_date"])

    panel  = panel[~panel["symbol"].isin({"VPL"})].copy()
    trades = trades[~trades["signal_date"].isnull()].copy()

    # ── Donchian signals (2025 only, computed on-the-fly) ─────────────────────
    log.info("Generating Donchian signals for 2025 test window...")
    don_rows: list[dict] = []
    for sym, grp in panel.groupby("symbol"):
        if sym == "VPL":
            continue
        don_rows.extend(run_donchian_on_symbol(grp))
    log.info(f"  Donchian 2025 signals: {len(don_rows):,}")

    # ── Level model signals (2025 only, from trades.csv) ──────────────────────
    level_test = trades[
        (trades["param_key"] == BEST_LEVEL_PARAM) &
        (trades["signal_type"] == "breakout") &
        (trades["signal_date"] >= TEST_START)
    ].copy()
    # exclude truncated
    for h in HORIZON_NAMES:
        tc = f"is_truncated_{h}"
        if tc in level_test.columns:
            level_test = level_test[level_test[tc] == 0]
    level_rows: list[dict] = []
    for _, row in level_test.iterrows():
        r = {"symbol": row["symbol"], "signal_date": row["signal_date"], "model": "level_breakout"}
        for h in HORIZON_NAMES:
            for prefix in ["fwd_ret_", "win_", "trade_success_"]:
                col = f"{prefix}{h}"
                if col in row.index:
                    r[col] = row[col]
        level_rows.append(r)
    log.info(f"  Level breakout 2025 signals: {len(level_rows):,}")

    # ── Compute stats for each (model, universe) ──────────────────────────────
    results = []
    for uname, excl in UNIVERSES.items():
        don_u   = [r for r in don_rows   if r["symbol"] not in excl]
        level_u = [r for r in level_rows if r["symbol"] not in excl]

        s = stats_row(don_u,   "donchian",       uname)
        if s: results.append(s)
        s = stats_row(level_u, "level_breakout",  uname)
        if s: results.append(s)

    out_df = pd.DataFrame(results)
    csv_path = OUT_DIR / "donchian_vs_level_oos.csv"
    out_df.to_csv(csv_path, index=False)
    log.info(f"Saved {csv_path}")

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        "# Donchian vs Level-Breakout — 2025 OOS Head-to-Head",
        "",
        f"**Test window:** {TEST_START.date()} – latest  ",
        "**Donchian rule:** `close > max(high[t-20:t]) AND bull_cloud AND above_cloud`, entry open[t+1]  ",
        f"**Level model:** best OOS param `{BEST_LEVEL_PARAM}`, breakout only  ",
        "**VPL:** excluded  |  **CIs:** Wilson 95%",
        "",
        "---",
        "",
    ]

    for uname in UNIVERSES:
        lines.append(f"## {uname}")
        lines.append("")
        lines.append("| model | n | success_63d | CI 95% | win_63d | mean_63d | median_63d |")
        lines.append("|-------|---|-------------|--------|---------|----------|------------|")
        for model in ["donchian", "level_breakout"]:
            row = next((r for r in results if r["model"] == model and r["universe"] == uname), None)
            if row is None:
                lines.append(f"| {model} | — | — | — | — | — | — |")
                continue
            ci = f"[{row.get('success_ci95_lo_63d','?')}, {row.get('success_ci95_hi_63d','?')}]"
            lines.append(
                f"| {model} | {row.get('n',0)} | {row.get('success_rate_63d','?')} | {ci}"
                f" | {row.get('win_rate_63d','?')} | {row.get('mean_ret_63d','?')}"
                f" | {row.get('median_ret_63d','?')} |"
            )
        lines.append("")

    lines += [
        "## Notes",
        "",
        "- Donchian has no train-period params — rule is fixed.",
        "- Level model best param selected on 2023–2024 train; applied to 2025 test.",
        "- If Donchian OOS success ≥ 28% with positive mean_ret: use as Step 7 baseline.",
        "- CI overlap = statistically indistinguishable.",
    ]

    md_path = OUT_DIR / "donchian_vs_level_oos.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved {md_path}")

    # ── Console summary ───────────────────────────────────────────────────────
    print("\n=== DONCHIAN vs LEVEL BREAKOUT — 2025 OOS ===\n")
    cols = ["model", "universe", "n", "success_rate_63d",
            "success_ci95_lo_63d", "success_ci95_hi_63d",
            "win_rate_63d", "mean_ret_63d", "median_ret_63d"]
    cols = [c for c in cols if c in out_df.columns]
    print(out_df[cols].sort_values(["universe", "model"]).to_string(index=False))


if __name__ == "__main__":
    main()
