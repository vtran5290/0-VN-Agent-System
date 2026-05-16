#!/usr/bin/env python3
"""Chain: propose -> risk-review -> execute -> reconcile -> report."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.trading.cli import main

if __name__ == "__main__":
    asof = sys.argv[1] if len(sys.argv) > 1 else None
    args = ["run-daily"]
    if asof:
        args.extend(["--asof", asof])
    raise SystemExit(main(args))
