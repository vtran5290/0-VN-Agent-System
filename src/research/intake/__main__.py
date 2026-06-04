"""CLI: python -m src.research.intake summarize-index"""

from __future__ import annotations

import sys

from src.research.intake.summarize_index import main


def _dispatch() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] in ("summarize-index", "summarize_index"):
        return main(sys.argv[2:])
    print("Usage: python -m src.research.intake summarize-index [--index PATH]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_dispatch())
