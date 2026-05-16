"""Risk enforcer smoke — expect block on research strategy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server import adapters as A

intent = {
    "symbol": "FPT",
    "side": "BUY",
    "strategy_id": "S3_best_dp",
    "setup_type": "smoke",
    "entry_price": 100000,
    "stop_price": 92000,
    "account_equity": 1_000_000_000,
    "adv50_vnd": 5_000_000_000,
    "asof": "2099-01-01",
}
result = A.enforce_portfolio_constraints_impl(order_intent=intent)
print(json.dumps(result, indent=2))
if result.get("allowed"):
    sys.exit(1)
print("OK: research order blocked as expected")
