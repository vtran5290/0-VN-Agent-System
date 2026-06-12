# Council Secretary — Weekly Checklist

## FACTS
- Latest decision log: `D:\V\0. VN Agent System\decision_log\2026-06-08.json`
- asof_date: 2026-06-08
- council.status: stale_meeting_id
- mechanically_executable: True
- guardrail_violations: 0

## Weekly Checklist
- [x] weekly packet generated
- [ ] council run completed
- [x] constraint check completed
- [x] chair decision logged

## BLOCKERS
- Council output missing (`data/decision/council_output.json` not provided or not loaded).

## Next Dates
- Next weekly council: 2026-06-15
- Next monthly audit: 2026-07-08

## Cadence Alerts
- Days since latest decision log: 4
- Weekly cadence: on track.
- Monthly audit cadence: on track.

## Flow Reminder (Run Order)
1. `make council-weekly`
2. In `CHAIRMAN` chat, run `prompts/council/orchestrator.md`.
3. Save JSON to `data/decision/council_output.json`.
4. In `CHAIRMAN` chat, run `prompts/council/constraint_enforcer.md`.
5. Re-run `make weekly` to persist council fields into `decision_log/<asof_date>.json`.
6. Confirm `council.status=provided` and non-empty `chair_decision` in latest decision log.

## Process Reminder
- If council output changes, re-run `make weekly` to refresh decision log.
- If a recommendation violates guardrails, only execute the downgraded executable action list.