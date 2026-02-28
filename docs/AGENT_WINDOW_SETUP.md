# Agent Window Setup — Beginner Guide (VN Agent System)

Goal: organize your Cursor chats as a small decision team, with clear boundaries and low token waste.

---

## 1) Create your pinned chats (one chat = one job)

Create and pin these chats in Cursor:

1. `CHAIRMAN - Weekly Decision`
2. `SECRETARY - Weekly Checklist`
3. `LAB - Backtest and Book Rules`
4. `AUDITOR - Monthly Lookback`
5. `ENGINE ROOM - Code Changes`

Why this matters:
- You avoid context contamination (research debate leaking into live decisions).
- You can resume each workflow quickly without re-explaining.

---

## 2) What each chat should do

- `CHAIRMAN - Weekly Decision`
  - Use: `prompts/council/orchestrator.md` then `prompts/council/constraint_enforcer.md`
  - Output: final next-week executable action list.

- `SECRETARY - Weekly Checklist`
  - Use: `prompts/council/secretary.md` (weekly section)
  - Inputs: `data/decision/council_secretary_weekly.md`, latest `decision_log/*.json`
  - Output: blockers + next dates + reminders.

- `LAB - Backtest and Book Rules`
  - Use: `prompts/gil_rule_extractor.md`, `prompts/experiment_planner.md`
  - Output: rulecards, test plan, experiment logs.
  - Never approve live portfolio actions here.

- `AUDITOR - Monthly Lookback`
  - Use: `prompts/council/secretary.md` (monthly section)
  - Inputs: `data/decision/council_audit_monthly.md` + last 4-5 `decision_log/*.json`
  - Output: process fixes (workflow only, no ad-hoc strategy rewrites).

- `ENGINE ROOM - Code Changes`
  - Use for implementation/refactor/tests only.
  - Never decide allocation/exposure in this chat.

---

## 3) Weekly cadence (step-by-step)

1. Run `make council-weekly`.
2. Open `data/decision/council_secretary_weekly.md`.
3. Clear `BLOCKER` items first.
4. In `CHAIRMAN` chat, run `prompts/council/orchestrator.md`.
5. Save JSON to `data/decision/council_output.json`.
6. Run `prompts/council/constraint_enforcer.md`.
7. Re-run `make weekly` (to persist council fields into `decision_log`).
8. Final sign-off in `CHAIRMAN` chat.

---

## 4) Monthly cadence (step-by-step)

1. Run `make council-audit-monthly`.
2. Read `data/decision/council_audit_monthly.md`.
3. In `AUDITOR` chat, run secretary monthly prompt.
4. Decide process improvements (checklist, cadence, logging), not strategy curve-fitting.

---

## 5) Reminder strategy (simple and reliable)

AI chat does not proactively notify you by itself. Use deterministic reminders:

- Calendar reminder every week: "Run make council-weekly"
- Calendar reminder every month: "Run make council-audit-monthly"
- Keep Secretary files as source of truth:
  - `data/decision/council_secretary_weekly.md`
  - `data/decision/council_audit_monthly.md`

---

## 6) Red flags to avoid

- Mixing lab research and live decision in one chat.
- Letting council recommendations bypass guardrails (`no_new_buys`, gross cap).
- Skipping monthly audit because performance is currently good.
- Changing strategy logic without passing pre-registered gates in `docs/BOOK_TEST_LADDER.md`.
