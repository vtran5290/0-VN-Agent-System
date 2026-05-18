# Weekly report generation flow

```
src.report.weekly --render     →  data/decision/weekly_report.json (+ .md)
scripts.ingest.normalize_weekly_report
  └─ portfolio_decision_enrich.enrich_portfolio_decision_sections
  └─ weekly_lean_sections.attach_lean_report   →  data/processed/weekly_report.json
scripts.reporting.render_weekly_report         →  reports/latest/index.html
```

**Template:** `templates/weekly_report_lean.html.j2`  
**Strategy config:** `config/weekly_report_strategy.yaml` (A3_PRODUCTION / B_cloud20_100)  
**Scan SSOT:** `scripts/ingest/scan_ssot.py` → phase36 CSV under `data/research/portfolio_optimization/missing_work/`  
**Holdings:** `data/raw/current_positions_derived.json` (FQuery derive)  
**Format helpers:** `scripts/reporting/report_format.py`

```powershell
python -m scripts.ingest.run_weekly_update
python -m scripts.reporting.render_weekly_report
```
