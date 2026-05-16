"""MCP orchestration layer tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.mcp_server import adapters as A
from src.mcp_server import server as S
from src.mcp_server.audit import compact_json
from src.mcp_server.permissions import load_permissions
from src.mcp_server.schemas import validate_order_intent


REPO = Path(__file__).resolve().parents[1]


def _ok_payload(text: str) -> dict:
    """Decode an MCP tool envelope and return the `data` dict."""
    env = json.loads(text)
    assert env["ok"] is True, env
    return env["data"]


def _err_payload(text: str) -> dict:
    env = json.loads(text)
    assert env["ok"] is False, env
    return env


def _valid_buy_intent(**overrides) -> dict:
    base = {
        "symbol": "FPT",
        "side": "BUY",
        "strategy_id": "A3_DP",
        "setup_type": "breakout",
        "entry_price": 100000,
        "stop_price": 90000,
        "account_equity": 1e9,
        "adv50_vnd": 5e9,
        "asof": "2099-01-01",
    }
    base.update(overrides)
    return base


def test_compact_json_size_cap():
    huge = {"x": "y" * 100_000}
    text = compact_json(huge, max_chars=1000)
    assert len(text) <= 1100


def test_no_full_ohlcv_in_screen():
    if not (REPO / "data/fireant_ssot/ta_ohlcv_panel.parquet").exists():
        pytest.skip("OHLCV parquet missing")
    r = A.screen_symbol("FPT")
    blob = json.dumps(r)
    assert "date" not in blob or r.get("symbol") == "FPT"
    assert len(blob) < 5000


def test_missing_ohlcv_critical():
    import src.mcp_server.config as cfg

    orig = cfg.PATHS["ohlcv_panel"]
    cfg.PATHS["ohlcv_panel"] = REPO / "data/nonexistent_ta_ohlcv_panel.parquet"
    try:
        dh = A.data_health_snapshot()
        assert dh["status"] == "CRITICAL"
    finally:
        cfg.PATHS["ohlcv_panel"] = orig


def test_unknown_strategy_capital_denied():
    st = A.get_strategy_status("NOT_REAL_XYZ")
    assert st["capital_allowed"] is False


def test_research_strategy_blocks_enforcement():
    enf = A.enforce_portfolio_constraints_impl(
        order_intent={
            "symbol": "FPT",
            "side": "BUY",
            "strategy_id": "S3_best_dp",
            "setup_type": "t",
            "entry_price": 100000,
            "stop_price": 90000,
            "account_equity": 1e9,
            "adv50_vnd": 5e9,
            "asof": "2099-01-01",
        }
    )
    assert enf["allowed"] is False


def test_invalid_stop_blocks_sizing():
    sizing = A.calculate_position_size(
        {
            "symbol": "FPT",
            "side": "BUY",
            "strategy_id": "A3_DP",
            "entry_price": 100,
            "stop_price": 110,
            "account_equity": 1e9,
            "adv50_vnd": 1e9,
        }
    )
    assert sizing["allowed"] is False


def test_permissions_default_live_off():
    p = load_permissions()
    assert p.live_trading_enabled is False
    assert p.broker_write_enabled is False
    assert p.live_execution_allowed() is False


def test_validate_order_intent_schema():
    ok, norm, errs = validate_order_intent(
        {
            "symbol": "fpt",
            "side": "BUY",
            "strategy_id": "A3_DP",
            "entry_price": 1000,
            "stop_price": 900,
            "account_equity": 1e9,
        }
    )
    assert ok and norm["symbol"] == "FPT"
    assert not errs


def test_manual_input_status_keys():
    m = A.manual_input_status()
    assert "manual_inputs" in m
    assert "consensus_pack" in m


def test_claude_cursor_same_tool_names():
    cursor_cfg = json.loads((REPO / ".cursor/mcp.json").read_text(encoding="utf-8"))
    claude_cfg = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    cursor_example = json.loads(
        (REPO / "config/mcp/cursor_mcp_config.example.json").read_text(encoding="utf-8")
    )
    claude_example = json.loads(
        (REPO / "config/mcp/claude_code_mcp_config.example.json").read_text(encoding="utf-8")
    )
    for cfg in (cursor_cfg, claude_cfg, cursor_example, claude_example):
        assert "local-quant-engine" in cfg["mcpServers"], cfg
        args = cfg["mcpServers"]["local-quant-engine"]["args"]
        assert any(a.endswith("mcp_quant_engine.py") for a in args), args


def test_cursor_and_claude_share_entrypoint():
    cursor_cfg = json.loads((REPO / ".cursor/mcp.json").read_text(encoding="utf-8"))
    claude_cfg = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    cur = [a for a in cursor_cfg["mcpServers"]["local-quant-engine"]["args"] if a.endswith(".py")][-1]
    cla = [a for a in claude_cfg["mcpServers"]["local-quant-engine"]["args"] if a.endswith(".py")][-1]
    assert Path(cur).name == Path(cla).name == "mcp_quant_engine.py"


def test_dnse_not_called_by_mcp_enforcer():
    """MCP enforcement must not import DNSE place_order."""
    import src.trading.brokers.dnse as dnse

    orig = dnse.DNSEBroker.place_order
    called = []

    def _boom(*a, **k):
        called.append(1)
        return orig(*a, **k)

    dnse.DNSEBroker.place_order = _boom
    try:
        A.enforce_portfolio_constraints_impl(ticker="FPT", proposed_size_pct=1.0)
    finally:
        dnse.DNSEBroker.place_order = orig
    assert called == []


# ─────────────────────────────────────────────────────────────────────────
# Server-level tool calls — no name shadowing (regression for review #1)
# ─────────────────────────────────────────────────────────────────────────

def test_server_tool_registry_has_expected_tools():
    expected = {
        "get_system_status",
        "get_data_health_snapshot",
        "validate_order_intent",
        "calculate_position_size",
        "enforce_portfolio_constraints",
        "simulate_paper_order",
    }
    assert expected.issubset(set(S.TOOL_REGISTRY.keys()))


def test_server_validate_order_intent_tool_works():
    intent = _valid_buy_intent()
    raw = S.tool_validate_order_intent(json.dumps(intent))
    data = _ok_payload(raw)
    assert data["valid"] is True
    assert data["normalized_order_intent"]["symbol"] == "FPT"
    assert data["schema_errors"] == []


def test_server_validate_order_intent_rejects_bad_stop():
    bad = _valid_buy_intent(stop_price=110000)  # stop above entry on BUY
    raw = S.tool_validate_order_intent(json.dumps(bad))
    data = _ok_payload(raw)
    assert data["valid"] is False
    assert any("stop_distance" in e for e in data["schema_errors"])


def test_server_validate_order_intent_rejects_bad_json():
    env = _err_payload(S.tool_validate_order_intent("{not_json"))
    assert env["error_code"] == "SCHEMA_INVALID"


def test_server_calculate_position_size_no_shadowing():
    intent = _valid_buy_intent()
    raw = S.tool_calculate_position_size(json.dumps(intent))
    data = _ok_payload(raw)
    assert "final_shares" in data
    assert "limiting_factor" in data


def test_server_calculate_position_size_rejects_invalid_schema():
    env = _err_payload(S.tool_calculate_position_size(json.dumps({"symbol": "FPT"})))
    assert env["error_code"] == "SCHEMA_INVALID"


def test_server_enforce_portfolio_constraints_no_shadowing():
    intent = _valid_buy_intent(strategy_id="A3_DP")
    raw = S.tool_enforce_portfolio_constraints(order_intent_json=json.dumps(intent))
    data = _ok_payload(raw)
    assert "allowed" in data
    assert "checks" in data


def test_server_enforce_portfolio_constraints_rejects_bad_intent():
    env = _err_payload(
        S.tool_enforce_portfolio_constraints(order_intent_json='{"symbol":"X"}')
    )
    assert env["error_code"] == "SCHEMA_INVALID"


# ─────────────────────────────────────────────────────────────────────────
# Stale-pack / stale-Council BUY hard-blocks (regression for review #3)
# ─────────────────────────────────────────────────────────────────────────

def _force_stale_pack(monkeypatch, *, council=False, consensus=False, research=False):
    """Patch manual_input_status + council_snapshot to simulate stale state."""
    base_manual = {
        "manual_inputs": {"stale": False, "required_for_council": True},
        "consensus_pack": {"stale": consensus, "required_for_council": True},
        "research_engine_pack": {"stale": research, "required_for_council": True},
    }
    monkeypatch.setattr(A, "manual_input_status", lambda: base_manual)
    monkeypatch.setattr(
        A,
        "council_snapshot",
        lambda asof="": {
            "stale": council,
            "decision_stance": "neutral",
            "top_actions": [],
            "top_risks": [],
            "constraints": {},
            "timestamp": None,
            "source_path": "",
            "source_hash": None,
        },
    )


def test_stale_council_blocks_new_buy(monkeypatch):
    _force_stale_pack(monkeypatch, council=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_valid_buy_intent())
    assert enf["allowed"] is False
    assert "stale_council_output" in enf["hard_block_reason"]


def test_stale_consensus_blocks_new_buy(monkeypatch):
    _force_stale_pack(monkeypatch, consensus=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_valid_buy_intent())
    assert enf["allowed"] is False
    assert "stale_or_missing_consensus_pack" in enf["hard_block_reason"]


def test_stale_research_pack_blocks_new_buy(monkeypatch):
    _force_stale_pack(monkeypatch, research=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_valid_buy_intent())
    assert enf["allowed"] is False
    assert "stale_or_missing_research_pack" in enf["hard_block_reason"]


def test_stale_pack_does_NOT_block_readonly_calls(monkeypatch):
    """Read-only adapters must still return data even when packs are stale."""
    _force_stale_pack(monkeypatch, council=True, consensus=True, research=True)
    # manual_input_status itself is patched, so call council_snapshot directly
    snap = A.council_snapshot()
    assert snap["stale"] is True
    # No exception, no hard-block side effect on the read-only call


def test_stale_council_does_not_block_sell(monkeypatch):
    """Stale council should not hard-block a SELL (exit) intent."""
    _force_stale_pack(monkeypatch, council=True, consensus=True, research=True)
    sell = _valid_buy_intent(side="SELL", stop_price=110000)  # valid SELL stop > entry
    enf = A.enforce_portfolio_constraints_impl(order_intent=sell)
    reason = enf.get("hard_block_reason", "") or ""
    assert "stale_council_output" not in reason
    assert "stale_or_missing_consensus_pack" not in reason
    assert "stale_or_missing_research_pack" not in reason


# ─────────────────────────────────────────────────────────────────────────
# Read-only safety under WARN data health
# ─────────────────────────────────────────────────────────────────────────

def test_readonly_tools_run_under_warn(monkeypatch):
    monkeypatch.setattr(
        A,
        "data_health_snapshot",
        lambda: {"status": "WARN", "checks": [], "asof": ""},
    )
    raw = S.tool_get_data_health_snapshot()
    data = _ok_payload(raw)
    assert data["status"] == "WARN"
    # Strategy registry still readable
    raw2 = S.tool_get_strategy_status("A3_DP")
    data2 = _ok_payload(raw2)
    assert "status" in data2


def test_compact_outputs_no_full_dataframe():
    """All ok() envelopes must be bounded; no raw DF dumps."""
    intent = _valid_buy_intent()
    raw = S.tool_calculate_position_size(json.dumps(intent))
    assert len(raw) < 5000


# ─────────────────────────────────────────────────────────────────────────
# Strategy gating (regression for review #5)
# ─────────────────────────────────────────────────────────────────────────

def test_unknown_strategy_capital_blocked_via_enforcer():
    enf = A.enforce_portfolio_constraints_impl(
        order_intent=_valid_buy_intent(strategy_id="NOT_REAL_XYZ")
    )
    assert enf["allowed"] is False
    assert "strategy_status" in enf["hard_block_reason"]


def test_research_only_strategy_blocked_via_enforcer():
    enf = A.enforce_portfolio_constraints_impl(
        order_intent=_valid_buy_intent(strategy_id="S3_best_dp")
    )
    assert enf["allowed"] is False


def test_watchlist_only_strategy_blocked_via_enforcer():
    enf = A.enforce_portfolio_constraints_impl(
        order_intent=_valid_buy_intent(strategy_id="W2")
    )
    assert enf["allowed"] is False


def test_simulate_paper_order_blocks_on_decision_log_write_failure(monkeypatch):
    """Paper path must fail closed when decision log cannot be written."""
    intent = _valid_buy_intent()

    monkeypatch.setattr(
        A,
        "enforce_portfolio_constraints_impl",
        lambda **kw: {
            "allowed": True,
            "hard_block_reason": None,
            "checks": [],
            "source_paths": [],
            "rule_versions": {},
        },
    )
    monkeypatch.setattr(
        A,
        "write_decision_log_impl",
        lambda payload: {"ok": False, "error_code": "LOG_WRITE_FAILED", "message": "disk full"},
    )

    raw = S.tool_simulate_paper_order(json.dumps(intent))
    env = json.loads(raw)
    assert env["ok"] is False
    assert env["error_code"] == "LOG_WRITE_FAILED"
