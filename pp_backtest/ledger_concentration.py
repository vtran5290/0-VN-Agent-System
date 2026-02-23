# pp_backtest/ledger_concentration.py — Concentration & return distribution (IC Scorecard)
from __future__ import annotations
import sys
import pandas as pd
import numpy as np


def analyze_ledger(path: str) -> None:
    df = pd.read_csv(path)

    if "ret" not in df.columns:
        raise ValueError("Column 'ret' not found in ledger.")

    rets = df["ret"].dropna().astype(float)

    if len(rets) == 0:
        print("No trades.")
        return

    # Basic stats
    median_ret = rets.median()
    pct_gt_10 = (rets > 0.10).mean() * 100
    pct_lt_m10 = (rets < -0.10).mean() * 100

    # Top 5 concentration (by absolute profit contribution)
    # Assume equal capital per trade
    profits = rets.copy()
    total_profit = profits.sum()

    if total_profit == 0:
        top5_pct = 0.0
    else:
        top5 = profits.sort_values(ascending=False).head(5)
        top5_pct = top5.sum() / total_profit * 100

    print("Trades:", len(rets))
    print("Median return:", round(median_ret * 100, 2), "%")
    print("% trades > +10%:", round(pct_gt_10, 2), "%")
    print("% trades < -10%:", round(pct_lt_m10, 2), "%")
    print("Top 5 winners contribution:", round(top5_pct, 2), "%")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m pp_backtest.ledger_concentration <ledger_path>")
        sys.exit(1)
    analyze_ledger(sys.argv[1])
