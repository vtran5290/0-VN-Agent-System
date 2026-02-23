# pp_backtest/kpi_from_ledger.py — Compute trades, PF, hold1_rate, tail5 from pp_trade_ledger.csv
# Usage: python -m pp_backtest.kpi_from_ledger [path_to_ledger.csv]
# Default: pp_backtest/pp_trade_ledger.csv
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else _PP / "pp_trade_ledger.csv"
    path = Path(path)
    if not path.is_absolute():
        path = _REPO / path
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    if df.empty or "ret" not in df.columns:
        print("Ledger empty or missing 'ret' column.")
        sys.exit(1)
    ret = df["ret"].astype(float)
    n = len(ret)
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
    hold_days = df["hold_cal_days"].astype(float) if "hold_cal_days" in df.columns else (
        df["hold_days"].astype(float) if "hold_days" in df.columns else pd.Series(dtype=float)
    )
    hold1 = int((hold_days == 1).sum()) if len(hold_days) else 0
    hold1_rate = hold1 / n if n else np.nan
    tail5 = float(np.nanpercentile(ret, 5))  # 5th percentile of ret
    if "exit_reason" in df.columns:
        sell_v4_exits = int((df["exit_reason"] == "SELL_V4").sum())
        market_dd_exits = int((df["exit_reason"] == "MARKET_DD").sum())
        stock_dd_exits = int((df["exit_reason"] == "STOCK_DD").sum())
        ugly_bar_exits = int((df["exit_reason"] == "UGLY_BAR").sum())
    else:
        sell_v4_exits = market_dd_exits = stock_dd_exits = ugly_bar_exits = 0
    valid_hold = hold_days.dropna()
    avg_hold_days = float(valid_hold.mean()) if len(valid_hold) else np.nan
    median_hold_days = float(valid_hold.median()) if len(valid_hold) else np.nan
    # hold_cal_days = calendar days (entry_date -> exit_date); hold_trading_bars = trading days (bar count)
    if "hold_trading_bars" in df.columns:
        hold_bars = df["hold_trading_bars"].astype(float)
    else:
        hold_bars = df["hold_bars"].astype(float) if "hold_bars" in df.columns else pd.Series(dtype=float)
    valid_bars = hold_bars.dropna()
    median_hold_bars = float(valid_bars.median()) if len(valid_bars) else np.nan
    print(f"trades:      {n}")
    print(f"PF:          {pf:.4f}" if pf == pf and np.isfinite(pf) else "PF:          nan")
    print(f"hold1_rate:  {hold1_rate:.4f}  (hold_days==1 / total = {hold1}/{n})")
    print(f"tail5_loss:  {tail5:.4f}  (5th percentile of ret)")
    print(f"sell_v4_exits: {sell_v4_exits}  (exits by SELL_V4)")
    print(f"market_dd_exits: {market_dd_exits}  stock_dd_exits: {stock_dd_exits}  ugly_bar_exits: {ugly_bar_exits}")
    print(f"avg_hold_days:   {avg_hold_days:.2f}" if np.isfinite(avg_hold_days) else "avg_hold_days:   nan")
    print(f"median_hold_days: {median_hold_days:.1f}" if np.isfinite(median_hold_days) else "median_hold_days: nan")
    print(f"median_hold_bars: {median_hold_bars:.1f}" if np.isfinite(median_hold_bars) else "median_hold_bars: nan")
    print("# hold_cal_days = calendar days (entry->exit); hold_trading_bars = trading days. min_hold_bars from [run] config.")


if __name__ == "__main__":
    main()
