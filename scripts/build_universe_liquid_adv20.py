#!/usr/bin/env python
"""
Build a liquid universe filtered by ADV20, using FireAntClient.

Usage:
    python scripts/build_universe_liquid_adv20.py \\
        --start 2025-01-01 \\
        --end   2026-12-31 \\
        --adv20-min 5000000000 \\
        --exchanges HOSE HNX UPCOM \\
        --out config/universe_liquid_adv20_5b.txt
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.fireant_client import get_client


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build liquid VN universe by ADV20 via FireAnt"
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD) for ADV20 window",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD) for ADV20 window",
    )
    parser.add_argument(
        "--adv20-min",
        type=float,
        default=5_000_000_000.0,
        help="Minimum ADV20 (VND) to include symbol (default: 5e9)",
    )
    parser.add_argument(
        "--out",
        default="config/universe_liquid_adv20_5b.txt",
        help="Output universe file (one symbol per line)",
    )
    parser.add_argument(
        "--exchanges",
        nargs="+",
        default=["HOSE", "HNX", "UPCOM"],
        help="Exchanges to include (e.g. HOSE HNX UPCOM)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Delay between requests in seconds (default 0.15)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = get_client()

    logger.info(
        "Building universe: exchanges=%s start=%s end=%s adv20_min=%.0f",
        args.exchanges,
        args.start,
        args.end,
        args.adv20_min,
    )

    df = client.build_universe(
        exchanges=args.exchanges,
        start=args.start,
        end=args.end,
        adv20_min=args.adv20_min,
        delay=args.delay,
    )

    if df.empty:
        logger.warning(
            "No symbols met ADV20 >= %.0f; output file will be empty.", args.adv20_min
        )

    repo_root = Path(__file__).resolve().parent.parent
    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    symbols = df["symbol"].tolist() if not df.empty else []
    out_path.write_text("\n".join(symbols) + ("\n" if symbols else ""), encoding="utf-8")

    logger.info("Universe size=%d  wrote: %s", len(symbols), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


