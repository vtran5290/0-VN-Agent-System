#!/usr/bin/env python3
"""Build VNINDEX Distribution Risk Lens research outputs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.market.distribution_risk_lens.pipeline import run_distribution_risk_lens


def main() -> int:
    ap = argparse.ArgumentParser(description="VNINDEX Distribution Risk Lens (research only)")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--as-of", default="latest", help="YYYY-MM-DD or latest")
    args = ap.parse_args()
    as_of = None if args.as_of == "latest" else args.as_of
    result = run_distribution_risk_lens(start=args.start, as_of=as_of)
    print(f"OK: {result['outputs_dir']} rows={result['n_features']}")
    if result.get("warnings"):
        for w in result["warnings"]:
            print(f"  WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
