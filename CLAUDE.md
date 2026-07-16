# Grand Collab — VN Agent System

Use the global Grand Collab skills, but apply these local constraints.

Domain: AI Systems & Automation (Vietnam investment agent — active development)
Global skills active here: `vn-agent-system-reviewer`, `ai-cursor-handoff-writer`, `weekly-review-and-action-register`

---

# Claude Code Project Instructions — VN Agent System

You are maintaining a 6-layer Vietnam investment workflow.

- Work inside the current repo structure; prefer adapting existing files over creating parallel duplicates.
- Before creating a new file, first check whether an equivalent file already exists and extend it instead of duplicating functionality.

## Cortex belief brain (do NOT copy into this folder)
Belief lifecycle SSOT: `D:\V\.claude\brains\vn-trading-advisor\` — access via `/cortex` skill only.
`knowledge/knowledge_ACTIVE.md` (this folder) is a derived distillate of that brain — read-only for the pipeline.
Direct belief-content edits to `knowledge_ACTIVE.md` = Trigger #3 flag. See source-of-truth.md → Brain sync rule.

## Session Start (run every session)
1. Read `data/state/regime_state.json` → output 3-line regime briefing: regime / active_filter / last_updated
2. Read `knowledge/knowledge_ACTIVE.md` → note CALIBRATED beliefs (C1–C3, S1, S2) and AXIOMATIC beliefs (A1–A4, C4) and any VINTAGE-CHECK flags
   - ⚠️ **C4 is AXIOMATIC, not CALIBRATED** — reclassified per Opus Amendment C, 2026-07-08 (sector classification must be verified against HOSE/HNX/FireAnt; origin: TCX incident). AXIOMATIC outranks CALIBRATED in the `source-of-truth.md` precedence stack. This line previously read "C1–C4" and mis-tiered a safety rule downward; corrected 2026-07-16 per Opus council RISK FLAG 1.
   - ID prefixes record **birth tier**, not current tier (S1/S2 are CALIBRATED but keep the S prefix; C4 is AXIOMATIC but keeps the C prefix). Section membership records current tier. Beliefs are never renumbered on promotion — see `2026-07-16-1100_VNAgent_BrainReconciliation_MANIFEST.md`.
3. Check `knowledge/knowledge_ACTIVE.md` line count — if >300, flag for archiving

Knowledge base: `knowledge/knowledge_ACTIVE.md` (cap 300 lines; archive >90-day entries to `knowledge/archive/`)

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

## AFL Workflow Rule (MANDATORY — read before any AFL mention)

**"AFL update" = write/edit AFL code so the user can VIEW the chart in AmiBroker.**

| When user says | What to do |
|---|---|
| "AFL update" / "update AFL" | Write or edit the `.afl` file; user opens AmiBroker manually to view chart |
| "run backtest" / "research" | Python scripts only — use `ta_ohlcv_panel.parquet` + `ta_vnindex.parquet` directly |
| "check the chart" / "xem chart" | Write AFL chart code → user views in AmiBroker |
| "export to Python" / "get trade data" | Use `base_trades.csv` SSOT OR simulate in Python from OHLCV — no AmiBroker needed |
| "test new entry logic" / "new C1 variant" | Simulate entries + exits in Python from OHLCV panel — do NOT ask user to run AFL |
| "exit calibration / TP1 / trail grid" | Re-simulate exits in Python from base_trades.csv entries + OHLCV panel |

**AmiBroker is a chart viewer only. Claude does ALL research computation in Python.**
- Do NOT invoke AmiBroker COM for data extraction or backtest runs.
- Do NOT ask the user to "run AFL and export CSV" — ever. Claude handles this in Python.
- `ta_ohlcv_panel.parquet` = full OHLCV for all A3 symbols (2017–present). Use it for any simulation.
- `ta_vnindex.parquet` = VNINDEX OHLCV. Use for regime signals.
- `base_trades.csv` = AFL entry SSOT. Use as entry universe for exit-only studies.
- New entry variant (e.g., breadth C1): simulate entry logic in Python from OHLCV → no AFL export needed.
- Exit grid (TP1/Trail/MaxHold): re-simulate exits from base_trades.csv entry dates using OHLCV → no AFL needed.

## Advisor Model — VN Agent System Override

- **Log/test scan, parallel module inspection** → `Agent(model="haiku")` — sub-agent worker for volume inspection. Guard: docs must be <200k tokens each.
- **Architecture / design / signal logic** → `Agent(model="opus")` — required before multi-file refactors or OMS/signal changes.
- **Pre-`live_auto` flip** → `Agent(model="opus")` hard gate. Do not proceed without explicit opus review + written user approval. (In Cursor: o3 devil's-advocate first, then opus — see advisor-routing.md.)
- **Routine code review / batch tasks** → Sonnet (no advisor needed)
- **Architecture advisor (fable)** → AVAILABLE (restored 2026-07-08). Use for: live_auto pathway design, cross-architecture promotion gate design (A3_RS → B_cloud), OMS architecture questions. Route display/calibration tasks to opus (not fable). See routing table in `.claude/CLAUDE.md`.

See `D:\V\.claude\rules\advisor-routing.md` for full routing table.

## MCP — Serena
Serena is available in this folder for semantic code navigation and analysis only.
Do not use Serena to modify A3/S3/OMS/DNSE logic or enable live trading.
All trading-code changes require explicit written user approval before execution.

## Verification (Boris, 2026-06-13)
"Done" = agent observed output matches expectation. Not "ran without error."
Full checklist: `D:\V\.claude\rules\verification-harness.md` → VN Agent System section.
- After any AFL/signal change: paper run exists + delta report vs prior version produced.
- After backtest: IS vs OOS comparison is explicit (pass / borderline / fail).
- After weekly report: `re
## MCP — bigdata.com (Cowork plugin — requires OAuth)
bigdata.com is available as a Cowork plugin for financial data (earnings, sector analysis, valuation snapshots, company briefs).
To connect: open Cowork → Settings → Capabilities → install bigdata.com plugin → authorize via OAuth.
Once connected, use for: earnings previews/digests, peer comparables, sector playbooks, investment memos.
NOT yet wired to .claude/settings.json (OAuth-only, not a local MCP server).

## Sub-agents (.claude/agents/)
- `vn-trading-advisor` — read-only signal/regime advisor (tools: Read, Grep, Glob, WebSearch)
- `vn-researcher` — read-only belief extraction + pre-reg drafting (tools: Read, Grep, Glob, WebSearch)

## Commands (.claude/commands/) — added 2026-07-06
VN-specific slash commands now available in Claude Code:
- `/vn-review` — system quality gate (regime consistency, S1/S2 calibration, report format)
- `/sbv` — SBV liquidity fetch (omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd)
- `/cycle` — weekly investment cycle orchestration (ingest → validate → render → summarize)
- `/vn-ta` — Vietnam TA via FireAnt (Wyckoff, VP, VSA, JSON output)
- `/fund-factsheet` — fund factsheet monitor/downloader (VNH, VEIL, VEF, KIM, VOF, VinaCapital)
- `/macro-ingest` — global macro + SBV liquidity data refresh
- `/policy-ingest` — policy events + research intake ingestion
- `/schema-guardian` — schema validation for weekly_report.json
- `/report-render` — HTML dashboard render
