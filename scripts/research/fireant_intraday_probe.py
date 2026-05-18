#!/usr/bin/env python3
"""Safe FireAnt intraday capability probe (3–5 symbols, read-only)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.trading.intraday.data_adapter import detect_intraday_source_capability
from src.trading.intraday.session import now_hcm


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="HPG,VPB,FPT,MWG,SSI")
    args = p.parse_args()
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    out = REPO / "data/research/intraday/source_probe" / f"fireant_probe_{now_hcm().strftime('%Y%m%d_%H%M')}.json"
    result = detect_intraday_source_capability(syms, save_probe_path=out)
    print(f"available={result.get('available')} method={result.get('recommended_method')}")
    print(f"saved: {out}")
    return 0 if result.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
