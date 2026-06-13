# Grand Collab — VN Agent System

Use the global Grand Collab skills, but apply these local constraints.

Domain: AI Systems & Automation (Vietnam investment agent — active development)
Global skills active here: `vn-agent-system-reviewer`, `ai-cursor-handoff-writer`, `weekly-review-and-action-register`

---

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

## Advisor Model — VN Agent System Override

- **Log/test scan, parallel module inspection** → `Agent(model="haiku")` — sub-agent worker for volume inspection. Guard: docs must be <200k tokens each.
- **Architecture / design / signal logic** → `Agent(model="opus")` — required before multi-file refactors or OMS/signal changes.
- **Pre-`live_auto` flip** → `Agent(model="opus")` hard gate. Do not proceed without explicit opus review + written user approval. (In Cursor: o3 devil's-advocate first, then opus — see advisor-routing.md.)
- **Routine code review / batch tasks** → Sonnet (no advisor needed)
- **Architecture advisor (fable)** → RESERVED/FUTURE — inaccessible via Agent() as of 2026-06-13; route to opus.

See `D:\V\.claude\rules\advisor-routing.md` for full routing table.

## MCP — Serena
Serena is available in this folder for semantic code navigation and analysis only.
Do not use Serena to modify A3/S3/OMS/DNSE logic or enable live trading.
All trading-code changes require explicit written user approval before execution.
