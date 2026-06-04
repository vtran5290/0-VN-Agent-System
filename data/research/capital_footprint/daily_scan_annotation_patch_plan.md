# Daily Scan Annotation Patch Plan — Capital Footprint Phase Labels

**Date:** 2026-05-30
**Status:** PROPOSAL ONLY. Not yet implemented. Requires explicit approval.

---

## Objective

Add 4 non-binding annotation columns to the daily scan output for operator review.
These columns do NOT change final_action, position sizing, OMS logic, or DNSE routing.

---

## Proposed Columns

| Column | Type | Source | Description |
|---|---|---|---|
| `cf_phase_label` | str | classifier.py → phase_label | Phase label assigned by CF classifier |
| `cf_operator_note` | str | derived from cf_phase_label | Human-readable note for operator |
| `cf_event_age` | int | event_age from detect_label_entry_events() | Days since this label first appeared for this symbol |
| `cf_event_cooldown_flag` | int (0/1) | event_cooldown_flag | 1 if within 20-bar cooldown window (duplicate signal) |

---

## cf_operator_note Values

| cf_phase_label | cf_operator_note |
|---|---|
| EXTENSION_DISTRIBUTION_RISK | ⚠ Extended — review for distribution before adding |
| SUPPLY_ABSORPTION_SETUP | ✓ Dry-up setup near high — monitor for entry |
| BREAKOUT_CONFIRMED | ✓ Volume-confirmed breakout — follow-through window |
| BREAKOUT_FOLLOW_THROUGH_PENDING | ~ Breakout pending volume confirm — watch |
| FAILED_BREAKOUT | ✗ Breakout failed — avoid until structure repairs |
| NEUTRAL | (blank) |

For extension sublabels:
| extension_sublabel | cf_operator_note suffix |
|---|---|
| LEADERSHIP_STRONG | (no warning — healthy leadership) |
| EXTENDED_BUT_HEALTHY | ~ Extended but healthy — trend continuation possible |
| EXTENSION_DISTRIBUTION_RISK | ⚠ Extended + distribution — mean-reversion risk |

---

## Implementation Plan

### Step 1: Add CF panel build to daily scan pipeline
File: `src/trading/daily_scan.py` (or equivalent scan runner)

```python
# Non-binding annotation — no effect on final_action
if CF_ANNOTATION_ENABLED:  # feature flag, default False
    cf_panel = build_feature_panel(min_adv50_vnd=1e8, include_fa=False)
    cf_panel = assign_phase_labels(cf_panel)
    cf_panel = detect_label_entry_events(cf_panel, cooldown_days=20)
    # Left-join to scan output on (symbol, date)
    scan_df = scan_df.merge(
        cf_panel[["symbol", "date", "phase_label", "event_age", "event_cooldown_flag"]],
        on=["symbol", "date"], how="left"
    )
    scan_df = scan_df.rename(columns={
        "phase_label": "cf_phase_label",
        "event_age": "cf_event_age",
        "event_cooldown_flag": "cf_event_cooldown_flag",
    })
    scan_df["cf_operator_note"] = scan_df["cf_phase_label"].map(CF_OPERATOR_NOTES)
```

### Step 2: Feature flag
Add `CF_ANNOTATION_ENABLED = False` to `config/trading.yaml` under `[research]` section.
Operator must explicitly set to `True` to activate.

### Step 3: JSON output
Add annotation columns to `data/decision/daily_scan.json` as a nested `cf_annotation` dict:
```json
{
  "symbol": "VHM",
  "final_action": "HOLD",
  ...
  "cf_annotation": {
    "cf_phase_label": "SUPPLY_ABSORPTION_SETUP",
    "cf_operator_note": "✓ Dry-up setup near high — monitor for entry",
    "cf_event_age": 3,
    "cf_event_cooldown_flag": 1
  }
}
```

---

## Constraints

| Constraint | Value |
|---|---|
| Affects final_action | **NO** |
| Affects position sizing | **NO** |
| Affects OMS | **NO** |
| Affects DNSE | **NO** |
| Requires approval to activate | **YES** — set CF_ANNOTATION_ENABLED=True in config |
| Runtime cost | ~30-45s additional (CF panel build) |

---

## Approval Required

Before any implementation:
1. Review Phase 3 event-level stats to confirm label quality
2. Confirm A3 diagnosis accepted (structural limit, no code fix needed)
3. Operator sets `CF_ANNOTATION_ENABLED=True` explicitly

---

*Patch plan: Phase 3 research output*
*Implementation target: Post Phase 3 evidence review*
