# MCP Tool Contracts

All tools return **compact JSON strings** (`ok`, `tool`, `data` / `error_code`). Max ~48KB; no full OHLCV/FA tables.

Permission default: `PAPER_ONLY` (`config/mcp/permissions.default.json`).

## Read-only / analysis

| Tool | Source module | Side effects |
|------|---------------|--------------|
| `get_system_status` | `adapters.system_status` | None |
| `get_data_health_snapshot` | `adapters.data_health_snapshot` | None |
| `get_strategy_status` | `config/mcp/strategy_registry.yaml` | None |
| `get_regime_snapshot` | `regime_state.json`, `state_machine` | None |
| `get_council_snapshot` | `council_output.json` | None |
| `get_allocation_plan` | `allocation_plan.json` | None |
| `get_portfolio_snapshot` | `paper_broker_state.json` | None |
| `screen_technical_setups` | FireAnt OHLCV parquet | None |
| `get_signal_evidence` | OHLCV parquet | None |
| `evaluate_fundamental_moat` | `fa_annual.parquet` | None |
| `get_manual_input_status` | manual JSON packs | None |

**Stale behavior:** `stale: true` + `recommended_action` when file age exceeds thresholds in `src/mcp_server/config.py`.

**Missing data:** `DATA_MISSING` / `CRITICAL` in health; tools return null fields, not invented values.

## Research

| Tool | Notes |
|------|-------|
| `run_isolated_backtest` | IS-only summary; does not change production params |

## Risk / enforcement

| Tool | Source | Blocks |
|------|--------|--------|
| `calculate_position_size` | deterministic sizing | invalid stop, zero ADV |
| `validate_order_intent` | `schemas.validate_order_intent` | schema |
| `evaluate_kill_switch` | `kill_switch.py` | BLOCK → no orders |
| `enforce_portfolio_constraints` | `risk/engine.py` + council + legacy caps | hard_block_reason |
| `propose_order_intent` | chains read + enforce | no execution |

## Paper / audit

| Tool | Side effects |
|------|--------------|
| `simulate_paper_order` | decision log write; paper broker **only if** `paper_execution_allowed()` |
| `write_decision_log` | atomic write under `data/decision/mcp_logs/` |
| `get_recent_decision_log` | read only |
| `run_council_audit` | runs `council_secretary` subprocess |

## Example — `enforce_portfolio_constraints`

```json
{
  "ok": true,
  "tool": "enforce_portfolio_constraints",
  "data": {
    "allowed": false,
    "hard_block_reason": "strategy_status:RESEARCH_ONLY",
    "checks": [{"check": "strategy_status", "passed": false}],
    "required_human_approval": true
  }
}
```

## Forbidden

- Returning full dataframes or >50 row OHLCV series
- Silent overwrite of `manual_inputs.json` / consensus / research packs
- Live DNSE execution via MCP
- Rerunning Council inside read tools
