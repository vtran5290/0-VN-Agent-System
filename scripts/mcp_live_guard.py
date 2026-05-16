"""Verify live trading remains disabled by default."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.permissions import load_permissions
from src.trading.config import load_live_trading_config, load_trading_config


def main() -> int:
    perms = load_permissions()
    tcfg = load_trading_config()
    lcfg = load_live_trading_config()
    failures = []
    if perms.live_trading_enabled:
        failures.append("mcp permissions live_trading_enabled")
    if perms.broker_write_enabled:
        failures.append("mcp permissions broker_write_enabled")
    if tcfg.live_trading:
        failures.append("trading.yaml live_trading")
    if lcfg.live_trading:
        failures.append("live_trading.yaml execution_flags.live_trading")
    if tcfg.live_dnse_orders_allowed():
        failures.append("DNSE orders unexpectedly allowed")
    if failures:
        print("FAIL:", failures)
        return 1
    print("OK: live execution guarded (live_trading=false, broker_write=false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
