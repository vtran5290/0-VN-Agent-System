# Weekly Report — 3rd AI Review Package

## Purpose

This package lets an **independent AI reviewer** audit the **Weekly Report / Portfolio Command Center** workflow: rendered HTML, source code, config, sample inputs, and tests — **without** live trading credentials or order routing.

**Decision support only.** Capital remains **NO-GO** unless separately approved in `docs/trading/REAL_CAPITAL_READINESS.md`.

## Current report objective

- Leaner, less repetitive, more **decision-useful** weekly/daily portfolio brief.
- Prioritize: **portfolio health**, **execution actions**, **B_cloud20_100 / A3_PRODUCTION watchlist**, **market pulse**, macro/liquidity implications.
- Move methodology, regime detail, full data freshness, and sources to **Appendix**.

## Strategy alignment (production)

| Item | Value |
|------|--------|
| Production strategy | **A3_DP / B_cloud20_100** |
| Signal SSOT | **phase36 daily scan CSV** (`phase36_daily_scan_latest.csv` or dated file) |
| Production rows | `strategy_classification == A3_PRODUCTION` |
| Watchlist default | **A3_PRODUCTION only** (`show_research_watchlist: false` in config) |
| Rank score | `a3_rank_score` = review priority only; **cannot** create/block/size orders |

**Hard constraints for reviewers:** do not propose recomputing EMA in the report, changing `final_action` logic, changing live trading/OMS, or recommending real capital.

## Workflow map

### A. Inputs

| Input | Path / source | Role |
|-------|----------------|------|
| Macro / manual KPIs | `data/raw/manual_inputs.json`, `manual_inputs_prev.json` | Fed, DXY, credit, OMO net, interbank, etc. |
| Portfolio holdings | `data/raw/current_positions_derived.json` | Positions, qty, cost |
| Phase36 scan (SSOT) | `data/research/.../phase36_daily_scan_latest.csv` | `final_action`, cloud, trail, A3 classification |
| Tech status (legacy/aux) | `data/raw/tech_status.json` | Wyckoff/RS labels; not order SSOT |
| Sell signals (legacy/aux) | `data/alerts/sell_signals.json` | Supplementary; scan forced exits preferred |
| Strategy config | `config/weekly_report_strategy.yaml` | A3 filter, research visibility |
| Sector map | `data/master/sector_map.csv` | Display sector |
| FireAnt prices | via `portfolio_decision_enrich` | Live mark; requires token at **generate** time (not in zip) |
| Regime / allocation | `data/state/regime_state.json`, `data/decision/allocation_plan.json` | Regime label, allocation hints |

### B. Processing

```
python -m src.report.weekly          → data/decision/weekly_report.json (+ weekly_report.md)
python -m scripts.ingest.run_weekly_update
    → normalize_weekly_report
    → portfolio_decision_enrich (holdings + scan join + prices)
    → weekly_lean_sections (command center, pulse, KPIs, viz payloads)
    → data/processed/weekly_report.json
python -m scripts.reporting.render_weekly_report
    → reports/latest/index.html
```

Key modules:

- `scripts/ingest/scan_ssot.py` — resolve scan path, filter A3_PRODUCTION
- `scripts/ingest/weekly_lean_sections.py` — section builders, immediate actions
- `scripts/reporting/metric_registry.py` — KPI definitions, dedup hints
- `scripts/reporting/report_format.py` — decimals, Missing, cloud labels
- `templates/weekly_report_lean.html.j2` — HTML layout

### C. Outputs

| Output | Path |
|--------|------|
| Lean HTML (primary artifact) | `reports/latest/index.html` |
| Processed JSON | `data/processed/weekly_report.json` |
| Markdown (legacy/council) | `data/decision/weekly_report.md` |
| Review zip | `outputs/review_packages/vn_weekly_report_3rd_ai_review.zip` |

### D. Source-of-truth hierarchy

1. **Scan CSV** — `final_action`, trail, cloud state for B_cloud20_100 / A3_PRODUCTION.
2. **Holdings file** — what you own; enriched with scan join (may be `scan_missing`).
3. **`config/weekly_report_strategy.yaml`** — production vs research visibility.
4. **`manual_inputs.json`** — macro/liquidity KPIs (operator-maintained).
5. **`sell_signals.json` / `tech_status.json`** — legacy/supplementary; immediate actions **prefer** scan forced exits.

## How to open the report

1. Unzip `vn_weekly_report_3rd_ai_review.zip`.
2. Open `outputs/reports_latest_index.html` in a browser (file:// or local static server).
3. Read `REVIEW_PROMPT.md` and follow its review checklist.

## How to regenerate the report

From repo root (with `.venv` and `FIREANT_TOKEN` in environment — **not** shipped in zip):

```powershell
cd "D:\V\0. VN Agent System"
# Optional: refresh phase36 scan
.venv\Scripts\python.exe pp_backtest\portfolio_optimization_final_steps.py --step scan
# Optional: tech_status for holdings
.venv\Scripts\python.exe scripts\update_tech_status.py --asof YYYY-MM-DD --tickers STB,BID,...
# Ingest + render
.venv\Scripts\python.exe -m scripts.ingest.run_weekly_update
.venv\Scripts\python.exe -m scripts.reporting.render_weekly_report
```

Full macro/FireAnt fetch pipeline: `python scripts/run_weekly_full_fetch.py` (see `docs/WEEKLY_FULL_FETCH.md`).

## How to run tests

```powershell
.venv\Scripts\python.exe -m pytest tests/test_report_format.py tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py tests/test_weekly_report_p0_fixes.py -q
```

## Rebuild this review zip

```powershell
.venv\Scripts\python.exe -m scripts.reporting.build_weekly_report_3rd_ai_review_zip
```

## Known issues / limitations (packaging-time)

- **8/14 holdings** may show `row-noscan` if not in A3_PRODUCTION scan universe.
- **NVL** may show scan `TRAIL_EXIT` vs report HOLD → Critical data-quality flag (by design).
- **VNINDEX trend**, **P/E/P/B**, **Fed multi-horizon curve**, **OMO stock / rolling series** — spec’d but not fully implemented in lean template.
- **Credit growth** may show scale warning if `manual_inputs.json` uses percent vs decimal inconsistently.
- **DXY WoW** needs fresh `manual_inputs_prev.json` for meaningful delta.
- Scan `as_of` date may lag if phase36 panel not re-run.
- Fundamentals on watchlist often **Missing** unless FA feed wired.

See `PACKAGING_AUDIT.md` inside the zip for machine snapshot at build time.

## Files included (typical)

- `REVIEW_PROMPT.md`, `README.md`, `PACKAGING_AUDIT.md`, `MANIFEST.txt`
- `outputs/reports_latest_index.html`, processed JSON trim, samples
- `scripts/ingest/*`, `scripts/reporting/*`, `templates/*`, `tests/*`
- `config/weekly_report_strategy.yaml`, docs (strategy sync, capital readiness, flow)

## Files intentionally excluded

- `.env`, tokens, FireAnt JWT, DNSE/broker credentials
- Live/paper order logs, OMS state, private account files
- Full git history, `cursor_chat_export/`, large backtest artifacts
- Anything matching secret patterns in zip builder

## Safety

- **No live trading** — report does not route orders.
- **No credentials** in zip — regenerate locally with your own token.
- **NO-GO capital** — see `docs/trading/REAL_CAPITAL_READINESS.md`.
