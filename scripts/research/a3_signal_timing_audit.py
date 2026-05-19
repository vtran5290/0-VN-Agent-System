"""
A3/S3 signal timing diagnostic.

Computes per-symbol, per-date signal fields including:
- cloud state, signal bar, entry bar, bars since signal/entry
- a3_signal_today, a3_planned_entry_timing
- whether latest-bar signal would have been missed by pre-fix scan

Outputs:
  data/research/cloud_timing/a3_signal_timing_diagnostic.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(_REPO))

from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.portfolio_optimization_final_steps import (
    compute_phase36_scan_df,
    ema_cloud,
    load_vnindex,
)
from pp_backtest.portfolio_optimization_phase2 import build_gk_cache
from src.trading.intraday.panel_overlay import EOD_PANEL_DEFAULT, load_eod_panel

OUT_DIR = _REPO / "data" / "research" / "cloud_timing"
FINDINGS_DOC = _REPO / "docs" / "trading" / "A3_SIGNAL_TIMING_DIAGNOSTIC_FINDINGS.md"
EOD_PANEL = EOD_PANEL_DEFAULT


def _analyze_symbol(sym: str, sdf: pd.DataFrame) -> list[dict]:
    sdf = sdf.sort_values("date").reset_index(drop=True)
    if len(sdf) < 120:
        return []

    c = sdf["close"].astype(float)
    dates = pd.to_datetime(sdf["date"])

    a3_cloud = ema_cloud(c, 20, 100)
    a3_fast = a3_cloud["ema_fast"]
    a3_slow = a3_cloud["ema_slow"]
    a3_bull = a3_cloud["cloud_bull"]
    a3_sig = cloud_only_entry(c, a3_fast, a3_bull, min_bars_bear=3, warmup=110)
    a3_idxs = np.where(a3_sig.values)[0]

    s3_cloud = ema_cloud(c, 21, 55)
    s3_fast = s3_cloud["ema_fast"]
    s3_bull = s3_cloud["cloud_bull"]
    s3_sig = cloud_only_entry(c, s3_fast, s3_bull, min_bars_bear=3, warmup=65)
    s3_idxs = np.where(s3_sig.values)[0]

    rows = []
    for i in range(len(sdf)):
        # Simulate running scan as-of date i (panel truncated at i)
        c_slice = c.iloc[: i + 1]
        a3_sig_slice = a3_sig.iloc[: i + 1]
        s3_sig_slice = s3_sig.iloc[: i + 1]
        n = len(c_slice)

        a3_signal_bar = bool(a3_sig.iloc[i])
        s3_signal_bar = bool(s3_sig.iloc[i])

        # A3 — post-fix logic (allows latest-bar signal)
        a3_active_postfix = False
        a3_bars_postfix = None
        a3_signal_today_postfix = False
        a3_bars_since_signal_postfix = None
        _a3_idxs_slice = np.where(a3_sig_slice.values)[0]
        if len(_a3_idxs_slice) > 0:
            li = int(_a3_idxs_slice[-1])
            _bss = n - 1 - li
            if _bss <= 40:
                a3_active_postfix = True
                a3_bars_postfix = max(0, n - 1 - (li + 1))
                a3_signal_today_postfix = (_bss == 0)
                a3_bars_since_signal_postfix = _bss

        # A3 — pre-fix logic (required next bar)
        a3_active_prefix = False
        a3_bars_prefix = None
        if len(_a3_idxs_slice) > 0:
            li = int(_a3_idxs_slice[-1])
            if li + 1 < n and (n - 1 - (li + 1)) <= 40:
                a3_active_prefix = True
                a3_bars_prefix = n - 1 - (li + 1)

        missed_by_prefix = (a3_active_postfix and not a3_active_prefix)

        # S3
        s3_active_postfix = False
        s3_bars_postfix = None
        _s3_idxs_slice = np.where(s3_sig_slice.values)[0]
        if len(_s3_idxs_slice) > 0:
            li_s3 = int(_s3_idxs_slice[-1])
            _bss_s3 = n - 1 - li_s3
            if _bss_s3 <= 40:
                s3_active_postfix = True
                s3_bars_postfix = max(0, n - 1 - (li_s3 + 1))

        # Next bar info (only if not the last bar in full dataset)
        next_bar_exists = (i + 1) < len(sdf)
        next_open = float(sdf["open"].iloc[i + 1]) if next_bar_exists else None
        signal_close = float(c.iloc[i])
        next_open_gap_pct = round((next_open / signal_close - 1) * 100, 3) if (next_bar_exists and next_open and signal_close) else None

        rows.append({
            "symbol": sym,
            "date": dates.iloc[i].date(),
            "close": round(signal_close, 3),
            "ema20": round(float(a3_fast.iloc[i]), 3),
            "ema100": round(float(a3_slow.iloc[i]), 3),
            "cloud_bull": bool(a3_bull.iloc[i]),
            "close_above_ema20": bool(c.iloc[i] > a3_fast.iloc[i]),
            "a3_signal_bar": a3_signal_bar,
            "s3_signal_bar": s3_signal_bar,
            "a3_scan_active_postfix": a3_active_postfix,
            "a3_scan_active_prefix": a3_active_prefix,
            "a3_signal_today": a3_signal_today_postfix,
            "a3_bars_since": a3_bars_postfix,
            "a3_bars_since_signal": a3_bars_since_signal_postfix,
            "a3_planned_entry_timing": ("NEXT_OPEN" if a3_signal_today_postfix else ("FILLED" if a3_active_postfix else None)),
            "s3_scan_active": s3_active_postfix,
            "s3_bars_since": s3_bars_postfix,
            "missed_by_prefix_scan": missed_by_prefix,
            "next_bar_exists": next_bar_exists,
            "next_open": next_open,
            "signal_close": signal_close,
            "next_open_gap_pct": next_open_gap_pct,
            "fill_assumption": "NEXT_OPEN_T+1" if a3_signal_bar else None,
        })
    return rows


def run_diagnostic(
    symbols: list[str] | None = None,
    lookback_days: int = 252,
    out_dir: Path = OUT_DIR,
) -> pd.DataFrame:
    panel = load_eod_panel(EOD_PANEL)
    if panel.empty:
        print("EOD panel not found or empty")
        return pd.DataFrame()

    panel["date"] = pd.to_datetime(panel["date"])
    latest = panel["date"].max()
    cutoff = latest - pd.Timedelta(days=lookback_days)
    panel = panel[panel["date"] >= cutoff]

    syms = symbols or sorted(panel["symbol"].unique().tolist())
    all_rows = []
    for sym in syms:
        sdf = panel[panel["symbol"] == sym]
        rows = _analyze_symbol(sym, sdf)
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "a3_signal_timing_diagnostic.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df)} rows, {df['symbol'].nunique()} symbols)")

    # Summary: latest date findings
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date]

    n_fresh_signal = int(latest["a3_signal_today"].sum())
    n_missed_prefix = int(latest["missed_by_prefix_scan"].sum())
    n_a3_active = int(latest["a3_scan_active_postfix"].sum())
    n_s3_active = int(latest["s3_scan_active"].sum())

    print(f"\n=== Latest date: {latest_date} ===")
    print(f"  A3 active: {n_a3_active}")
    print(f"  A3 signal today (fresh, entry=next open): {n_fresh_signal}")
    print(f"  Would have been missed by pre-fix scan: {n_missed_prefix}")
    print(f"  S3 active: {n_s3_active}")

    if n_fresh_signal > 0:
        fresh = latest[latest["a3_signal_today"]]
        print(f"\n  Fresh A3 signals today (planned fill: next open):")
        for _, r in fresh.iterrows():
            print(f"    {r['symbol']}: close={r['close']}, ema20={r['ema20']}")

    # Entry gap analysis
    gap_df = df[(df["a3_signal_bar"]) & df["next_open_gap_pct"].notna()]
    if not gap_df.empty:
        gap_path = out_dir / "entry_gap_analysis.csv"
        gap_df[["symbol", "date", "close", "next_open", "next_open_gap_pct"]].to_csv(gap_path, index=False)
        print(f"\nEntry gap analysis: {len(gap_df)} signal bars")
        print(f"  Mean gap: {gap_df['next_open_gap_pct'].mean():.2f}%")
        print(f"  Median gap: {gap_df['next_open_gap_pct'].median():.2f}%")
        print(f"  90th pct gap: {gap_df['next_open_gap_pct'].quantile(0.9):.2f}%")
        print(f"  Written to {gap_path}")

    return df


def _write_findings_doc(df: pd.DataFrame) -> None:
    if df.empty:
        return
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date]
    gap_df = df[(df["a3_signal_bar"]) & df["next_open_gap_pct"].notna()]

    n_total_signal_bars = int(df["a3_signal_bar"].sum())
    n_missed = int(df["missed_by_prefix_scan"].sum())
    n_fresh = int(latest["a3_signal_today"].sum())
    pct_missed = round(n_missed / max(n_total_signal_bars, 1) * 100, 1)

    gap_mean = round(gap_df["next_open_gap_pct"].mean(), 3) if not gap_df.empty else "N/A"
    gap_p90 = round(gap_df["next_open_gap_pct"].quantile(0.9), 3) if not gap_df.empty else "N/A"

    doc = f"""# A3 Signal Timing Diagnostic Findings

**Generated:** {pd.Timestamp.now().date()}
**Symbols analyzed:** {df['symbol'].nunique()}
**Date range:** {df['date'].min()} to {df['date'].max()}

---

## Key Finding: Latest-Bar Signal Miss Rate

- Total A3 signal bars in period: {n_total_signal_bars}
- Would-have-been-missed by pre-fix scan: {n_missed} ({pct_missed}%)
- These are all bars where signal fires on the latest bar in history (no next bar yet)

**Root cause:** `li + 1 < len(c)` condition in `compute_phase36_scan_df` required the entry bar to already exist before marking `a3_active = True`. Signals on the latest bar were silently dropped.

**Fix applied:** Changed guard to `bars_since_signal <= 40` (allows latest-bar signals). Added `a3_signal_today`, `a3_bars_since_signal`, `a3_planned_entry_timing` fields.

---

## Entry Gap Analysis (Signal Close → Next Open)

- Signal bars with next bar available: {len(gap_df)}
- Mean gap: {gap_mean}%
- 90th percentile gap: {gap_p90}%
- Interpretation: gap represents slippage vs theoretical signal-close fill price

This gap is the cost of Variant B0 (fill at next open) vs Variant B1 (fill at signal close/ATC).

---

## Latest Date ({latest_date}) Summary

- A3 active (post-fix): {int(latest['a3_scan_active_postfix'].sum())}
- A3 signal today (fresh signals): {n_fresh}
- S3 active: {int(latest['s3_scan_active'].sum())}

---

## Backtest Variants Note

| Variant | Description | Testable |
|---|---|---|
| B0 | Signal T, fill T+1 open | YES — production baseline |
| B1 | Signal T, fill T close/ATC | YES — requires ATC price from EOD OHLCV, labeled optimistic |
| B2 | Signal T, fill T+1 close or VWAP proxy | YES — use EOD next-day close as proxy |
| B3 | Intraday provisional, pre-lunch entry | NOT_TESTABLE_WITH_CURRENT_DATA — requires pre-ATC snapshots by date |
| B4 | ATC trigger price diagnostic | YES — see a3_pre_atc_trigger_levels.csv |

---

## Verdict

**SCAN_LAYER_FIX_REQUIRED** — fix has been applied.

- Bug: latest-bar A3 signals were dropped from EOD scan and intraday scan.
- Fix: `compute_phase36_scan_df` now uses `bars_since_signal <= 40` gate.
- New fields: `a3_signal_today`, `a3_bars_since_signal`, `a3_planned_entry_timing`.
- A3 production rule unchanged.
- Intraday preview unchanged — benefits from scan fix automatically.
"""
    FINDINGS_DOC.write_text(doc, encoding="utf-8")
    print(f"Wrote findings to {FINDINGS_DOC}")


def main():
    ap = argparse.ArgumentParser(description="A3 signal timing diagnostic")
    ap.add_argument("--symbols", nargs="*", help="Symbols to analyze (default: all in panel)")
    ap.add_argument("--lookback", type=int, default=252, help="Lookback days (default: 252)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    df = run_diagnostic(args.symbols, args.lookback, args.out_dir)
    _write_findings_doc(df)


if __name__ == "__main__":
    main()
