# Research Machine Intake Contract (Non-fund Reports)

Scope: macro reports, broker notes, company updates, sector adhoc notes, policy updates.

This contract is for **information ingestion**, not portfolio decision.

---

## 1) What ChatGPT must do

- Output STRICT JSON only when using machine mode.
- Keep extraction factual; no trade advice.
- Include citation evidence (`page`, `evidence_quote`, `source_id`) for hard facts.
- Keep `manual_inputs_patch` empty unless high-confidence, directly cited macro fields exist.

---

## 2) Required JSON controls

- `extraction_mode` must be: `non_fund_intake_v1`
- `drift_guard` must include:
  - `interpretation_added` (bool)
  - `decision_added` (bool)

Example:

```json
"extraction_mode": "non_fund_intake_v1",
"drift_guard": {
  "interpretation_added": false,
  "decision_added": false
}
```

If either drift_guard flag is true, pack is considered non-pure intake.

---

## 3) Data quality rules

- Max 8 hard facts per file.
- Unknown values -> `null` (never guessed numbers).
- Preserve source lineage in `sources[]`.
- `report_date`, `target_price`, ratings may be null/Unknown if not stated.

---

## 4) Mapper behavior in repo

Command:

```bash
make research-pack-apply RESEARCH_PACK=data/raw/research_engine_pack.json
```

Strict mode (recommended for production hygiene):

```bash
make research-pack-apply-strict RESEARCH_PACK=data/raw/research_engine_pack.json
```

What it does:
- Updates `data/raw/manual_inputs.json` and `data/raw/weekly_notes.json`
- Archives full raw pack under `data/intake/machine/archive/`
- Writes per-file cards to `data/intake/machine/research_files/<asof_date>/`

Safety:
- Manual patch is non-destructive by default (null/unknown does not wipe existing values).

---

## 5) Additional request checklist for ChatGPT

Before returning output, enforce:

1. No allocation/sizing/overweight suggestions.
2. Hard facts all have citation fields.
3. `manual_inputs_patch` only filled for explicitly stated macro values.
4. No narrative-only statements in machine JSON.
5. Keep array size compact (<=5 items for weekly notes arrays).

