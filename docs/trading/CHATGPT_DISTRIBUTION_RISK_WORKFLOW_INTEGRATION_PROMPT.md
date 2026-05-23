# ChatGPT Review Prompt — Distribution Risk Workstream × Existing Operator Workflow

**Paste this entire file into ChatGPT (High / Codex).**  
**Attach:** `distribution_risk_workflow_integration_chatgpt_YYYYMMDD.zip` (build below).

No prior chat context required.

---

## Your role

You are my **workflow architect** for a Vietnam equities **Stage 0** operator stack (manual execution, no live auto-trading).

**Goal:** Make the **new Distribution Risk + session-monitor workstream** fit **perfectly** into my **existing Pareto backbone** — without duplicating SSOTs, without strategy creep, and without bloating the weekly path.

**Deliver:**

1. **Integrated operator runbook** — single ordered checklist for **EOD**, **intraday preview**, and **weekly** (what runs when, what can be skipped).
2. **SSOT map** — which file wins for each question (dist counts, probabilities, `final_action`, NAV, positions).
3. **Tooling role matrix** — Cursor vs Claude Code vs ChatGPT vs local scripts (who owns what).
4. **De-duplication plan** — legacy vs canonical paths (see table below).
5. **Gaps only:** If changes are needed, output **`## CURSOR_IMPLEMENTATION_PROMPT`** (docs + small automation only — **no** A3/S3 rule changes, no OMS, no live capital).

**Do not** recommend changing `final_action`, breadth gates, T1/T2 sizing, exit policy, broker submission, `live_auto`, or DNSE live capital.

---

## What changed (FACTS — commit `59caf39` on `master`)

| Item | Value |
|------|--------|
| **Lens version** | `distribution_risk_lens_v1.2` |
| **Canonical CLI** | `python -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest` |
| **Launcher** | `monitor_distribution_risk.cmd` |
| **New outputs (every lens run)** | `distribution_risk_latest.json` + **`distribution_risk_latest.html`** + **`distribution_risk_latest.md`** |
| **Output dir** | `data/research/market_risk/` |
| **Primary view** | `ex_vin_proxy` (derived — **not** native ex-VIN index) |
| **Safety invariant** | Lens is **market context only** — does **not** change `final_action` |
| **Cloud report** | Section G embeds same card HTML from JSON (`cloud-daily-report`) |
| **Daily scan** | `daily_scan.md` can auto-refresh lens via `build_distribution_risk_section_for_daily_scan()` |
| **Session use** | Cursor chat: operator says **`check dist`** → agent reads JSON (or HTML) after HOSE close |

**Latest snapshot in zip (update dates when rebuilding package):**

| Field | Example (refresh zip after EOD) |
|-------|----------------------------------|
| `as_of_date` | 2026-05-21 |
| VNINDEX raw warning | `DISTRIBUTION_CLUSTER` (dist 10/25/50 ≈ 3/4/8) |
| ex-VIN proxy warning | `DISTRIBUTION_CLUSTER` (dist 10/25/50 ≈ 3/4/7) |
| VIN basket warning | `CORRECTION_RISK` |
| `vin_distortion_flag` | check `vin_group.distortion_flag` + `comparison` |

---

## My existing workflow (do not replace — integrate)

Source: `docs/OPERATING_BACKBONE_PARETO.md`

**Stage:** 0 — Manual decision-support. **Real capital: NO-GO.**

**Pareto keep list (max 7 recurring actions):**

1. Update positions → `derive-current` → `data/raw/current_positions_derived.json`; NAV in `data/trading/live/portfolio_state.json` (user-updated)
2. Run Phase36 scan → `--step scan` → `phase36_daily_scan_latest.csv` → **`final_action` only** for production logic
3. Weekly report → `reports/latest/index.html`
4. Review regime / actions / holdings / data quality
5. Log manual cloud exceptions (cloud ≠ CSV)
6. Log manual trades (broker truth)
7. Order-intent dry run (`order_sent=NO`)

**Weekly driver:** `.\scripts\trading\weekly_pareto_operator.ps1 -Date YYYY-MM-DD -Tickers "..."`

**Signal SSOT:** `phase36_daily_scan_latest.csv` — OMS and capital use **`final_action` only**.  
`a3_rank_score` = review sort only. Intraday = preview only, not OMS.

**Cloud daily report (parallel path):**

```powershell
python -m src.trading.cli cloud-daily-report --mode eod   # after close
python -m src.trading.cli cloud-daily-report --mode pre-lunch
python -m src.trading.cli cloud-daily-report --mode pre-atc
```

Outputs: `data/research/reports/cloud_daily_report_latest.html` (full board A–I, includes lens Section G).

**Daily scan packet:**

```powershell
python scripts/reporting/daily_scan_report.py
```

Outputs: `data/decision/daily_scan.md` + `.json`

---

## New workstream (what you must fit in)

| Layer | Command / artifact | Purpose |
|-------|-------------------|---------|
| **Data refresh** | `scripts/append_fireant_ohlcv_to_data_stocks.py --data-stocks --minervini-raw --end YYYY-MM-DD` | VNINDEX + stocks through as-of |
| **ex-VIN rebuild** | `scripts/research/vnindex_low_dist_ex_vin.py --end YYYY-MM-DD` | `vnindex_ex_vin_daily_series.csv` |
| **Lens + HTML** | `distribution-risk` CLI or `monitor_distribution_risk.cmd` | JSON + HTML + MD + research CSVs |
| **Chat session** | `docs/DIST_SESSION_MONITOR.md` — **`check dist`** in Cursor | Per-session distribution monitoring |
| **Legacy (optional)** | `scripts/monitor_vnindex_distribution_session.py` | Lighter O'Neil dist snapshot → `data/alerts/dist_session_*` |

**Open questions for you to resolve:**

1. Should **distribution-risk** run **before** or **after** Phase36 scan, cloud report, and `daily_scan_report.py`?
2. Should **OHLCV append + ex-VIN rebuild** be one scripted **EOD refresh** step, or stay manual pre-lens?
3. Is **`distribution_risk_latest.html`** the right **primary human view** for session dist checks, or only **`cloud_daily_report_latest.html`**?
4. Should **`weekly_pareto_operator.ps1`** call `distribution-risk` once per week, or is that **daily-only**?
5. How do **intraday previews** use lens data (stale ex-VIN / `NEEDS_REVIEW`) without polluting `final_action`?
6. Retire, gate, or document **`dist_session_*`** vs lens SSOT?
7. Where does **FireAnt token / append** belong in Pareto 7 (or explicitly *outside* the 7)?

---

## Hard constraints (mandatory)

| Rule | Detail |
|------|--------|
| **Facts vs interpretation** | Separate FACTS and INTERPRETATION in operator guidance |
| **FireAnt discipline** | State source, method, symbols, date range, proxy vs native |
| **ex-VIN** | Proxy-derived; never present as native index |
| **VIN baseline** | Dual reporting full vs ex-VIN (`VIC`,`VHM`,`VRE`); `VPL` excluded until ≥252 bars; cap-weight VNINDEX 2025–2026 may be VIN-skewed |
| **No hallucination** | Missing data → Unknown + what would confirm |
| **Lens boundary** | No `final_action` override; no order routing |
| **Stage 0** | No live auto; order-intent preview only |

---

## Files in attachment zip (expected)

| Path in zip | Role |
|-------------|------|
| `REVIEW_PROMPT.md` | This file |
| `README.txt` | Build instructions |
| `docs/OPERATING_BACKBONE_PARETO.md` | Current 7-action backbone |
| `docs/DIST_SESSION_MONITOR.md` | Session monitor + canonical CLI |
| `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` | Scan + daily_scan |
| `docs/trading/CLOUD_DAILY_REPORT_GUIDE.md` | Cloud report modes |
| `docs/research/VIN_EMA_CLOUD_BASELINE.md` | VIN / ex-VIN research rules |
| `src/market/distribution_risk_lens/` | Lens pipeline |
| `src/trading/reports/distribution_risk_card.py` | HTML/MD writers + card |
| `src/trading/reports/cloud_daily_report.py` | Section G integration |
| `src/trading/cli.py` | `distribution-risk`, `cloud-daily-report` |
| `monitor_distribution_risk.cmd` | Double-click launcher |
| `scripts/reporting/daily_scan_report.py` | Daily scan + lens section |
| `outputs/distribution_risk_latest.json` | Lens SSOT snapshot |
| `outputs/distribution_risk_latest.html` | Standalone HTML card |
| `outputs/distribution_risk_latest.md` | Standalone MD |
| `outputs/cloud_daily_report_latest.html` | Full operator board (if present) |
| `outputs/daily_scan.md` | Daily packet (if present) |
| `outputs/phase36_daily_scan_latest.csv` | Signal SSOT (if present) |

---

## Review focus — 10 integration checks

### Check 1 — SSOT hierarchy

Map answers for:

- “How many distribution days in last 25 sessions?” → which file?
- “P(negative 25d return) given current bucket?” → which file?
- “Should I take NEW_T1 today?” → **only** `final_action` from scan CSV

Flag any doc or script that implies lens overrides scan.

### Check 2 — EOD sequence (single canonical order)

Propose **one** ordered checklist (PowerShell-friendly) that includes:

1. Positions / NAV (if needed)
2. FireAnt OHLCV append (if needed)
3. ex-VIN series rebuild (if VNINDEX/VIN changed)
4. `distribution-risk`
5. Phase36 `--step scan`
6. `daily_scan_report.py`
7. `cloud-daily-report --mode eod`

Mark **optional** vs **mandatory** per step. Estimate operator time.

### Check 3 — Weekly vs daily placement

| Path | Should lens run? | Rationale |
|------|------------------|-----------|
| `weekly_pareto_operator.ps1` | ? | |
| Daily EOD only | ? | |
| Intraday pre-lunch / pre-atc | ? (read-only stale?) | |

### Check 4 — HTML surface area

Compare:

- `distribution_risk_latest.html` (narrow card)
- `cloud_daily_report_latest.html` (full board)
- `reports/latest/index.html` (weekly command center)

When should operator open which? Avoid three conflicting “command centers.”

### Check 5 — Duplication: legacy session monitor

`scripts/monitor_vnindex_distribution_session.py` vs `distribution-risk` CLI.

Recommend: **keep / merge / deprecate** with migration steps.

### Check 6 — Staleness & `NEEDS_REVIEW`

When `ex_vin_proxy.is_stale_for_as_of` or `report_status=NEEDS_REVIEW`:

- What should operator do before trusting probabilities?
- How should cloud report + standalone HTML banner align?

### Check 7 — Chat / Cursor session workflow

Document how **`check dist`** fits:

- After which commands must operator run before asking agent?
- Agent reads JSON vs HTML — preference?
- Per-session log (`dist_session_log.jsonl`) — still needed?

### Check 8 — Claude Code vs Cursor split

| Task type | Best owner |
|-----------|------------|
| Batch OHLCV append, FA refresh | ? |
| `distribution-risk` + HTML | ? |
| Phase36 scan | ? |
| Refactor / architect | ? |
| Chat dist interpretation | ? |

Align with existing handoff: *Cursor = build/architect; Claude Code = batch maintenance.*

### Check 9 — Packaging & review cadence

- When to rebuild `distribution_risk_*_chatgpt_*.zip`?
- Separate **methodology review** (`CHATGPT_DISTRIBUTION_RISK_DAILY_SCAN_REVIEW_PROMPT.md`) vs this **workflow integration** review — cadence?

### Check 10 — Pareto bloat guard

Lens adds CSVs + HTML. Confirm it stays **outside** the 7 weekly actions unless you justify replacing an existing step.

---

## Output format (strict)

```markdown
## Executive summary
(≤5 bullets)

## Integrated EOD checklist
(numbered steps, mandatory/optional, commands)

## Integrated weekly checklist
(deltas vs OPERATING_BACKBONE_PARETO.md only)

## SSOT map
(table: question → file → refresh command)

## HTML / report routing
(which URL/file to open when)

## De-duplication decisions
(legacy monitor, double refresh paths)

## Tooling role matrix
(Cursor / Claude Code / ChatGPT / operator)

## Risks & conflict rules
(lens vs scan vs cloud vs weekly)

## CURSOR_IMPLEMENTATION_PROMPT
(only if gaps — copy-paste tasks for Cursor; docs/scripts/tests; no strategy change)
```

If no code changes needed, write: **`## CURSOR_IMPLEMENTATION_PROMPT`** → `_None — documentation-only deltas listed above._`

---

## Build attachment zip (operator)

```powershell
cd "c:\Users\LOLII\Documents\V\0. VN Agent System"
.\.venv\Scripts\python.exe -m scripts.reporting.build_distribution_risk_workflow_integration_chatgpt_zip
```

Then attach `outputs/review_packages/distribution_risk_workflow_integration_chatgpt_YYYYMMDD.zip`.

---

## Data discipline reminder (for your review text)

When citing market numbers from the zip:

- **source** = FireAnt REST (OHLCV) + repo CSV merge for VNINDEX
- **method** = REST append + derived ex-VIN proxy + O'Neil distribution-day rule on index views
- **symbols** = VNINDEX; ex-VIN proxy; VIN basket VIC/VHM/VRE
- **date range** = 2012-01-01 → as-of in `distribution_risk_latest.json`
- **proxy** = ex-VIN is derived, not exchange-listed
- **limitations** = VNINDEX cap-weight may be VIN-skewed 2025–2026; lens horizons 5/10/25/75/100d

---

*End of prompt.*
