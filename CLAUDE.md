# Claude Code Project Instructions — VN Agent System

You are maintaining a 6-layer Vietnam investment workflow.

- Work inside the current repo structure; prefer adapting existing files over creating parallel duplicates.
- Before creating a new file, first check whether an equivalent file already exists and extend it instead of duplicating functionality.

Non-negotiables:
- Facts-first. Separate FACTS vs INTERPRETATION.
- No hallucination: if missing data, output "Unknown" and list what would confirm/deny.
- Preserve file-based SSOT: do not invent sources. Update files in /data and /src.

**EMA-cloud / VIN baseline:** Before batch research, backtests, or interpretation of breakout/retest pipelines, read `docs/research/VIN_EMA_CLOUD_BASELINE.md`. Default: dual universe (**full** + **ex-VIN**), exclude **VPL** until 252 bars, flag VIN **return** distortion, caveat on cap-weight **VNINDEX** 2025–2026.

Commands:
- Generate weekly packet: `python -m src.report.weekly`
- Full fetch (global + SBV + FireAnt weekly + HTML): `python scripts/run_weekly_full_fetch.py` (see `docs/WEEKLY_FULL_FETCH.md`)

Outputs:
- data/decision/weekly_report.md
- data/state/regime_state.json
- data/decision/allocation_plan.json

Always end weekly_report.md with:
- Signals to monitor next week
- If X happens → do Y

✅ Đây là "handover brain" cho Claude Code. Claude Code đọc repo là hiểu ngay.

---

## Nguyên tắc "mượt" (thực chiến)

- **Cursor:** build / architect / refactor
- **Claude Code:** chạy batch tasks, update nhiều file, quick query/maintenance
- Cả hai cùng làm trên repo → không có "migration", chỉ có "đổi công cụ làm việc".
