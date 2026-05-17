# Phase36C — Sizing Overlay

Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold=0.446

## Tested Variants

| Variant | gk_col flag | size_mult | MAR | Δ-MAR | Accept? |
|---------|-------------|-----------|-----|-------|---------|
| lead_best_125x | - | - | 0.3746 | -0.0414 | no |
| chase_75x | - | - | 0.3725 | -0.0435 | no |
| equal_weight | - | - | 0.3462 | -0.0698 | no |

## Conclusion

Best sizing variant: lead_best_125x
MAR = 0.3746
Accepted: NO — improvement below +0.03 threshold

## Hard Rules

- Sizing adjustments are ADVISORY only
- GK multiplier (Phase33) is already implemented and validated
- S3-lead sizing boost does NOT block A3 signals
- No sizing variant may exceed 2× base slot weight
