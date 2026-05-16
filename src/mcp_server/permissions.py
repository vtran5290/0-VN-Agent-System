"""MCP permission model — hard caps on live execution."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from src.mcp_server.config import PATHS


@dataclass(frozen=True)
class MCPPermissions:
    live_trading_enabled: bool = False
    broker_write_enabled: bool = False
    paper_trading_enabled: bool = True
    human_approval_required: bool = True
    max_permission: str = "PAPER_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "live_trading_enabled": self.live_trading_enabled,
            "broker_write_enabled": self.broker_write_enabled,
            "paper_trading_enabled": self.paper_trading_enabled,
            "human_approval_required": self.human_approval_required,
            "max_permission": self.max_permission,
        }

    def live_execution_allowed(self) -> bool:
        return (
            self.live_trading_enabled
            and self.broker_write_enabled
            and self.max_permission == "LIVE_ENABLED"
        )


def load_permissions(path: Path | None = None) -> MCPPermissions:
    p = path or PATHS["permissions"]
    if not p.exists():
        return MCPPermissions()
    raw = json.loads(p.read_text(encoding="utf-8"))
    return MCPPermissions(
        live_trading_enabled=bool(raw.get("live_trading_enabled", False)),
        broker_write_enabled=bool(raw.get("broker_write_enabled", False)),
        paper_trading_enabled=bool(raw.get("paper_trading_enabled", True)),
        human_approval_required=bool(raw.get("human_approval_required", True)),
        max_permission=str(raw.get("max_permission", "PAPER_ONLY")),
    )
