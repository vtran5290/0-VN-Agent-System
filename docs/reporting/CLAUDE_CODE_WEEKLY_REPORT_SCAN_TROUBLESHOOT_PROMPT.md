# Claude Code Prompt — Weekly Report + Phase36 Scan Troubleshoot

Copy **everything below the line** into Claude Code. Work in repo **VN Agent System** (Windows). Do **not** ask the user for FireAnt token unless a data pull is required and fails.

---

You are a **senior quant systems engineer** troubleshooting the **Weekly Report / Portfolio Command Center** and its join to the **phase36 daily scan CSV**. The operator reports:

1. **Many “missing” fields** in the HTML report (scan join, market pulse WoW, stops, breadth).
2. **Holdings show scan-missing** even after running phase36 scan.
3. **FPT and AAA appeared as “A3 candidates”** — operator says this makes no sense.
4. General distrust that the **rendered HTML reflects live production data**.

Your job: **prove what is wrong vs expected**, separate **FACTS vs INTERPRETATION**, fix **report-layer bugs only** (no scan signal recompute, no live trading), regenerate artifacts, and deliver a short operator memo.

---

## Non-negotiables (do NOT violate)

| Rule | Detail |
|------|--------|
| Scan SSOT | `final_action` / cloud / trail come **only** from phase36 CSV — report must **not** recompute EMA/cloud. |
| No `final_action` logic changes | Do not alter phase36 production classification or `final_action` rules in `pp_backtest/` unless user explicitly requests a scan-pipeline change. |
| No live trading | No DNSE, OMS, order routing, position sizing from report. |
| Capital | **NO-GO** per `docs/trading/REAL_CAPITAL_READINESS.md`. |
| `a3_rank_score` | Display/sort only — cannot create, block, or size orders. |
| S3 / research rows | `S3_RESEARCH_ONLY` must not appear as production “Buy Now” unless `show_research_watchlist: true` in config (it is **false** today). |
| VIN baseline | For market-health claims, read `docs/research/VIN_EMA_CLOUD_BASELINE.md` — dual **full vs ex-VIN**, cap-weight VNINDEX caveat 2025–2026. |
| Facts-first | Missing → label **Missing** / **Unknown**; never invent prices, scan rows, or macro numbers. |

---

## Architecture (SSOT chain)

```
src.report.weekly --render
  → data/decision/weekly_report.json (+ .md)

scripts.ingest.run_weekly_update
  → portfolio_decision_enrich.enrich_portfolio_decision_sections
  → weekly_lean_sections.attach_lean_report
  → data/processed/weekly_report.json

scripts.reporting.render_weekly_report
  → reports/latest/index.html
  → reports/archive/{date}/index.html
```

| Role | Path |
|------|------|
| Scan resolver | `scripts/ingest/scan_ssot.py` (`PHASE36_DAILY_SCAN_PATH` env > `phase36_daily_scan_latest.csv`) |
| Strategy filter | `config/weekly_report_strategy.yaml` → `A3_PRODUCTION` only for production join |
| Holdings | `data/raw/current_positions_derived.json` |
| Manual macro/market | `data/raw/manual_inputs.json`, `manual_inputs_prev.json` |
| Legacy sell hints | `data/alerts/sell_signals.json` (may **mismatch** scan — flag, do not silently override scan) |
| HTML template | `templates/weekly_report_lean.html.j2` |
| Format helpers | `scripts/reporting/report_format.py` |

**Regenerate production report (always run both):**

```powershell
cd "D:\V\0. VN Agent System"   # or actual repo root on disk
.venv\Scripts\python.exe -m scripts.ingest.run_weekly_update
.venv\Scripts\python.exe -m scripts.reporting.render_weekly_report
```

Open **`reports/latest/index.html`** — this is the **only** user-facing production artifact.  
Do **not** treat review zip / pytest output as production unless explicitly reconciled.

---

## CRITICAL: Production scan vs review fixture (common false alarm)

### Production scan SSOT

`data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv`

### Review-only fixture (pytest / 3rd-party zip)

| Path | Purpose |
|------|---------|
| `tests/fixtures/phase36_daily_scan_review_fixture.csv` | Pytest only; `tests/conftest.py` sets `PHASE36_DAILY_SCAN_PATH` |
| `samples/phase36_daily_scan_review_fixture.csv` | Bundled in review zip for AI review |

**Fixture uses fake tickers `ZX99` (NEW_T1) and `ZX98` (SKIP_LIQUIDITY)** — NOT real FPT/AAA.

If you see **FPT / AAA** in HTML or JSON:

1. Check **which scan file** was used (`watchlist_board.scan_source` in processed JSON).
2. Check env: `$env:PHASE36_DAILY_SCAN_PATH` — must be **empty** for production.
3. Ignore stale dirs: `outputs/review_packages/extracted_review_test*/` — pytest artifacts, not production.

**Stale HTML trap:** `outputs/review_packages/*/outputs/reports_latest_index.html` may show FPT/AAA from an old test run. Always prefer `reports/latest/index.html`.

---

## Verified facts from prior investigation (re-confirm before trusting)

### A. FPT / AAA in **live** production (as of last check)

| Symbol | In `phase36_daily_scan_latest.csv`? | In `reports/latest/index.html`? |
|--------|--------------------------------------|----------------------------------|
| FPT | **No row** (no active A3/S3 in last 40 bars) | **Not present** |
| AAA | **No row** | **Not present** |
| FRT | Yes — **S3_RESEARCH_ONLY / WATCH_ONLY** (sector label “FPT Retail”) | Not in A3 production watchlist if filter correct |

Live scan had **0** rows with `final_action == NEW_T1` or `SKIP_LIQUIDITY`.  
Watchlist banner: **“No Buy Now Candidates under A3_PRODUCTION.”**

### B. Why holdings show “scan missing” (14 holdings example)

Phase36 **only writes symbols** to daily scan when:

```text
a3_active OR s3_active   (signal within last 40 bars)
```

Code reference: `pp_backtest/portfolio_optimization_final_steps.py` (~line 1617: `if not a3_active and not s3_active: continue`).

| Category | Example tickers | Report behavior |
|----------|-----------------|-----------------|
| In scan as **A3_PRODUCTION** | NVL, HDB, MSB, VPB, HCM, GVR, PVS | Joined — show scan `final_action` |
| **Not in CSV** (no recent signal) | STB, BID, TCX, PDR | `row-noscan` — “no scan row — phase36 only outputs symbols with active A3 or S3 signal within last 40 bars” |
| In CSV as **S3_RESEARCH_ONLY** only | DXG, PHR, DPR | Not production join — “excluded from A3_PRODUCTION production book” |

This is **scan output scope**, not a stale-report bug after `run_weekly_update`.

### C. Other “Missing” labels (may be expected)

| UI area | Common cause |
|---------|----------------|
| Market Pulse Δ 1W | `manual_inputs_prev.json` market block missing or not wired |
| Breadth VN30>MA20 | `vn30_trend_ok` not in market levels payload |
| Trail / cloud on noscan rows | No A3 row → display Missing |
| NVL HOLD vs scan TRAIL_EXIT | Legacy `sell_signals` / tech_status mismatch — **real DQ flag** |

### D. Report-layer fixes already landed (verify still present)

- `scan_price_kVND_to_vnd()` — dist trail kVND scale
- `fmt_credit_growth` — credit % scale
- Split execution banners (scan-missing vs mismatch vs stops)
- `portfolio_scan_gap_reason()` — clearer noscan reasons
- Watchlist skips `SKIP_*` final_actions from display table
- Market pulse WoW from `manual_inputs_prev.market`

---

## Your mission — step-by-step

### Phase 1 — Environment & SSOT proof (no code changes)

1. Print repo root; confirm git branch (informational only).
2. Echo `$env:PHASE36_DAILY_SCAN_PATH` — must be empty for production check.
3. Resolve scan path via Python:

```powershell
.venv\Scripts\python.exe -c "from scripts.ingest.scan_ssot import resolve_scan_path; print(resolve_scan_path())"
```

4. Load holdings tickers from `data/raw/current_positions_derived.json`.
5. For **each holding**, classify against **live** `phase36_daily_scan_latest.csv`:

```powershell
.venv\Scripts\python.exe -c "
import json
import pandas as pd
from pathlib import Path
from scripts.ingest.scan_ssot import resolve_scan_path, load_scan_rows, load_scan_lookup_all

pos = json.loads(Path('data/raw/current_positions_derived.json').read_text(encoding='utf-8'))
holdings = [r['ticker'].upper() for r in pos.get('rows', pos) if isinstance(r, dict) and r.get('ticker')]
if not holdings and isinstance(pos, list):
    holdings = [r['ticker'].upper() for r in pos if r.get('ticker')]

p = resolve_scan_path()
df = pd.read_csv(p)
df['symbol'] = df['symbol'].astype(str).str.upper()
prod, _, _ = load_scan_rows(production_only=True, path=p)
full, _ = load_scan_lookup_all(path=p)
prod_syms = {r['symbol'].upper() for r in prod}
full_map = full

print('scan:', p)
print('as_of:', df['as_of_date'].iloc[0] if 'as_of_date' in df.columns else '?')
print('rows:', len(df), 'A3_PRODUCTION:', (df['strategy_classification']=='A3_PRODUCTION').sum())
print()
for t in sorted(holdings):
    if t in prod_syms:
        r = next(x for x in prod if x['symbol'].upper()==t)
        print(f'{t}: MATCH A3_PRODUCTION | {r.get(\"final_action\")}')
    elif t in full_map:
        r = full_map[t]
        print(f'{t}: IN SCAN NOT PROD | {r.get(\"strategy_classification\")} | {r.get(\"final_action\")}')
    else:
        sub = df[df['symbol']==t]
        print(f'{t}: NOT IN CSV (phase36 skipped — no a3_active/s3_active in 40 bars)')
"
```

6. Grep **production** HTML only:

```powershell
Select-String -Path reports\latest\index.html -Pattern 'FPT|AAA|ZX99|ZX98|scan_source|Buy Now|scan missing'
```

7. Compare `data/processed/weekly_report.json` keys: `watchlist_board.scan_source`, `execution.rows[].scan_missing`, `portfolio_command_center`.

**Deliverable after Phase 1:** Table — Holding | In CSV? | Classification | final_action | Report row_class | Root cause category.

---

### Phase 2 — Regenerate & diff

1. Run full weekly update + render (commands above).
2. Re-run Phase 1 checks.
3. Count execution rows: `scan_missing` true vs false; `action_mismatch` true.
4. List watchlist `candidates[:40]` tickers and buckets — confirm **no FPT/AAA** unless fixture path was used.
5. Run tests:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_weekly_report_review_fixture.py tests/test_weekly_report_p0_fixes.py tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py -q
```

---

### Phase 3 — Fix only what is broken

**Allowed report-layer fixes:**

- Wrong scan path resolution / env leakage into production
- Misleading UI labels (e.g. “A3 candidate” for S3 or SKIP rows)
- Missing `scan_gap_reason` / wrong bucket mapping in `watchlist_bucket()`
- `manual_inputs` / prev wiring for Market Pulse
- Template showing fixture data without disclaimer
- Stale packaged HTML in review zip builder pointing at wrong artifact

**Requires explicit user approval (separate proposal):**

- Phase36 emitting rows for **all open holdings** without active signal
- Changing `final_action` or A3 cloud logic in `pp_backtest/`
- Enabling `show_research_watchlist: true`

**Do not:**

- Commit secrets; commit only if user asks
- “Fix” noscan holdings by faking scan rows in report code

---

### Phase 4 — Operator memo (required format)

```markdown
## Weekly report troubleshoot — {date}

### Production SSOT used
- Scan: {path} | as_of: {date} | rows: {n}
- HTML: reports/latest/index.html | generated: {timestamp if available}
- PHASE36_DAILY_SCAN_PATH: {empty or WRONG PATH}

### Holdings vs scan ({n_holdings} positions)
| Ticker | Status | Why |
| ... |

### FPT / AAA / FRT
- FACTS: ...
- INTERPRETATION: ...

### Remaining Missing labels (by section)
| Section | Field | Status | Fix or expected? |

### Fixes applied (if any)
- file: reason

### If X → do Y
- If scan as_of < last trading day → re-run phase36 scan then run_weekly_update
- If env PHASE36_DAILY_SCAN_PATH set → unset and regenerate
- ...
```

---

## Files to read first (in order)

1. `docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md`
2. `scripts/ingest/scan_ssot.py` — `resolve_scan_path`, `load_scan_rows`, `watchlist_bucket`, `portfolio_scan_gap_reason`
3. `scripts/ingest/weekly_lean_sections.py` — `build_execution_scan_aligned`, `build_watchlist_a3`, `build_market_pulse`
4. `config/weekly_report_strategy.yaml`
5. `samples/REVIEW_FIXTURE_README.txt`
6. `data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv` (header + holdings rows)
7. `reports/latest/index.html` (Execution + Watchlist sections)
8. `tests/test_weekly_report_review_fixture.py` — documents fixture behavior

---

## Acceptance criteria (production)

- [ ] `reports/latest/index.html` built from **`phase36_daily_scan_latest.csv`**, not fixture
- [ ] `watchlist_board.scan_source` path ends with `phase36_daily_scan_latest.csv`
- [ ] **No FPT / AAA** in watchlist unless they appear in **live** scan with `A3_PRODUCTION` (unlikely; document if so)
- [ ] Each holding’s scan status explainable (match / S3-only / not in CSV)
- [ ] Scan-forced exits (e.g. NVL TRAIL_EXIT) in Immediate Actions
- [ ] Scan-missing holdings use `row-noscan` + explicit gap reason (not fake HOLD)
- [ ] `SKIP_*` rows not promoted as buy candidates in watchlist table
- [ ] Pytest suite above passes
- [ ] Operator memo delivered with FACTS vs INTERPRETATION separated

---

## Optional: holdings-always-in-scan (design note only)

If operator wants **zero noscan holdings** without changing signals:

- Add phase36 flag e.g. `--include-holdings path/to/current_positions_derived.json` to emit **HOLD_CONTEXT** rows (display-only) for symbols in book but without 40-bar signal.
- Report joins those rows with label **“No active A3 signal — position context only”**.
- Do **not** implement without explicit user sign-off.

---

## Review zip (secondary)

If user attached `outputs/review_packages/vn_weekly_report_3rd_ai_review.zip`:

- Use `outputs/reports_latest_index.html` inside zip **only** after confirming it was copied from latest `reports/latest/` at build time.
- Run pytest from extracted root: `pytest tests/test_weekly_report_review_fixture.py -q`
- Fixture tests **intentionally** use `ZX99`/`ZX98` — not production tickers.

---

End of prompt. Execute all phases; show command output snippets as evidence; propose minimal diffs only for confirmed bugs.
