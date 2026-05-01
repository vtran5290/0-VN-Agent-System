# Report Viewer

The weekly report is rendered as a local HTML dashboard from the normalized JSON (schema v1.0).

## Run instructions

1. **Generate the report**
   - Full cycle (recommended):  
     `make weekly-report`  
     or  
     `python -m scripts.run_full_weekly_cycle`
   - This runs: ingestion (existing weekly + normalizer) → validation → HTML render.

2. **Render only** (if `data/processed/weekly_report.json` already exists):
   ```bash
   python -m scripts.reporting.render_weekly_report
   ```

3. **Open the report**
   - **Latest:** open `reports/latest/index.html` in your browser or in Cursor (right-click → Open with Live Server, or open file directly).
   - **Archived:** `reports/archive/<asof_date>/index.html` for a specific week.

## Input

- **Primary input:** `data/processed/weekly_report.json` (produced by `scripts.ingest.run_weekly_update` or full cycle).
- **Template:** `templates/weekly_report.html.j2`
- **Styles:** inlined in the template for portability; optional `templates/styles.css` for standalone use.

## Sections in the dashboard

1. Header / metadata (as-of date, confidence, stale warning)
2. Executive summary (regime, top actions, top risks)
3. KPI tiles (UST 2Y/10Y, DXY, VNINDEX, VN30, OMO, interbank, USD/VND, dist days, risk flag)
4. Global macro
5. Vietnam liquidity
6. Market structure
7. Regime engine
8. Decision layer
9. Watchlist
10. Execution & sell/trim
11. Portfolio health
12. Geo layer (Hormuz / energy shock)
13. Open questions
14. Signals to monitor next week
15. If X happens → do Y

## Dependencies

- **Jinja2** for full template rendering: `pip install jinja2`
- Without Jinja2, the renderer produces a minimal HTML fallback with the JSON payload.

## Print / PDF

- Use the browser’s Print → Save as PDF. The layout is print-friendly; the sidebar is hidden in print media.
