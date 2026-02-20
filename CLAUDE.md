# Claude Code Project Instructions — VN Agent System

You are maintaining a 6-layer Vietnam investment workflow.

Non-negotiables:
- Facts-first. Separate FACTS vs INTERPRETATION.
- No hallucination: if missing data, output "Unknown" and list what would confirm/deny.
- Preserve file-based SSOT: do not invent sources. Update files in /data and /src.

Commands:
- Generate weekly packet: `python -m src.report.weekly`

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
