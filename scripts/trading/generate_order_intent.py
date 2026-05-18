#!/usr/bin/env python3
"""CLI wrapper for order-intent dry run. This command does not send broker orders."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.trading.order_intent_dry_run import main

if __name__ == "__main__":
    raise SystemExit(main())
