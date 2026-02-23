# minervini_backtest/scripts/report_compare_versions.py — Read backtest result CSVs, output comparison table (PF, fee sensitivity, etc.)
"""
Expects minervini_backtest_results.csv (or multiple runs with different fee_bps) to produce:
- Summary table: version, trades, win_rate, PF, expectancy, max_drawdown, CAGR, trades_per_year
- Optional: sensitivity PF vs fee (10/20/30/50 bps) + min_hold (0/3/5) if you have multiple runs.
Usage:
  python minervini_backtest/scripts/report_compare_versions.py [results.csv]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

MB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = MB_ROOT / "minervini_backtest_results.csv"


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULTS
    if not path.exists():
        print(f"Results not found: {path}. Run minervini_backtest/run.py first.")
        return
    df = pd.read_csv(path)
    cols = ["version", "trades", "win_rate", "profit_factor", "avg_ret", "expectancy", "max_drawdown", "median_hold_bars", "trades_per_year"]
    if "cagr" in df.columns:
        cols.append("cagr")
    out = df[[c for c in cols if c in df.columns]]
    print("=== Minervini backtest comparison ===")
    print(out.to_string(index=False))
    print("\nRead: PF >1.2 ok, >1.5 good; avg_ret; max_drawdown; trades_per_year.")
    out_path = MB_ROOT / "minervini_comparison_report.csv"
    out.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
