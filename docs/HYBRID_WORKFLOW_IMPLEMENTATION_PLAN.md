# Hybrid Workflow — Implementation Plan (ChatGPT → Cursor)

**Role:** Senior AI systems engineer / institutional research workflow architect.  
**Goal:** Convert operating logic from ChatGPT research workflow into a clean, implementation-oriented plan for the Cursor engine.

---

## 1) SYSTEM UPDATE SUMMARY

### What to ADD

| Item | Location | Description |
|------|----------|-------------|
| **Bond/monetary snapshot apply** | New script or intake step | Apply `bond_monetary_snapshot` from a JSON pack into `manual_inputs` (or dedicated `data/state/bond_monetary_snapshot.json`) so Fed Dashboard / VN rates are updated without overwriting other manual_inputs keys. |
| **Research pack hard_facts validation** | `src/intake/apply_research_engine_pack.py` | Validate each `research_files[].hard_facts`: max 8 per file; each fact must have `value`, `unit`, `period`, `page`, `evidence_quote`, `source_id`. Warn or reject on violation. |
| **doc_type enum extension** | `data/raw/research_engine_pack.template.json` + prompts | Add `strategy_note` and `flashnote` to `doc_type` enum in template and document in prompts (prompts already have them). |
| **intake_takeaways "source" preservation** | `src/intake/apply_consensus_pack.py` | In `_norm_takeaways()`, preserve `source` from each item into the normalized output so Research Intake can show provenance. |
| **Strategy_note / flashnote in report** | `src/interpret/templates.py` | Add `strategy_note` and `flashnote` to `INTAKE_TYPE_HEADING` and to the loop in `render_research_intake_section()` so they appear under "Strategy note" / "Flashnote" subsections. |
| **Revision tracker** | New script + path | Script to append/write `data/intake/earnings/revisions/<asof_date>.csv` (columns: ticker, revision_signal, magnitude_if_any, reason_short, source_id). Optional: read from weekly_notes or a small pack. |
| **Council packet v2 extensions** | `scripts/build_council_packet_v2.py` | (Optional) Read `data/config/coverage_tiers.yaml` for tier1/tier2/tier3; add `tier1_anomaly_queue` when Tier1 ticker has anomaly. Read `data/config/sensitivity_map.yaml` and add `sensitivity_map` to packet for regime-aware council. |
| **Make target: bond-snapshot-apply** | Makefile | Target to apply `data/raw/bond_monetary_snapshot.json` (or env-specified path) into state/manual_inputs. |
| **ChatGPT command aliases reference** | `knowledge/prompt_aliases.md` or `docs/` | One-pager listing: PromptList, DualExtract, ResearchEngine, BizSummary, MacroDeep, SectorDeep, CouncilRun, MonthlyRegimeRun, BondSnapshot with one-line contract (e.g. ResearchEngine = STRICT JSON only). |

### What to CHANGE

| Item | Current | Change |
|------|---------|--------|
| **weekly_notes_patch application** | Research pack uses same `_apply_weekly_notes_patch` as consensus; patch keys **replace** entire arrays (e.g. `intake_takeaways`). | Document clearly: Information Flow (research) **replaces** by key; Capital Flow (consensus) **replaces** by key. No merge-by-item to avoid ambiguity. |
| **Drift guard key names** | Template uses `interpretation_added`, `decision_added`. | Keep as-is; user contract matches. Ensure all prompts and validation use these exact keys. |
| **Default allow_null_overwrite** | `False` in both consensus and research apply. | Keep `False`; require explicit `--allow-null-overwrite` for machine intake so null/unknown never overwrite by default. |

### What to DEPRECATE

| Item | Action |
|------|--------|
| **None** | No removal of existing behavior. Clarify in docs: **Consensus pack** = Capital Flow (fund commentary / holdings) = monthly cadence. **Research engine pack** = Information Flow (macro / sector / company / policy / strategy_note / flashnote) = weekly cadence. |

---

## 2) REPO IMPLEMENTATION PLAN

### Files to CREATE

| File | Purpose |
|------|---------|
| `scripts/apply_bond_monetary_snapshot.py` | Read `data/raw/bond_monetary_snapshot.json` (or path arg); merge `bond_monetary_snapshot.us` / `.vietnam` into `data/state/bond_monetary_snapshot.json` or into `manual_inputs.json` under a key `bond_monetary` (non-destructive: only set keys present in pack). |
| `data/intake/earnings/revisions/.gitkeep` | Ensure directory exists for revision_tracker output. |
| `scripts/revision_tracker.py` | Read a small pack or `weekly_notes.earnings_facts`; write/append `data/intake/earnings/revisions/<asof_date>.csv` (ticker, revision_signal, magnitude_if_any, reason_short, source_id). |
| `docs/CHATGPT_COMMAND_ALIASES.md` | List of command aliases and their contract (ResearchEngine = strict JSON only; DualExtract = markdown + JSON; Human prompts = markdown only; CouncilRun, MonthlyRegimeRun, BondSnapshot). |

### Files to MODIFY

| File | Change |
|------|--------|
| `data/raw/research_engine_pack.template.json` | In `research_files[0]`, set `doc_type` to `"macro_report"` and add comment or second example with `strategy_note` / `flashnote`. Add comment: `hard_facts` max 8 per file; each requires value, unit, period, page, evidence_quote, source_id. |
| `src/intake/apply_consensus_pack.py` | In `_norm_takeaways()`, add `"source": _safe_text(item.get("source"), "")` to each output item so `intake_takeaways` in weekly_notes can carry source. |
| `src/interpret/templates.py` | Add `"strategy_note": "Strategy note"`, `"flashnote": "Flashnote"` to `INTAKE_TYPE_HEADING`. In `render_research_intake_section()`, extend the loop to iterate over `("macro_report", "sector_report", "company_report", "policy_report", "strategy_note", "flashnote")` so new types render. |
| `src/intake/apply_research_engine_pack.py` | After reading pack, validate each `research_files[].hard_facts`: length ≤ 8; each element has required keys. Log warning or raise if invalid. Optionally validate `doc_type` in allowed set. |
| `Makefile` | Add `bond-snapshot-apply:` target calling `python -m scripts.apply_bond_monetary_snapshot` (or similar). Ensure `monthly-regime-run` or equivalent exists if needed for MonthlyRegimeRun alias. |

### Suggested folder structure (already largely in place)

```
data/
  raw/                    # Input packs (research_engine_pack.json, consensus_pack.json, bond_monetary_snapshot.json, earnings_heatmap_pack.json)
  state/                  # regime_state, last_regime_state, bond_monetary_snapshot (if split out)
  decision/               # council_output, weekly_report, allocation_plan
  intake/
    machine/              # research pack archive + research_files cards
      archive/
      research_files/
    earnings/
      heatmap/            # earnings heatmap by asof_date
      revisions/          # revision_tracker output CSVs
  config/
    coverage_tiers.yaml   # tier1, tier2, tier3
    one_off_watchlist.yaml
    sensitivity_map.yaml
artifacts/                # council_packet_weekly.json, earnings_heatmap.md/csv, earnings_quality_flags.csv
knowledge/                # resolver_rules, prompt_aliases (optional)
docs/                     # EARNINGS_INTAKE_SPEC, HYBRID_WORKFLOW_IMPLEMENTATION_PLAN, CHATGPT_COMMAND_ALIASES
```

### Make targets / scripts to add

| Target | Command / note |
|--------|----------------|
| `bond-snapshot-apply` | `python -m scripts.apply_bond_monetary_snapshot` [--pack path] |
| `revision-tracker` | `python -m scripts.revision_tracker` [--asof YYYY-MM-DD] [--pack path] |
| Existing: `research-pack-apply` | `python -m src.intake.apply_research_engine_pack --pack $(RESEARCH_PACK)` |
| Existing: `research-pack-apply-strict` | Same with `--strict-drift-guard` |
| Existing: `earnings-heatmap-apply` | `python -m scripts.earnings_heatmap_apply` |
| Existing: `earnings-quality-flags` | `python -m scripts.earnings_quality_flags` |
| Existing: `council-packet-v2` | `python -m scripts.build_council_packet_v2` |

---

## 3) DATA CONTRACTS

### Machine intake contract (research_engine_pack)

- **extraction_mode:** `"non_fund_intake_v1"`. Engine may warn if different; apply still proceeds unless strict validation is added.
- **drift_guard:** `{ "interpretation_added": false, "decision_added": false }`. If either true, `--strict-drift-guard` fails the apply.
- **manual_inputs_patch:** `{}` unless explicit, validated macro numbers with citation. No allocation, no trade advice, no sizing.
- **weekly_notes_patch:** Only keys present are applied; each key **replaces** the full array in weekly_notes (policy_facts, earnings_facts, broker_notes, intake_takeaways).
- **research_files[].hard_facts:** Max 8 per file. Each fact: `value`, `unit`, `period`, `page`, `evidence_quote`, `source_id`. Use `null` for unknown; do not invent.
- **research_files[].doc_type:** One of `macro_report`, `sector_report`, `company_report`, `policy_report`, `strategy_note`, `flashnote`.
- **unknown_fields:** List of field names that were in the source but not in the schema; pass through for audit.

### Bond/monetary snapshot schema

- As in `data/raw/bond_monetary_snapshot.template.json`: `bond_monetary_snapshot.us` (fed_funds_rate, ust_2y, ust_10y, real_yield_10y, qt_qe_status), `bond_monetary_snapshot.vietnam` (refinancing_rate, omo_rate, interbank_overnight, credit_growth_ytd, vn_10y_gov_bond, fx_usd_vnd). Each metric: `value`, `unit`, `date` or `period`.

### Drift guard rules

- **interpretation_added:** Must be false for pure machine intake. If true, pack is considered to contain human interpretation; strict mode rejects.
- **decision_added:** Must be false for pure machine intake. If true, pack is considered to contain allocation/decision content; strict mode rejects.

### Null overwrite rules

- **Default:** `allow_null_overwrite=False`. Values that normalize to `null` or `"unknown"` (e.g. fed_tone, liquidity states) do **not** overwrite existing values in manual_inputs.
- **Explicit:** With `--allow-null-overwrite`, null/unknown in patch **do** overwrite. Use only when intentionally clearing fields.

### Archive rules

- **Research pack:** Every apply writes `data/intake/machine/archive/research_pack_<asof>_<utc_timestamp>.json` and updates `research_pack_latest.json`. Per-file cards go to `data/intake/machine/research_files/<asof>/<doc_id>.json`. Non-destructive: existing archives are never overwritten by timestamp.
- **Consensus pack:** Writes to `data/smart_money/weekly/` (latest + dated). No archive dir for consensus; dated file is the audit.
- **Bond snapshot:** Apply script should merge into state or manual_inputs; optional archive to `data/intake/machine/archive/bond_snapshot_<asof>_<timestamp>.json` for traceability.

---

## 4) NEW MODULES TO ADD (or clarify)

| Module | Status | Action |
|--------|--------|--------|
| **earnings_heatmap_pack** | Exists | `data/raw/earnings_heatmap_pack.json` + `scripts/earnings_heatmap_apply.py`. Score 1–5 by sector; archive to `data/intake/earnings/heatmap/<asof>.json`; render artifacts. No change except ensure score is 1–5 in spec. |
| **tiered_coverage** | Config exists | `data/config/coverage_tiers.yaml` (tier1, tier2, tier3). Optionally have `build_council_packet_v2` read it and add `tier1_list`, `tier2_list` to packet for council prioritization. |
| **one_off_flagger** | Exists | `scripts/earnings_quality_flags.py`; QUALITY_FLAGS = one_off_gain, provision_cleanup, inventory_gain_loss, fx_gain_loss, disposal_gain, accounting_reversal. Output: `artifacts/earnings_quality_flags.csv`. Align with user list; no code change if already complete. |
| **council_packet_v2 builder** | Exists | `scripts/build_council_packet_v2.py`. Extend: (1) read coverage_tiers and add to packet; (2) read sensitivity_map and add sector→regime_vars for council; (3) optional invalidators from weekly_report or market_flags. |
| **revision_tracker** | Path in spec | Create `scripts/revision_tracker.py` that writes `data/intake/earnings/revisions/<asof>.csv` (ticker, revision_signal, magnitude_if_any, reason_short, source_id). Input: small pack or earnings_facts with revision info. |
| **sensitivity_map** | Config exists | `data/config/sensitivity_map.yaml` (sector → list of regime variables). Add a small reader in `build_council_packet_v2` or a dedicated `src/intake/sensitivity_map.py` and expose in council packet for regime-aware early warning. |

---

## 5) PRIORITY ORDER

### Quick wins (do first)

1. Add `strategy_note` and `flashnote` to `INTAKE_TYPE_HEADING` and to the render loop in `src/interpret/templates.py`.
2. In `_norm_takeaways()`, preserve `source` in each intake_takeaway item.
3. Add `bond-snapshot-apply` Make target and `scripts/apply_bond_monetary_snapshot.py` (merge snapshot into state or manual_inputs, non-destructive).
4. Document drift_guard and null-overwrite rules in `docs/` (this file and/or EARNINGS_INTAKE_SPEC).
5. Add `docs/CHATGPT_COMMAND_ALIASES.md` with ResearchEngine, DualExtract, CouncilRun, etc.

### Medium-term improvements

1. In `apply_research_engine_pack.py`, add validation: each `research_files[].hard_facts` length ≤ 8; each fact has required keys; log warning or reject.
2. Implement `scripts/revision_tracker.py` and `revision-tracker` Make target.
3. Extend `build_council_packet_v2.py` to include coverage_tiers and sensitivity_map in the packet.
4. Update `research_engine_pack.template.json` with doc_type comment and hard_facts comment.

### Later / nice-to-have

1. Council packet v2: invalidators from weekly_report/market_flags; tier1_anomaly_queue when Tier1 ticker has anomaly.
2. Optional: merge strategy_note and flashnote into a single "Other research" subsection if they are rare.
3. Bond snapshot: optional archive to `data/intake/machine/archive/` for full audit trail.

---

## 6) EXACT COMMANDS / MAKE TARGETS

### Weekly (Information Flow + Council)

```bash
# 1) Roll week (optional, if you use roll)
make roll

# 2) Apply research pack (when ChatGPT produces research_engine_pack.json)
make research-pack-apply
# Or strict: make research-pack-apply-strict  # fails if drift_guard has interpretation/decision

# 3) Generate weekly report (JSON + optional MD)
make weekly

# 4) Council secretary weekly checklist
make council-secretary-weekly

# 5) Human: run council prompts (orchestrator → constraint_enforcer), save council_output.json

# 6) Re-run weekly so decision log gets council fields (optional)
make weekly
```

### Monthly (Capital Flow + Audit)

```bash
# 1) Council audit monthly
make council-audit-monthly

# 2) Apply consensus pack (Capital Flow: fund commentary / holdings)
make consensus-apply
# Or dry-run: make consensus-apply-dry-run

# 3) Monthly regime / review (if applicable)
make monthly-review
```

### Ad hoc

```bash
# Bond snapshot (after BondSnapshot in ChatGPT)
make bond-snapshot-apply

# Earnings heatmap (after earnings heatmap pack is filled)
make earnings-heatmap-apply

# Earnings quality flags (from weekly_notes.earnings_facts)
make earnings-quality-flags

# Council packet v2 (after weekly + council_output)
make council-packet-v2

# Revision tracker (when revision pack or earnings_facts have revision data)
make revision-tracker
```

---

## 7) RISK REVIEW

### Likely failure modes

| Risk | Description | Prevention |
|------|-------------|------------|
| **Wrong extraction_mode** | Pack from ChatGPT with wrong mode (e.g. fund intake) applied as research. | Engine warns when mode != `non_fund_intake_v1`. Consider strict option to reject. |
| **Drift guard bypass** | Machine intake contains interpretation or decision but drift_guard not set. | Require drift_guard in schema; `--strict-drift-guard` fails apply if interpretation_added or decision_added is true. |
| **Null overwrite wiping data** | Patch with null/unknown overwrites good manual_inputs. | Default `allow_null_overwrite=False`; never use in automated pipeline without explicit flag. |
| **Archive overwrite** | New apply overwrites previous archive. | Archive filenames include UTC timestamp; only `research_pack_latest.json` and `*_latest.json` are overwritten. |
| **Full replace of weekly_notes key** | Sending a partial intake_takeaways patch and expecting merge. | Document: patch **replaces** entire array for that key. ChatGPT must send full array for the week or merge client-side before sending. |
| **hard_facts too many or missing fields** | Model emits >8 facts or omits evidence_quote/source_id. | Validation in apply_research_engine_pack: truncate to 8 and warn, or reject; require fields or warn. |

### Drift risks

- **Intake vs decision blur:** Keep ResearchEngine output strictly to facts; no allocation/sizing/trade advice. Council layer is the only place that produces decisions.
- **Capital Flow vs Information Flow:** Consensus pack = monthly, fund-focused. Research pack = weekly, non-fund. Do not mix; use different apply targets and different prompts.

### Ingestion risks

- **Large packs:** Very large research_files arrays could make weekly report slow. Consider max files per pack (e.g. 20) and truncate with warning.
- **Invalid JSON or schema:** Validate schema on apply; fail fast with clear error.

### Overwrite risks

- **manual_inputs:** Only keys in `manual_inputs_patch` are touched; nested keys are merged (e.g. patch `global.ust_2y` only updates that). So long as patch does not send null with allow_null_overwrite, existing values stay.
- **weekly_notes:** If patch contains `policy_facts`, the **entire** `policy_facts` array is replaced. So ChatGPT must send complete array for the week, not only new items.

### How to prevent

1. **Strict drift guard** in CI or weekly script when applying research pack: `make research-pack-apply-strict`.
2. **No allow_null_overwrite** in any scheduled or default path; only when human explicitly clears a field.
3. **Archive with timestamp** for every research pack apply; keep at least 4 weeks of archives.
4. **Schema validation** for research_engine_pack and consensus_pack before apply; document required and allowed keys in this doc and in template comments.
5. **Prompt contract** in CHATGPT_COMMAND_ALIASES: ResearchEngine = STRICT JSON only; no allocation, no trade advice, no sizing; unknown → null; max 8 hard_facts per file.

---

*End of implementation plan. Use this document for Cursor planning and incremental implementation.*
