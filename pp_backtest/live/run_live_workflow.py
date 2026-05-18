#!/usr/bin/env python3
"""Thin wrapper — delegates to src.trading.live.workflow."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description="Live trading workflow (canonical: src.trading)")
    parser.add_argument("--mode", required=True, choices=["paper", "dry_run", "live_manual", "live_auto"])
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--scan-path", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--account", default=None, help="Paper account id (default A3_PROD_PAPER_5B)")
    args = parser.parse_args()
    from src.trading.live.workflow import run
    result = run(
        args.mode,
        args.date,
        scan_path=args.scan_path,
        force=args.force,
        account_id=args.account,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
