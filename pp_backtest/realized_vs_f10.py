"""
realized_vs_f10.py
==================
Pre-registered: f10 vs realized return gap + tail analysis.
DO NOT add DoF after seeing results.

Purpose:
    Test whether exit timing / fee / tail explain PF < 1 given EDGE_EXISTS (median f10 > 0).

Metrics:
    - pct_realized_lt_f10: % trades where realized < f10 ("exit cut edge")
    - median_gap: f10 - realized (edge left on table)
    - tail5_realized, tail5_f10: 5th percentile
    - fee_adj_f10_median: (f10 - fee_round_trip).median()

Decision rules (pre-registered):
    - pct_realized_lt_f10 > 60% -> EXIT_TIMING (exit cutting edge)
    - median_gap < fee_round_trip -> FEE_EROSION (edge too thin)
    - tail5_realized > tail5_f10 -> EXIT_SAVING_TAIL (exit limited losses)

Usage:
    python -m pp_backtest.realized_vs_f10 --ledger pp_backtest/pp_trade_ledger_baseline.csv --use-fetch [--fee-bps 30]
"""

import argparse
import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import numpy as np

# Reuse OHLCV + f10 logic from forward_return_analysis
from pp_backtest.forward_return_analysis import (
    load_ohlcv_from_dir,
    fetch_ohlcv_for_symbol,
    compute_forward_returns,
)
FORWARD_BARS = [10]  # only f10
BAR_BUFFER_DAYS = 45
DEFAULT_LEDGER = "pp_backtest/pp_trade_ledger_baseline.csv"
RET_COL_CANDIDATES = ("ret", "return", "pnl_pct")


def detect_ret_column(df: pd.DataFrame) -> str:
    for c in RET_COL_CANDIDATES:
        if c in df.columns:
            return c
    raise ValueError(f"Ledger must have one of {RET_COL_CANDIDATES}. Columns: {list(df.columns)}")


def main():
    parser = argparse.ArgumentParser(description="f10 vs realized gap + tail (pre-registered)")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help="Trade ledger CSV")
    parser.add_argument("--ohlcv-dir", default=None, help="Local OHLCV CSVs; else use --use-fetch")
    parser.add_argument("--use-fetch", action="store_true", help="Fetch OHLCV from API (same as backtest)")
    parser.add_argument("--vnstock", action="store_true", help="Use vnstock when --use-fetch")
    parser.add_argument("--fee-bps", type=float, default=30, help="Round-trip fee in bps (default 30 = 0.30% total)")
    args = parser.parse_args()

    use_fetch = args.use_fetch or (args.ohlcv_dir is None)
    if not use_fetch and not args.ohlcv_dir:
        args.ohlcv_dir = "data/ohlcv"

    fee_round_trip = (args.fee_bps * 2) / 10000.0  # entry + exit

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"[ERROR] Ledger not found: {ledger_path}")
        sys.exit(1)

    ledger = pd.read_csv(ledger_path, parse_dates=["entry_date"])
    ret_col = detect_ret_column(ledger)
    ledger["realized"] = ledger[ret_col].astype(float)

    print(f"[info] Ledger: {len(ledger)} trades, return column: {ret_col}")
    print(f"[info] OHLCV: {'fetch' if use_fetch else args.ohlcv_dir}, fee_round_trip={fee_round_trip:.4f}")
    print()

    symbol_ranges = ledger.groupby("symbol")["entry_date"].agg(["min", "max"]) if use_fetch else None
    ohlcv_cache = {}
    rows = []

    for _, row in ledger.iterrows():
        symbol = row["symbol"]
        entry_date = row["entry_date"]
        realized = row["realized"]

        if symbol not in ohlcv_cache:
            if use_fetch and symbol_ranges is not None:
                start = symbol_ranges.loc[symbol, "min"]
                end = symbol_ranges.loc[symbol, "max"] + timedelta(days=BAR_BUFFER_DAYS)
                ohlcv_cache[symbol] = fetch_ohlcv_for_symbol(symbol, start, end, use_vnstock=args.vnstock)
            else:
                ohlcv_cache[symbol] = load_ohlcv_from_dir(symbol, args.ohlcv_dir or "")

        ohlcv = ohlcv_cache[symbol]
        if ohlcv is None:
            continue

        fwd = compute_forward_returns(entry_date, symbol, ohlcv, FORWARD_BARS)
        if fwd is None or fwd.get("f10") is None:
            continue

        rows.append({"symbol": symbol, "entry_date": entry_date, "realized": realized, "f10": fwd["f10"]})

    if not rows:
        print("[ERROR] No (realized, f10) pairs. Check OHLCV.")
        sys.exit(1)

    df = pd.DataFrame(rows)
    n = len(df)

    # Metrics (pre-registered)
    gap = df["f10"] - df["realized"]
    pct_realized_lt_f10 = (df["realized"] < df["f10"]).mean()
    median_gap = gap.median()
    tail5_realized = df["realized"].quantile(0.05)
    tail5_f10 = df["f10"].quantile(0.05)
    fee_adj_f10_median = (df["f10"] - fee_round_trip).median()

    # Diagnoses (pre-registered)
    diagnoses = []
    if pct_realized_lt_f10 > 0.60:
        diagnoses.append("EXIT_TIMING")
    if median_gap < fee_round_trip:
        diagnoses.append("FEE_EROSION")
    if tail5_realized > tail5_f10:
        diagnoses.append("EXIT_SAVING_TAIL")

    # Output
    print("=" * 60)
    print("F10 vs REALIZED GAP (pre-registered)")
    print("=" * 60)
    print(f"  n:                    {n}")
    print(f"  pct_realized_lt_f10:  {pct_realized_lt_f10:.1%}")
    print(f"  median_gap:           {median_gap:+.2%}")
    print(f"  fee_adj_f10_median:   {fee_adj_f10_median:+.2%}")
    print(f"  tail5_realized:       {tail5_realized:+.2%}")
    print(f"  tail5_f10:            {tail5_f10:+.2%}")
    print(f"  diagnoses:            {diagnoses}")
    print()
    print("Paste format:")
    print(f"  pct_realized_lt_f10: {pct_realized_lt_f10:.0%}")
    print(f"  median_gap:          {median_gap:+.2%}")
    print(f"  fee_adj_f10_median:  {fee_adj_f10_median:+.2%}")
    print(f"  tail5_realized:      {tail5_realized:+.2%}")
    print(f"  tail5_f10:           {tail5_f10:+.2%}")
    print(f"  diagnoses:           {diagnoses}")


if __name__ == "__main__":
    main()
