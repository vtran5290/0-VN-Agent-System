"""Repo root on sys.path.

When collecting both `tests/` and `minervini_backtest/tests/`, use `--import-mode=importlib`
(see `pytest.ini`) so `import scripts` resolves to repo `scripts/`, not `minervini_backtest/scripts/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
