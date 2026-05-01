# Cursor Skills — Weekly Report Workflow

These skills help Cursor (and you) run the VN Weekly Investment Report workflow consistently.

## Skill locations

All under `.cursor/skills/`:

| Folder | Purpose |
|--------|--------|
| `macro_data_ingestion` | Update global macro, VN liquidity, market data; refresh raw + processed; validate freshness |
| `vn_sbv_liquidity` | Fetch Vietnam liquidity from SBV (OMO, interbank overnight, credit growth, FX); merge into manual_inputs with `--force-vn-liquidity` |
| `policy_research_ingestion` | Scan/update policy events; map transmission; append research intake; confidence downgrade when sources weak |
| `weekly_report_render` | Render HTML report; archive versions; ensure dashboard is complete and readable |
| `schema_guardian` | Protect schema consistency; validate JSON shape; catch missing required fields; prevent drift |
| `weekly_investment_cycle` | Orchestrate full weekly cycle: ingestion → validate → render → summarize |

## How to use

1. **Reference in chat**  
   When you want the agent to run the weekly cycle or refresh data, say e.g. “run the weekly investment cycle” or “update macro data and render the report.” The agent can load the relevant skill from `.cursor/skills/weekly_investment_cycle/skill.md` (or the others) and follow the steps.

2. **One command**  
   From repo root:
   ```bash
   make weekly-report
   ```
   or
   ```bash
   python -m scripts.run_full_weekly_cycle
   ```

3. **Step-by-step**  
   - Ingestion: `python -m scripts.ingest.run_weekly_update`  
   - Render: `python -m scripts.reporting.render_weekly_report`  
   - Validate: see `schema_guardian` skill or `tests/test_weekly_schema.py`.

## Intended use

- **macro_data_ingestion:** When you add or change UST, DXY, VN OMO, interbank, market levels, or data sources.
- **vn_sbv_liquidity:** When you want to fetch Vietnam liquidity from SBV (omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd) and plug into automation. See `docs/SBV_LIQUIDITY_SOURCES.md`.
- **policy_research_ingestion:** When you add policy events or research files under `inputs/research/` or `weekly_notes.json`.
- **weekly_report_render:** When you want to regenerate the HTML dashboard or archive a version.
- **schema_guardian:** When you add new fields to the report or need to validate the JSON.
- **weekly_investment_cycle:** When you want to run the full weekly pipeline in one go.

Each skill file is concise, imperative, and references concrete paths and success/failure handling so the agent can execute without guessing.
