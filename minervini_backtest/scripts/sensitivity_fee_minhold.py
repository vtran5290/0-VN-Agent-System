# minervini_backtest/scripts/sensitivity_fee_minhold.py — PF × fee_bps × min_hold_bars (VN realism)
"""
Output: table PF, expectancy, trades for each (version, fee_bps, min_hold_bars).
Run: python minervini_backtest/scripts/sensitivity_fee_minhold.py [--config M1] [--symbols MBB SSI ...]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Import run's helpers
sys.path.insert(0, str(ROOT))
from run import load_config, load_curated_data, fetch_fireant, run_one

FEE_BPS = [0, 10, 20, 30, 50]
MIN_HOLD_BARS = [0, 3]
DEFAULT_CONFIG = "M1"


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Config name (default M1)")
    p.add_argument("--symbols", nargs="*", default=None)
    p.add_argument("--fetch", action="store_true", help="Fetch from FireAnt if no data")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--out", "-o", default=None, help="Output CSV")
    args = p.parse_args()

    data = load_curated_data(args.symbols)
    if not data and args.fetch:
        start = args.start or "2018-01-01"
        end = args.end or "2024-12-31"
        tickers = args.symbols or ["MBB", "SSI", "VCI", "TCB"]
        for sym in tickers:
            try:
                data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception as e:
                print(f"[skip] {sym}: {e}")
    if not data:
        print("No data. Use --fetch or populate data/curated.")
        return 1
    if args.start or args.end:
        for sym in list(data):
            data[sym] = data[sym].copy()
            data[sym] = data[sym].set_index("date")
            if args.start:
                data[sym] = data[sym].loc[args.start:]
            if args.end:
                data[sym] = data[sym].loc[:args.end]
            data[sym] = data[sym].reset_index()

    rows = []
    for fee_bps in FEE_BPS:
        for min_hold in MIN_HOLD_BARS:
            try:
                _, ledger = run_one(args.config, data, {"fee_bps": fee_bps, "min_hold_bars": min_hold})
            except Exception as e:
                print(f"Error fee_bps={fee_bps} min_hold={min_hold}: {e}")
                continue
            if ledger.empty:
                rows.append({"fee_bps": fee_bps, "min_hold_bars": min_hold, "trades": 0, "profit_factor": None, "expectancy": None})
                continue
            ret = ledger["ret"].astype(float)
            wins, losses = ret[ret > 0], ret[ret <= 0]
            pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else None
            rows.append({
                "fee_bps": fee_bps,
                "min_hold_bars": min_hold,
                "trades": len(ledger),
                "profit_factor": round(pf, 4) if pf is not None else None,
                "expectancy": round(ret.mean(), 4),
            })
    df = pd.DataFrame(rows)
    out = Path(args.out) if args.out else ROOT / "sensitivity_fee_minhold.csv"
    df.to_csv(out, index=False)
    print(df.to_string())
    print(f"\nWrote: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
