# Operating Backbone (Pareto)

**Current stage:** Stage 0 — Manual decision-support.  
**Real capital: NO-GO.** **OMS consumes final_action only.** **Manual cloud scan is sanity check only.** **Screenshots are not SSOT.** **Order-intent dry run sends no orders.**

---

## A. Current workflow

| Layer | What you do | Repo role |
|-------|-------------|-----------|
| Weekly command center | Read `reports/latest/index.html` | Lane 1 — decision support |
| Manual cloud / EMA review | Sanity check vs CSV | Exception log only — not SSOT |
| Manual discretionary trades | Broker execution | Real execution today |
| Paper accounts (5) | Validation only | Lane 3 — not live capital |
| Order-intent dry run | Human preview CSV | Stage 1 bridge — **no orders** |

- **Weekly report** is the main command center.
- **Manual cloud scan** is a sanity check only.
- **Manual trades** are the real current execution layer.
- **Paper accounts** are validation only, not the destination.
- **No live auto-trading** is enabled (`live_auto`, DNSE/DSE live: NO-GO).
- **Copytrade / content business** is future roadmap only — not current ops.

---

## B. Simple backbone diagram

```text
[1] POSITIONS SSOT
FQuery / broker export
→ data/raw/current_positions_derived.json

[2] SIGNAL SSOT
phase36 scan
→ phase36_daily_scan_latest.csv
→ final_action only

[3] WEEKLY DECISION SUPPORT
run_weekly_update + render_weekly_report
→ reports/latest/index.html

[4] MANUAL DECISION LAYER
manual cloud exception log
manual trade log
screenshots optional only

[5] FUTURE BRIDGE
order-intent dry run
→ tiny real sandbox later
→ copytrade/content later
```

---

## C. Pareto keep list (max 7 recurring actions)

1. **Update positions** — `derive-current` → positions JSON  
2. **Run phase36 scan** — `--step scan` → `phase36_daily_scan_latest.csv`  
3. **Generate weekly report** — lean HTML command center  
4. **Review** regime, immediate actions, holdings mismatch, data quality strip  
5. **Log manual cloud exceptions** — when cloud view ≠ CSV (`templates/manual_decision_log_template.md`)  
6. **Log actual manual trades** — broker truth for monthly lessons  
7. **Generate order-intent dry run** — preview only; `order_sent` always NO  

**Weekly paper cadence: A3_DSE_PILOT_PAPER_SMALL + A3_PROD_PAPER_5B**  
**Monthly only: A3_SCALE_PAPER_10B, A3_SCALE_PAPER_20B, S3_MAX60_SHADOW_PAPER**

---

## D. Pareto cut list (ignore 90 days)

1. Council weekly (`make council-weekly`) unless you explicitly restart it  
2. Consensus apply (`make consensus-apply`)  
3. Research pack apply (`make research-pack-apply`)  
4. Full weekly fetch every week (`run_weekly_full_fetch.py` — use lean subset)  
5. Intraday orders / intraday → OMS routing  
6. Daily S3 shadow as weekly workload  
7. Weekly 10B/20B scale paper accounts  
8. Quarterly formal tooling (rollup from monthlies manually)  
9. Screenshots as SSOT  
10. Backtest ladders during weekly ops  
11. MCP / agent orchestra for routine weekly ops  
12. Earnings heatmap / bond snapshot bloat in weekly path  
13. `live_auto`  
14. Copytrade marketing before verified track record  
15. Content bot auto-posting stock calls  

---

## E. Weekly checklist

```powershell
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "STB,HDB,MSB,..."
```

Or step-by-step:

```powershell
python -m src.review.cli derive-current
python pp_backtest/portfolio_optimization_final_steps.py --step scan
python scripts/update_tech_status.py --asof YYYY-MM-DD --tickers <YOUR_TICKERS>
python -m scripts.ingest.run_weekly_update
python -m scripts.reporting.render_weekly_report
# Open reports/latest/index.html
# Review regime / immediate actions / holdings / data quality
# Log manual cloud exceptions
# Log manual trade decisions
python -m src.trading.cli generate-order-intent --date YYYY-MM-DD --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv --positions-path data/raw/current_positions_derived.json --output data/trading/order_intent/order_intent_YYYY-MM-DD.csv
```

---

## F. Monthly checklist

**One mandatory artifact first:** `make trade-review-monthly` (or `python -m src.review.cli run-monthly` after trade history import).

- Council audit (`make council-audit-monthly`) — **not** mandatory yet  
- CPR (`make monthly-review`) — **not** mandatory yet  
- Use `templates/monthly_progress_review_template.md` for stage-gate decision  

---

## G. Outside-A3 holdings (discretionary book)

Holdings without an `A3_PRODUCTION` scan row are **not** production signals.

| Label | Use |
|-------|-----|
| `A3_PRODUCTION_MATCHED` | In scan + order-intent dry run |
| `DISCRETIONARY_OUTSIDE_A3` | Manual book; no OMS action |
| `LEGACY_POSITION` | Pre-A3 / migrate or exit |
| `WATCHLIST_ONLY` | Radar only |
| `RESEARCH_SHADOW` | S3/research; never production capital |

Template: `templates/outside_a3_holding_review_template.md`  
Order-intent dry run sets `holding_classification=DISCRETIONARY_OUTSIDE_A3` and does **not** create production orders for these names.

## H. Conflict rules

| Conflict | Rule |
|----------|------|
| Position mismatch | Broker/FQuery-derived positions win; fix positions JSON |
| Manual cloud says buy, CSV says no buy | No production automated buy; discretionary only if logged |
| CSV says TRAIL_EXIT, manual says hold | Red flag; override requires reason + invalidation level |
| Manual trade has no scan match | Label discretionary / outside-A3 |
| Screenshot differs from structured data | Structured data wins |
| S3 says buy, A3 does not | Research only |
| Intraday preview says action | No OMS action; EOD only |
| a3_rank_score ranks high | Review priority only, not trade signal |

---

## I. Paper cadence

| Cadence | Accounts |
|---------|----------|
| **Weekly** | `A3_DSE_PILOT_PAPER_SMALL`, `A3_PROD_PAPER_5B` |
| **Monthly** | `A3_SCALE_PAPER_10B`, `A3_SCALE_PAPER_20B`, `S3_MAX60_SHADOW_PAPER` |

- **S3** remains shadow/research only — not production P&L.  
- **10B/20B** are scale/capacity checks, not weekly workload.  
- Paper accounts validate future OMS readiness but are **not** the destination.

See also: `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`, `docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md`.

---

## J. Mental models (short)

| Model | Application |
|-------|-------------|
| Pareto | 7 weekly actions above; defer cut list 90 days |
| Single SSOT | Positions JSON, scan CSV, weekly HTML — one owner each |
| Theory of Constraints | Trust = fresh data + explainable action + fail-closed |
| OODA | Observe (report) → Orient (cloud sanity) → Decide → Act (manual trade; dry run next) |
| Stage-Gate | Stage 0 now → Stage 1 dry run → sandbox → scale → copytrade → content |
| Inversion | Design for stale scan, duplicate truth, S3/intraday leaks |
| Barbell | A3 conservative; S3/intraday/content isolated |

---

## K. Related docs

| Doc | Purpose |
|-----|---------|
| `docs/ROADMAP_AND_STAGE_TRACKER.md` | Long-term stages and gates |
| `docs/trading/ORDER_INTENT_DRY_RUN.md` | Dry-run command and rules |
| `docs/trading/AUTO_ACCOUNT_READINESS_LADDER.md` | Sandbox → copytrade ladder |
| `docs/business/COPYTRADE_AND_CONTENT_ROADMAP.md` | Future business only |
| `data/roadmap/stage_tracker.yaml` | Machine-readable stage state |

**Roadmap status:** `python -m src.review.cli roadmap-status`
