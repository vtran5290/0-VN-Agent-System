# Institutional Accumulation Scan — Operator Output Layer

## What was added

| Output | Role |
|--------|------|
| `institutional_accumulation_operator_summary_{date}.html` | **Start here (browser)** — lean dark UI, sidebar nav |
| `institutional_accumulation_operator_summary_{date}.md` | Same content, markdown |
| `institutional_accumulation_operator_summary_{date}.json` | Same content, machine-readable |
| `institutional_accumulation_weekly_brief_{date}.md` | Weekly-style research brief (edit macro sections here) |
| `institutional_accumulation_weekly_brief_{date}.html` | **Auto-synced from weekly brief MD** on every scan |
| `institutional_accumulation_compact_{date}.json` | Dated copy alongside `data/decision/..._compact.json` |
| CSV columns: `primary_driver`, `secondary_driver`, `main_risk`, `operator_note`, `reject_failure_reason` | Rule-based explainers (derived only) |
| Enhanced `institutional_accumulation_compact.json` | tier2_focus, tier3_near_miss (always), bucket diagnostics, warnings, important rejects |

## Why it helps

- Answers **what to open first** without reading 1,500-row CSV.
- Separates **fund-backed**, **emerging**, **important rejects**, and **caution** names.
- Surfaces **bucket skew** and workflow warnings (no Tier 1, outside_fund dominance, VIN flags).
- Keeps **weekly/council** file small but actionable.

## What was NOT changed

- Scoring weights, tiers, emerging gates, ETF exclusion, VIN rules.
- Execution, OMS, `final_action`, A3/S3, DNSE, orders.

## HTML acceptance (auto-checked on write)

Every scan run writes `institutional_accumulation_operator_summary_{date}.html` via `operator_summary_html.py`. `write_operator_summary_html` fails closed if:

- `operator_summary_html` key present in pipeline `outputs` dict  
- All **11 sections** present: `snapshot` → `changes` → `fund-backed` → `emerging` → `rejects` → `distortion` → `warnings` → `signals` → `playbook` → `files` → `appendix` (plus `header` overview)
- **Appendix** (`#appendix`): liquid universe tiers from scan CSV (`liquidity_ok=True`) — Tier 1/2/3 tables; display-only, loaded by `_liquid_appendix_html()` in `operator_summary_html.py`  
- KPI grid wired (`tier_counts`, emerging, caution-proxy)  
- `IntersectionObserver` scroll-spy on sidebar links  
- `.md` and `.json` unchanged paths in `outputs`  
- `weekly_diff.py` compact pointer → `.html`  

Stable shortcut after each run: `outputs/scans/institutional_accumulation_operator_summary_latest.html`

## Workflow

1. Monthly Smart Money composite  
2. `make institutional-accumulation-scan` or  
   `python -m src.scans.institutional_accumulation.run --as-of YYYY-MM-DD --smart-money-month 2026-04`  
   - **Market/OHLCV:** `--as-of` or latest VNINDEX bar  
   - **Fund context:** `--smart-money-month 2026-04` (April priors until monthly file exists)  
   - Writes operator summary **.md + .json + .html** and refreshes weekly brief HTML from `.md`  
3. Open `institutional_accumulation_operator_summary_{date}.html` or `_latest.html` (operator cards)  
4. After editing weekly brief MD only:  
   `python -m src.scans.institutional_accumulation.run --sync-weekly-html --as-of YYYY-MM-DD`  
5. Use `institutional_accumulation_compact.json` in weekly packet  
6. Human research — separate execution workflow  

## Modules

- `operator_explain.py` — deterministic explain columns  
- `operator_diagnostics.py` — bucket mix + warnings  
- `operator_summary.py` — operator MD/JSON
- `operator_summary_html.py` — HTML renderer (IBM Plex lean theme; generated each scan)  
- `weekly_brief.py` / `weekly_brief_html.py` — weekly brief MD skeleton + MD→HTML sync  
- `weekly_diff.py` — compact + diff enhancements  
