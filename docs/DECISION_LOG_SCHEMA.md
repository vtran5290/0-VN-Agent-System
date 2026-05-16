# Decision Log Schema (MCP)

Written by `write_decision_log` to `data/decision/mcp_logs/{timestamp}_{symbol}.json`.

## Required fields

| Field | Type | Notes |
|-------|------|-------|
| `created_at` | ISO8601 UTC | |
| `asof` | YYYY-MM-DD | trade / signal date |
| `tool_name` | string | MCP tool |
| `agent_name` | string | user or agent id |
| `agent_client` | enum | `claude_code` \| `cursor` \| `manual` \| `unknown` |
| `symbol` | string | |
| `side` | BUY \| SELL | |
| `strategy_id` | string | |
| `setup_type` | string | |
| `strategy_status` | string | from registry |
| `final_decision` | string | proposed \| blocked \| paper_simulate |
| `source_paths` | array | repo-relative paths |
| `rule_versions` | object | e.g. `{"mcp": "mcp_orchestration_v1"}` |

## Recommended snapshots

`signal_evidence`, `regime_snapshot`, `council_snapshot`, `allocation_snapshot`, `portfolio_snapshot`, `kill_switch_snapshot`, `risk_checks`, `blocked_reason`, `recommended_action`, `source_hashes`, `config_versions`.

Validation: `src/mcp_server/schemas.validate_decision_payload`.

If write fails → `LOG_WRITE_FAILED` and paper/live paths must not proceed.
