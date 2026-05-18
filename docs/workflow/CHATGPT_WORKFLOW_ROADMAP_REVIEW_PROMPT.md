# ChatGPT Review Prompt — VN Agent Workflow Cleanup + Roadmap + Order-Intent Dry Run

**Paste this entire file into ChatGPT and attach the zip:** `vn_workflow_roadmap_chatgpt.zip`

No prior chat context required.

---

## Your role

You are my **workflow architect and operating partner** for a Vietnam equities system (VN Agent System repo). Cursor has just implemented a **Pareto cleanup**, **stage-gate roadmap tracker**, and **order-intent dry run** (preview only — no broker orders).

Your job:

1. **Validate** the cleaned backbone matches how I actually operate (not repo fantasy).
2. **Tighten** Pareto further — what to keep vs cut for the next 90 days.
3. **Design** my weekly + monthly rhythm (time-boxed, day-job friendly).
4. **Define** when I advance from Stage 0 → Stage 1 → Stage 2 (evidence-based, not hype).
5. **Produce** a copy-paste **`## CURSOR_IMPLEMENTATION_PROMPT`** block for the next small Cursor batch (docs/automation only unless I explicitly approve strategy work).

---

## My actual operating reality (FACTS)

| I do regularly | Notes |
|----------------|-------|
| Weekly HTML command center | `reports/latest/index.html` |
| Manual EMA/cloud review | Sanity check — may disagree with phase36 CSV |
| Manual discretionary trades | Real broker — outside OMS today |
| Occasional portfolio screenshots | **Not SSOT** — ad-hoc only |
| 5 paper accounts | Recently built — **validation only**, not live capital |

| I do NOT do regularly (repo supports but defer) |
|------------------------------------------------|
| Council weekly, consensus/research packs |
| Full `run_weekly_full_fetch` every week |
| Daily `paper-accounts run-all` on all 5 accounts |
| Monthly CPR + council audit + trade review (all three) |
| Intraday scan for decisions |
| Quarterly automation |
| Copytrade / content monetization |

**Capital:** Real capital **NO-GO**. DSE/DNSE live **NO-GO**. `live_auto` **NO-GO**.

---

## What Cursor built (2026-05-17)

### Backbone (3 lanes — do not merge)

```text
Lane 1 — Weekly decision support (read-only HTML)
Lane 2 — Signal production (phase36 scan CSV, final_action SSOT)
Lane 3 — Paper execution (separate; not weekly report)
```

### New operator artifacts

| Artifact | Path |
|----------|------|
| Operating backbone | `docs/OPERATING_BACKBONE_PARETO.md` |
| Roadmap | `docs/ROADMAP_AND_STAGE_TRACKER.md` |
| Stage tracker YAML | `data/roadmap/stage_tracker.yaml` |
| Order-intent dry run doc | `docs/trading/ORDER_INTENT_DRY_RUN.md` |
| Readiness ladder | `docs/trading/AUTO_ACCOUNT_READINESS_LADDER.md` |
| Weekly script | `scripts/trading/weekly_pareto_operator.ps1` |
| Dry-run command | `python -m src.trading.cli generate-order-intent ...` |
| Roadmap status | `python -m src.review.cli roadmap-status` |
| Manual decision log | `templates/manual_decision_log_template.md` |
| Monthly review template | `templates/monthly_progress_review_template.md` |
| Implementation summary | `review_outputs/workflow_cleanup_and_roadmap_summary.md` |

### Stage gate (current)

| | |
|--|--|
| **Current** | Stage 0 — Manual decision-support |
| **Next** | Stage 1 — Order-intent dry run (`order_sent` always NO) |
| **Future** | Stage 2 tiny sandbox → 3 scale → 4 copytrade → 5 content |

**Do not recommend skipping to live/copytrade/content automation.**

### SSOT rules (non-negotiable)

- Positions: `data/raw/current_positions_derived.json` (FQuery `derive-current`)
- Signals: `phase36_daily_scan_latest.csv` — **OMS consumes `final_action` only**
- Manual cloud: sanity check + exception log only
- Screenshots: optional evidence — **not SSOT**
- `a3_rank_score`: review sort only — **not** trade signal
- No S3/intraday in production weekly path without labels
- Order-intent dry run: **This command does not send broker orders**

### Known friction (verify in zip / summary)

- ~8/14 holdings may show `OUTSIDE_A3_OR_NO_SCAN_MATCH` in dry-run CSV (discretionary book vs A3 universe)
- Council STATE vs scan `regime_bull` not fully merged in weekly HTML
- `manual_inputs_prev.json` often missing → weak WoW macro deltas

### Tests (Cursor ran)

- `tests/test_order_intent_dry_run.py` — **8 passed**
- Other trading suites not re-run in that session

---

## Hard constraints (do not violate)

- Do **not** recommend real capital, DNSE/DSE live, or `live_auto`
- Do **not** change A3 T1/T2/TP/trail/maxhold/breadth contract
- Do **not** promote S3 or PTS to production
- Do **not** route intraday CSV to OMS
- Do **not** recommend OMS signal recompute
- Do **not** build auto-posting stock buy/sell content bots
- Do **not** suggest managing follower passwords/accounts
- Pareto: total recurring **ops** time ≤ **90 min/week** excluding actual trading

---

## Questions you MUST answer

### 1. Backbone validation

One-page diagram (max 5 boxes). Confirm or correct the 3-lane model for **my** habits.

### 2. Pareto keep (≤7) with time budget

| # | Action | Minutes/week |
|---|--------|--------------|
| | | |

Total ops budget: ___ min/week.

### 3. Pareto cut (≥12) for 90 days

Explicit list of repo features to **ignore**.

### 4. Weekly checklist (≤10 lines)

Copy-paste ready for Sunday/post-close. Include whether to run **pilot+5B paper** weekly or only on scan-refresh days.

### 5. Monthly — one mandatory artifact first

Recommend **one** of: `trade-review-monthly` vs `monthly-review` vs `council-audit-monthly`.  
Define **quarterly** as rollup of N monthlies (no new tooling yet).

### 6. Conflict rules

Validate or improve the table in `OPERATING_BACKBONE_PARETO.md` (positions vs CSV vs manual cloud vs screenshots).

### 7. Screenshot placement

Keep ad-hoc, or replace with a 5-line weekly “portfolio delta” template?

### 8. Paper account cadence

Confirm: weekly **A3_DSE_PILOT_PAPER_SMALL + A3_PROD_PAPER_5B**; monthly **10B/20B/S3**. When is `run-all` worth it vs waste?

### 9. Stage 0 → 1 gate

Exact evidence checklist before I count a “clean weekly cycle” or “clean order-intent cycle”. What to log in `stage_tracker.yaml`.

### 10. Stage 1 → 2 gate (future)

What would convince **you** I am ready for 20–50m VND tiny sandbox? What must stay locked?

### 11. Discretionary holdings (outside A3 scan)

How should I label/track the ~8 names with no `A3_PRODUCTION` row without polluting production signals?

### 12. Scope creep alarm

Top 5 ways I will accidentally re-expand scope — and one sentence each on how to prevent.

---

## Required deliverable format

```markdown
# Workflow Backbone (validated)

## Pareto: Keep (≤7) + time budget
## Pareto: Cut (≥12)
## Weekly checklist (≤10 lines)
## Monthly checklist (≤6 lines)
## Quarterly (definition only)
## Conflict rules (final table)
## Screenshot policy
## Paper cadence (final)
## Stage 0→1 evidence checklist
## Stage 1→2 pre-conditions (future)
## Discretionary / outside-A3 book policy
## Risks if scope creeps back

## CURSOR_IMPLEMENTATION_PROMPT

(paste-ready block for Cursor Agent: ordered P0/P1 tasks only, file paths, acceptance tests, explicit "do not change strategy")
```

---

## ChatGPT command aliases (use in follow-ups)

| Alias | Meaning |
|-------|---------|
| **ParetoWeeklyRun** | Weekly decision-support only; no orders |
| **ManualCloudException** | Log template when cloud ≠ CSV |
| **RoadmapStatus** | `roadmap-status` / stage_tracker.yaml |
| **OrderIntentDryRun** | Preview CSV; `order_sent=NO` |

---

## Zip contents guide

| File | Why attached |
|------|----------------|
| `CHATGPT_WORKFLOW_ROADMAP_REVIEW_PROMPT.md` | This prompt |
| `CHATGPT_WORKSTREAM_PARETO_PROMPT.md` | Earlier Pareto context |
| `docs/OPERATING_BACKBONE_PARETO.md` | SSOT operating doc |
| `docs/ROADMAP_AND_STAGE_TRACKER.md` | Stage ladder |
| `data/roadmap/stage_tracker.yaml` | Current counters |
| `docs/trading/ORDER_INTENT_DRY_RUN.md` | Dry-run spec |
| `docs/trading/AUTO_ACCOUNT_READINESS_LADDER.md` | Sandbox ladder |
| `docs/trading/REAL_CAPITAL_READINESS.md` | NO-GO contract |
| `review_outputs/workflow_cleanup_and_roadmap_summary.md` | Cursor implementation summary |
| `weekly_pareto_operator.ps1` | Weekly wrapper |
| `order_intent_dry_run.py` | Dry-run code |
| Sample `order_intent_*.csv` | If present — real book shape |

---

## One-line opener (optional)

> Read the attached zip. You are my workflow architect. Apply Pareto 80/20 and stage-gate discipline. Answer all 12 questions and output the required deliverable format including CURSOR_IMPLEMENTATION_PROMPT. Do not recommend live capital or skip stages.

---

*End of prompt.*
