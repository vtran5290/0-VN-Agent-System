# Grand Collab — VN Agent System

Use the global Grand Collab skills, but apply these local constraints.

Domain: AI Systems & Automation (Vietnam investment agent — active development)
Global skills active here: `vn-agent-system-reviewer`, `ai-cursor-handoff-writer`, `weekly-review-and-action-register`
Graphify canonical target for this repo: `graphify-out/` at this root only (registry: `D:\V\00. Command Center\06_File_Index/graphify_registry.yaml` — never fall back to `D:\V\graphify-out`).

---

## Purpose
Automated VN equity trading system in paper mode (Stage 4B). Signal generation → paper execution → daily monitoring → weekly regime review. Target: live trading (Stage 5) pending opus + ChatGPT dual-judge gate.

You are maintaining a 6-layer Vietnam investment workflow.
- Work inside the current repo structure; prefer adapting existing files over creating parallel duplicates.
- Before creating a new file, first check whether an equivalent file already exists and extend it instead of duplicating functionality.

## System architecture
| Layer | Path | Role |
|---|---|---|
| Signal engine | `src/` + AFL scripts | Generate raw signals |
| Data pipeline | `data/` | Market data, fundamentals, macro |
| Paper execution | `data/decision/final_action/` | OMS reads here — PRODUCTION PATH |
| Shadow track | `data/decision/shadow_a3rs_s1/` | Research quarantine — NOT OMS |
| Reports | `reports/` | HTML dashboards, performance |
| Brain | `D:\V\.claude\brains\vn-trading-advisor\` | Cortex belief system (canonical — absolute path; domain copy deleted per Patch 4C 2026-07-18) |
| Knowledge | `knowledge/` | Resolver rules, forward returns, weekly notes |

## Cortex belief brain (do NOT copy into this folder)
Belief lifecycle SSOT: `D:\V\.claude\brains\vn-trading-advisor\` — access via `/cortex` skill only.
`knowledge/knowledge_ACTIVE.md` (this folder) is a derived distillate of that brain — read-only for the pipeline.
Direct belief-content edits to `knowledge_ACTIVE.md` = Trigger #3 flag. See source-of-truth.md → Brain sync rule.

## Report Suite vs Weekly Report — two separate artifacts, do not conflate (added 2026-08-28)
Recurring confusion point — read before touching either:
| | **Report Suite** | **Weekly Report** |
|---|---|---|
| What | 6 HTML pages: Cloud Daily, Portfolio Monitor, PM Regime, E&MA Research, Inst. Accumulation, Tollbooth 10Y | 1 doc: `data/decision/weekly_report.md` (+ HTML render) |
| Trigger | `SUITE_REFRESH.md` (daily/weekly/monthly cadence runner) | `/weekly` command |
| Code | `src/trading/reports/report_suite_common.py` (`REPORT_SUITE` dict) + per-page generators | `render_weekly_report.py` → `templates/weekly_report_lean.html.j2` |
| Structural TA impl | `report_suite_common.py` (own load/index/render functions) | `scripts/ingest/weekly_lean_sections.py::build_structural_ta_block()` (own normalizer) |
Both read the same `data/processed/ta_structural_support.json` and share `sta-*` CSS naming +
"ADVISORY — not a signal input" framing — that's *why* they get confused, not evidence they're
one component. **They are two independent renderers.** Before editing a Structural TA display
bug, confirm which pipeline the report actually came from.

**Daily producer for that JSON:** EOD-CLOSE §1g (`scripts/run_structural_ta_adv50_universe.py --asof $Date`);
SUITE-REFRESH §1a-sta re-invokes with `--skip-if-fresh` before Portfolio Monitor.

## Session Start (MANDATORY — run before any VN Agent work)
Full sentinel rules: `docs/workflow/DATA_SENTINEL.md` (machine-readable freshness thresholds + action on fail).
1. `cat data/state/regime_state.json` — current regime (Bull/Neutral/Bear). Age >7 days → flag [STALE-REGIME], run regime check before proceeding. Output 3-line regime briefing: regime / active_filter / last_updated
2. `cat data/decision/kill_criterion_status.json 2>/dev/null` — any KILL-CANDIDATE? If yes → escalate to user immediately.
3. `ls data/decision/ | tail -5` — when was the last paper check? Gap >1 business day → flag [PAPER-CHECK-GAP].
4. Confirm S2 status: S2 vol-filter is advisory-only. S2 signals must NOT reach `final_action/`.
5. Secrets: `git status .env` — must show "not tracked". If tracked → halt, escalate per secrets-policy.md.
6. Check `knowledge/weekly_notes/` newest file — age >10 days → flag [STALE-WEEKLY-NOTE].
7. Read `knowledge/knowledge_ACTIVE.md` → note CALIBRATED beliefs (C1–C3, S1, S2) and AXIOMATIC beliefs (A1–A4, C4) and any VINTAGE-CHECK flags
   - ⚠️ **C4 is AXIOMATIC, not CALIBRATED** — reclassified per Opus Amendment C, 2026-07-08 (sector classification must be verified against HOSE/HNX/FireAnt; origin: TCX incident). AXIOMATIC outranks CALIBRATED in the `source-of-truth.md` precedence stack. This line previously read "C1–C4" and mis-tiered a safety rule downward; corrected 2026-07-16 per Opus council RISK FLAG 1.
   - ID prefixes record **birth tier**, not current tier (S1/S2 are CALIBRATED but keep the S prefix; C4 is AXIOMATIC but keeps the C prefix). Section membership records current tier. Beliefs are never renumbered on promotion — see `2026-07-16-1100_VNAgent_BrainReconciliation_MANIFEST.md`.
8. Check `knowledge/knowledge_ACTIVE.md` line count — if >300, flag for archiving

Knowledge base: `knowledge/knowledge_ACTIVE.md` (cap 300 lines; archive >90-day entries to `knowledge/archive/`)

Non-negotiables:
- Facts-first. Separate FACTS vs INTERPRETATION.
- No hallucination: if missing data, output "Unknown" and list what would confirm/deny.
- Preserve file-based SSOT: do not invent sources. Update files in /data and /src.
- User is color blind (green-weak). Colorblind-safe design applies to every output produced for this domain (reports, decks, models, dashboards) too — full rule + on-brand color guidance: global `CLAUDE.md` → Accessibility — Color Vision, and `00. Command Center/00_AI_Operating_Protocol/html-design-system.md` → Colorblind-safe color rules. Short version: never rely on red vs green alone to signal status — always pair with an icon or label; otherwise keep this domain's existing colors as-is.

**EMA-cloud / VIN baseline:** Before batch research, backtests, or interpretation of breakout/retest pipelines, read `docs/research/VIN_EMA_CLOUD_BASELINE.md`. Default: dual universe (**full** + **ex-VIN**), exclude **VPL** until 252 bars, flag VIN **return** distortion, caveat on cap-weight **VNINDEX** 2025–2026.

**Multi-timeframe structural support:** Before any chart analysis, stock screening, Wyckoff read, or entry-timing judgment, read `docs/MULTI_TIMEFRAME_STRUCTURAL_SUPPORT.md`. Zoom out (monthly = structural supply/demand, Part I) → weekly (= intermediate structure/MA compression/role reversal/LPS quality, Part II) → daily/intraday (= timing/trigger); never let a daily read override monthly or weekly structure, and weight the weekly close/body over an intraweek wick. Part III: **support quality and trend quality are separate axes — never infer one from the other**; score both, place the name in one of 4 quadrants (§ 38), and downgrade any previously-broken zone to `FAILED_SUPPORT` until reclaim conditions (§ 29) are met. Part IV: **support/resistance is contextual, not a permanent label** — classify a level as a structural pivot zone first, assign role by approach direction/break history/acceptance/retest (§ 45-50), and require a close-through + successful retest (not a mere wick-cross) before calling a role reversal real (§ 47-48, § 51 quality score). Governs support/resistance confluence scoring and supply-absorption reads for `/vn-ta`; companion to `docs/WYCKOFF_ONTOLOGY.md` (phase state machine).

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

## Active strategies
| Strategy | Status | Output path | Notes |
|---|---|---|---|
| S1 (base momentum) | ACTIVE — paper | `final_action/` | Core signal; OMS reads this |
| S2 (vol filter overlay) | ADVISORY ONLY | Advisory layer | Does NOT write to OMS |
| Shadow A3_RS | RESEARCH TRACK | `shadow_a3rs_s1/` | Quarantine; Trigger #5 before graduation |

## Hard guardrails (NEVER violate without dual-judge + user sign-off)
- `final_action/` is the OMS production path — no writes without explicit approval
- `live_auto` flag must NOT be set without opus + ChatGPT dual-judge + written user approval
- S2 signals: advisory-only — never route to OMS under any circumstance
- Shadow runner writes: quarantine path only (`data/decision/shadow_a3rs_s1/`) — never `final_action/`
- No DNSE/live order routing changes
- No trading signal contract changes without Trigger #5 dual-judge (high-stakes-triggers.md)
- Cross-architecture promotion (A3_RS → B_cloud): requires fresh pre-registered gates on target architecture

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

## Advisor Model / Model routing — VN Agent System Override
See `D:\V\.claude\rules\advisor-routing.md` for full routing table.

| Task | Model | Notes |
|---|---|---|
| File inspection, data extraction, log parsing | haiku | |
| Log/test scan, parallel module inspection | haiku | Guard: docs must be <200k tokens each |
| Report build, pipeline coding, review pack assembly | sonnet | |
| Routine code review / batch tasks | sonnet | No advisor needed |
| Signal logic verdict, OOS gate judgment | opus | One per artifact per session |
| Architecture / design / signal logic | opus | Required before multi-file refactors or OMS/signal changes |
| Pre-`live_auto` flip | opus | Hard gate — do not proceed without explicit opus review + written user approval (in Cursor: o3 devil's-advocate first, then opus) |
| Live_auto pathway design, architecture questions | fable → opus fallback | |
| Cross-architecture promotion gate design (A3_RS → B_cloud) | fable | Council seat required |

Architecture advisor (fable) AVAILABLE (restored 2026-07-08). Route display/calibration tasks to opus (not fable).

## Command registry (key commands)
| Command | Purpose |
|---|---|
| `/weekly` | Weekly regime report + Cortex belief update + decision-quality log |
| `/cycle` | Daily paper check cycle — weekly investment cycle orchestration (ingest → validate → render → summarize) |
| `/vn-ta` | Technical analysis session — Vietnam TA via FireAnt (Wyckoff, VP, VSA, JSON output) |
| `/research` | New signal candidate research |
| `/council` | Dual-judge council session |
| `/council-verify` | Verify council verdict |
| `/finreport` | Financial report generation |
| `/schema-guardian` | Schema integrity check — schema validation for weekly_report.json |
| `/sbv` | SBV liquidity fetch (omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd) |
| `/macro-ingest` | Global macro + SBV liquidity data refresh |
| `/vn-review` | System quality gate (regime consistency, S1/S2 calibration, report format) |
| `/fund-factsheet` | Fund factsheet monitor/downloader (VNH, VEIL, VEF, KIM, VOF, VinaCapital) |
| `/policy-ingest` | Policy events + research intake ingestion |
| `/report-render` | HTML dashboard render |

## Write guard
PreToolUse hook runs `scripts/write_guard.py` on every Edit/Write/MultiEdit.
If it blocks a write, read the guard output — do not override silently or retry blindly.

## Worktrees
See `.claude/WORKTREES.md` for convention, naming, and how to spin up new parallel backtest worktrees.

## MCP — Serena
Serena is available in this folder for semantic code navigation and analysis only.
Do not use Serena to modify A3/S3/OMS/DNSE logic or enable live trading.
All trading-code changes require explicit written user approval before execution.

## MCP — bigdata.com (Cowork plugin — requires OAuth)
bigdata.com is available as a Cowork plugin for financial data (earnings, sector analysis, valuation snapshots, company briefs).
To connect: open Cowork → Settings → Capabilities → install bigdata.com plugin → authorize via OAuth.
Once connected, use for: earnings previews/digests, peer comparables, sector playbooks, investment memos.
NOT yet wired to .claude/settings.json (OAuth-only, not a local MCP server).

## Sub-agents (.claude/agents/)
- `vn-trading-advisor` — read-only signal/regime advisor (tools: Read, Grep, Glob, WebSearch)
- `vn-researcher` — read-only belief extraction + pre-reg drafting (tools: Read, Grep, Glob, WebSearch)

## Commands (.claude/commands/) — added 2026-07-06
VN-specific slash commands (see Command registry above for the full list).

## Verification (Boris, 2026-06-13)
"Done" = agent observed output matches expectation. Not "ran without error."
Full checklist: `D:\V\.claude\rules\verification-harness.md` → VN Agent System section.
- After any AFL/signal change: paper run exists + delta report vs prior version produced.
- After backtest: IS vs OOS comparison is explicit (pass / borderline / fail).
- After weekly report: `re[SOURCE TRUNCATED — pre-existing in the original file as of 2026-08-16, not introduced by this merge; likely intended to read "regime_state.json updated; ends with If X → do Y" per the parallel Weekly Regime Report Updater routine — verify against verification-harness.md and fix at next edit.]`

## Source-of-truth files (never override without explicit approval)
- `knowledge/resolver_rules.yml` — signal resolver (SOT)
- `data/config/coverage_tiers.yaml` — universe definition
- `data/decision/final_action/` — OMS production input
- `D:\V\.claude\rules\` — all agent operating rules (root CLAUDE.md governs this domain)
