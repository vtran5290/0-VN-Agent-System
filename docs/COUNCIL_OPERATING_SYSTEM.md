# Council Operating System v1 — VN Agent System

Purpose: run a repeatable decision process with multiple investment philosophies, while keeping execution deterministic under existing guardrails.

This is workflow-only. It does not change strategy logic.

---

## 1) Core idea

- You are the Chairman.
- Masters are independent minds (Buffett, O'Neil, Minervini, Morales), not rigid job titles.
- A non-philosophical Constraint Enforcer checks mechanical executability.
- A Secretary agent manages cadence, reminders, and logs.

This avoids narrative drift and keeps the process auditable.

---

## 2) Should you add a Secretary / reminder layer?

Yes. For a new AI-agent operator, this is high ROI.

Without a Secretary layer, the common failure is:
- skip weekly review steps,
- forget monthly lookback,
- overreact to one narrative in one chat.

Secretary is not "alpha generator". It is discipline infrastructure.

---

## 3) Agent set (minimal, recommended)

Use these prompts as your working team:

- `prompts/council/orchestrator.md`
  - Runs the full council protocol.
- `prompts/council/buffett_mind.md`
  - Capital preservation and opportunity-cost lens.
- `prompts/council/oneil_mind.md`
  - Market direction, breadth, accumulation/distribution lens.
- `prompts/council/minervini_mind.md`
  - Trend structure, timing precision, risk/reward lens.
- `prompts/council/morales_mind.md`
  - Failure detection and exit aggression lens.
- `prompts/council/constraint_enforcer.md`
  - Checks if recommendations violate guardrails; outputs executable actions only.
- `prompts/council/secretary.md`
  - Creates todo/reminder cadence and monthly audit checklist.

Your existing specialized prompts remain valid:
- `prompts/gil_rule_extractor.md` (book-to-rule extraction)
- `prompts/experiment_planner.md` (pre-registered experiment planning)

---

## 4) Hard input contract (non-negotiable)

Council must only use:
- `data/decision/weekly_report.md`
- `data/decision/allocation_plan.json`
- `data/alerts/market_flags.json`
- `data/alerts/sell_signals.json`
- latest `decision_log/<asof_date>.json`
- optional: `data/decision/council_output.json` from previous week

No external speculation. If data missing: say "Unknown" and list what confirms/denies.

---

## 5) Step-by-step workflow

### Daily (5-10 minutes)

1. Run `make daily`.
2. Open `data/decision/daily_snapshot.md`.
3. If `risk_flag=High` or `no_new_buys=True`, prioritize risk protocol, not idea generation.

### Weekly (main council run)

1. Optional ingest: `make ingest`.
2. Run `make council-weekly`.
3. Open `data/decision/council_secretary_weekly.md` and clear `BLOCKER` items first.
4. Run Council via `prompts/council/orchestrator.md`.
5. Save output to `data/decision/council_output.json` (schema in `prompts/council/orchestrator.md`).
6. Run `prompts/council/constraint_enforcer.md` to convert recommendations into executable actions.
7. Re-run `make weekly` to write council snapshot into `decision_log/<asof_date>.json`.
8. Chairman decision: approve/freeze next-week action list.

### Monthly (lookback and system optimization)

1. Run `make council-audit-monthly`.
2. Review `data/decision/council_audit_monthly.md` (auto summary from logs).
3. Run `prompts/council/secretary.md` (monthly section) to review:
   - discipline breaches,
   - guardrail violations,
   - recurring execution mistakes,
   - process improvements.
4. Only optimize workflow/process unless strategy gates in `docs/BOOK_TEST_LADDER.md` justify model changes.

---

## 6) Cursor organization (for new users)

Create and pin these chats:

1. `CHAIRMAN - Weekly Decision`
   - Use orchestrator + enforcer.
2. `SECRETARY - Cadence and Reminders`
   - Use secretary prompt only.
3. `LAB - Book Rules and Backtests`
   - Use `gil_rule_extractor` and `experiment_planner`.
4. `AUDITOR - Monthly Discipline Review`
   - Use `prompts/council/secretary.md` monthly section + `data/decision/council_audit_monthly.md`.
5. `ENGINE ROOM - Implementation`
   - Use for code/refactor tasks only; never decide live exposure here.

Rule:
- Never run deep backtest discussion in Chairman chat.
- Never approve live actions in Lab chat.
- Keep one chat = one job. Do not mix council debate and code implementation in the same thread.

---

## 7) What is right/wrong in current system (quick audit)

### Right
- Strong guardrails already exist (`risk_flag`, `gross cap`, `no_new_buys`).
- Decision logs already exist and are written weekly.
- Backtest governance is pre-registered (`docs/BOOK_TEST_LADDER.md`, `docs/EXPERIMENT_SPACE_GIL.yaml`).
- Council prompts now exist for orchestrator + 4 masters + enforcer + secretary.

### Gaps
- Backtest engines currently serve two purposes (book-brain synthesis + strategy testing), so context can bleed from research into live decision chat.
- Without a fixed Secretary cadence, weekly process drift can still happen.
- If `council_output.json` is not saved, council quality is hard to audit over time.

### What to do now (no strategy changes)
- Keep extraction workflow in Lab (`rulecards`, `experiment_planner`) and keep live decisions in Chairman chat.
- Treat Secretary outputs as mandatory checklist: `make council-weekly`, `make council-secretary-weekly`, `make council-audit-monthly`.
- Require Constraint Enforcer before any chairman sign-off.

This v1 addresses the process gaps without touching strategy engine logic.

---

## 8) Operating rules

- Council can debate, but cannot bypass guardrails.
- Constraint Enforcer has veto on non-executable recommendations.
- Chairman can override only with explicit reason logged in council output.
- Monthly audit is mandatory even when performance is good.
- `council_output.meeting_id` should match current `asof_date`; stale council files are treated as invalid for the week.

