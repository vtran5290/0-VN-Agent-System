from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.data.fireant_client import get_client


REPO = Path(__file__).resolve().parents[2]
DEBUG_PATH = REPO / "data" / "decision" / "market_snapshot_debug.json"


def build_auto_inputs(asof: Optional[str] = None) -> Dict[str, Any]:
    """
    Backward-compatible wrapper returning the same schema as before,
    now powered by FireAntClient.get_macro_snapshot().

    Also writes a temporary debug artifact (market_snapshot_debug.json)
    so we can audit the exact FireAnt payload and mapping used.
    """
    client = get_client()
    snapshot = client.get_macro_snapshot(asof=asof)

    try:
        market = snapshot.get("market", {}) if isinstance(snapshot, dict) else {}
        debug_payload: Dict[str, Any] = {
            "requested_asof": asof,
            "asof_date_used": snapshot.get("asof_date") if isinstance(snapshot, dict) else None,
            "mapped_vnindex_level": market.get("vnindex_level"),
            "mapped_vn30_level": market.get("vn30_level"),
            # Cache is implemented at the OHLCV level; we conservatively mark this
            # field as False here (caller can still inspect raw_source.warnings).
            "cache_hit": False,
            "raw_source": snapshot,
        }
        DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEBUG_PATH.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Debug write should never break the main pipeline.
        pass

    return snapshot

