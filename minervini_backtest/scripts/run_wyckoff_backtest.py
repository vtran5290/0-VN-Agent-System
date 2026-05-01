# Run Wyckoff (W2) backtest on subset of symbols and print results. Usage: python run_wyckoff_backtest.py [--symbols A B C ...]
from __future__ import annotations
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DATA_RAW = ROOT / "data" / "raw"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from run import load_config, load_curated_data, run_one

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", "-c", default="W2_Institutional_Flow", help="Config name")
    ap.add_argument("--symbols", "-s", nargs="*", default=None, help="Symbol list; default first 30 from raw")
    args = ap.parse_args()
    data = load_curated_data(args.symbols)
    if not data:
        if DATA_RAW.exists():
            syms = sorted(p.stem for p in DATA_RAW.glob("*.csv"))[:30]
            data = load_curated_data(syms)
        if not data:
            print("No data. Put CSVs in minervini_backtest/data/raw/")
            return
    cfg = load_config(args.config)
    print(f"Config: {args.config}, symbols: {len(data)}")
    stats_df, ledger_df = run_one(args.config, data)
    if ledger_df.empty:
        print("No trades.")
        return
    from metrics import trade_metrics, trades_per_year, minervini_r_metrics
    m = trade_metrics(ledger_df)
    r = minervini_r_metrics(ledger_df)
    print(f"Trades: {m['trades']}, WinRate: {m['win_rate']:.2%}, PF: {m['profit_factor']:.2f}, Expectancy: {m['expectancy']:.4f}")
    print(f"Expectancy_R: {r.get('expectancy_r', 0):.3f}, CAGR: {r.get('cagr', 0):.2%}, Trades/year: {trades_per_year(ledger_df):.1f}")
    out = ROOT / "wyckoff_backtest_results.csv"
    ledger_df.to_csv(out, index=False)
    print(f"Ledger: {out}")

if __name__ == "__main__":
    main()
