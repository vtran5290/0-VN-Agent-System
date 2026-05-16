# Manual Inputs — MCP Policy

## Files

| File | Makefile | MCP |
|------|----------|-----|
| `data/raw/manual_inputs.json` | `make weekly`, ingestion | `get_manual_input_status` — read/validate only |
| `data/raw/consensus_pack.json` | `make consensus-apply` | read/validate only |
| `data/raw/research_engine_pack.json` | `make research-pack-apply` | read/validate only |

## Allowed MCP actions

- Read freshness (`get_manual_input_status`)
- Include stale flags in `get_data_health_snapshot` / `enforce_portfolio_constraints`

## Forbidden

- MCP tools **must not** silently overwrite manual packs
- Council rerun is **not** implicit in `get_council_snapshot`

## Stale impact

Stale `manual_inputs` → `enforce_portfolio_constraints` hard block `stale_manual_inputs`.

Council weekly (`make council-weekly`) consumes packs after human curation; MCP reads resulting `council_output.json` only.
