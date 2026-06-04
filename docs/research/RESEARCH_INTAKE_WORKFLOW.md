# Research Intake Workflow (Stage 0)

**Stage:** 0 — Manual decision-support  
**Real capital:** NO-GO  
**Signal SSOT:** `phase36_daily_scan_latest.csv` → **`final_action` only**

Research is **thesis / watchlist context only**. It does **not** set or override `final_action`.

> **Safety:** Research is thesis/watchlist context only and does not set or override final_action.

---

## Purpose

Ingest equity research, AGM notes, management meetings, earnings notes, and sector reports into a **file-based index** and **research cards** so you can:

1. Upgrade / downgrade watchlist (`config/watchlist.txt`)
2. Raise / lower **review priority** before weekly HTML
3. Document **manual override justification** (when you disagree with scan)
4. Feed **monthly thesis** updates

Research does **not** participate in signal production, OMS, or order routing.

---

## Folder structure

```text
data/research/intake/
├── raw/                 # Drop original PDFs / notes
├── extracted/           # Full-text .txt (from batch_extract_pdfs or manual)
├── cards/               # One markdown card per report
├── index/
│   └── research_index.csv   # Master index (SSOT for intake metadata)
├── weekly_digest/       # Weekly top-10 digest outputs
└── sector_dashboard/    # Sector rollup outputs

templates/research/
├── research_card_template.md
├── weekly_research_digest_template.md
└── sector_thesis_dashboard_template.md
```

**Legacy extracts:** `data/intake/raw_extract/` may be copied or referenced into `extracted/`.

**Stage 0 dated index (batch snapshots):**

```text
data/research/stage0/
├── research_index_YYYY-MM-DD.csv
├── research_index_latest.csv      # copy of newest batch
└── README.md
```

After ChatGPT synthesis + manifest bootstrap (2026-05-24 example):

```powershell
.\.venv\Scripts\python.exe scripts\research\bootstrap_stage0_research_index.py
```

Digest: `data/research/intake/weekly_digest/2026-05-24_chatgpt_synthesis.md`

---

## Index schema (`research_index.csv`)

| Column | Description |
|--------|-------------|
| `source_id` | Unique id, e.g. `SSI_HPG_20260520` |
| `file_name` | Original filename |
| `source_type` | See allowed values below |
| `ticker` | Primary symbol or empty for sector/macro |
| `sector` | ICB / logical sector label |
| `source_date` | Report date (YYYY-MM-DD) |
| `broker_or_source` | House name (SSI, HSC, Vietcap, …) |
| `report_title` | Short title |
| `extraction_date` | When text was extracted |
| `confidence` | Operator 0–1 or High/Medium/Low |
| `thesis_impact` | IMPROVED / UNCHANGED / WEAKENED / MIXED / UNKNOWN |
| `watchlist_action` | See allowed values below |
| `key_catalyst` | One-line catalyst |
| `key_risk` | One-line risk |
| `linked_card_path` | Relative path to card markdown |
| `status` | Pipeline status |

### Allowed `source_type`

`equity_research` · `agm_note` · `management_meeting` · `earnings_note` · `sector_report` · `macro_strategy` · `fund_factsheet` · `other`

### Allowed `status`

`RAW_EXTRACTED` → `CARD_CREATED` → `REVIEWED` → `WATCHLIST_UPDATED` → `ARCHIVED`

### Allowed `thesis_impact`

`IMPROVED` · `UNCHANGED` · `WEAKENED` · `MIXED` · `UNKNOWN`

### Allowed `watchlist_action`

`UPGRADE` · `MAINTAIN` · `DOWNGRADE` · `REMOVE` · `ADD_TO_WATCH` · `NO_ACTION`

---

## Weekly operator rhythm

| Step | Action | Output |
|------|--------|--------|
| 1 | Drop new PDFs in `raw/` | — |
| 2 | Extract text | `extracted/<source_id>.txt` via `scripts/ingest/batch_extract_pdfs.py` |
| 3 | Add row to `research_index.csv` | `status=RAW_EXTRACTED` |
| 4 | Fill card from template | `cards/<source_id>.md`, `status=CARD_CREATED` |
| 5 | Review facts vs source | `status=REVIEWED` |
| 6 | Update watchlist if needed | `config/watchlist.txt`, `status=WATCHLIST_UPDATED` |
| 7 | Publish weekly digest (top 10 each section) | `weekly_digest/YYYY-MM-DD.md` |
| 8 | Optional sector dashboard | `sector_dashboard/<sector>_YYYY-MM-DD.md` |
| 9 | Index summary | `python -m src.research.intake summarize-index` |

**Time-box:** 30–45 min weekly for digest + index hygiene (excluding deep read of new reports).

---

## Research card rules

Each card (`templates/research/research_card_template.md`) must include:

1. **Facts only** (source-linked)
2. **Thesis impact**
3. **Catalysts**
4. **Risks**
5. **Watchlist decision**
6. **Trading workflow implication** (explicit NO to `final_action` / orders)

---

## What research **can** influence

| # | Influence |
|---|-----------|
| 1 | Watchlist upgrade / downgrade |
| 2 | Review priority (which names to read first in weekly HTML / cloud board) |
| 3 | Manual override **justification** (logged separately — not automatic) |
| 4 | Monthly thesis update memos |

---

## What research **cannot** do

| # | Prohibited |
|---|------------|
| 1 | Create `final_action` |
| 2 | Override `final_action` |
| 3 | Create orders |
| 4 | Change sizing / T1 / T2 |
| 5 | Promote S3 / intraday to production OMS |

---

## Integration with Stage 0 lanes

```text
Lane 2 — Signal SSOT (unchanged)
  phase36 scan → phase36_daily_scan_latest.csv → final_action

Lane 1 — Weekly decision support (unchanged)
  weekly_pareto_operator → reports/latest/index.html

Lane R — Research intake (NEW, parallel, read-only vs Lane 2)
  PDF → extracted → card → index → weekly_digest
  Never writes to scan CSV, OMS, or allocation_plan.json
```

**Phase36 overlap:** Weekly digest section 5 lists tickers that appear in both research cards and the scan — for **context only**. Operator reconciles manually.

**Distribution Risk / cloud board:** Research may inform how you *read* context; it does not change `distribution_risk_latest.json` or cloud signal math.

---

## Commands

```powershell
# Extract PDFs (batch)
.\.venv\Scripts\python.exe scripts\ingest\batch_extract_pdfs.py `
  --source "C:\path\to\pdfs" `
  --out data\research\intake\extracted\batch_YYYYMMDD

# Index summary (no LLM)
.\.venv\Scripts\python.exe -m src.research.intake summarize-index
```

---

## Related docs

- `docs/OPERATING_BACKBONE_PARETO.md` — Stage 0 backbone
- `docs/workflow/CHATGPT_STAGE0_OPERATOR_WORKFLOW_OPTIMIZATION_PROMPT.md` — full workflow review
- `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` — scan SSOT
- `data/research/intake/README.md` — folder quick reference

---

*No strategy logic changed. Research does not set or override final_action. Real capital remains NO-GO.*
