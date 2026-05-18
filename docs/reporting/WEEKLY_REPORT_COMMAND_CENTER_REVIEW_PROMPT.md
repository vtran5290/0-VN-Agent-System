# External AI Review Prompt — Weekly Report Portfolio Command Center

**Attach zip:** `vn_weekly_report_command_center_review.zip`  
**Repo:** VN Agent System (Vietnam weekly investment + EMA-cloud trading stack)  
**As-of sample in zip:** 2026-05-17

Copy everything below the line into your review chat.

---

You are a **senior quant + product engineer** reviewing a reporting upgrade: the weekly HTML report was extended from a macro dashboard into a **portfolio decision command center**. The owner also wants a concrete plan to **sync this report with the production strategy** (`B_cloud20_100` / **A3_DP** EMA 20/100 cloud breakout), and to allow future strategies once validated.

## Your deliverables

1. **Architecture review** — data flow, separation of facts vs interpretation, missing-data handling  
2. **UX / decision usability** — can an operator answer in **60 seconds**: exposure up/down, forced sells, healthy holds, next buys, plan-changing signals, stale/missing data?  
3. **Strategy alignment review** — gap analysis vs `B_cloud20_100` / phase36 scan SSOT (see `docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md` in zip)  
4. **Prioritized patch list** — P0 (correctness/safety), P1 (strategy sync), P2 (nice-to-have)  
5. **Test gaps** — what to add to `tests/test_portfolio_command_center_report.py`  
6. **Do NOT** propose changing live order logic unless you flag it as a separate “trading engine” change with explicit NO-GO boundaries from `docs/trading/REAL_CAPITAL_READINESS.md`

## Read first (in zip order)

| # | File | Why |
|---|------|-----|
| 1 | `REVIEW_PROMPT.md` | This file |
| 2 | `docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md` | Strategy sync target state |
| 3 | `docs/trading/REAL_CAPITAL_READINESS.md` | Frozen production contract (A3_DP, NO-GO capital) |
| 4 | `docs/research/VIN_EMA_CLOUD_BASELINE.md` | ex-VIN dual reporting, VNINDEX distortion |
| 5 | `scripts/ingest/portfolio_decision_enrich.py` | Command center + execution enrich logic |
| 6 | `templates/weekly_report_portfolio_blocks.j2` | Command center + WoW HTML |
| 7 | `samples/processed_weekly_report_keys.json` | Schema surface (trimmed) |
| 8 | `samples/index.html` | Rendered output (open in browser) |
| 9 | `data/research/.../phase36_daily_scan_schema.csv` | Scan column contract |

## What was built (Tasks 2–12 summary)

### New / upgraded HTML sections

- **Portfolio Command Center** — regime, gross band, buy/add/trim/stop modes, highest-priority action, data quality  
- **What Changed Since Last Week** — macro/liquidity/market WoW table  
- **Regime Rules** — A–E table; current row highlighted (STATE B → gross **50–60%**, restricted new buys)  
- **Decision** — Immediate / Conditional / Do-not-do  
- **Watchlist board** — buckets from phase36 scan CSV (or config fallback)  
- **Execution** — 16-column position table (sector, weight, cost, last, P/L%, R, stop, MA20/50, technical, action, next trigger)  
- **Portfolio Risk Summary** — concentration, MA breaches, active sell count  
- **Portfolio Health** — sector limits (30% sector / 12% name), unmapped ticker warning  
- **Decision Review** — prior-week log or schema placeholder  
- **Data Freshness** — per-block source/stale flags  

### Pipeline (do not edit generated HTML by hand)

```
src.report.weekly --render  →  data/decision/weekly_report.json
normalize_weekly_report()  →  portfolio_decision_enrich.enrich_*  →  data/processed/weekly_report.json
render_weekly_report.py      →  reports/latest/index.html
```

Entry command:

```powershell
python -m scripts.ingest.run_weekly_update
python -m scripts.reporting.render_weekly_report
```

Full fetch (macro + positions + downtrend): `python scripts/run_weekly_full_fetch.py`

## Regime → exposure rules (implemented in enrich)

| Regime | Gross band | New buys | Adds | Trims | Stops |
|--------|------------|----------|------|-------|-------|
| A Risk-on | 70–90% | Allowed | Breakouts/reclaims | Weak only | Normal |
| **B Fragile uptrend** | **50–60%** | **Restricted** | Leaders / confirmed only | Active | Normal–tight |
| C Tight+tight | 20–40% | No | No | Aggressive | Tight |
| D Correction | 0–25% | No | No | Exit weak | Hard stop |
| E Recovery | 30–50% | Pilot only | Small tests | Strict | Normal |

**Current sample (2026-05-17):** STATE B, gross 55%, **MWG SELL/EXIT** (Day-2 confirmation breach) in highest-priority slot.

## Known gaps / stale inputs (FACTS from last render)

| Input | Status | Effect |
|-------|--------|--------|
| `manual_inputs_prev.json` | Often missing | WoW “last week” = Missing |
| `tech_status.json` | Stale (~2026-03-28) | MA20/50/stop often Missing in execution table |
| FireAnt last close | Token/fetch dependent | Current price Missing → partial risk metrics |
| `decision_log/*.json` | Minimal structure | Decision Review is placeholder |
| Fundamental thesis per ticker | Not wired | Shows “Missing” |
| **Strategy filter on watchlist** | **Not implemented** | Watchlist mixes all scan rows; not filtered to `B_cloud20_100` / `A3_PRODUCTION` only |

## Strategy sync question (primary extension request)

**Production SSOT today:** phase36 daily scan CSV (`final_action`, `tp1_price`, `trail_price`, `pb_trigger_price`, `strategy_classification`, `breadth_zone`, cloud flags `a3_cloud_bull`, etc.). Strategy family **B_cloud20_100** = EMA **20/100** cloud (see `docs/ema_cloud_strategy_spec.md` and AFL `Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` in repo).

**Weekly report today uses:**

- Generic `sell_signals.json` + `tech_status.json` for execution (not scan-native triggers)  
- Watchlist from latest `phase36*daily_scan*.csv` but **no `strategy_id` / active-strategy filter**  
- Regime A–E from council/regime engine (not `regime_bull` / `pct_cloud_bull_a3` from scan)  
- Portfolio positions from FQuery Excel derive (not tagged with which strategy book owns the line)

**Please design** (no code required in review, but be specific):

1. Config: `active_production_strategy: B_cloud20_100` (and future strategies as validated)  
2. Watchlist: filter `strategy_classification == A3_PRODUCTION` + map buckets from `final_action`  
3. Execution table: per-row `final_action`, `trail_price`, `tp1_price`, `pb_trigger_price`, `a3_cloud_bull`, `breadth_zone` from scan join on ticker  
4. Command center: optional second line “Cloud regime (VNINDEX EMA20/100): bull/bear” + `pct_cloud_bull_a3` with VININDEX caveat from baseline doc  
5. Regime rules: either map council STATE ↔ cloud regime or show both side-by-side without contradiction  
6. Position book: tag each holding with `strategy_book` when multiple strategies run in research  

## Acceptance criteria (verify against `samples/index.html`)

Within 60 seconds the operator should answer:

- [ ] Increase, maintain, or reduce exposure?  
- [ ] Which positions must sell/trim? (MWG forced exit visible?)  
- [ ] Which are healthy holds?  
- [ ] Next buy candidates? (watchlist buckets populated or explicit empty message)  
- [ ] What market signal changes the plan? (conditional actions + WoW)  
- [ ] What data is missing or stale? (banners + data freshness table)  

## Tests in zip

`tests/test_portfolio_command_center_report.py` — 8 tests (regime B band, forced exit priority, regime highlight, sector unmapped warning, render smoke).  
Note: 3 older regression tests in `test_weekly_report_regression.py` may fail on VNINDEX snapshot vs latest_market (pre-existing).

## Review tone

- Facts vs interpretation separated  
- No invented metrics — “Missing” preferred  
- FireAnt/proxy disclosure when relevant  
- Flag VIN contamination on aggregates (VIC/VHM/VRE; exclude VPL &lt;252 bars)  
- Do not treat cap-weight VNINDEX alone as broad health in 2025–2026 without breadth caveat  

## Output format

```markdown
## Verdict (1 paragraph)
## P0 issues
## P1 strategy sync plan (ordered steps)
## P2 improvements
## Test recommendations
## Open questions for owner
```

---

_End of prompt. Zip built by `scripts/reporting/build_weekly_review_zip.py`._
