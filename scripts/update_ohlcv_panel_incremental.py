"""
SSOT panel refresh — HARDENED.

Previously this script appended FireAnt bars to `ta_ohlcv_panel.parquet` without
provenance / adjRatio back-adjustment (root cause of 2026-07-23 NaN-provenance drift).

Policy (DATA_SSOT_REBUILD_SPEC): `scripts/build_fireant_ssot.py` is the ONLY sanctioned
writer of `data/fireant_ssot/ta_ohlcv_panel.parquet`.

Usage:
  python scripts/update_ohlcv_panel_incremental.py --via-builder [--end YYYY-MM-DD]
  python scripts/update_ohlcv_panel_incremental.py --dry-run   # proves no panel write
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PANEL_PATH = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
BUILDER = REPO / "scripts" / "build_fireant_ssot.py"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "SSOT panel refresh gate. Direct incremental append is DISABLED. "
            "Use --via-builder to run build_fireant_ssot.py (sole sanctioned writer)."
        )
    )
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--delay", type=float, default=0.08, help="Passed through to builder")
    ap.add_argument(
        "--via-builder",
        action="store_true",
        help="Run scripts/build_fireant_ssot.py (RE-FETCH_PRIMARY) instead of unsafe append",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Prove this entrypoint does not write the panel; exit 0",
    )
    ap.add_argument("--skip-fa-refresh", action="store_true", default=True)
    args = ap.parse_args()

    if args.dry_run:
        print(
            "DRY RUN — update_ohlcv_panel_incremental will NOT write "
            f"{PANEL_PATH.relative_to(REPO)}. "
            "Unsafe append path is disabled; use --via-builder for a real refresh."
        )
        return 0

    if not args.via_builder:
        print(
            "REFUSED: direct incremental append to ta_ohlcv_panel.parquet is disabled "
            "(caused NaN provenance / manifest drift on 2026-07-23).\n"
            "Use:\n"
            f"  python scripts/build_fireant_ssot.py --end {args.end}\n"
            "or:\n"
            f"  python scripts/update_ohlcv_panel_incremental.py --via-builder --end {args.end}\n",
            file=sys.stderr,
        )
        return 2

    cmd = [
        sys.executable,
        str(BUILDER),
        "--end",
        args.end,
        "--delay",
        str(args.delay),
        "--skip-fa-refresh",
    ]
    print(f"[via-builder] {' '.join(cmd)}")
    return int(subprocess.call(cmd, cwd=str(REPO)))


if __name__ == "__main__":
    raise SystemExit(main())
