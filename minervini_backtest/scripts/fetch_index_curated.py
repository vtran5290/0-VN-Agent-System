from __future__ import annotations

"""
fetch_index_curated.py
======================

Fetch index (or any symbol) OHLCV from FireAnt and store it in the
Minervini backtest curated store so that FA Cohort and other scripts
can use it as a benchmark.

CLI example (from repo root):

  python minervini_backtest/scripts/fetch_index_curated.py ^
      --symbol VNINDEX ^
      --start 2012-01-01 ^
      --end 2026-12-31

The script writes a CSV to `minervini_backtest/data/raw/{SYMBOL}.csv`
with columns: date, open, high, low, close, volume.
`run.load_curated_data()` will then pick it up automatically.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    root = Path(__file__).resolve().parent.parent  # .../minervini_backtest
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from run import fetch_fireant  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"[fetch_index_curated] Failed to import run.fetch_fireant: {e}")
        return 1

    parser = argparse.ArgumentParser(description="Fetch index prices into minervini_backtest/data/raw for FA Cohort benchmarks")
    parser.add_argument("--symbol", default="VNINDEX", help="Index or symbol to fetch (default VNINDEX)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--out-dir",
        default=str(root / "data" / "raw"),
        help="Output directory for raw CSV (default: minervini_backtest/data/raw)",
    )
    args = parser.parse_args()

    symbol = args.symbol.upper()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[fetch_index_curated] Fetching {symbol} from FireAnt {args.start} -> {args.end}...")
    try:
        df = fetch_fireant(symbol, args.start, args.end)
    except Exception as e:
        print(f"[fetch_index_curated] Error fetching {symbol}: {e}")
        return 1

    if df is None or df.empty:
        print(f"[fetch_index_curated] No data returned for {symbol}. Nothing written.")
        return 0

    d = df.copy()
    # Ensure schema: date, open, high, low, close, volume; sorted ascending.
    if "date" not in d.columns:
        raise ValueError("Expected 'date' column in fetched data.")
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    cols = ["date", "open", "high", "low", "close", "volume"]
    for c in cols:
        if c not in d.columns:
            raise ValueError(f"Expected column '{c}' in fetched data.")
    d = d[cols]

    out_path = out_dir / f"{symbol}.csv"
    d.to_csv(out_path, index=False)
    print(f"[fetch_index_curated] Wrote {len(d)} rows for {symbol} to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

