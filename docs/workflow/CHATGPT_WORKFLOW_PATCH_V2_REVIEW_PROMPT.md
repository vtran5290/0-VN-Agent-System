# ChatGPT Review Prompt — VN Agent Workflow Patch v2

**Paste this entire file into ChatGPT and attach:** `vn_workflow_patch_v2_chatgpt.zip`

No prior chat context required.

---

## Your role

You are my **workflow architect**. Cursor applied **Patch v2** after your earlier Pareto/workflow review. Validate the fixes, tighten operator discipline, and output an updated **`## CURSOR_IMPLEMENTATION_PROMPT`** only if small gaps remain.

**Do not** recommend live capital, tiny sandbox (Stage 2), copytrade (Stage 4), or content automation (Stage 5).

---

## What Patch v2 fixed (FACTS)

### P0-1 — Order-intent date safety

**Problem:** `order_intent_2026-05-17.csv` had `date=2099-01-01` (test fixture date picked by `max(as_of_date)`).

**Fix:**
- Placeholder years `>= 2090` excluded from production runs
- Fallback = latest scan date **on or before** requested date (not blind `max`)
- Fail-closed if gap > 7 days (`--max-stale-days`) unless `--allow-test-sample`
- Output `date` = **effective_scan_date**; `notes` always has `requested_date=` + `effective_scan_date=`
- Production filenames cannot contain placeholder dates; test outputs need `test` or `sample` in filename
- Bad file deleted; regenerated `order_intent_2026-05-18.csv` with **0** `2099` rows

### P0-2 — Outside-A3 classification

- Template: `templates/outside_a3_holding_review_template.md`
- Labels: `A3_PRODUCTION_MATCHED`, `DISCRETIONARY_OUTSIDE_A3`, `LEGACY_POSITION`, `WATCHLIST_ONLY`, `RESEARCH_SHADOW`
- Dry-run CSV column: `holding_classification`
- Outside-A3 → `NO_ACTION_FAIL_CLOSED` — no OMS action

### P0-3 — Stage tracker evidence

Added to `data/roadmap/stage_tracker.yaml`:
- `outside_a3_holdings_reviewed`, `order_intent_rows_reviewed`
- `last_reviews`: `last_weekly_run_date`, `last_order_intent_date`, `last_manual_review_date`
- `roadmap-status` CLI prints last reviews (read-only; counters updated manually)

### Tests

- `tests/test_order_intent_dry_run.py` — **13 passed** (date safety, outside-A3, no broker imports)

---

## Current stage (unchanged)

| | |
|--|--|
| **Current** | Stage 0 — Manual decision-support |
| **Next** | Stage 1 — Order-intent dry run |
| **Locked** | Stage 2 sandbox, Stage 4 copytrade, Stage 5 content |

---

## Hard constraints

- Real capital **NO-GO**; no DNSE/DSE live; no `live_auto`
- No strategy / A3 rule changes
- Order-intent: **`order_sent` always NO**; no broker submission
- OMS consumes **`final_action` only**; no signal recompute
- Manual cloud = sanity check only; screenshots not SSOT
- `a3_rank_score` = sort only

---

## Operator commands (canonical)

```powershell
# Weekly decision support (no orders)
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "STB,HDB,..."

# Order-intent dry run
python -m src.trading.cli generate-order-intent --date YYYY-MM-DD `
  --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv `
  --positions-path data/raw/current_positions_derived.json `
  --output data/trading/order_intent/order_intent_YYYY-MM-DD.csv

# Roadmap (read-only)
python -m src.review.cli roadmap-status
```

---

## Questions for you

1. **Date safety** — Is the effective vs requested date policy correct for a Sunday operator running Friday scan data?
2. **Outside-A3 book** — Is the 5-label taxonomy enough for ~8 discretionary names? Suggest a minimal weekly review ritual (≤5 min).
3. **Stage 0→1 gate** — Define exact checklist for incrementing `clean_weekly_cycles` and `clean_order_intent_cycles` in YAML.
4. **Evidence logging** — Should next Cursor batch add a safe `record-weekly-run` command (append-only YAML) or keep manual YAML edits?
5. **Remaining risks** — Any other ways placeholder/test data can leak into operator artifacts?
6. **Pareto trim** — Anything still over-scoped in the repo for my 90-day cut list?

---

## Required deliverable format

```markdown
# Patch v2 Review (validated / gaps)

## Date policy verdict
## Outside-A3 ritual (≤5 min/week)
## Stage 0→1 evidence checklist (copy-paste)
## Evidence logging recommendation (manual vs command)
## Remaining artifact risks
## Pareto cut additions (if any)

## CURSOR_IMPLEMENTATION_PROMPT
(only if gaps remain — P0/P1 docs/automation, no strategy change)
```

---

## One-line opener

> Read the attached Patch v2 zip. Validate date safety and outside-A3 policy. Answer all 6 questions. Output the deliverable format. Do not recommend live capital or skip stages.

---

*End of prompt.*
