"""Decision log and order-intent schema validation."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

REQUIRED_DECISION_FIELDS = [
    "created_at",
    "asof",
    "tool_name",
    "agent_name",
    "agent_client",
    "symbol",
    "side",
    "strategy_id",
    "setup_type",
    "strategy_status",
    "final_decision",
    "source_paths",
    "rule_versions",
]

ORDER_INTENT_FIELDS = ["symbol", "side", "strategy_id", "entry_price", "stop_price", "account_equity"]


def validate_order_intent(raw: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
    errors: List[str] = []
    if not isinstance(raw, dict):
        return False, {}, ["order_intent must be a JSON object"]

    missing = [f for f in ORDER_INTENT_FIELDS if f not in raw or raw[f] in (None, "")]
    if missing:
        errors.extend([f"missing:{m}" for m in missing])

    sym = str(raw.get("symbol", "")).upper().strip()
    side = str(raw.get("side", "")).upper().strip()
    if side not in ("BUY", "SELL"):
        errors.append("invalid:side")

    normalized: Dict[str, Any] = {
        "symbol": sym,
        "side": side,
        "strategy_id": str(raw.get("strategy_id", "UNKNOWN")),
        "setup_type": str(raw.get("setup_type", "unknown")),
        "entry_price": float(raw.get("entry_price", 0) or 0),
        "stop_price": float(raw.get("stop_price", 0) or 0),
        "account_equity": float(raw.get("account_equity", 0) or 0),
        "risk_pct": float(raw.get("risk_pct", 0.01) or 0.01),
        "adv50_vnd": float(raw.get("adv50_vnd", 0) or 0),
        "participation_cap": float(raw.get("participation_cap", 0.05) or 0.05),
        "asof": str(raw.get("asof", "")),
        "metadata": raw.get("metadata") or {},
    }
    if normalized["entry_price"] <= 0:
        errors.append("invalid:entry_price")
    if normalized["side"] == "BUY" and normalized["stop_price"] >= normalized["entry_price"]:
        errors.append("invalid:stop_distance")
    if normalized["account_equity"] <= 0:
        errors.append("invalid:account_equity")

    return len(errors) == 0, normalized, errors


def validate_decision_payload(raw: Dict[str, Any]) -> Tuple[bool, List[str]]:
    missing = [f for f in REQUIRED_DECISION_FIELDS if f not in raw]
    if raw.get("agent_client") not in ("claude_code", "cursor", "manual", "unknown", None):
        missing.append("agent_client")
    return len(missing) == 0, missing
