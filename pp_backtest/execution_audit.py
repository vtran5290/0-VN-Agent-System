#!/usr/bin/env python3
"""
Execution audit — quantify signal-close vs T+1 open gap.

Reads the paper trade execution_audit.csv (written by daily_paper_trade_runner.py)
and computes summary statistics for the go/no-go gate:

  Gate requirement: < 5% of trades with gap > 2%

Usage:
    .venv\\Scripts\\python.exe pp_backtest/execution_audit.py
    .venv\\Scripts\\python.exe pp_backtest/execution_audit.py --backtest
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO    = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "paper_trade"
AUDIT_CSV = OUT_DIR / "execution_audit.csv"

# For backtest-mode: compute historical gap from panel
PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"


def audit_summary(df: pd.DataFrame) -> dict:
    """Compute gap statistics from audit dataframe."""
    gaps = df["gap_pct"].dropna()
    if len(gaps) == 0:
        return {}
    return {
        "n_observations":    len(gaps),
        "avg_gap":           float(gaps.mean()),
        "median_gap":        float(gaps.median()),
        "std_gap":           float(gaps.std()),
        "p90_gap":           float(gaps.quantile(0.90)),
        "p95_gap":           float(gaps.quantile(0.95)),
        "pct_gap_gt_1pct":   float((gaps.abs() > 0.01).mean()),
        "pct_gap_gt_2pct":   float((gaps.abs() > 0.02).mean()),
        "pct_gap_negative":  float((gaps < 0).mean()),   # favorable (gap down)
        "pct_gap_positive":  float((gaps > 0).mean()),   # unfavorable (gap up)
        "avg_positive_gap":  float(gaps[gaps > 0].mean()) if (gaps > 0).any() else 0.0,
        "avg_negative_gap":  float(gaps[gaps < 0].mean()) if (gaps < 0).any() else 0.0,
    }


def print_audit_report(stats: dict, df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("EXECUTION AUDIT — Signal Close vs T+1 Open Gap")
    print("=" * 60)
    print(f"  Observations:        {stats.get('n_observations', 0)}")
    print(f"  Avg gap:             {stats.get('avg_gap', 0):+.2%}")
    print(f"  Median gap:          {stats.get('median_gap', 0):+.2%}")
    print(f"  Std gap:             {stats.get('std_gap', 0):.2%}")
    print(f"  90th pct gap:        {stats.get('p90_gap', 0):+.2%}")
    print(f"  95th pct gap:        {stats.get('p95_gap', 0):+.2%}")
    print(f"")
    print(f"  Gap > 1% (adverse):  {stats.get('pct_gap_gt_1pct', 0):.1%}")
    print(f"  Gap > 2% (adverse):  {stats.get('pct_gap_gt_2pct', 0):.1%}  "
          f"{'FAIL — gate requires < 5%' if stats.get('pct_gap_gt_2pct', 0) > 0.05 else 'PASS'}")
    print(f"  Favorable (gap dn):  {stats.get('pct_gap_negative', 0):.1%}  "
          f"avg={stats.get('avg_negative_gap', 0):+.2%}")
    print(f"  Unfavorable (gap up):{stats.get('pct_gap_positive', 0):.1%}  "
          f"avg={stats.get('avg_positive_gap', 0):+.2%}")

    # Cost impact
    avg_gap = stats.get("avg_gap", 0)
    print(f"\n  Effective cost adj:  +{avg_gap:.0%} avg gap on top of 40 bps assumed")
    effective_cost = 0.004 + abs(avg_gap) if avg_gap > 0 else 0.004
    print(f"  Total effective cost: ~{effective_cost*10000:.0f} bps")

    # By symbol (top 10 worst gaps)
    if not df.empty and "gap_pct" in df.columns:
        worst = (df.groupby("symbol")["gap_pct"]
                 .agg(["mean", "count"])
                 .query("count >= 2")
                 .sort_values("mean", ascending=False)
                 .head(10))
        if not worst.empty:
            print(f"\n  Symbols with highest avg gap (min 2 entries):")
            for sym, row in worst.iterrows():
                print(f"    {sym:<8}  avg_gap={row['mean']:+.2%}  n={int(row['count'])}")


def backtest_gap_analysis(panel: pd.DataFrame, universe: list[str],
                          from_date: str = "2023-01-01") -> pd.DataFrame:
    """
    Compute signal→T+1 open gap historically using the panel.
    Uses the same cloud_only signal logic as the paper trader.
    """
    sys.path.insert(0, str(REPO))
    from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
    from pp_backtest.ema_levels.entry import cloud_only_entry

    EMA_FAST = 20; EMA_SLOW = 100; MIN_BARS_BEAR = 3; WARMUP = 105

    sub   = panel[panel["symbol"].isin(universe) & (panel["date"] >= from_date)]
    rows  = []

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if len(sdf) < WARMUP + 10:
            continue
        cloud = ema_cloud(sdf["close"], EMA_FAST, EMA_SLOW)
        sig   = cloud_only_entry(sdf["close"], cloud["ema_fast"], cloud["cloud_bull"],
                                 min_bars_bear=MIN_BARS_BEAR, warmup=WARMUP)
        sdf   = sdf[sdf["date"] >= from_date].copy()
        sig   = sig[sdf.index]

        signal_bars = sdf.index[sig.values].tolist()
        for bar_i in signal_bars:
            loc = sdf.index.get_loc(bar_i)
            if loc + 1 >= len(sdf):
                continue
            next_row    = sdf.iloc[loc + 1]
            signal_row  = sdf.iloc[loc]
            signal_cl   = float(signal_row["close"])
            next_open   = float(next_row["open"]) if "open" in next_row.index else float(next_row["close"])
            gap_pct     = (next_open - signal_cl) / signal_cl if signal_cl > 0 else 0.0
            rows.append({
                "date":         signal_row["date"],
                "symbol":       sym,
                "signal_close": signal_cl,
                "next_open":    next_open,
                "gap_pct":      gap_pct,
                "direction":    "up" if gap_pct > 0 else "down",
            })

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true",
                    help="Run historical gap analysis from panel (2023+)")
    ap.add_argument("--from-date", default="2023-01-01")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.backtest:
        print("Running historical gap analysis from panel...")
        EX_VIN3 = {"VIC", "VHM", "VRE"}; EXCLUDE = {"VPL"}
        panel = pd.read_parquet(PANEL_PATH)
        panel["date"] = pd.to_datetime(panel["date"])
        panel.sort_values(["symbol", "date"], inplace=True)
        all_syms = sorted(panel["symbol"].unique())
        universe = [s for s in all_syms if s not in EXCLUDE and s not in EX_VIN3]
        df = backtest_gap_analysis(panel, universe, from_date=args.from_date)
        if df.empty:
            print("No signals found.")
            return
        out = REPO / "data" / "research" / "hardening" / "execution_audit_backtest.csv"
        df.to_csv(out, index=False)
        print(f"Saved backtest audit: {out}  ({len(df)} observations)")
    else:
        if not AUDIT_CSV.exists():
            print(f"No audit data yet. Run daily_paper_trade_runner.py first, "
                  f"or use --backtest for historical gap analysis.")
            return
        df = pd.read_csv(AUDIT_CSV)

    stats = audit_summary(df)
    print_audit_report(stats, df)

    # Save summary
    summary_path = OUT_DIR / "execution_audit_summary.csv"
    pd.DataFrame([stats]).to_csv(summary_path, index=False)
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
