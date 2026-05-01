"""
Single entrypoint: fetch latest inputs (global + SBV), weekly report, normalize, HTML.

Delegates to scripts/run_weekly_full_fetch.py — see docs/WEEKLY_FULL_FETCH.md.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    script = REPO / "scripts" / "run_weekly_full_fetch.py"
    r = subprocess.run([sys.executable, str(script)], cwd=REPO, timeout=600)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
