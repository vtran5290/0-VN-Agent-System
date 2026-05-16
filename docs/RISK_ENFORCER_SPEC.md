# Risk Enforcer — Hard Blocks

`enforce_portfolio_constraints` must set `allowed: false` when any of:

- Strategy status not production-approved (`config/mcp/strategy_registry.yaml`)
- Setup research-only / watchlist-only
- Council stance blocks new exposure (`no new` in recommendation)
- Allocation has no room (future: explicit capacity check)
- Regime / VNINDEX gate blocks T1/T2 (`get_regime_snapshot`)
- Breadth / manual review flags in signal metadata
- Kill switch `BLOCK` (`evaluate_kill_switch`)
- Kill switch `WARN` when rule requires block
- Data health `CRITICAL`
- Stale OHLCV / VNINDEX (via health)
- Stale paper broker state
- Stale / missing manual inputs when required
- Stale consensus / research packs when required for council
- ADV50 missing or below `min_adv50_vnd`
- ADV participation cap breached
- Sector concentration > 30% (legacy enforcer)
- Position count ≥ 20
- Gross / single-name limits (`src/trading/risk/rules.py`)
- Invalid stop distance
- `final_shares <= 0`
- Order intent schema invalid
- Decision log write failure (paper path)
- Reconciliation `BLOCK_NEW_ORDERS`
- `live_trading_enabled` without human approval
- `broker_write_enabled` false for live

Local `src/trading/risk/engine.py` is authoritative when `order_intent_json` is provided.
