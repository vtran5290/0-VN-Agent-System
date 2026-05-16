# Sector L4 Patch Notes

Date: 2026-05-16

## What Changed

SECTOR_L4_FINAL_FINDINGS.md incorrectly classified sector L4 as SHADOW_RISK_CONTROL.

### Original wording:
```
## Decision
SHADOW_RISK_CONTROL
```

### Correct wording:
```
## Decision: DASHBOARD_WARNING_ONLY
```

## Why SHADOW_RISK_CONTROL Was Wrong

SHADOW_RISK_CONTROL implies the rule is actively applied in shadow mode (e.g. paper trade capital is
managed using the sector rule). This is incorrect — the sector stress tests showed:

- Best sector rule (l4_breadth<50%): MAR 0.416 → 0.438 (+0.022). Marginal, not material.
- All name caps HURT MAR: max_1_per_l4 MAR=0.197, max_2_per_l4 MAR=0.319.
- Decision: sector L4 is dashboard awareness only. No automatic trade blocks.

## Correct Final Status

| Mechanism | Status |
|-----------|--------|
| Sector L4 breadth stress rules | DASHBOARD_WARNING_ONLY |
| Sector L4 name/exposure caps | REJECTED — hurts MAR |
| Concentration alert (>30% same L4) | Dashboard warning only, operator judgment |

## Files Updated

| Original | Updated | Change |
|----------|---------|--------|
| SECTOR_L4_FINAL_FINDINGS.md | UPDATED_SECTOR_L4_FINAL_FINDINGS.md | SHADOW_RISK_CONTROL → DASHBOARD_WARNING_ONLY |
| FINAL_OPEN_ITEMS.md | UPDATED_FINAL_OPEN_ITEMS.md | Sector stress rule rejection reason added |
