#!/usr/bin/env python
"""
Fetch Vietnam market snapshot (VNINDEX, VN30 levels) via FireAntClient.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.fireant_client import get_client

logger = logging.getLogger(__name__)


def fetch_vietnam_market(asof: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns:
        {
          "market": {
            "vnindex_level": float | None,
            "vn30_level":    float | None,
          }
        }
    """
    try:
        snapshot = get_client().get_macro_snapshot(asof=asof)
        mkt = snapshot.get("market", {})
        return {
            "market": {
                "vnindex_level": mkt.get("vnindex_level"),
                "vn30_level": mkt.get("vn30_level"),
            }
        }
    except Exception as exc:
        logger.error("fetch_vietnam_market: %s", exc)
        return {"market": {"vnindex_level": None, "vn30_level": None}}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(fetch_vietnam_market(), indent=2, ensure_ascii=False))

