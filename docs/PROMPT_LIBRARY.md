# Prompt Library (ChatGPT <-> Cursor)

Use this page as command center for prompt invocation and low-token workflow.

---

## 1) Mode split (recommended)

- **ChatGPT mode (reading + extraction):**
  - Deep reading of long PDF reports.
  - Strict JSON machine intake output.
- **Cursor mode (mapping + storage + workflow):**
  - Apply JSON pack into repo.
  - Build weekly council packet and logs.

Rule of thumb:
- ChatGPT reads documents.
- Cursor reads JSON.

---

## 2) Prompts to use in ChatGPT

- **Smart Money weekly feeder:**
  - `prompts/smart_money_consensus_pack.md`
- **Non-fund machine intake (strict JSON only):**
  - `prompts/research_engine_machine_intake.md`
- **Dual output for long reports (human deep dive + JSON):**
  - `prompts/research_engine_dual_output_long_report.md`
- **Bond / monetary quick snapshot (strict JSON):**
  - `prompts/bond_monetary_snapshot_extract.md`

Optional aliases you can use manually:
- `SmartMoneyPack`
- `ResearchMachine`
- `DualExtract`

---

## 3) Cursor commands after you paste JSON

### Smart Money weekly pack

1. Save JSON to: `data/raw/consensus_pack.json`
2. Apply:

```bash
make consensus-apply
```

Preview before apply:

```bash
make consensus-apply-dry-run
```

### Non-fund machine intake pack

1. Save JSON to: `data/raw/research_engine_pack.json`
2. Apply:

```bash
make research-pack-apply
```

Optional strict mode (fail when drift_guard is violated):

```bash
make research-pack-apply-strict
```

### Continue weekly council flow

```bash
make council-weekly
```

### Weekly Smart Money change monitor

```bash
make smart-money-weekly-diff
```

---

## 4) Minimal files to keep in mind

- `data/raw/consensus_pack.template.json`
- `data/raw/research_engine_pack.template.json`
- `data/raw/bond_monetary_snapshot.template.json`
- `docs/SMART_MONEY_DATA_CONTRACT.md`
- `docs/RESEARCH_MACHINE_INTAKE_CONTRACT.md`

