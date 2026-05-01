# Policy & Research Ingestion

Use this skill when scanning/updating policy events, transmission channels, or research intake for the weekly report.

## Steps

1. **Policy events**
   - Add or update `data/raw/weekly_notes.json` with `policy_facts` or `policy_events` (array of events with date/title/body/transmission).
   - Normalizer and report will pick these up when building `vietnam_policy` and `research_intake`.

2. **Research intake**
   - Place files in `inputs/research/` (or path in `configs/weekly_sources.yml` → `research_intake.path`). Supported: .md, .json, .txt.
   - Or append to `weekly_notes.json`: `intake_takeaways`, `broker_notes`, `earnings_facts`, `policy_facts`.

3. **Confidence**
   - If sources are weak or missing, `metadata.data_confidence` may be downgraded (see normalizer confidence logic in `scripts/ingest/normalize_weekly_report.py`).

4. **Run pipeline**
   - `python -m scripts.ingest.run_weekly_update` to refresh and normalize.

## Key paths

- `data/raw/weekly_notes.json` — policy_facts, intake_takeaways, broker_notes, earnings_facts
- `inputs/research/` — optional folder for research files
- `configs/weekly_sources.yml` — research_intake.path

## Success criteria

- `vietnam_policy.events` and `research_intake` sections in `data/processed/weekly_report.json` reflect updates.
- No overwrite of existing good data; additive only.

## Failure handling

- Missing or invalid JSON: skip section; do not crash. Log and add warning to metadata.
