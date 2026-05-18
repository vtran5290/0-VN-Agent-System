# Independent Review Prompt — Weekly Report / Portfolio Command Center

You are an **independent senior quant + product reviewer** for the VN Agent System weekly report. You have received a zip package (`vn_weekly_report_3rd_ai_review.zip`) containing the **rendered HTML**, **source code**, **config**, **sample inputs**, and **tests**.

Your job is to validate **decision usefulness**, **information hierarchy**, **strategy alignment**, and **implementation quality** — not to redesign live trading.

---

## Mission

The Weekly Report evolved from a macro dashboard into a **Portfolio Command Center** for daily/weekly decisions. The product goal:

- Leaner, smarter, less repetitive, more action-oriented.
- Prioritize: portfolio health → execution → B_cloud20_100 watchlist → market pulse → macro/liquidity implications.
- Keep methodology, regime detail, full freshness, and sources in **Appendix**.

---

## Hard constraints (do NOT violate)

| Rule | Detail |
|------|--------|
| No EMA recompute | Report must **not** recompute EMA/cloud signals; SSOT is phase36 daily scan CSV. |
| No `final_action` changes | Do not propose altering scan `final_action` logic in report code. |
| No live trading changes | No OMS, DNSE, order routing, position sizing from report. |
| No real capital | Capital is **NO-GO** unless `docs/trading/REAL_CAPITAL_READINESS.md` explicitly approves (it does not today). |
| `a3_rank_score` | Review priority only — cannot create, block, size, or modify orders. |
| Research rows | `S3_RESEARCH_ONLY` / `WATCH_ONLY` must not mix into production watchlist unless clearly labeled and config-enabled. |

---

## Primary artifact

Open **`outputs/reports_latest_index.html`** in a browser first. Treat it as the user-facing product. Cross-check every claim against **source code** in the zip — not docs alone.

---

## Expected main report structure (target spec)

1. Header  
2. Portfolio Command Center  
3. What Changed / Market Pulse  
4. Portfolio Summary & Health  
5. Execution / Position Actions  
6. Watchlist / Next Buy Candidates  
7. Smart KPI Board (Global Drivers · Vietnam Liquidity & Policy · Market Internals)  
8. Smart Visualizations  
9. Decision Plan  
10. Decision Review  
11. Compact Data Quality / Freshness  
12. Appendix (regime, rules, methodology, full freshness, sources, optional research section)

---

## Product rules to audit

1. Numbers: **1–2 decimals** consistently.  
2. No repeated/redundant metrics; **one metric → one main home**.  
3. If a metric is a **delta in Market Pulse**, do not repeat raw KPI elsewhere unless distinct decision purpose.  
4. Data Freshness: **compact** in main body; **full** in Appendix.  
5. Visuals must be meaningful (VNINDEX trend, VNINDEX P/E·P/B, Fed curve 3M/6M/1Y/2Y, VN liquidity impulse, OMO stock/rolling net, A3 cloud breadth, portfolio action distribution).  
6. Global Macro narrative must **not duplicate** KPI board numbers.  
7. VN Liquidity: not only daily OMO net — consider aggregate OMO / stock / rolling net.  
8. Regime explanation → Appendix (one-liner in Command Center OK).  
9. Section order: **Portfolio Summary above Execution above Watchlist**.  
10. Missing values → **"Missing"**, never None/null/NaN in HTML.  
11. Scan-missing holdings must **not** look like normal B_cloud20_100 HOLDs (`row-noscan` / REVIEW).  
12. Immediate Actions must include **all scan-based forced exits** (e.g. TRAIL_EXIT), not only legacy `sell_signals`.

---

## Files to inspect first

### Rendered output

| Path | Notes |
|------|--------|
| `outputs/reports_latest_index.html` | Primary UI artifact |
| `outputs/processed_weekly_report_lean_keys.json` | Trimmed JSON sections |
| `outputs/data_processed_weekly_report.json` | Full processed payload |
| `PACKAGING_AUDIT.md` | Build-time HTML checks |

### Templates & rendering

| Path | Notes |
|------|--------|
| `templates/weekly_report_lean.html.j2` | Lean HTML template |
| `templates/weekly_report_portfolio_blocks.j2` | Portfolio blocks partial |
| `scripts/reporting/render_weekly_report.py` | Jinja render entry |

### Ingest & sections

| Path | Notes |
|------|--------|
| `scripts/ingest/run_weekly_update.py` | Orchestrator |
| `scripts/ingest/weekly_lean_sections.py` | Command center, pulse, KPIs, viz |
| `scripts/ingest/scan_ssot.py` | Scan path + A3 filter |
| `scripts/ingest/portfolio_decision_enrich.py` | Holdings + scan join + prices |
| `scripts/ingest/normalize_weekly_report.py` | Legacy normalize |

### Reporting helpers

| Path | Notes |
|------|--------|
| `scripts/reporting/metric_registry.py` | KPI registry / dedup |
| `scripts/reporting/report_format.py` | fmt, Missing, decimals |

### Config & strategy

| Path | Notes |
|------|--------|
| `config/weekly_report_strategy.yaml` | A3_PRODUCTION, research visibility |
| `docs/WEEKLY_REPORT_STRATEGY_SYNC.md` | Strategy ↔ report contract |

### Sample inputs (sanitized)

| Path | Notes |
|------|--------|
| `samples/current_positions_derived.json` | Holdings |
| `samples/phase36_daily_scan_latest.csv` | Signal SSOT snapshot |
| `samples/manual_inputs.json` | Macro/liquidity KPIs |
| `samples/sell_signals.json` | Legacy sell list |
| `samples/tech_status.json` | TA labels |

### Tests

| Path | Notes |
|------|--------|
| `tests/test_weekly_report_p0_fixes.py` | P0 acceptance |
| `tests/test_portfolio_command_center_report.py` | Command center structure |
| `tests/test_lean_weekly_report.py` | Lean sections |
| `tests/test_report_format.py` | Formatting |

### Docs & archive

| Path | Notes |
|------|--------|
| `README.md` | Package readme |
| `docs/WEEKLY_REPORT_GENERATION_FLOW.md` | Pipeline |
| `docs/trading/REAL_CAPITAL_READINESS.md` | Capital gate |
| `archive/CURSOR_PATCH_BRIEF.md` | Prior patch brief |
| `docs/KPI_IMPORTANCE_BACKTEST_PROMPT.md` | KPI research prompt |

### Expected but missing (if not in zip)

| Path | Status |
|------|--------|
| `outputs/reports_latest_index.html` at repo root | Lives under `reports/latest/index.html` in repo |
| `scripts/weekly_lean_sections.py` (flat) | Actual: `scripts/ingest/weekly_lean_sections.py` |
| `scripts/scan_ssot.py` (flat) | Actual: `scripts/ingest/scan_ssot.py` |
| VNINDEX / P/E chart data series in repo | Often not wired to lean viz yet |
| Fed 3M/6M/1Y/2Y curve data | Often not in `manual_inputs` yet |
| `weekly_notes.json` | Optional operator notes — may be absent |

---

## Workflow map (validate this)

```
Inputs:
  manual_inputs.json, holdings, phase36_daily_scan_latest.csv,
  tech_status, sell_signals, regime_state, weekly_report_strategy.yaml
       ↓
run_weekly_update → portfolio_decision_enrich + weekly_lean_sections
       ↓
data/processed/weekly_report.json
       ↓
render_weekly_report → reports/latest/index.html
```

Confirm: scan join keys, A3_PRODUCTION filter, immediate-actions source, chart JSON init, appendix split.

---

## Review checklist (code + HTML)

- [ ] Section order matches spec  
- [ ] No `None` / `null` / `NaN` in visible HTML  
- [ ] TRAIL_EXIT holdings in Immediate Actions + Command Center  
- [ ] Scan-missing holdings flagged (amber / REVIEW), not silent HOLD  
- [ ] Watchlist = A3_PRODUCTION only by default  
- [ ] S3 / WATCH_ONLY hidden or labeled  
- [ ] KPI dedup: pulse deltas vs Smart KPI Board  
- [ ] Global Macro narrative vs KPI numbers  
- [ ] OMO units (VND bn) vs interbank (%) — separate charts?  
- [ ] Chart canvases backed by `<script type="application/json" id="viz-data-*">`  
- [ ] `a3_rank_score` never drives execution text  
- [ ] Tests cover critical regressions; note gaps  

---

## Required output format

Produce **all** sections below in order:

### 1. Verdict
One paragraph: ship-ready / needs P0 fixes / needs redesign — for **decision support report only**.

### 2. 60-second usability score
Score 1–10 + one sentence: can an operator act in 60 seconds?

### 3. Workflow map validation
Confirm or correct the pipeline; note SSOT breaks.

### 4. Biggest information hierarchy problems
Top 5 ordering/clarity issues.

### 5. Repetition / redundancy audit
List duplicate metrics/narratives with suggested single home.

### 6. Smart KPI assessment
Global Drivers · VN Liquidity · Market Internals — completeness, units, decimals.

### 7. Visualization assessment
Which spec charts exist, which are missing/empty/decorative; data backing.

### 8. Data freshness / data quality assessment
Compact vs appendix; critical flags (scan mismatch, stale as_of).

### 9. B_cloud20_100 / A3_PRODUCTION strategy alignment
Scan SSOT, filter, watchlist, research leakage.

### 10. Portfolio Summary / Execution / Watchlist assessment
Health verdict, table usability (incl. wide columns), watchlist usefulness.

### 11. Number formatting issues
List offenders with file/section references.

### 12. Source-code issues
Bugs, dead paths, misleading names, security (no credentials in repo samples).

### 13. Test gaps
Missing cases; propose test names only (no live trading tests).

### 14. P0 patch list
Must-fix before next weekly run (report/ingest/template/tests only).

### 15. P1 improvement plan
High-value next sprint items.

### 16. P2 polish ideas
UX/copy/collapsible appendix, etc.

### 17. Open questions
Needs human decision (data source, holdings policy, etc.).

### 18. Final recommendation
Go / no-go for weekly operator use; what to verify after patches.

### 19. Prompt for Cursor — follow-up zip after patches

End your review with a **copy-paste block** for the user to give Cursor:

```
Cursor: After implementing your P0/P1 recommendations (report layer only; no trading logic):
1. Regenerate: python -m scripts.ingest.run_weekly_update && python -m scripts.reporting.render_weekly_report
2. Run: pytest tests/test_report_format.py tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py tests/test_weekly_report_p0_fixes.py -q
3. Rebuild: python -m scripts.reporting.build_weekly_report_3rd_ai_review_zip
4. Package for ChatGPT final review: attach outputs/review_packages/vn_weekly_report_3rd_ai_review.zip and paste your P0/P1 summary + before/after screenshots if any.
```

---

## What you must NOT recommend

- Changing live trading, DNSE, or order routers  
- Recomputing EMA/cloud in the report layer  
- Changing phase36 `final_action` semantics in production scan  
- Enabling real capital without updating `REAL_CAPITAL_READINESS.md` with evidence  

---

## Context: production strategy

- **Strategy:** A3_DP / B_cloud20_100 (EMA 20/100 cloud via phase36).  
- **Production classification:** `A3_PRODUCTION`.  
- **Report role:** Decision support — portfolio command, not signal generation.

Good luck. Be blunt, specific, and file-referenced.
