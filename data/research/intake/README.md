# Research intake (Stage 0)

Thesis / watchlist context only — does **not** set or override `final_action`.

| Folder | Purpose |
|--------|---------|
| `raw/` | Original PDFs / notes (drop zone) |
| `extracted/` | Full-text `.txt` from PDF extraction |
| `cards/` | One markdown card per report (`research_card_template.md`) |
| `index/` | `research_index.csv` — master index |
| `weekly_digest/` | Weekly top-10 digest (template output) |
| `sector_dashboard/` | Sector thesis rollup (template output) |

**Workflow:** `docs/research/RESEARCH_INTAKE_WORKFLOW.md`

**Prior batch extracts (legacy path):** `data/intake/raw_extract/` — copy or link into `extracted/` as needed.

**Index summary:** `python -m src.research.intake summarize-index`
