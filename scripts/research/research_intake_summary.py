"""
Thin wrapper: python scripts/research/research_intake_summary.py

Delegates to src.research.intake.summarize_index (no trading / broker imports).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.research.intake.summarize_index import main

if __name__ == "__main__":
    raise SystemExit(main())
