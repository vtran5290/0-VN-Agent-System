"""FastMCP server — registers all orchestration tools.

Tool bodies are defined at module scope (prefixed `tool_*`) so they are
unit-testable without spinning up the FastMCP runtime, and the import
`validate_order_intent_schema` from `schemas` is aliased to avoid being
shadowed by the MCP tool named `validate_order_intent`.
"""
from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from src.mcp_server import adapters as A
from src.mcp_server.audit import err, ok, utc_now_iso
from src.mcp_server.schemas import validate_order_intent as validate_order_intent_schema


# ──────────────────────────────────────────────────────────────────────────
# Read-only / analysis
# ──────────────────────────────────────────────────────────────────────────

def tool_get_system_status() -> str:
    return ok("get_system_status", A.system_status())


def tool_get_data_health_snapshot() -> str:
    return ok("get_data_health_snapshot", A.data_health_snapshot())


def tool_get_strategy_status(strategy_id: str = "") -> str:
    if strategy_id:
        return ok("get_strategy_status", A.get_strategy_status(strategy_id))
    reg = A.strategy_registry()
    items = {k: A.get_strategy_status(k) for k in reg.get("strategies", {})}
    return ok("get_strategy_status", {"strategies": items})


def tool_get_regime_snapshot(asof: str = "") -> str:
    return ok("get_regime_snapshot", A.regime_snapshot(asof))


def tool_get_council_snapshot(asof: str = "") -> str:
    return ok("get_council_snapshot", A.council_snapshot(asof))


def tool_get_allocation_plan(asof: str = "") -> str:
    return ok("get_allocation_plan", A.allocation_plan_snapshot(asof))


def tool_get_portfolio_snapshot(asof: str = "") -> str:
    return ok("get_portfolio_snapshot", A.portfolio_snapshot(asof))


def tool_get_manual_input_status() -> str:
    return ok("get_manual_input_status", A.manual_input_status())


def tool_screen_technical_setups(
    ticker: str = "",
    filters_json: str = "{}",
    asof: str = "",
    setup_type: str = "any",
    max_results: int = 20,
) -> str:
    if ticker:
        return ok("screen_technical_setups", A.screen_symbol(ticker))
    try:
        filt = json.loads(filters_json) if filters_json else {}
    except json.JSONDecodeError as e:
        return err("screen_technical_setups", "SCHEMA_INVALID", str(e))
    universe = filt.get("universe") or []
    if not universe:
        return err("screen_technical_setups", "SCHEMA_INVALID", "ticker or universe required")
    results = [A.screen_symbol(s) for s in universe[:max_results]]
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return ok(
        "screen_technical_setups",
        {"asof": asof, "setup_type": setup_type, "results": results},
    )


def tool_get_signal_evidence(symbol: str, strategy_id: str = "A3_DP", asof: str = "") -> str:
    return ok("get_signal_evidence", A.signal_evidence(symbol, strategy_id, asof))


def tool_evaluate_fundamental_moat(ticker: str) -> str:
    return ok("evaluate_fundamental_moat", A.evaluate_moat(ticker))


def tool_run_isolated_backtest(strategy_name: str, params_json: str) -> str:
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as e:
        return err("run_isolated_backtest", "SCHEMA_INVALID", str(e))
    return ok("run_isolated_backtest", A.run_isolated_backtest_impl(strategy_name, params))


# ──────────────────────────────────────────────────────────────────────────
# Risk / enforcement (uses aliased schema validator — no name shadowing)
# ──────────────────────────────────────────────────────────────────────────

def tool_validate_order_intent(order_intent_json: str) -> str:
    try:
        raw = json.loads(order_intent_json)
    except json.JSONDecodeError as e:
        return err("validate_order_intent", "SCHEMA_INVALID", str(e))
    valid, norm, errors = validate_order_intent_schema(raw)
    return ok(
        "validate_order_intent",
        {
            "valid": valid,
            "normalized_order_intent": norm if valid else None,
            "schema_errors": errors,
        },
    )


def tool_calculate_position_size(order_intent_json: str) -> str:
    try:
        raw = json.loads(order_intent_json)
    except json.JSONDecodeError as e:
        return err("calculate_position_size", "SCHEMA_INVALID", str(e))
    valid, norm, errors = validate_order_intent_schema(raw)
    if not valid:
        return err("calculate_position_size", "SCHEMA_INVALID", ";".join(errors))
    return ok("calculate_position_size", A.calculate_position_size(norm))


def tool_evaluate_kill_switch(asof: str = "") -> str:
    return ok("evaluate_kill_switch", A.evaluate_kill_switch_snapshot(asof))


def tool_enforce_portfolio_constraints(
    ticker: str = "",
    proposed_size_pct: float = 0.0,
    order_intent_json: str = "",
) -> str:
    intent = None
    if order_intent_json:
        try:
            raw = json.loads(order_intent_json)
        except json.JSONDecodeError as e:
            return err("enforce_portfolio_constraints", "SCHEMA_INVALID", str(e))
        valid, norm, errors = validate_order_intent_schema(raw)
        if not valid:
            return err("enforce_portfolio_constraints", "SCHEMA_INVALID", ";".join(errors))
        intent = norm
    return ok(
        "enforce_portfolio_constraints",
        A.enforce_portfolio_constraints_impl(intent, ticker, proposed_size_pct),
    )


def tool_propose_order_intent(symbol: str, strategy_id: str, side: str, asof: str = "") -> str:
    return ok(
        "propose_order_intent",
        A.propose_order_intent_impl(symbol, strategy_id, side, asof),
    )


# ──────────────────────────────────────────────────────────────────────────
# Audit / paper
# ──────────────────────────────────────────────────────────────────────────

def tool_write_decision_log(decision_payload_json: str) -> str:
    try:
        payload = json.loads(decision_payload_json)
    except json.JSONDecodeError as e:
        return err("write_decision_log", "SCHEMA_INVALID", str(e))
    result = A.write_decision_log_impl(payload)
    if not result.get("ok"):
        return err(
            "write_decision_log",
            result.get("error_code", "LOG_WRITE_FAILED"),
            result.get("message", ""),
        )
    return ok("write_decision_log", result)


def tool_get_recent_decision_log(limit: int = 10) -> str:
    return ok("get_recent_decision_log", {"decisions": A.recent_decision_logs(limit)})


def tool_run_council_audit(month: str = "") -> str:
    import subprocess
    import sys

    mode = "monthly" if month else "weekly"
    repo = A.PATHS["ohlcv_panel"].parents[2]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.report.council_secretary", "--mode", mode],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=120,
        )
        returncode = proc.returncode
        stderr_tail = (proc.stderr or "")[-500:]
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        returncode = -1
        stderr_tail = f"subprocess_error:{e}"
    out_path = repo / "data/decision/council_audit_monthly.md"
    return ok(
        "run_council_audit",
        {
            "audit_status": "completed" if returncode == 0 else "failed",
            "returncode": returncode,
            "output_path": str(out_path) if out_path.exists() else None,
            "stderr_tail": stderr_tail,
            "manual_inputs": A.manual_input_status(),
        },
    )


def tool_simulate_paper_order(order_intent_json: str, decision_payload_json: str = "") -> str:
    from src.mcp_server.permissions import load_permissions

    perms = load_permissions()
    if not perms.paper_trading_enabled:
        return err("simulate_paper_order", "PERMISSION_DENIED", "paper_trading_enabled=false")
    if perms.live_execution_allowed():
        return err("simulate_paper_order", "LIVE_EXECUTION_BLOCKED", "live not allowed via MCP")

    try:
        raw = json.loads(order_intent_json)
    except json.JSONDecodeError as e:
        return err("simulate_paper_order", "SCHEMA_INVALID", str(e))
    valid, norm, errors = validate_order_intent_schema(raw)
    if not valid:
        return err("simulate_paper_order", "SCHEMA_INVALID", ";".join(errors))

    enf = A.enforce_portfolio_constraints_impl(order_intent=norm)
    if not enf.get("allowed"):
        return err("simulate_paper_order", "RISK_BLOCKED", enf.get("hard_block_reason", ""))

    if decision_payload_json:
        try:
            payload = json.loads(decision_payload_json)
        except json.JSONDecodeError as e:
            return err("simulate_paper_order", "SCHEMA_INVALID", str(e))
        log_result = A.write_decision_log_impl(payload)
    else:
        log_result = A.write_decision_log_impl(
            {
                "created_at": utc_now_iso(),
                "asof": norm.get("asof", ""),
                "tool_name": "simulate_paper_order",
                "agent_name": "mcp",
                "agent_client": "unknown",
                "symbol": norm["symbol"],
                "side": norm["side"],
                "strategy_id": norm["strategy_id"],
                "setup_type": norm.get("setup_type", ""),
                "strategy_status": A.get_strategy_status(norm["strategy_id"])["status"],
                "final_decision": "paper_simulate",
                "source_paths": enf.get("source_paths", []),
                "rule_versions": enf.get("rule_versions", {}),
            }
        )
    if not log_result.get("ok"):
        return err("simulate_paper_order", "LOG_WRITE_FAILED", "decision log required")

    from src.trading.brokers.paper import PaperBroker
    from src.trading.config import load_trading_config

    tcfg = load_trading_config()
    if not tcfg.paper_execution_allowed():
        return ok(
            "simulate_paper_order",
            {
                "paper_order_id": None,
                "fill_status": "dry_run_only",
                "note": "paper_execution_allowed=false in trading config; logged only",
                "decision_log_path": log_result.get("decision_log_path"),
            },
        )

    broker = PaperBroker(tcfg)
    broker.login()
    qty = int(norm.get("quantity") or A.calculate_position_size(norm).get("final_shares", 0))
    if qty <= 0:
        return err("simulate_paper_order", "RISK_BLOCKED", "zero_quantity")
    order = broker.place_order(
        {
            "symbol": norm["symbol"],
            "side": norm["side"],
            "quantity": qty,
            "price": norm["entry_price"],
        }
    )
    return ok(
        "simulate_paper_order",
        {
            "paper_order_id": order.get("broker_order_id"),
            "fill_status": order.get("state"),
            "updated_paper_state_summary": A.portfolio_snapshot(),
            "decision_log_path": log_result.get("decision_log_path"),
        },
    )


# Tool registry — single source of truth for both the MCP server and tests.
TOOL_REGISTRY: dict[str, Any] = {
    "get_system_status": tool_get_system_status,
    "get_data_health_snapshot": tool_get_data_health_snapshot,
    "get_strategy_status": tool_get_strategy_status,
    "get_regime_snapshot": tool_get_regime_snapshot,
    "get_council_snapshot": tool_get_council_snapshot,
    "get_allocation_plan": tool_get_allocation_plan,
    "get_portfolio_snapshot": tool_get_portfolio_snapshot,
    "get_manual_input_status": tool_get_manual_input_status,
    "screen_technical_setups": tool_screen_technical_setups,
    "get_signal_evidence": tool_get_signal_evidence,
    "evaluate_fundamental_moat": tool_evaluate_fundamental_moat,
    "run_isolated_backtest": tool_run_isolated_backtest,
    "validate_order_intent": tool_validate_order_intent,
    "calculate_position_size": tool_calculate_position_size,
    "evaluate_kill_switch": tool_evaluate_kill_switch,
    "enforce_portfolio_constraints": tool_enforce_portfolio_constraints,
    "propose_order_intent": tool_propose_order_intent,
    "write_decision_log": tool_write_decision_log,
    "get_recent_decision_log": tool_get_recent_decision_log,
    "run_council_audit": tool_run_council_audit,
    "simulate_paper_order": tool_simulate_paper_order,
}


def create_mcp_app() -> FastMCP:
    mcp = FastMCP("local-quant-engine")
    for name, fn in TOOL_REGISTRY.items():
        mcp.tool(name=name)(fn)
    return mcp
