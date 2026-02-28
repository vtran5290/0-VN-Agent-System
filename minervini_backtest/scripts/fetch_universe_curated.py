from __future__ import annotations

"""
fetch_universe_curated.py
=========================

Fetch OHLCV data for a universe of symbols from FireAnt and store them
in `minervini_backtest/data/raw` so that `run.load_curated_data()`
can use them for backtests and FA cohort studies.

Example usage (from repo root):

  python minervini_backtest/scripts/fetch_universe_curated.py ^
      --symbols-file config/watchlist_80.txt ^
      --start 2012-01-01 ^
      --end 2026-12-31
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd


def _load_symbols(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    out: List[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def main() -> int:
    root = Path(__file__).resolve().parent.parent  # .../minervini_backtest
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from run import fetch_fireant  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"[fetch_universe_curated] Failed to import run.fetch_fireant: {e}")
        return 1

    p = argparse.ArgumentParser(description="Fetch OHLCV for a universe into minervini_backtest/data/raw")
    p.add_argument(
        "--symbols-file",
        required=True,
        help="Path to text file with one symbol per line (e.g. config/watchlist_80.txt)",
    )
    p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    p.add_argument(
        "--out-dir",
        default=str(root / "data" / "raw"),
        help="Output directory for raw CSVs (default: minervini_backtest/data/raw)",
    )
    args = p.parse_args()

    symbols_path = Path(args.symbols_file)
    if not symbols_path.exists():
        print(f"[fetch_universe_curated] Symbols file not found: {symbols_path}")
        return 1

    symbols = _load_symbols(symbols_path)
    if not symbols:
        print(f"[fetch_universe_curated] No symbols found in {symbols_path}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for sym in symbols:
        out_path = out_dir / f"{sym}.csv"
        print(f"[fetch_universe_curated] Fetching {sym} from FireAnt {args.start} -> {args.end}...")
        try:
            df = fetch_fireant(sym, args.start, args.end)
        except Exception as e:
            print(f"[fetch_universe_curated] {sym}: fetch failed: {e}")
            continue

        if df is None or df.empty:
            print(f"[fetch_universe_curated] {sym}: no data returned, skipping.")
            continue

        d = df.copy()
        if "date" not in d.columns:
            print(f"[fetch_universe_curated] {sym}: missing 'date' column, skipping.")
            continue
        d["date"] = pd.to_datetime(d["date"])
        d = d.sort_values("date").drop_duplicates(subset=["date"], keep="last")

        cols = ["date", "open", "high", "low", "close", "volume"]
        missing = [c for c in cols if c not in d.columns]
        if missing:
            print(f"[fetch_universe_curated] {sym}: missing columns {missing}, skipping.")
            continue

        d = d[cols]
        d.to_csv(out_path, index=False)
        print(f"[fetch_universe_curated] Wrote {len(d)} rows for {sym} to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

