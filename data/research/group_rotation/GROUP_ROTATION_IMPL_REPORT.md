# Group Rotation Dashboard Integration — Implementation Report

**Date:** 20260525

## Verdict

GROUP_ROTATION_DASHBOARD_RANKING_ONLY

## Output Files

- `data/research/group_rotation/group_rotation_latest.csv` — 39 groups
- `data/research/group_rotation/group_rotation_latest.json`
- `data/research/reports/group_rotation_card_latest.md`

## Snapshot Statistics

| Item | Value |
|---|---|
| Total groups | 39 |
| Snapshot date | 2026-05-25 |
| Tier A | 6 |
| Tier B | 2 |
| Tier C | 13 |
| Tier D | 18 |
| GROUP_STRONG_ROTATION | 0 |
| GROUP_MODERATE_ROTATION | 0 |
| GROUP_WEAK_ROTATION | 2 |
| GROUP_RESEARCH_ONLY | 6 |
| GROUP_NO_SIGNAL | 31 |

## No-Production-Change Confirmation

- A3 production logic: UNCHANGED
- OMS: UNCHANGED
- Phase36 final_action: UNCHANGED
- S3 status: UNCHANGED
- DNSE routing: UNCHANGED
- execution_allowed_flag = false for ALL rows (assertion checked at runtime)

## Open Issues

- OI-GR-1 (HIGH): No daily NAV series — scores are not portfolio-MAR-validated
- OI-GR-2 (MEDIUM): follower_score uses last-5-session cloud transitions from cached panel; needs live daily refresh for production
- OI-GR-3 (LOW): Leader classification uses historical data; LEADER_DRIVEN groups may be BROAD_BASED in current market conditions
- OI-GR-4 (LOW): Only 1 group (theme_tag: rubber) passes A3 hard gate — group filter must not be used as A3 hard filter

## Integration (post ChatGPT APPROVE_WITH_NOTES 2026-05-25)

- **Panel 8** in `phase36_daily_operator_report.md` via `scripts/research/group_rotation/report_section.py`
- **Section** in `data/decision/daily_scan.md` (same renderer)
- **EOD:** refreshed inside `pp_backtest/... --step scan` → `refresh_group_rotation_snapshot()` (cached P1 only)

## Patch Fixes Applied (chatgpt_review_20260525)

- Fix 1: Tier D badge cap — score>=0.5 -> GROUP_RESEARCH_ONLY, else GROUP_NO_SIGNAL
- Fix 2: follower_score = min(n/3, 1.0) * 0.30 (explicit formula per spec)
- Fix 3: Added alias columns group_tier, dashboard_badge, a3_gate_status, operator_note; added delta_mean_60d from P1 filter_value (available, not null)
- No production files changed
