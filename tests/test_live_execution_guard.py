"""Live execution guard tests — confirm DNSE remains unreachable via MCP."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.mcp_server import adapters as A
from src.mcp_server import server as S
from src.mcp_server.permissions import MCPPermissions, load_permissions

REPO = Path(__file__).resolve().parents[1]


def test_default_permissions_live_off():
    p = load_permissions()
    assert p.live_trading_enabled is False
    assert p.broker_write_enabled is False
    assert p.live_execution_allowed() is False
    assert p.max_permission in {"PAPER_ONLY", "READ_ONLY"}


def test_permissions_file_on_disk_live_off():
    raw = json.loads((REPO / "config/mcp/permissions.default.json").read_text(encoding="utf-8"))
    assert raw["live_trading_enabled"] is False
    assert raw["broker_write_enabled"] is False
    assert raw["max_permission"] != "LIVE_ENABLED"


def test_live_execution_allowed_requires_all_three():
    """live_execution_allowed must require all gates simultaneously."""
    assert MCPPermissions(True, True, True, True, "LIVE_ENABLED").live_execution_allowed() is True
    assert MCPPermissions(True, True, True, True, "PAPER_ONLY").live_execution_allowed() is False
    assert MCPPermissions(True, False, True, True, "LIVE_ENABLED").live_execution_allowed() is False
    assert MCPPermissions(False, True, True, True, "LIVE_ENABLED").live_execution_allowed() is False


def test_simulate_paper_order_blocks_live(monkeypatch):
    """Even if perms claim live, MCP simulate_paper_order must refuse."""
    fake = MCPPermissions(
        live_trading_enabled=True,
        broker_write_enabled=True,
        paper_trading_enabled=True,
        human_approval_required=True,
        max_permission="LIVE_ENABLED",
    )
    import src.mcp_server.permissions as perms_mod

    monkeypatch.setattr(perms_mod, "load_permissions", lambda *a, **k: fake)

    raw = S.tool_simulate_paper_order(
        json.dumps(
            {
                "symbol": "FPT",
                "side": "BUY",
                "strategy_id": "A3_DP",
                "entry_price": 100000,
                "stop_price": 90000,
                "account_equity": 1e9,
                "adv50_vnd": 5e9,
            }
        )
    )
    env = json.loads(raw)
    assert env["ok"] is False
    assert env["error_code"] == "LIVE_EXECUTION_BLOCKED"


def test_dnse_place_order_not_invoked_by_any_mcp_tool():
    """No MCP tool path should call DNSEBroker.place_order, ever."""
    import src.trading.brokers.dnse as dnse

    original = dnse.DNSEBroker.place_order
    calls = []

    def _spy(*a, **k):
        calls.append(a)
        return original(*a, **k)

    dnse.DNSEBroker.place_order = _spy
    try:
        S.tool_get_system_status()
        S.tool_get_data_health_snapshot()
        S.tool_evaluate_kill_switch()
        S.tool_enforce_portfolio_constraints(ticker="FPT", proposed_size_pct=1.0)
        S.tool_validate_order_intent(
            json.dumps(
                {
                    "symbol": "FPT",
                    "side": "BUY",
                    "strategy_id": "A3_DP",
                    "entry_price": 100000,
                    "stop_price": 90000,
                    "account_equity": 1e9,
                    "adv50_vnd": 5e9,
                }
            )
        )
    finally:
        dnse.DNSEBroker.place_order = original
    assert calls == [], f"DNSE.place_order was called by MCP: {calls}"


def test_mcp_outputs_remain_compact():
    """Spot-check: standard tool envelopes stay under the JSON char cap."""
    from src.mcp_server.config import MAX_JSON_CHARS

    raw = S.tool_get_system_status()
    assert len(raw) <= MAX_JSON_CHARS
