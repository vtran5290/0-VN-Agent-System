# ChatGPT Review Prompt — Stage 0 Operator Workflow (Full Stack Optimization)

**Paste this entire file into ChatGPT (High / Codex).**  
**Attach:** `stage0_operator_workflow_chatgpt_YYYYMMDD.zip` (build below).

No prior chat context required.

---

## Your role

You are my **workflow architect and efficiency partner** for the **VN Agent System** — a Vietnam equities **Stage 0** stack (manual execution, no live auto-trading).

**Goal:** Streamline and optimize how I operate **day-job friendly** — without strategy creep, SSOT duplication, or bloating the weekly path.

**Deliver:**

1. **One-page operator rhythm** — daily EOD (minutes) + weekly (time-boxed) + monthly (light).
2. **Consolidated SSOT map** — every question → one file → one command.
3. **Workstream de-duplication** — what runs in parallel vs what must never merge.
4. **Pareto tightening** — cut list validation for next 90 days.
5. **Tooling role matrix** — Cursor vs Claude Code vs ChatGPT vs me (what to stop doing in chat).
6. **Friction & automation gaps** — ranked P0/P1 with effort estimate.
7. **`## CURSOR_IMPLEMENTATION_PROMPT`** — only if gaps need repo changes (docs + small scripts; **no** A3/S3/`final_action`/OMS/live).

**Do not recommend:** changing `final_action`, breadth gates, T1/T2 sizing, exit policy, broker submission, `live_auto`, DNSE/DSE live, intraday→OMS, or merging Distribution Risk / Institutional Accumulation into production signals.

---

## Operating facts (locked)

| Item | Value |
|------|--------|
| **Stage** | 0 — Manual decision-support (**CURRENT**) |
| **Next stage** | 1 — Order-intent dry run (`order_sent` always NO) |
| **Real capital** | **NO-GO** |
| **Production action** | `phase36_daily_scan_latest.csv` → **`final_action` only** |
| **Weekly command center** | `reports/latest/index.html` |
| **Daily full board** | `data/research/reports/cloud_daily_report_latest.html` |
| **Daily text packet** | `data/decision/daily_scan.md` |
| **Distribution Risk SSOT** | `data/research/market_risk/distribution_risk_latest.json` (context only) |
| **Positions SSOT** | `data/raw/current_positions_derived.json` |
| **NAV** | `data/trading/live/portfolio_state.json` (user-updated) |
| **Screenshots** | Not SSOT |
| **Intraday** | Preview only — no OMS |
| **Legacy dist_session_*** | Not SSOT |

**Data discipline (FireAnt):** source = FireAnt REST + repo CSV; ex-VIN = proxy-derived; VNINDEX cap-weight may be VIN-skewed 2025–2026; lens probabilities = historical conditional estimates, not forecasts.

---

## What I actually do (honest baseline)

| Cadence | Reality |
|---------|---------|
| **Weekly** | Read `reports/latest/index.html`; manual cloud sanity check; discretionary broker trades |
| **Daily EOD** | New: `eod_market_context_refresh.ps1` (~30s) → cloud board + lens + scan |
| **Session** | Cursor `check dist` or read `distribution_risk_latest.html` |
| **Research parallel** | Institutional accumulation weekly brief (Tier 1–2 names) — **not** production orders |
| **Paper (5 accts)** | Validation only — not weekly workload for all accounts |
| **Defer** | Council weekly, full fetch, intraday OMS, copytrade, content bot |

---

## Three lanes (do not merge)

```text
Lane 1 — Weekly decision support (read-only HTML)
  weekly_pareto_operator.ps1 → reports/latest/index.html

Lane 2 — Signal production (SSOT)
  phase36 scan → phase36_daily_scan_latest.csv → final_action

Lane 3 — Paper / future execution (separate)
  paper accounts, order-intent dry run — not weekly report body
```

**Parallel context lanes (read-only, never override Lane 2):**

```text
[5a] Distribution Risk Lens → distribution_risk_latest.json/.html
[5b] Institutional Accumulation → outputs/scans/institutional_accumulation_weekly_brief_*.html
[5c] Research Intake → data/research/intake/ (cards + research_index.csv) — thesis/watchlist only
```

Research intake does **not** set or override `final_action`. See `docs/research/RESEARCH_INTAKE_WORKFLOW.md`.

---

## Canonical commands (2026-05-22 state)

### Daily EOD (after HOSE close)

```powershell
.\scripts\trading\eod_market_context_refresh.ps1 -Date YYYY-MM-DD -OpenCloudReport
```

Sequence: FireAnt OHLCV append → ex-VIN rebuild → `distribution-risk` → phase36 scan → `daily_scan.md` → cloud EOD.  
**~27s** when OHLCV cached. Banner: NO ORDERS.

### Weekly (Sunday or chosen day)

```powershell
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "STB,HDB,..."
# Optional if lens stale:
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "..." -RefreshMarketContext
```

7 Pareto actions max — see `docs/OPERATING_BACKBONE_PARETO.md`. Distribution Risk is **not** an 8th action.

### Status / dry run

```powershell
python -m src.review.cli roadmap-status
python -m src.trading.cli generate-order-intent --date YYYY-MM-DD ...
python -m src.trading.cli validate-order-intent --path data/trading/order_intent/order_intent_YYYY-MM-DD.csv
```

### Institutional accumulation (research — weekly council read)

```powershell
python -m src.scans.institutional_accumulation.run --as-of YYYY-MM-DD
```

Does **not** set `final_action`. Compact JSON: `data/decision/institutional_accumulation_compact.json`.

---

## SSOT map (verify in zip)

| Question | SSOT | Refresh |
|----------|------|---------|
| What to do per symbol? | `phase36_daily_scan_latest.csv` → `final_action` | `--step scan` |
| Holdings for report? | `current_positions_derived.json` | `derive-current` |
| NAV / lots? | `portfolio_state.json` | user |
| Market dist context? | `distribution_risk_latest.json` | `distribution-risk` CLI |
| Daily board? | `cloud_daily_report_latest.html` | `cloud-daily-report --mode eod` |
| Weekly center? | `reports/latest/index.html` | `weekly_pareto_operator.ps1` |
| Accumulation research? | `institutional_accumulation_weekly_brief_*.html` | `institutional_accumulation.run` |
| Order preview? | `order_intent_YYYY-MM-DD.csv` | `generate-order-intent` |

---

## Pareto cut list (90 days — validate)

From `OPERATING_BACKBONE_PARETO.md` §D: council, consensus packs, full weekly fetch, intraday→OMS, daily S3 shadow workload, screenshots-as-SSOT, live_auto, copytrade marketing, etc.

**Ask:** Is anything on the keep list actually waste for me? Is anything on the cut list still sneaking into my routine?

---

## Known friction (optimize these)

| Friction | Evidence in zip |
|----------|-----------------|
| Two EOD entry points | `eod_market_context_refresh.ps1` vs `daily_eod_operator.ps1` |
| ~8/14 holdings `OUTSIDE_A3` in order-intent | dry-run CSV sample |
| Council STATE vs scan `regime_bull` not merged | weekly HTML |
| `manual_inputs_prev.json` often missing | weak WoW macro |
| Institutional vs Distribution vs Phase36 — operator confusion | three parallel outputs |
| Stage tracker counters at 0 | `stage_tracker.yaml` |
| ChatGPT re-explaining repo every session | need stable aliases |

---

## Recent repo evolution (FACTS — check `README_GIT_LOG.txt` in zip)

| Area | Status |
|------|--------|
| Distribution Risk Lens v1.2 | JSON + HTML + MD; Cloud Section G; daily_scan section |
| EOD wrapper | `eod_market_context_refresh.ps1` |
| Operator integration runbook | `DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md` |
| Pareto backbone + weekly script | `OPERATING_BACKBONE_PARETO.md`, `weekly_pareto_operator.ps1` |
| Order-intent dry run + validation | v3 placeholder-date guard |
| Institutional accumulation v1.1 | weekly brief HTML + compact JSON |
| Dual-cloud Wyckoff research | closed — do not reopen in weekly ops |

---

## Required output format

```markdown
## Executive summary
(≤6 bullets: fit, biggest waste, top win)

## One-page operator rhythm
| When | Minutes | Steps | Open which file |
|------|---------|-------|-----------------|
| Daily EOD | | | |
| Weekly | | | |
| Monthly | | | |

## Consolidated SSOT map
(table — question → file → command → cadence)

## Workstream matrix
| Workstream | SSOT | Overrides final_action? | Weekly? | Daily? |
|------------|------|-------------------------|---------|--------|

## Pareto recommendations
### Keep (7 max)
### Cut harder
### Optional (monthly only)

## Tooling role matrix
| Task | Cursor | Claude Code | ChatGPT | Me |
|------|--------|-------------|---------|-----|

## Friction fixes (ranked)
| P | Issue | Fix type | Effort | Owner |
|---|-------|----------|--------|-------|

## Stage gate advice
(When to move 0→1 — evidence-based)

## EOD acceptance template
(copy-ready checklist for daily close)

## CURSOR_IMPLEMENTATION_PROMPT
(copy-paste for Cursor — docs/scripts only; or "_None_")
```

---

## Build attachment zip

```powershell
cd "c:\Users\LOLII\Documents\V\0. VN Agent System"
.\.venv\Scripts\python.exe -m scripts.workflow.build_stage0_operator_workflow_chatgpt_zip
```

Attach: `outputs/review_packages/stage0_operator_workflow_chatgpt_YYYYMMDD.zip`

---

## Acceptance criteria for your review

- [ ] Daily EOD ≤ 5 operator decisions (run/skip/open)
- [ ] Weekly ≤ 7 recurring actions
- [ ] No workstream implies lens or accumulation overrides `final_action`
- [ ] Clear file to open for each question (no "check 4 places")
- [ ] ChatGPT aliases map 1:1 to scripts
- [ ] Monthly/quarterly explicitly lighter than weekly

---

*End of prompt.*
