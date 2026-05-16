"""Paths and thresholds for MCP layer (no strategy logic)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PATHS = {
    "ohlcv_panel": REPO_ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet",
    "vnindex": REPO_ROOT / "data/fireant_ssot/ta_vnindex.parquet",
    "fa_annual": REPO_ROOT / "data/fireant_ssot/fa_annual.parquet",
    "fa_quarterly": REPO_ROOT / "data/fireant_ssot/fa_quarterly.parquet",
    "sector_map": REPO_ROOT / "data/master/sector_map.csv",
    "manual_inputs": REPO_ROOT / "data/raw/manual_inputs.json",
    "consensus_pack": REPO_ROOT / "data/raw/consensus_pack.json",
    "research_pack": REPO_ROOT / "data/raw/research_engine_pack.json",
    "council_output": REPO_ROOT / "data/decision/council_output.json",
    "allocation_plan": REPO_ROOT / "data/decision/allocation_plan.json",
    "regime_state": REPO_ROOT / "data/state/regime_state.json",
    "paper_broker_state": REPO_ROOT / "data/trading/paper_broker_state.json",
    "kill_switch_status": REPO_ROOT / "data/trading/live/kill_switch_status.json",
    "permissions": REPO_ROOT / "config/mcp/permissions.default.json",
    "strategy_registry": REPO_ROOT / "config/mcp/strategy_registry.yaml",
    "live_trading_yaml": REPO_ROOT / "config/live_trading.yaml",
    "trading_yaml": REPO_ROOT / "config/trading.yaml",
    "decision_log_dir": REPO_ROOT / "decision_log",
    "mcp_decision_log_dir": REPO_ROOT / "data/decision/mcp_logs",
}

STALE_DAYS = {
    "ohlcv": 5,
    "vnindex": 5,
    "manual_inputs": 10,
    "consensus_pack": 14,
    "research_pack": 14,
    "paper_broker": 3,
    "council_output": 14,
    "allocation_plan": 14,
}

RULE_VERSION = "mcp_orchestration_v1"
MAX_JSON_CHARS = 48_000
