# minervini_backtest/scripts/test_market_health.py — Quick diagnostic: distribution + breadth by year (sanity before full MHC)
"""
Run: python minervini_backtest/scripts/test_market_health.py [--universe A|B] [--fetch] [--out CSV]
Output: by year, avg distribution count (VN30), avg % above MA50 (universe), then % OFF/ON/NEUTRAL from composite.
Use Universe A first (liquidity = cleaner breadth). Visual check: 2023 vs 2020-2021 clearly different?
"""
from __future__ import annotations
import sys
from pathlib import Path
import argparse
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import load_curated_data, fetch_fireant
from market_health import compute_distribution, compute_breadth, composite_signal


def main():
    p = argparse.ArgumentParser(description="Market Health diagnostic: distribution + breadth by year")
    p.add_argument("--universe", choices=["A", "B"], default="A", help="A = top liquidity (cleaner breadth)")
    p.add_argument("--fetch", action="store_true", help="Fetch index/universe via FireAnt if no curated data")
    p.add_argument("--out", "-o", default=None, help="Optional CSV path")
    p.add_argument("--min-down-pct", type=float, default=0.002, help="Distribution day: index down >= this (default 0.2%%)")
    args = p.parse_args()

    # Load data
    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        start, end = "2018-01-01", "2025-12-31"
        watchlist = REPO_ROOT / "config" / "watchlist.txt"
        tickers = ["VN30", "MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "VHM", "HPG", "MSN", "VIC"]
        if watchlist.exists():
            tickers = [ln.strip() for ln in watchlist.read_text(encoding="utf-8").strip().splitlines() if ln.strip()]
        for sym in (["VN30"] + [t for t in tickers if t.upper() != "VN30"])[:50]:
            try:
                all_data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception:
                pass
    if not all_data:
        print("No data. Use data/curated or --fetch.")
        return 1

    # Index = VN30
    index_df = all_data.get("VN30")
    if index_df is None or index_df.empty:
        print("VN30 not in data. Add VN30 to curated or use --fetch.")
        return 1
    index_df = index_df.copy()
    index_df["date"] = pd.to_datetime(index_df["date"])

    # Universe A = first 15, B = all
    syms = [s for s in all_data if s != "VN30"]
    n_a = min(15, len(syms))
    universe_a = {s: all_data[s] for s in syms[:n_a]}
    universe_b = {s: all_data[s] for s in syms}
    universe = universe_a if args.universe == "A" else universe_b
    label = "A_top_liquidity" if args.universe == "A" else "B_broad"

    # Distribution (index), breadth (universe)
    dist = compute_distribution(index_df, lookback=20, min_down_pct=args.min_down_pct)
    breadth = compute_breadth(universe, ma_window=50)
    # Align: dist has date index from module; dropna for valid rolling window
    dist_aligned = dist.dropna()
    breadth_aligned = breadth.reindex(dist_aligned.index)
    comp = composite_signal(dist_aligned, breadth_aligned)

    # By year
    years = dist_aligned.index.year.unique()
    rows = []
    for yr in sorted(years):
        mask = dist_aligned.index.year == yr
        avg_dist = dist_aligned.loc[mask].mean()
        b = breadth_aligned.loc[mask]
        avg_breadth = b.mean() if b.notna().any() else float("nan")
        c = comp.reindex(dist_aligned.index[mask])
        n = c.count()
        pct_off = (c == "OFF").sum() / n * 100 if n else 0
        pct_on = (c == "ON").sum() / n * 100 if n else 0
        pct_neutral = (c == "NEUTRAL").sum() / n * 100 if n else 0
        rows.append({
            "year": yr,
            "avg_dist_count": round(avg_dist, 2),
            "avg_pct_above_ma50": round(avg_breadth * 100, 1) if pd.notna(avg_breadth) else None,
            "pct_OFF": round(pct_off, 1),
            "pct_ON": round(pct_on, 1),
            "pct_NEUTRAL": round(pct_neutral, 1),
        })

    df = pd.DataFrame(rows)
    print("Market Health diagnostic (index=VN30, breadth=universe " + label + ")")
    print("Distribution: close<prev_close & vol>prev_vol & down>=%.2f%%" % (args.min_down_pct * 100))
    print(df.to_string(index=False))
    if args.out:
        df.to_csv(args.out, index=False)
        print("Wrote: %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
