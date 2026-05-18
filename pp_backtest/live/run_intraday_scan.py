#!/usr/bin/env python3
"""CLI wrapper for intraday preview scan."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.trading.intraday.intraday_scan import run_intraday_scan


def main() -> int:
    p = argparse.ArgumentParser(description="Intraday A3/S3 preview scan (no live orders)")
    p.add_argument("--mode", choices=["pre-lunch", "pre-atc", "ad-hoc"], default="ad-hoc")
    p.add_argument("--symbols", default="", help="Comma-separated tickers")
    p.add_argument("--volume-projection", default=None, choices=["session_time", "historical_curve", "no_projection"])
    args = p.parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    df, meta = run_intraday_scan(symbols=syms, mode=args.mode, volume_projection=args.volume_projection)
    print(f"status={meta.get('status')} rows={len(df)} mode={args.mode}")
    return 0 if meta.get("status") in ("OK",) or len(df) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
