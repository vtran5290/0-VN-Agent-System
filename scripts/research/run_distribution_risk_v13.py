#!/usr/bin/env python3
"""Build Distribution Risk Lens v1.3 research outputs (context only)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.market.distribution_risk_lens.pipeline import run_distribution_risk_lens
from src.market.distribution_risk_lens.v13_research import run_v13_research


def main() -> int:
    ap = argparse.ArgumentParser(description="Distribution Risk Lens v1.3 research pipeline")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--as-of", default="latest", help="YYYY-MM-DD or latest")
    ap.add_argument("--skip-v12", action="store_true", help="Skip v1.2 refresh")
    args = ap.parse_args()
    as_of = None if args.as_of == "latest" else args.as_of
    if not args.skip_v12:
        run_distribution_risk_lens(start=args.start, as_of=as_of)
    result = run_v13_research(start=args.start, as_of=as_of)
    print(f"OK v1.3: {result['outputs_dir']} rows={result['n_dataset']} liquid_n={result['liquid_n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
