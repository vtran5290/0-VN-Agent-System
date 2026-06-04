# Stage 0 research index (dated snapshots)

Thesis / watchlist context only — does **not** set or override `final_action`.

| File | Purpose |
|------|---------|
| `research_index_YYYY-MM-DD.csv` | Dated snapshot after a research batch |
| `research_index_latest.csv` | Pointer copy of the newest batch |

**Intake SSOT (same rows):** `data/research/intake/index/research_index.csv`

**Synthesis digest:** `data/research/intake/weekly_digest/2026-05-24_chatgpt_synthesis.md`

**Raw text extracts:** `data/intake/raw_extract/2026-05-24*` (88 files as of 2026-05-24)

**Rebuild index from manifests:**

```powershell
.\.venv\Scripts\python.exe scripts\research\bootstrap_stage0_research_index.py
```

**Summary:**

```powershell
.\.venv\Scripts\python.exe -m src.research.intake summarize-index
```
