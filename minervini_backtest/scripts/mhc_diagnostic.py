# minervini_backtest/scripts/mhc_diagnostic.py — MHC quick diagnostic: yearly CSV (dist20, breadth_ma50, breadth_ma20, nh20_pct)
"""
No composite. Output yearly means for visual check: does 2023 separate from 2020-2021?
Run: python minervini_backtest/scripts/mhc_diagnostic.py [--universe A|B] [--fetch] [--out CSV]
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
from market_health import distribution_count, breadth_above_ma, new_high_pct


def yearly_summary(s: pd.Series, name: str) -> pd.DataFrame:
    """Series (date index) -> DataFrame with columns year, name (yearly mean)."""
    df = s.dropna().to_frame(name)
    df["year"] = df.index.year
    return df.groupby("year")[name].mean().reset_index()


def main():
    ap = argparse.ArgumentParser(description="MHC diagnostic: yearly dist20, breadth_ma50, breadth_ma20, nh20_pct")
    ap.add_argument("--universe", default="A", choices=["A", "B"], help="A = top liquidity (cleaner breadth)")
    ap.add_argument("--fetch", action="store_true", help="Fetch via FireAnt if no curated data")
    ap.add_argument("--out", "-o", default=None, help="Output CSV (default: minervini_backtest/mhc_diag_<universe>.csv)")
    ap.add_argument("--down-thresh", type=float, default=-0.003, help="Distribution day: index down >= |this| (default 0.3%%)")
    args = ap.parse_args()

    # Load data. For B (broad), prefer watchlist_80 so breadth = 50–80 names, not narrow elite.
    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        start, end = "2018-01-01", "2026-12-31"
        watchlist_80 = REPO_ROOT / "config" / "watchlist_80.txt"
        watchlist_path = REPO_ROOT / "config" / "watchlist.txt"
        tickers = ["VN30", "MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "VHM", "HPG", "MSN", "VIC"]
        if args.universe == "B" and watchlist_80.exists():
            tickers = [ln.strip() for ln in watchlist_80.read_text(encoding="utf-8").strip().splitlines() if ln.strip() and not ln.strip().startswith("#")]
        elif watchlist_path.exists():
            tickers = [ln.strip() for ln in watchlist_path.read_text(encoding="utf-8").strip().splitlines() if ln.strip()]
        max_syms = 80 if args.universe == "B" else 50
        for sym in (["VN30"] + [t for t in tickers if t.upper() != "VN30"])[:max_syms]:
            try:
                all_data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception:
                pass
    if not all_data:
        print("No data. Use data/curated or --fetch.")
        return 1

    index_df = all_data.get("VN30")
    if index_df is None or index_df.empty:
        print("VN30 not in data. Add VN30 to curated or use --fetch.")
        return 1
    index_df = index_df.copy()
    index_df["date"] = pd.to_datetime(index_df["date"])

    syms = [s for s in all_data if s != "VN30"]
    n_a = min(15, len(syms))
    universe = {s: all_data[s] for s in syms[:n_a]} if args.universe == "A" else {s: all_data[s] for s in syms}
    if not universe:
        print("No universe symbols.")
        return 1

    # Compute series (no composite)
    dist20 = distribution_count(index_df, lookback=20, down_thresh=args.down_thresh)
    breadth_ma50 = breadth_above_ma(universe, ma=50)
    breadth_ma20 = breadth_above_ma(universe, ma=20)
    nh20 = new_high_pct(universe, lookback=20)

    # Yearly means and merge
    rows = []
    for name, ser in [
        ("dist20", dist20),
        ("breadth_ma50", breadth_ma50),
        ("breadth_ma20", breadth_ma20),
        ("nh20_pct", nh20),
    ]:
        if ser is None or ser.empty:
            continue
        try:
            rows.append(yearly_summary(ser, name))
        except Exception:
            continue

    if not rows:
        print("No series produced.")
        return 1

    out = rows[0]
    for r in rows[1:]:
        out = out.merge(r, on="year", how="outer")
    out["year"] = out["year"].astype(int)

    out_path = args.out or str(ROOT / "mhc_diag_{}.csv".format(args.universe))
    out.to_csv(out_path, index=False)
    print("MHC diagnostic (index=VN30, universe=%s, no composite)" % args.universe)
    print(out.to_string(index=False))
    print("Wrote: %s" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
