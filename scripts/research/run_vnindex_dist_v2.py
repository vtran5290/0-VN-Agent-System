#!/usr/bin/env python3
"""Entry: VNINDEX distribution v2 study."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.research.vnindex_dist_v2.cli import main

if __name__ == "__main__":
    main()
