# minervini_backtest/scripts/liquidity_diag.py — Liquidity gate diagnostics by year
"""
Diagnostic for liquidity_gate (execution realism):

For each year, report % of (symbol, day) bars that pass the ADTV VND threshold.
Useful to see how aggressive the liquidity thresholds are for 2012–2016 etc.

Run examples (from repo root):
  .\.venv\Scripts\python.exe minervini_backtest/scripts/liquidity_diag.py --universe B --fetch
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
from filters import liquidity_gate


DEFAULT_MIN_ADTV_VND_BY_YEAR = {
    2012: 5e9,
    2013: 6e9,
    2014: 8e9,
    2015: 10e9,
    2016: 12e9,
    2017: 15e9,
    "2018+": 20e9,
}


def main() -> int:
    p = argparse.ArgumentParser(description="Liquidity gate diagnostic: % of bars eligible by year")
    p.add_argument("--universe", choices=["A", "B"], default="B", help="A = top 15, B = broad (all symbols)")
    p.add_argument("--fetch", action="store_true", help="Fetch via FireAnt if curated data missing")
    p.add_argument("--start", default="2012-01-01")
    p.add_argument("--end", default="2026-12-31")
    p.add_argument("--adtv-window", type=int, default=50)
    p.add_argument("--out", "-o", default=None, help="Output CSV path (default: outputs/liquidity_diag.csv)")
    args = p.parse_args()

    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        watchlist_path = REPO_ROOT / "config" / "watchlist_80.txt"
        watchlist_fallback = REPO_ROOT / "config" / "watchlist.txt"
        tickers: list[str] = []
        if watchlist_path.exists():
            tickers = [
                ln.strip()
                for ln in watchlist_path.read_text(encoding="utf-8").strip().splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        elif watchlist_fallback.exists():
            tickers = [
                ln.strip()
                for ln in watchlist_fallback.read_text(encoding="utf-8").strip().splitlines()
                if ln.strip()
            ]
        if not tickers:
            tickers = ["VN30", "MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "VHM", "HPG", "MSN", "VIC"]
        for sym in tickers[:80]:
            try:
                all_data[sym.upper()] = fetch_fireant(sym, args.start, args.end)
            except Exception:
                continue
    if not all_data:
        print("No data. Use curated data or --fetch.")
        return 1

    # Universe selection
    syms = [s for s in all_data if s != "VN30"]
    if args.universe == "A":
        n_a = min(15, len(syms))
        universe_syms = syms[:n_a]
    else:
        universe_syms = syms

    rows = []
    for sym in universe_syms:
        df = all_data[sym].copy()
        if df is None or df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= args.start) & (df["date"] <= args.end)]
        if df.empty:
            continue
        try:
            elig = liquidity_gate(
                df,
                adtv_window=args.adtv_window,
                min_adtv_vnd_by_year=DEFAULT_MIN_ADTV_VND_BY_YEAR,
            )
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            continue
        tmp = pd.DataFrame({"date": df["date"], "eligible": elig.astype(float)})
        tmp["year"] = tmp["date"].dt.year
        tmp["symbol"] = sym
        rows.append(tmp)

    if not rows:
        print("No eligible data to compute diagnostics.")
        return 1

    all_rows = pd.concat(rows, ignore_index=True)
    grp = all_rows.groupby("year")["eligible"]
    out = grp.mean().reset_index(name="eligible_share")
    out["eligible_share"] = out["eligible_share"].round(4)
    out["eligible_pct"] = (out["eligible_share"] * 100).round(1)

    print("Liquidity gate diagnostic (universe=%s, adtv_window=%s):" % (args.universe, args.adtv_window))
    print(out.to_string(index=False))

    out_path = Path(args.out) if args.out else ROOT / "outputs" / "liquidity_diag.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print("Wrote:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

