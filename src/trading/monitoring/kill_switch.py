"""Kill switch evaluation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from src.trading.config import LiveTradingConfig
from src.trading.util.timeutil import utc_now_iso


@dataclass
class KillSwitchStatus:
    status: str  # CLEAR | WARN | BLOCK
    reasons: List[str]
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "reasons": self.reasons, "generated_at": self.generated_at}


def evaluate_kill_switch(
    config: LiveTradingConfig,
    data_health: Dict[str, Any],
    reconciliation: Dict[str, Any],
    extra: Dict[str, Any] | None = None,
) -> KillSwitchStatus:
    extra = extra or {}
    reasons: List[str] = []

    if config.block_on_data_health_critical and data_health.get("status") == "CRITICAL_FAIL":
        reasons.append("data_health_critical")

    if config.block_on_reconciliation_failure and reconciliation.get("BLOCK_NEW_ORDERS"):
        reasons.append("reconciliation_failed")

    if config.block_on_adv_unit_failure:
        for c in data_health.get("checks", []):
            if c.get("check") == "adv_unit" and c.get("level") == "CRITICAL":
                reasons.append("adv_unit_failure")

    if config.mode == "live_auto" and not config.enable_live_auto:
        reasons.append("live_auto_disabled")

    if extra.get("duplicate_order"):
        reasons.append("duplicate_order_detected")

    if extra.get("broker_unavailable") and config.mode in ("dry_run", "live_manual"):
        reasons.append("broker_api_unavailable")

    if reasons and config.block_on_kill_switch:
        status = "BLOCK"
    elif reasons:
        status = "WARN"
    else:
        status = "CLEAR"

    return KillSwitchStatus(status=status, reasons=reasons, generated_at=utc_now_iso())


def save_kill_switch(config: LiveTradingConfig, ks: KillSwitchStatus) -> None:
    config.live_dir.mkdir(parents=True, exist_ok=True)
    config.kill_switch_status_path.write_text(json.dumps(ks.to_dict(), indent=2), encoding="utf-8")


def load_kill_switch(config: LiveTradingConfig) -> Dict[str, Any]:
    p = config.kill_switch_status_path
    if not p.exists():
        return {"status": "CLEAR", "reasons": []}
    return json.loads(p.read_text(encoding="utf-8"))
