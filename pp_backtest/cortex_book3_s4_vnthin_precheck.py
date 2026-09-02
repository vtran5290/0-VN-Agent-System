#!/usr/bin/env python3
"""
Cortex Book 3 — S4 Darvas box VN-THIN empirical pre-check.

Pre-registration: knowledge/backtests/2026-07-05_cortex_book3_s4_darvas_box_prereg.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    python pp_backtest/cortex_book3_s4_vnthin_precheck.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from pp_backtest.cortex_book2_common import build_signal_filter_map
from pp_backtest.p0_realism_p1_winner import _build_honest_cache
from pp_backtest.sprint2b_common import build_baseline_stack

IS_START = pd.Timestamp("2012-01-01")
IS_END = pd.Timestamp("2019-12-31")
OOS_START = pd.Timestamp("2020-01-01")
OOS_END = pd.Timestamp("2026-07-03")
TURNOVER_FLOOR_VND = 2e9
BOX_WINDOWS = (20, 40)
OUT_PATH = REPO / "knowledge" / "backtests" / "2026-07-05_s4_vnthin_precheck.md"


def _range_ratio(high: np.ndarray, low: np.ndarray, end_i: int, n: int) -> float:
    """max(high)/min(low) over [end_i-n+1, end_i] inclusive."""
    start = max(0, end_i - n + 1)
    h_slice = high[start : end_i + 1]
    l_slice = low[start : end_i + 1]
    if len(h_slice) < n // 2:
        return np.nan
    lo = float(np.min(l_slice))
    hi = float(np.max(h_slice))
    if lo <= 0:
        return np.nan
    return hi / lo


def _prior_n_high_excl_today(high: np.ndarray, end_i: int, n: int) -> float:
    """max(high[t-N:t-1]) — prior N days excluding signal bar."""
    start = max(0, end_i - n)
    if start >= end_i:
        return np.nan
    return float(np.max(high[start:end_i]))


def _mean_daily_value(close: np.ndarray, volume: np.ndarray, end_i: int, n: int) -> float:
    start = max(0, end_i - n + 1)
    dv = close[start : end_i + 1] * volume[start : end_i + 1]
    if len(dv) == 0:
        return 0.0
    return float(np.mean(dv))


def collect_signal_metrics(panel: pd.DataFrame, cache: dict) -> pd.DataFrame:
    """One row per A3_RS signal (signal bar) with box metrics for N=20 and N=40."""
    vol_lookup: dict[tuple[str, pd.Timestamp], float] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        dates = pd.to_datetime(sdf["date"])
        close = sdf["close"].astype(float).values
        vol = sdf["volume"].astype(float).values
        for i in range(len(sdf)):
            d = dates.iloc[i].normalize()
            vol_lookup[(str(sym), d)] = close[i] * vol[i]

    rows: list[dict] = []
    for sym, data in cache.items():
        high = data["high"]
        low = data["low"]
        close = data["close"]
        dates = pd.to_datetime(data["dates"])
        for si in data["sig_idxs"]:
            sig_dt = pd.Timestamp(dates[si]).normalize()
            rec: dict = {
                "symbol": str(sym),
                "signal_date": sig_dt,
                "close_sig": float(close[si]),
            }
            for n in BOX_WINDOWS:
                rec[f"range_ratio_{n}"] = _range_ratio(high, low, si, n)
                prior_hi = _prior_n_high_excl_today(high, si, n)
                rec[f"breakout_{n}"] = (
                    np.isfinite(prior_hi) and float(close[si]) > prior_hi
                )
                rec[f"turnover_ok_{n}"] = (
                    _mean_daily_value(close, data.get("volume", close * 0), si, n)
                    >= TURNOVER_FLOOR_VND
                )
            rows.append(rec)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Attach volume from panel if not in cache
    if "volume" not in next(iter(cache.values()), {}):
        for i, row in df.iterrows():
            for n in BOX_WINDOWS:
                si_key = (row["symbol"], row["signal_date"])
                # recompute turnover from panel slice
                pass
    return df


def collect_signal_metrics_v2(panel: pd.DataFrame, cache: dict) -> pd.DataFrame:
    """Build metrics using panel OHLCV grouped by symbol."""
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    sym_groups = {
        str(sym): g.sort_values("date").reset_index(drop=True)
        for sym, g in panel.groupby("symbol", sort=False)
    }

    rows: list[dict] = []
    for sym, data in cache.items():
        if sym not in sym_groups:
            continue
        sdf = sym_groups[sym]
        p_dates = pd.to_datetime(sdf["date"])
        date_to_i = {pd.Timestamp(d).normalize(): i for i, d in enumerate(p_dates)}
        high = sdf["high"].astype(float).values
        low = sdf["low"].astype(float).values
        close = sdf["close"].astype(float).values
        volume = sdf["volume"].astype(float).values

        for si in data["sig_idxs"]:
            sig_dt = pd.Timestamp(data["dates"][si]).normalize()
            pi = date_to_i.get(sig_dt)
            if pi is None:
                continue
            rec: dict = {"symbol": sym, "signal_date": sig_dt}
            for n in BOX_WINDOWS:
                rec[f"range_ratio_{n}"] = _range_ratio(high, low, pi, n)
                prior_hi = _prior_n_high_excl_today(high, pi, n)
                rec[f"breakout_{n}"] = (
                    np.isfinite(prior_hi) and float(close[pi]) > prior_hi
                )
                start = max(0, pi - n + 1)
                mean_dv = float(np.mean(close[start : pi + 1] * volume[start : pi + 1]))
                rec[f"turnover_ok_{n}"] = mean_dv >= TURNOVER_FLOOR_VND
            rows.append(rec)
    return pd.DataFrame(rows)


def run_s4_vnthin_precheck() -> dict:
    print("S4 VN-THIN pre-check — Darvas box criterion", flush=True)
    stack = build_baseline_stack()
    panel = stack["ctx"].panel
    cache = _build_honest_cache(panel)
    base_trades = stack["base_trades"]
    filter_map = build_signal_filter_map(panel)

    sig_df = collect_signal_metrics_v2(panel, cache)
    if sig_df.empty:
        raise RuntimeError("No signal metrics collected")

    # IS tercile cutpoint per window (tightest tercile = bottom 33% of range_ratio)
    is_mask = (sig_df["signal_date"] >= IS_START) & (sig_df["signal_date"] <= IS_END)
    cutpoints: dict[int, float] = {}
    for n in BOX_WINDOWS:
        col = f"range_ratio_{n}"
        is_vals = sig_df.loc[is_mask, col].dropna()
        cutpoints[n] = float(is_vals.quantile(1 / 3)) if len(is_vals) else np.nan
        print(f"  IS tightness tercile cutpoint N={n}: {cutpoints[n]:.4f}", flush=True)

    oos_mask = (sig_df["signal_date"] >= OOS_START) & (sig_df["signal_date"] <= OOS_END)
    oos_sigs = sig_df.loc[oos_mask]
    n_base_oos = len(oos_sigs)

    # Align with executed baseline trades (ADV-qualified honest trades)
    base_oos = base_trades.copy()
    base_oos["entry_date"] = pd.to_datetime(base_oos["entry_date"])
    base_oos = base_oos[
        (base_oos["entry_date"] >= OOS_START) & (base_oos["entry_date"] <= OOS_END)
    ]
    if "signal_date" in base_oos.columns:
        base_oos["signal_date"] = pd.to_datetime(base_oos["signal_date"]).dt.normalize()
    else:
        base_oos["signal_date"] = base_oos["entry_date"] - pd.Timedelta(days=1)

    results: dict[int, dict] = {}
    for n in BOX_WINDOWS:
        tight_col = f"range_ratio_{n}"
        cp = cutpoints[n]
        tight = oos_sigs[tight_col] <= cp
        brk = oos_sigs[f"breakout_{n}"]
        turn = oos_sigs[f"turnover_ok_{n}"]
        box_mask = tight & brk & turn
        box_sigs = oos_sigs.loc[box_mask]
        n_box = len(box_sigs)
        pct_base = 100.0 * n_box / n_base_oos if n_base_oos else 0.0

        s1_overlap = 0.0
        if n_box > 0:
            prox_hits = 0
            for _, row in box_sigs.iterrows():
                entry_dt = row["signal_date"] + pd.Timedelta(days=1)
                key = (row["symbol"], pd.Timestamp(entry_dt).normalize())
                rec = filter_map.get(key)
                if rec and rec.get("prox", 0) >= 0.80:
                    prox_hits += 1
            s1_overlap = 100.0 * prox_hits / n_box

        results[n] = {
            "n_oos": n_box,
            "pct_base": pct_base,
            "s1_overlap": s1_overlap,
            "cutpoint": cp,
        }
        print(
            f"  N={n}: OOS count={n_box}, % base={pct_base:.1f}%, S1 overlap={s1_overlap:.1f}%",
            flush=True,
        )

    max_n = max(r["n_oos"] for r in results.values())
    if max_n >= 30:
        verdict = "VIABLE"
    elif max_n >= 15:
        verdict = "BORDERLINE"
    else:
        verdict = "VN-THIN"

    # Use N=20 cutpoint as primary reported cutpoint (or both)
    cp_primary = cutpoints[20]

    lines = [
        "# S4 VN-THIN PRE-CHECK REPORT",
        "",
        f"**Generated:** {date.today()}",
        f"**OOS window:** {OOS_START.date()} → {OOS_END.date()}",
        f"**IS window for tercile:** {IS_START.date()} → {IS_END.date()}",
        "",
        "```",
        "S4 VN-THIN PRE-CHECK REPORT",
        f"Window N=20: OOS count = {results[20]['n_oos']}, "
        f"% of A3_RS base = {results[20]['pct_base']:.1f}%, "
        f"S1 overlap = {results[20]['s1_overlap']:.1f}%",
        f"Window N=40: OOS count = {results[40]['n_oos']}, "
        f"% of A3_RS base = {results[40]['pct_base']:.1f}%, "
        f"S1 overlap = {results[40]['s1_overlap']:.1f}%",
        f"Tightness tercile cutpoint (IS): N20={cutpoints[20]:.4f}, N40={cutpoints[40]:.4f}",
        f"Turnover floor applied: {TURNOVER_FLOOR_VND/1e9:.0f}B VND/day",
        f"VERDICT: {verdict}",
        "```",
        "",
        "## Details",
        "",
        f"- A3_RS OOS signal instances (all signals in window): **{n_base_oos}**",
        f"- Baseline honest OOS trades: **{len(base_oos)}**",
        "",
        "| Window | IS cutpoint | OOS box count | % of signal base | S1 overlap (prox≥0.80) |",
        "|--------|-------------|---------------|------------------|-------------------------|",
    ]
    for n in BOX_WINDOWS:
        r = results[n]
        lines.append(
            f"| N={n} | {r['cutpoint']:.4f} | {r['n_oos']} | {r['pct_base']:.1f}% | {r['s1_overlap']:.1f}% |"
        )
    lines.extend([
        "",
        f"**VERDICT: {verdict}**",
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {OUT_PATH}", flush=True)
    return {"verdict": verdict, "results": results, "cutpoints": cutpoints}


def main() -> None:
    run_s4_vnthin_precheck()


if __name__ == "__main__":
    main()
