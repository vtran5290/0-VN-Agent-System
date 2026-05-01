"""Compute regime engine state from existing state files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import REPO
from scripts.utils.io import read_json

REGIME_STATE = REPO / "data" / "state" / "regime_state.json"


def compute_regime_engine(asof: str | None = None) -> Dict[str, Any]:
    """Build regime_engine section from regime_state.json."""
    state = read_json(REGIME_STATE)
    return {
        "current_regime": state.get("regime"),
        "suggested_regime": state.get("suggested_regime"),
        "mismatch": False,
        "inputs": {
            "global_liquidity": state.get("global_liquidity"),
            "vn_liquidity": state.get("vn_liquidity"),
        },
        "reasoning": [],
    }
