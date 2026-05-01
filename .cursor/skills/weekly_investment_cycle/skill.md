# Weekly Investment Cycle (Orchestration)

Use this skill when running the full weekly cycle: ingestion → validate → render → summarize.

## One command

From repo root:

```bash
python -m scripts.run_full_weekly_cycle
```

Or step by step:

1. **Ingestion**  
   `python -m scripts.ingest.run_weekly_update`  
   - Runs existing `src.report.weekly --render` to refresh `data/decision/weekly_report.json`.  
   - Normalizes to schema v1.0 and writes `data/processed/weekly_report.json`.

2. **Validate**  
   Validation runs inside full cycle; or run:  
   `python -c "from scripts.utils.validation import validate_weekly_report_file; from pathlib import Path; ok, errs = validate_weekly_report_file(Path('data/processed/weekly_report.json')); print('OK' if ok else errs)"`

3. **Render**  
   `python -m scripts.reporting.render_weekly_report`  
   - Produces `reports/latest/index.html` and `reports/archive/<asof_date>/index.html`.

4. **Summary**  
   After run, check:  
   - `metadata.warnings` in `data/processed/weekly_report.json`  
   - `metadata.report_age_days` (stale if > 3)  
   - `metadata.data_confidence` (High/Medium/Low)

## Makefile

If Makefile exists, use:

```bash
make weekly-report
```

(target added for full cycle)

## Key paths

- `data/decision/weekly_report.json` — legacy output from `src.report.weekly`
- `data/processed/weekly_report.json` — normalized schema v1.0
- `reports/latest/index.html` — dashboard
- `logs/weekly_update.log` — ingestion log

## Success criteria

- All three steps complete without crash.
- Outputs exist and validation passes.
- Missing metrics or stale data appear as warnings, not silent.

## Failure handling

- Ingestion failure: fix data sources or use `--skip-weekly` to normalize from existing JSON only.
- Render failure: ensure `data/processed/weekly_report.json` exists; install jinja2 if needed.
- Validation failure: fix normalizer or schema; do not ship invalid report.
