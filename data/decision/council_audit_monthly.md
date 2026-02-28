# Council Secretary — Monthly Audit

## FACTS
- Logs reviewed: 1 (`2026-02-28` -> `2026-02-28`)
- Council missing weeks: 1
- Missing chair decision weeks: 1
- Non-executable recommendation weeks: 0
- Weeks with guardrail violations: 0
- Weeks with `new_buys_allowed=false`: 1

## INTERPRETATION
- Cadence discipline drift exists; secretary checklist must be enforced weekly.

## Top Recurring Guardrail Violations
- None.

## Top Recurring Council Conflicts
- None.

## Process Improvements (No Strategy Change)
- Make `make council-weekly` mandatory before weekly chairman decision.
- Require non-empty `chair_decision` every week.
- If guardrail violation appears, record nearest executable downgrade in council output.
- Keep Lab research and live decision threads separate to prevent narrative contamination.

## Flow Reminder (Next Cycle)
1. Weekly: `make council-weekly` -> orchestrator -> enforcer -> `make weekly`.
2. Mid-week check: open `data/decision/council_secretary_weekly.md` and clear BLOCKERS.
3. Monthly: `make council-audit-monthly` and review `data/decision/council_audit_monthly.md`.