# Weekly Report Render

Use this skill when rendering the HTML dashboard or archiving report versions.

## Steps

1. **Ensure input exists**
   - Input: `data/processed/weekly_report.json` (schema v1.0). If missing, run `python -m scripts.ingest.run_weekly_update` first.

2. **Render**
   - From repo root: `python -m scripts.reporting.render_weekly_report`
   - Outputs:
     - `reports/latest/index.html` — always the latest run
     - `reports/archive/<asof_date>/index.html` — dated copy

3. **Optional**
   - `--input <path>` to use a different JSON path.
   - `--out <path>` to set custom HTML output path.

4. **View**
   - Open `reports/latest/index.html` in browser or Cursor (right-click → Open with Live Server or open file).

## Key paths

- `data/processed/weekly_report.json` — input
- `templates/weekly_report.html.j2` — Jinja2 template
- `templates/styles.css` — styles (inlined in template for portability)
- `reports/latest/index.html`, `reports/archive/<asof>/index.html`

## Success criteria

- HTML is generated without crash.
- All sections (header, executive, KPIs, global macro, VN liquidity, market, regime, decision, watchlist, execution, portfolio health, geo, open questions, monitoring, playbook) are present and readable.

## Failure handling

- If Jinja2 is not installed, renderer falls back to minimal HTML with payload dump. Install: `pip install jinja2`.
- If input JSON is empty or invalid, exit 1 and report.
