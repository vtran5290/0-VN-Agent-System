from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

_MA_LEVELS_PATH = Path("data/state/ma_levels_daily.json")


def _load_ma_breach_map() -> Dict[str, Dict]:
    """Load primary MA breach data; return {} if file absent."""
    if not _MA_LEVELS_PATH.exists():
        return {}
    try:
        data = json.loads(_MA_LEVELS_PATH.read_text(encoding="utf-8"))
        return {r["symbol"]: r for r in data.get("records", [])}
    except Exception:
        return {}


def evaluate_row(r: Dict[str, Any], ma_breach_map: Dict[str, Dict] | None = None) -> Dict[str, Any]:
    tier = r.get("tier")
    day2 = r.get("day2_trigger", False)
    day1 = r.get("day1_trigger", False)
    below = r.get("close_below_ma", False)

    # Primary MA breach from E&MA Research / DNA line
    ma_rec = (ma_breach_map or {}).get(r.get("ticker", ""), {})
    primary_breach = ma_rec.get("primary_ma_breach", False)
    primary_ma_label = ma_rec.get("ma_label")
    primary_ma_pct   = ma_rec.get("pct_distance")

    action = "HOLD"
    reason = "No violation"

    if day2:
        action = "SELL / EXIT"
        reason = "Day-2 confirmation breach"
    elif day1 or (below and tier in (1, 2, 3)):
        action = "TRIM / TIGHTEN STOP"
        reason = "Day-1 close below key MA"
    elif primary_breach:
        action = "TRIM / TIGHTEN STOP"
        pct_str = f"{primary_ma_pct:+.1f}%" if primary_ma_pct is not None else "?"
        reason = f"Primary MA breach ({primary_ma_label} {pct_str})"

    row_out = {**r, "action": action, "reason": reason}
    if primary_ma_label:
        row_out["primary_ma_label"]  = primary_ma_label
        row_out["primary_ma_pct"]    = primary_ma_pct
        row_out["primary_ma_breach"] = primary_breach
    return row_out


def evaluate(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("tickers", [])
    ma_breach_map = _load_ma_breach_map()
    return [evaluate_row(r, ma_breach_map) for r in rows]
