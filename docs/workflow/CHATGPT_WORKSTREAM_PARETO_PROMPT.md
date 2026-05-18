# VN Agent System — Workstream Backbone & Pareto Streamlining Prompt

**Purpose:** Give this file (and optional zip of key docs) to **ChatGPT** so it can:
1. Clarify your **actual** operating backbone vs repo capabilities you do **not** use.
2. Apply **Pareto discipline** — keep the 20% that drives decisions; trim or defer the 80%.
3. Produce a **single implementation brief** for Cursor (concrete prompts, file paths, cadence).

**No prior chat context required.**

---

## A. Operator context (FACTS — as stated 2026-05-18)

| What you actually do regularly | Notes |
|--------------------------------|--------|
| **Weekly report** | Lean HTML command center (`reports/latest/index.html`) |
| **Manual cloud scan** | Your own cloud-strategy review (EMA cloud / B_cloud20_100 mindset) — may or may not match automated `phase36` CSV |
| **Manual trade** | Real discretionary execution at broker — **not** paper OMS unless you choose |
| **Portfolio screenshots** | Occasional; **not** a documented repo step — likely ad-hoc for ChatGPT/notes |
| **5 paper accounts** | Recently built — validation path, **not** live capital |

| What you are **not** doing regularly (repo supports but optional) | |
|-------------------------------------------------------------------|--|
| Council prompts → `council_output.json` | Makefile `council-weekly` exists |
| Consensus / research engine pack apply | `make consensus-apply`, `make research-pack-apply` |
| Full weekly fetch (FRED + SBV scrape + all layers) | `scripts/run_weekly_full_fetch.py` |
| Daily paper `run-all` on schedule | `scripts/trading/daily_paper_live_full_run.ps1` |
| Monthly CPR / trade postmortem / council audit | `make monthly-review`, `make trade-review-monthly`, `make council-audit-monthly` |
| Intraday scan for orders | Preview only — **must not** route to OMS |
| Quarterly review | **Does not exist** in repo |

**Capital verdict (repo SSOT):** `docs/trading/REAL_CAPITAL_READINESS.md` → **NO-GO** real capital; paper observation only.

---

## B. Repo backbone — three lanes (do not merge mentally)

```
LANE 1 — DECISION SUPPORT (weekly, read-only)
  Inputs → weekly report JSON/HTML
  SSOT for scan display: phase36_daily_scan_latest.csv (A3_PRODUCTION rows)
  Does NOT place orders

LANE 2 — SIGNAL PRODUCTION (batch, research)
  pp_backtest/portfolio_optimization_final_steps.py --step scan
  → phase36_daily_scan_latest.csv
  OMS reads final_action only — no EMA recompute in report or OMS

LANE 3 — EXECUTION (paper / future live)
  resolve-scan → paper-accounts run-all (5 accounts)
  Separate from HTML report generation
  Manual discretionary trades are OUTSIDE this lane unless logged
```

**Your manual cloud scan** may duplicate Lane 2 intellectually but is **not wired** unless you export/compare to `phase36_daily_scan_latest.csv`.

**Portfolio screenshots** are **not** ingested by repo today. Closest structured input:
- `data/raw/current_positions_derived.json` from FQuery Excel (`python -m src.review.cli derive-current`)
- See `docs/WEEKLY_FULL_FETCH.md`, `docs/OPEN_RISK_DASHBOARD.md`

---

## C. Canonical commands you care about

### Weekly report (what you use)

```powershell
# Prerequisite: holdings + scan + .env (FIREANT_TOKEN)
python pp_backtest/portfolio_optimization_final_steps.py --step scan
python -m src.review.cli derive-current          # FQuery Excel → positions JSON
python scripts/update_tech_status.py --asof YYYY-MM-DD --tickers <YOUR_14_TICKERS>

# Report
python -m scripts.ingest.run_weekly_update
python -m scripts.reporting.render_weekly_report
# → reports/latest/index.html
```

Or one-shot fetch: `python scripts/run_weekly_full_fetch.py` (heavier; many optional layers).

**Docs:** `docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md`

### Paper accounts (what you just built — next optimization candidate)

```powershell
python pp_backtest/portfolio_optimization_final_steps.py --step scan
python -m src.trading.cli resolve-scan --date YYYY-MM-DD --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv
python -m src.trading.cli paper-accounts run-all --date YYYY-MM-DD --scan-path <same_csv> --include-s3-shadow
```

Or: `.\scripts\trading\daily_paper_live_full_run.ps1`

**Accounts (config/paper_accounts.yaml):**
1. A3_DSE_PILOT_PAPER_SMALL (30M)
2. A3_PROD_PAPER_5B (5B)
3. A3_SCALE_PAPER_10B (10B)
4. A3_SCALE_PAPER_20B (20B)
5. S3_MAX60_SHADOW_PAPER (shadow only)

**Docs:** `docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md`, `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`

### Monthly (exists; you rarely run — Pareto candidate)

| Step | Command | Output |
|------|---------|--------|
| Council Performance Review | `make monthly-review` | `review/reports/monthly_report.md` |
| Trade lessons | `make trade-review-monthly` | lesson artifacts per `docs/TRADE_REVIEW_LAYER.md` |
| Council process audit | `make council-audit-monthly` | `data/decision/council_audit_monthly.md` |

**Quarterly:** no script — roll up 3× monthly or 12× weekly manually.

### Council weekly (repo “official” next step after weekly — you skip today)

```
make council-weekly  →  weekly + council secretary
ChatGPT CouncilRun   →  data/decision/council_output.json
```

**Docs:** `docs/CHATGPT_COMMAND_ALIASES.md`

---

## D. Weekly report — what it is for (60-second test)

Answers:
1. Increase / maintain / reduce exposure? → Regime + gross band + command center
2. Portfolio health? → Portfolio summary + data quality strip
3. Immediate actions? → Scan-forced exits + mismatches + scan-missing holdings
4. Healthy holds vs review? → Execution table (amber = no scan / UNKNOWN book)
5. Next buys under B_cloud20_100? → Watchlist (A3_PRODUCTION only)
6. What changed? → Market Pulse
7. Stale/missing data? → Data quality strip + appendix

**Not for:** auto-trading (use Lane 3); not for intraday entries (intraday = preview).

**Known gaps (2026-05-18):**
- Holdings outside A3 universe → “No production scan match” (e.g. STB, BID, TCX) — discretionary names, not report bug
- Council STATE A–E vs scan `regime_bull` / breadth — related but not fully merged (`docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md`)
- `manual_inputs_prev.json` often missing → weak WoW macro deltas
- Credit growth / DXY sanity flags in `manual_inputs.json`

---

## E. Pareto hypothesis (for ChatGPT to validate)

### Likely **essential 20%** (keep)

| # | Activity | Why |
|---|----------|-----|
| 1 | **Weekly report** after fresh **phase36 scan** + **positions JSON** | Single decision dashboard |
| 2 | **One scan SSOT** per week — align manual cloud review with `phase36_daily_scan_latest.csv` | Avoid double truth (manual vs CSV) |
| 3 | **Manual trade** with explicit log (even lightweight) | Postmortem and monthly lessons need data |
| 4 | **Paper `run-all` weekly or on scan refresh days** | Validates OMS before any live capital |
| 5 | **One monthly loop** (pick ONE: trade review OR council audit OR CPR — not all three at first) | Compounding lessons without weekly noise |

### Likely **defer / trim 80%** (unless proven ROI)

| Item | Reason to trim |
|------|----------------|
| Council weekly + consensus + research packs + earnings heatmap + bond snapshot | Heavy ChatGPT/curation; you don’t run today |
| Full `run_weekly_full_fetch` every week | Run subset: positions + scan + render only |
| Intraday scan for decisions | Preview only; confuses weekly SSOT |
| S3 shadow account daily | Research; not production |
| 4 scale paper accounts every day | Pareto: run **pilot 30M + prod 5B** weekly; 10B/20B monthly |
| Book backtests / pp_backtest ladders | Research, not operations |
| MCP / Cursor agent orchestra for daily ops | Overkill for solo operator |
| Quarterly formal pack | Build **after** monthly habit sticks |
| Portfolio screenshots as primary input | Replace with `derive-current` + optional single “portfolio snapshot” markdown you paste to ChatGPT |

---

## F. Alignment problem: your three truths

| Source | What it represents |
|--------|-------------------|
| **Manual cloud scan** | Your eyes + rules — may include names outside A3 universe |
| **phase36 CSV** | Automated A3_PRODUCTION `final_action` — OMS + weekly report execution column |
| **Manual trades** | What you actually hold — may lag `current_positions_derived.json` |

**ChatGPT must recommend ONE hierarchy**, e.g.:

1. **Positions:** FQuery derive (or broker export) → `current_positions_derived.json` weekly  
2. **Signals:** `phase36_daily_scan_latest.csv` after `--step scan`  
3. **Manual cloud:** sanity check only; if disagree with CSV, log exception in one line (decision log)  
4. **Screenshots:** optional archive for ChatGPT vision — not SSOT  

---

## G. Suggested operating cadence (draft for ChatGPT to refine)

### Weekly (Sunday or post-close)

| Order | Task | Time box |
|-------|------|----------|
| 1 | Update positions (`derive-current`) | 5 min |
| 2 | Run phase36 scan | 5–15 min |
| 3 | Generate + read weekly HTML | 15 min |
| 4 | Execute Immediate Actions (real account) | varies |
| 5 | Paper `run-all` on **pilot + 5B** only (optional) | 10 min |

### Monthly (first business day)

| Pick one starter pack | Command |
|-----------------------|---------|
| **Trade lessons** (if you log closes) | `make trade-review-monthly` |
| **Process audit** (if you use council at all) | `make council-audit-monthly` |
| **Governance metrics** | `make monthly-review` |

### Quarterly (manual until automated)

- Roll up: regime changes, hit rate on scan-forced exits, paper vs real slippage, 3 biggest process fixes.
- **Do not build tooling until monthly works 2–3 cycles.**

---

## H. Questions ChatGPT MUST answer (structured output required)

1. **Backbone diagram** — one page: max 5 boxes, your three lanes, what you touch weekly.
2. **Pareto keep list** — max 7 recurring actions with time budget (total ≤ 90 min/week ops excluding trading).
3. **Pareto cut list** — repo features to **ignore** for 90 days (explicit).
4. **Screenshot placement** — keep as ad-hoc, or replace with a 5-line weekly “portfolio delta” template?
5. **Manual cloud vs phase36** — single rule when they conflict.
6. **Paper accounts** — which 2 accounts weekly, which monthly, drop schedule for 10B/20B/S3.
7. **Monthly vs quarterly** — recommend **one** monthly artifact first; define quarterly as rollup of N monthlies.
8. **Council** — skip entirely vs one lightweight monthly substitute.
9. **Implementation priority for Cursor** — ordered P0/P1 list (max 10 items) for **automation/docs only**, no strategy change.
10. **Cursor handoff** — final section: `## CURSOR_IMPLEMENTATION_PROMPT` — copy-paste block for the IDE agent.

---

## I. Hard constraints for any recommendation

- **NO-GO** real capital, DNSE live, `live_auto` (`docs/trading/REAL_CAPITAL_READINESS.md`)
- **NO** OMS signal recompute; scan `final_action` is SSOT for paper/production path
- **NO** mix S3/intraday into weekly production report without labels
- **NO** duplicate macro metrics 3× in weekly HTML (already patched lean report)
- VIN ex-VIN dual reporting for research (`docs/research/VIN_EMA_CLOUD_BASELINE.md`) — optional for ops
- `a3_rank_score` = sort only, not trade signal

---

## J. Key file paths (SSOT)

| Artifact | Path |
|----------|------|
| Holdings | `data/raw/current_positions_derived.json` |
| Daily scan | `data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv` |
| Weekly processed | `data/processed/weekly_report.json` |
| Weekly HTML | `reports/latest/index.html` |
| Strategy config | `config/weekly_report_strategy.yaml` |
| Paper accounts | `config/paper_accounts.yaml` |
| Manual macro | `data/raw/manual_inputs.json` |
| Regime | `data/state/regime_state.json` |
| Allocation | `data/decision/allocation_plan.json` |

---

## K. Related docs to attach in zip (optional)

- `docs/trading/REAL_CAPITAL_READINESS.md`
- `docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md`
- `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`
- `docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md`
- `docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md`
- `docs/TRADE_REVIEW_LAYER.md`
- `docs/CHATGPT_COMMAND_ALIASES.md`
- `docs/WEEKLY_FULL_FETCH.md`
- `docs/trading/POST_PATCH_REVIEW_PROMPT_FOR_CHATGPT.md` (auto-trading review context)

---

## L. What Cursor already fixed (weekly report — 2026-05-18)

For context only; ChatGPT should not re-litigate unless trimming scope:

- Scan resolver prefers `phase36_daily_scan_latest.csv`
- Immediate actions from all `TRAIL_EXIT` holdings (not legacy sell_signals only)
- FireAnt prices via `.env` + OHLC `.c` fix
- Execution table horizontal scroll + Required action column
- Data quality Critical when scan missing / mismatch
- Narrative panels don’t repeat macro 3×

---

## M. Required ChatGPT deliverable format

```markdown
# Workstream Backbone (final)
## Pareto: Keep (≤7)
## Pareto: Cut (≥10)
## Weekly checklist (≤10 lines)
## Monthly checklist (≤6 lines)
## Quarterly (definition only)
## Conflict rules (manual cloud vs CSV vs manual trade)
## Paper account cadence
## Risks if scope creeps back
## CURSOR_IMPLEMENTATION_PROMPT
(paste-ready for Cursor Agent — ordered tasks, files, acceptance tests)
```

---

*End of prompt. Attach this file to ChatGPT. Ask it to output section M in full.*
