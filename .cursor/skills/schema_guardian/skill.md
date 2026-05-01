# Schema Guardian

Use this skill when protecting schema consistency, validating JSON shape, or preventing drift between schema and runtime output.

## Steps

1. **Validate a report file**
   - From repo root: run `python -c "from scripts.utils.validation import validate_weekly_report_file; from pathlib import Path; ok, errs = validate_weekly_report_file(Path('data/processed/weekly_report.json')); print('OK' if ok else errs)"`
   - Or use tests: `python -m pytest tests/test_weekly_schema.py -v`

2. **Schema and docs**
   - Schema: `schemas/weekly_report.schema.json`
   - Docs: `docs/weekly_report_schema.md`
   - Example: `data/examples/weekly_report.example.json`

3. **Required fields**
   - Top-level: `metadata` must exist.
   - Inside metadata: `asof_date`, `schema_version` are required. All other sections are optional for partial reports.

4. **When adding new fields**
   - Add to `schemas/weekly_report.schema.json` under the appropriate section (and definitions if new type).
   - Update `docs/weekly_report_schema.md`.
   - Update normalizer in `scripts/ingest/normalize_weekly_report.py` if the field is populated from legacy report.
   - Update template `templates/weekly_report.html.j2` if the field should appear in the dashboard.

## Key paths

- `schemas/weekly_report.schema.json`
- `scripts/utils/validation.py` — `validate_weekly_report_payload`, `validate_weekly_report_file`
- `tests/test_weekly_schema.py`

## Success criteria

- `validate_weekly_report_payload(payload)` returns (True, []) for any report produced by the normalizer.
- No silent drift: new required fields must be added explicitly and backfilled or defaulted.

## Failure handling

- Validation errors: do not overwrite production report; fix normalizer or input data and re-run.
