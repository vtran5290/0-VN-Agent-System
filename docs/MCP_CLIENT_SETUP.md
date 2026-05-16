# MCP Client Setup (Cursor + Claude Code)

> All example paths use `<your-repo-path>` or `${workspaceFolder}`.
> Substitute with your local clone path. Do not commit absolute personal paths.

## Repository config conventions

| Client | Config file (in repo) | Example file |
|--------|------------------------|--------------|
| Cursor | `.cursor/mcp.json` | `config/mcp/cursor_mcp_config.example.json` |
| Claude Code | `.mcp.json` (repo root) | `config/mcp/claude_code_mcp_config.example.json` |

Both must register a server named `local-quant-engine` whose command runs
`${workspaceFolder}/scripts/mcp_quant_engine.py`. Tool names are shared by both
clients (see `MCP_TOOL_CONTRACTS.md`).

The review-bundle paths `client_config/cursor_mcp.json` and
`client_config/claude_mcp.json` are **flattened copies for offline review only**
— they are not the live config locations.

## 1. Install deps

```powershell
cd <your-repo-path>
.\.venv\Scripts\pip install -r requirements.txt
```

## 2. Environment

Copy `config/mcp/local_quant_engine.env.example` → `.env` (gitignored). Set `FRED_API_KEY`. Keep `LIVE_TRADING=false`.

Install FRED MCP shim (Windows-safe bootstrap; run once after clone):

```powershell
cd mcp/fred-mcp
npm install
```

## 3. Cursor

Copy `config/mcp/cursor_mcp_config.example.json` → `.cursor/mcp.json` (or merge). Reload window.

Verify: Settings → MCP → `local-quant-engine` connected.

## 4. Claude Code

Copy `config/mcp/claude_code_mcp_config.example.json` → `.mcp.json` at repo root.

```powershell
claude mcp list
```

## 5. Same tool names

Both clients must call `scripts/mcp_quant_engine.py` with identical tool names (see `docs/MCP_TOOL_CONTRACTS.md`).

## 6. Smoke tests

```powershell
make mcp-smoke
make mcp-test
make mcp-status
make mcp-risk-smoke
make mcp-live-guard
```

## 7. Confirm live disabled

`make mcp-live-guard` must print `OK: live execution guarded`.

## Troubleshooting

- **MCP Logs** (Cursor Output panel): server crash, bad path, missing `fastmcp`
- **Path**: use `${workspaceFolder}` — never hardcode `D:\` or `C:\Users\<name>`
- **Parquet missing**: run `make ingestion` / FireAnt SSOT build
- **Serena / FRED**: separate servers; optional for quant tools
- **Windows `npx`**: use `"command": "cmd", "args": ["/c", "npx", ...]` (see repo `.cursor/mcp.json`)
- **Serena CLI**: use `serena start-mcp-server --context ide --project-from-cwd` with `"cwd": "${workspaceFolder}"` (not legacy `--context ide-assistant`)

## Secrets

Never commit `.env` or API keys inside `mcp.json`. Use `envFile` (Cursor) or `${env:FRED_API_KEY}`.
