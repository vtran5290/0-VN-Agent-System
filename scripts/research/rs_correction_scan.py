"""CLI: RS vs VNINDEX from latest correction anchor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.market.rs_correction_lens.pipeline import run_rs_correction_lens


def main() -> int:
    p = argparse.ArgumentParser(description="Run RS correction lens (SSOT JSON + CSV).")
    p.add_argument("--as-of", default=None, help="End date YYYY-MM-DD")
    p.add_argument("--anchor", default=None, help="Force anchor date YYYY-MM-DD")
    args = p.parse_args()
    result = run_rs_correction_lens(as_of=args.as_of, anchor_date=args.anchor)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
