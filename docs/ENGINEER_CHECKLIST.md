# Engineer Handoff Checklist (MVP hardening)

Bắt buộc trước merge PR / handoff.

## Hardening & determinism

- [x] **compute_relevance** fallback → label `Unknown`, score `null`, no crash when context missing (`vn30_dd20`, `stock_below_ma50`, `regime_flag`)
- [x] **Decision flags deterministic** from resolver results: `records_queried`, `loaded_records`, `stale_warnings` set by code; **Knowledge used: Yes/No** = `loaded_records > 0`
- [x] **mtime staleness warning**: record stores `inputs.results_csv_mtime`, `inputs.ledger_csv_mtime`; resolver compares current file mtime → "Backtest data newer than knowledge record — re-publish recommended."
- [x] **params_hash stale warning** (preset mismatch) mandatory when hash in record ≠ current preset hash
- [x] **regime_break.json** with `expires_at`; when `active==true` and `today > expires_at` → treat as **inactive** (no downgrade), add warning "Regime break expired — manual review recommended."; optional log to `knowledge/logs/system_warnings.log`; do not write back to file
- [x] **setup_quality.py** deterministic scoring 0–100, subscores (trend 40% / tightness 30% / volume 30%), weights documented in file header
- [x] **render_weekly_note.py** reads JSON truth → outputs `knowledge/weekly_notes/YYYYMMDD.md`; no manual MD as source of truth

## Scope control

- [x] Semi-auto execution (e.g. scheduled backtest, auto-publish) moved to **Future Phases** doc — out of MVP

## Files to verify

| Item | Location |
|------|----------|
| regime_break schema | `knowledge/regime_break.json` (active, reason, since, expires_at, notes) |
| Resolver relevance | `src/knowledge/resolver.py` — `compute_relevance()`, `load_regime_break()`, `_mtime_stale_warning()` |
| Publish inputs mtime | `pp_backtest/publish_knowledge.py` — `build_record(..., results_mtime, ledger_mtime)`, `inputs` in record |
| Weekly flags | `src/report/weekly.py` — `loaded_records`, `records_queried`, `stale_warnings`, `knowledge_used`, system_warnings (regime_break expired) |
| Setup quality | `src/signals/setup_quality.py` — weights 40/30/30, subscores, notes |
| Render weekly note | `knowledge/render_weekly_note.py` — JSON → MD sections |
