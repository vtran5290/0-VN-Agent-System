# minervini_backtest/scripts/mh_overlay_diag.py — Market Health overlay diagnostic (breadth + NH20% + ON/OFF/NEUTRAL days)
"""
Diagnostic for Market Health overlay (MH gate, NH-heavy):

For a given universe (A or B), compute daily:
  - breadth_ma50 = % stocks above MA50
  - nh20_pct     = % stocks making new 20-day highs (excl. current bar)
  - mh_signal    = ON / OFF / NEUTRAL (based on thresholds)
Then aggregate by year:
  - avg breadth_ma50, avg nh20_pct
  - days_ON, days_OFF, days_NEUTRAL

Run example (from repo root):
  .\.venv\Scripts\python.exe minervini_backtest/scripts/mh_overlay_diag.py --universe B --fetch --out minervini_backtest/outputs/mh_overlay_diag.csv
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
from market_health import compute_breadth_above_ma, compute_new_high_pct, mh_signal


def main() -> int:
    p = argparse.ArgumentParser(description="Market Health overlay diagnostic (breadth + NH20%)")
    p.add_argument("--universe", choices=["A", "B"], default="B", help="A=top 15, B=broad (all symbols)")
    p.add_argument("--fetch", action="store_true", help="Fetch via FireAnt if curated empty")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-12-31")
    p.add_argument("--out", "-o", default=None)
    # Threshold overrides (match mh_signal defaults)
    p.add_argument("--breadth-off", type=float, default=0.45)
    p.add_argument("--nh20-off", type=float, default=0.06)
    p.add_argument("--breadth-on", type=float, default=0.55)
    p.add_argument("--nh20-on", type=float, default=0.09)
    args = p.parse_args()

    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        start, end = args.start, args.end
        watchlist80 = REPO_ROOT / "config" / "watchlist_80.txt"
        watchlist = REPO_ROOT / "config" / "watchlist.txt"
        tickers: list[str] = []
        if watchlist80.exists():
            tickers = [
                ln.strip()
                for ln in watchlist80.read_text(encoding="utf-8").strip().splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        elif watchlist.exists():
            tickers = [ln.strip() for ln in watchlist.read_text(encoding="utf-8").strip().splitlines() if ln.strip()]
        if not tickers:
            tickers = ["VN30", "MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "VHM", "HPG", "MSN", "VIC"]
        for sym in tickers[:80]:
            try:
                all_data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception:
                continue
    if not all_data:
        print("No data. Use curated data or --fetch.")
        return 1

    # Universe selection
    syms = [s for s in all_data if s != "VN30"]
    if args.universe == "A":
        n_a = min(15, len(syms))
        use_syms = syms[:n_a]
    else:
        use_syms = syms

    universe = {}
    for sym in use_syms:
        df = all_data[sym]
        if df is None or df.empty:
            continue
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        d = d[(d["date"] >= args.start) & (d["date"] <= args.end)]
        if d.empty:
            continue
        universe[sym] = d
    if not universe:
        print("No universe data after date filter.")
        return 1

    breadth = compute_breadth_above_ma(universe, ma=50)
    nh20 = compute_new_high_pct(universe, lookback=20)
    if breadth.empty or nh20.empty:
        print("Insufficient data to compute breadth/NH20.")
        return 1

    cfg = {
        "breadth_ma50_off": args.breadth_off,
        "nh20_off": args.nh20_off,
        "breadth_ma50_on": args.breadth_on,
        "nh20_on": args.nh20_on,
    }
    sig = mh_signal(breadth, nh20, cfg)

    idx = sig.index
    df = pd.DataFrame(
        {
            "date": idx,
            "breadth_ma50": breadth.reindex(idx).values,
            "nh20_pct": nh20.reindex(idx).values,
            "mh_signal": sig.values,
        }
    )
    df["year"] = pd.to_datetime(df["date"]).dt.year

    grp = df.groupby("year")
    out = grp.agg(
        avg_breadth_ma50=("breadth_ma50", "mean"),
        avg_nh20_pct=("nh20_pct", "mean"),
        days_total=("mh_signal", "count"),
        days_on=("mh_signal", lambda s: (s == "ON").sum()),
        days_off=("mh_signal", lambda s: (s == "OFF").sum()),
        days_neutral=("mh_signal", lambda s: (s == "NEUTRAL").sum()),
    ).reset_index()
    out["avg_breadth_ma50"] = out["avg_breadth_ma50"].round(4)
    out["avg_nh20_pct"] = out["avg_nh20_pct"].round(4)

    print("Market Health overlay diagnostic (universe=%s):" % args.universe)
    print(out.to_string(index=False))

    out_path = Path(args.out) if args.out else ROOT / "outputs" / "mh_overlay_diag.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print("Wrote:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

