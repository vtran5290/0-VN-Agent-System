# ChatGPT Review Prompt — VN Agent Workflow Patch v3

**Paste this entire file into ChatGPT and attach:** `vn_workflow_patch_v3_chatgpt.zip`

No prior chat context required.

---

## Your role

You are my **workflow architect**. Cursor applied **Patch v3** (small operator-safety fixes) after Patch v2 was validated for **Stage 0 → Stage 1** discipline.

Validate Patch v3, confirm nothing regressed, and output **`## CURSOR_IMPLEMENTATION_PROMPT`** only if small gaps remain (docs/automation/safety — no strategy change).

**Do not** recommend live capital, Stage 2 sandbox, copytrade (Stage 4), or content automation (Stage 5).

---

## Patch history (short)

| Patch | Focus |
|-------|--------|
| v1 | Pareto backbone, roadmap tracker, order-intent dry run, weekly operator script |
| v2 | Date safety (no `2099` in production CSV), outside-A3 template, stage_tracker evidence counters |
| v3 | Fix broken PowerShell placeholder guard → Python `validate-order-intent` SSOT |

---

## What Patch v3 fixed (FACTS)

### P0-1 — PowerShell placeholder-date guard

**Problem:** `weekly_pareto_operator.ps1` used:

```powershell
Select-String -SimpleMatch "^2099-"
```

`-SimpleMatch` treats `^` literally — **does not** match lines starting with `2099-`. Placeholder dates could pass undetected.

**Fix:**
- New: `validate_order_intent_csv()` in `src/trading/order_intent_dry_run.py`
- CLI: `python -m src.trading.cli validate-order-intent --path <csv>`
- Weekly script calls Python validator after `generate-order-intent`
- Checks: `date` year ≥ 2090, `order_sent` always `NO`, placeholder dates in `notes`
- Tests: **16 passed** in `tests/test_order_intent_dry_run.py`

---

## Current operating model (unchanged)

| Item | Value |
|------|--------|
| **Stage** | 0 — Manual decision-support |
| **Next** | 1 — Order-intent dry run (`order_sent=NO`) |
| **Weekly** | `.\scripts\trading\weekly_pareto_operator.ps1` |
| **Positions SSOT** | `data/raw/current_positions_derived.json` |
| **Signal SSOT** | `phase36_daily_scan_latest.csv` → `final_action` only |
| **Capital** | **NO-GO** real / DNSE / `live_auto` |

---

## Hard constraints

- No strategy / A3 T1/T2/TP/trail/breadth changes
- No broker submission; order-intent sends no orders
- No OMS signal recompute; no intraday → OMS
- Manual cloud = sanity check; screenshots not SSOT
- `a3_rank_score` = sort only

---

## Canonical commands

```powershell
# Full weekly (decision support only)
.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "STB,HDB,..."

# Dry run
python -m src.trading.cli generate-order-intent --date YYYY-MM-DD `
  --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv `
  --positions-path data/raw/current_positions_derived.json `
  --output data/trading/order_intent/order_intent_YYYY-MM-DD.csv

# Post-check (Patch v3)
python -m src.trading.cli validate-order-intent --path data/trading/order_intent/order_intent_YYYY-MM-DD.csv

# Roadmap (read-only)
python -m src.review.cli roadmap-status
```

---

## Open items from Patch v2 review (for you to close or defer)

1. **Sunday + Friday scan** — Is `requested_date` vs `effective_scan_date` policy still correct?
2. **Outside-A3 ritual** — ≤5 min/week review using `templates/outside_a3_holding_review_template.md`
3. **Stage 0→1 gate** — Exact checklist to increment `clean_weekly_cycles` / `clean_order_intent_cycles` in `stage_tracker.yaml`
4. **`record-weekly-run`** — Safe append-only command vs manual YAML edits?
5. **Discretionary book** — ~8 names with `DISCRETIONARY_OUTSIDE_A3` — enough structure?

---

## Questions for this review

1. Is Patch v3 sufficient for placeholder-date safety, or one more guard needed (e.g. scan CSV pre-check)?
2. Should `weekly_pareto_operator.ps1` auto-call `record-weekly-run` when you approve that design?
3. Anything still over-scoped in repo for 90-day Pareto cut?
4. Ready to count first **clean weekly cycle** after operator runs one full Sunday workflow?

---

## Required deliverable format

```markdown
# Patch v3 Review

## Patch v3 verdict (PASS / gaps)
## Placeholder safety (sufficient?)
## Stage 0→1 evidence checklist (copy-paste for YAML)
## Outside-A3 weekly ritual (≤5 min)
## record-weekly-run recommendation (yes/no + spec)
## Pareto cut additions (if any)

## CURSOR_IMPLEMENTATION_PROMPT
(only if gaps — P0/P1 docs/automation, no strategy change)
```

---

## One-line opener

> Read the attached Patch v3 zip. Validate the placeholder-date fix. Answer all 4 questions. Output the deliverable format. Do not recommend live capital or skip stages.

---

*End of prompt.*
