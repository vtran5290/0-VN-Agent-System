# Path A Latest-week Freshness Audit

## Key dates by layer

- Monitoring snapshot period label: **2024-01-01_to_2026-03-16**
- Candidate-check latest `entry_week` in `pp_portfolio_signal_log.csv`: **2026-02-13**
- Raw VN30 daily max date (probe 2026-02-01..2026-03-18): **2026-03-18**
- Weekly regime max date (probe build_weekly_dfs end=2026-03-18): **2026-03-20**
- Weekly symbol max date (probe build_weekly_dfs end=2026-03-18): **2026-03-20**

## Root cause

- candidate_check_used_stale_pp_portfolio_signal_log
