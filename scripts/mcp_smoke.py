"""MCP smoke tests — no stdio server start."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mcp_server import adapters as A
from src.mcp_server.permissions import load_permissions


def main() -> int:
    failures = []
    perms = load_permissions()
    if perms.live_trading_enabled or perms.broker_write_enabled:
        failures.append("permissions: live must be false by default")

    st = A.system_status()
    if "repo" not in st:
        failures.append("system_status missing repo")

    dh = A.data_health_snapshot()
    if dh["status"] not in ("OK", "WARN", "CRITICAL"):
        failures.append("data_health bad status")

    unknown = A.get_strategy_status("NOT_A_REAL_STRATEGY")
    if unknown.get("capital_allowed"):
        failures.append("unknown strategy must not allow capital")

    enf = A.enforce_portfolio_constraints_impl(
        order_intent={
            "symbol": "FPT",
            "side": "BUY",
            "strategy_id": "S3_best_dp",
            "setup_type": "test",
            "entry_price": 100000,
            "stop_price": 90000,
            "account_equity": 1e9,
            "adv50_vnd": 5e9,
            "asof": "2099-01-01",
        }
    )
    if enf.get("allowed"):
        failures.append("research strategy should block")

    print(json.dumps({"failures": failures, "permissions": perms.to_dict()}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
