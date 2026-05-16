# Permission Model

## States

| State | Meaning |
|-------|---------|
| `RESEARCH_ONLY` | Backtests / reads only |
| `WATCHLIST_ONLY` | Screen + evidence, no capital |
| `PAPER_ONLY` | Paper path after enforce + log (**default max**) |
| `HUMAN_APPROVAL_REQUIRED` | Live-like intent needs human file/token |
| `LIVE_ENABLED` | Not default; requires explicit config |

## Default (`config/mcp/permissions.default.json`)

```json
{
  "live_trading_enabled": false,
  "broker_write_enabled": false,
  "paper_trading_enabled": true,
  "human_approval_required": true,
  "max_permission": "PAPER_ONLY"
}
```

## By client

| Client | Config file | Same `local-quant-engine` tools |
|--------|-------------|----------------------------------|
| Cursor | `.cursor/mcp.json` | Yes |
| Claude Code | `.mcp.json` | Yes |
| `fred-mcp-server` | npx | Macro read only |
| `tradingview-mcp-server` | npx | Screener only |
| `serena` | uvx | Code only — no orders |

Neither Claude Code nor Cursor can live-execute by default. `live_execution_allowed()` requires all of: `live_trading_enabled`, `broker_write_enabled`, `max_permission == LIVE_ENABLED`.
