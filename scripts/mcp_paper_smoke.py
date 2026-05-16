"""Paper flow smoke — enforcement only (no broker write unless config allows)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server import adapters as A
from src.mcp_server.permissions import load_permissions

perms = load_permissions()
if not perms.paper_trading_enabled:
    print("SKIP: paper_trading_enabled=false")
    sys.exit(0)

intent = {
    "symbol": "FPT",
    "side": "BUY",
    "strategy_id": "A3_DP",
    "setup_type": "smoke",
    "entry_price": 100000,
    "stop_price": 92000,
    "account_equity": 1_000_000_000,
    "adv50_vnd": 5_000_000_000,
    "asof": "2099-01-01",
}
enf = A.enforce_portfolio_constraints_impl(order_intent=intent)
print(json.dumps({"enforcement": enf}, indent=2))
print("OK: paper smoke completed (enforcement path only)")
