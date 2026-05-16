"""Baseline position snapshots for reconciliation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.brokers.base import BaseBroker
from src.trading.config import TradingConfig
from src.trading.util.timeutil import utc_now_iso


def snapshot_baseline(config: TradingConfig, broker: BaseBroker, asof_date: str) -> Path:
    config.baseline_positions_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "asof_date": asof_date,
        "generated_at": utc_now_iso(),
        "cash_vnd": broker.get_cash_balance().get("cash_vnd", 0),
        "positions": broker.get_positions(),
    }
    path = config.baseline_positions_dir / f"baseline_{asof_date}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_latest_baseline(config: TradingConfig, asof_date: str) -> Optional[Dict[str, Any]]:
    if not config.baseline_positions_dir.exists():
        return None
    candidates = sorted(config.baseline_positions_dir.glob("baseline_*.json"))
    best = None
    for p in candidates:
        d = p.stem.replace("baseline_", "")
        if d <= asof_date[:10]:
            best = json.loads(p.read_text(encoding="utf-8"))
    return best


def baseline_positions_qty(baseline: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not baseline:
        return {}
    out: Dict[str, int] = {}
    for p in baseline.get("positions", []):
        out[p["symbol"]] = int(p.get("quantity", 0))
    return out
