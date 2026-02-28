# Smart Money Data Contract (Hybrid)

Purpose: keep weekly workflow simple while preserving monthly institutional depth.

This contract defines what data goes into:
- `data/smart_money/*` (Capital Flow Layer)
- `data/raw/weekly_notes.json` (Information Flow Layer)

It also defines the JSON format accepted by:
- `python -m src.intake.apply_consensus_pack`

**Format check (10s):** Compare your JSON to the samples before apply.
- **Good (passes schema):** `data/raw/consensus_pack.good.json`
- **Bad (fails schema):** `data/raw/consensus_pack.bad.json`  
Dry-run: `make consensus-apply-dry-run CONSENSUS_PACK=data/raw/consensus_pack.good.json` vs same with `.bad.json` to see errors.

---

## 1) Two-layer rule (non-negotiable)

### Layer A - Capital Flow (monthly, deep)

Store in `data/smart_money/`:
- fund holdings (top positions, weights)
- sector allocation
- fund cash levels
- manager commentary from official fund letters

Do **not** store:
- broker research notes
- generic macro commentary
- ad-hoc company updates

Use this layer to track:
- ownership momentum
- crowding
- risk-on/off posture

Reference schema:
- `data/smart_money/_template.smart_money_month.json`
- `docs/SMART_MONEY_DASHBOARD.md`

### Layer B - Information Flow (weekly, light)

Store in `data/raw/weekly_notes.json`:
- policy facts
- earnings facts
- broker notes
- macro/sector/company intake takeaways

Use this layer for weekly Council context and event updates.

---

## 2) Consensus pack schema (accepted by mapper)

Top-level required keys:
- `asof_date`
- `extraction_mode` (`smart_money_consensus_v1`)
- `drift_guard`
- `manual_inputs_patch`
- `weekly_notes_patch`

Optional keys:
- `report_month_ref` (YYYY-MM, alias for `smart_money_month_ref`)
- `smart_money_month_ref`
- `smart_money_signals`
- `consensus_card`
- `unknown_fields`
- `sources`

Minimal example:

```json
{
  "asof_date": "2026-02-28",
  "extraction_mode": "smart_money_consensus_v1",
  "drift_guard": {
    "interpretation_added": false,
    "decision_added": false
  },
  "report_month_ref": "2026-02",
  "smart_money_month_ref": "2026-02",
  "smart_money_signals": {
    "mega_consensus": [],
    "sector_consensus": [],
    "crowding_score": null,
    "risk_on_score": null,
    "policy_alignment_score": null,
    "risk_flags": []
  },
  "manual_inputs_patch": {
    "global": {
      "fed_tone": "neutral",
      "ust_2y": null,
      "ust_10y": null,
      "dxy": null,
      "cpi_yoy": null,
      "nfp": null
    },
    "vietnam": {
      "omo_net": null,
      "interbank_on": null,
      "credit_growth_yoy": null,
      "fx_usd_vnd": null
    },
    "market": {
      "vnindex_level": null,
      "distribution_days_rolling_20": null
    },
    "overrides": {
      "global_liquidity": "tight",
      "vn_liquidity": "easing"
    }
  },
  "weekly_notes_patch": {
    "policy_facts": [],
    "earnings_facts": [],
    "broker_notes": [],
    "intake_takeaways": []
  }
}
```

Quick start:

```bash
cp data/raw/consensus_pack.template.json data/raw/consensus_pack.json
```

---

## 3) Mapper behavior (`apply_consensus_pack`)

Command:

```bash
python -m src.intake.apply_consensus_pack --pack data/raw/consensus_pack.json
```

Dry-run preview (no write):

```bash
python -m src.intake.apply_consensus_pack --pack data/raw/consensus_pack.json --dry-run
```

What it updates:
- `data/raw/manual_inputs.json`
- `data/raw/weekly_notes.json`

What it also writes for history:
- `data/smart_money/weekly/smart_money_consensus_latest.json`
- `data/smart_money/weekly/smart_money_consensus_<asof_date>.json` (if date exists)

Normalization rules:
- Unknown numeric values become `null`.
- `fed_tone` and liquidity overrides are constrained to known enums.
- Invalid intake type falls back to `company_report`.
- Manual patch is non-destructive by default (null/unknown does not wipe existing values). Use `--allow-null-overwrite` only when intentional.
- `drift_guard` should remain `false/false` (intake purity, no decision content).
- Schema validation runs before apply (required fields, enums, max list lengths, month/date format).

---

## 4) Scope boundary checklist (quick)

If a data point is about **capital actually allocated by funds** -> Layer A (`data/smart_money`).

If a data point is about **news/research/opinion/event** -> Layer B (`weekly_notes`).

Never merge the two into one table.

That separation prevents crowding distortion and narrative bias in weekly decisions.

