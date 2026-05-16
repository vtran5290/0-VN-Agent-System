# MCP Architecture — VN Agent System

## Six-layer production stack

```
Regime Detection → Smart Money → Council Decision → Allocation → Risk/Kill Switch → Execution
```

| Layer | SSOT / modules | MCP role |
|-------|----------------|----------|
| Regime | `src/regime/state_machine.py`, `data/state/regime_state.json` | `get_regime_snapshot` (read) |
| Smart Money | `data/raw/consensus_pack.json`, `make consensus-apply` | `get_manual_input_status` (freshness) |
| Council | `data/decision/council_output.json`, `prompts/council/*` | `get_council_snapshot` (read) |
| Allocation | `data/decision/allocation_plan.json`, `src/alloc/engine.py` | `get_allocation_plan` (read) |
| Risk / Kill switch | `src/trading/risk/*`, `src/trading/monitoring/kill_switch.py` | `enforce_portfolio_constraints`, `evaluate_kill_switch` |
| Execution | `src/trading/pipeline.py`, `src/trading/brokers/*` | **Blocked by default**; `simulate_paper_order` only when permitted |

## Core principle

- **LLM (Claude Code / Cursor):** orchestrator, reviewer, explainer — calls MCP tools only.
- **Local Python:** calculator, validator, risk enforcer, logger.
- **MCP:** thin deterministic JSON API over existing repo logic (`src/mcp_server/`).
- **FireAnt parquets:** SSOT for OHLCV/FA (`data/fireant_ssot/*`) — never streamed into chat.

## Why one MCP server for both clients

`local-quant-engine` is registered identically in:

- `.cursor/mcp.json` (Cursor; commit to repo or place in `${workspaceFolder}/.cursor/`)
- `.mcp.json` (Claude Code; repo root)

Both invoke `${workspaceFolder}/scripts/mcp_quant_engine.py` → `src/mcp_server/server.py`. Tool names and JSON shapes must match.

Example templates live under `config/mcp/` (see `MCP_CLIENT_SETUP.md`). Review
bundles flatten these to `client_config/` — that path is for offline review
only, not for runtime.

## External MCP servers (not SSOT)

| Server | Purpose | Not used for |
|--------|---------|--------------|
| `fred-mcp-server` | Macro series (UST, CPI, DXY) | Allocation / orders |
| `tradingview-mcp-server` | Screener / symbol lookup | Price SSOT |
| `serena` | LSP code intelligence | Trading decisions, raw data |

## Live DNSE

Default: **disabled** (`config/mcp/permissions.default.json`, `config/live_trading.yaml`, `config/trading.yaml`). MCP has no live `execute_order` tool. `simulate_paper_order` requires enforcement + decision log.

## Package layout

```
src/mcp_server/
  adapters.py    # wraps regime, risk, council, screening
  server.py      # FastMCP tool registration
  permissions.py # PAPER_ONLY default
scripts/mcp_quant_engine.py  # stdio entrypoint
```

See also: `MCP_TOOL_CONTRACTS.md`, `PERMISSION_MODEL.md`, `RISK_ENFORCER_SPEC.md`, `MCP_CLIENT_SETUP.md`.

## Serena (repo intelligence only)

**Use for:** symbol search, dependency lookup, refactors, navigating `src/` and `pp_backtest/`.

**Do not use for:** trading decisions, reading OHLCV/FA parquets into chat, bypassing MCP risk tools, or skipping tests. Market facts must come from `local-quant-engine` + FireAnt SSOT.
