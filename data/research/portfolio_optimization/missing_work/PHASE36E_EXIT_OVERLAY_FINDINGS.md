# Phase36E — Exit Overlay

Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold=0.446

## Method

Tests different exit parameters applied globally to A3 trades.
Per-trade exit conditioning on S3 lead is not implemented in this pass
(would require separate per-symbol rebuilds by lead group).

| Variant | trail_mult | max_hold | MAR | Δ-MAR | Accept? |
|---------|-----------|---------|-----|-------|---------|
| max_hold_180_all | - | - | 0.2900 | -0.1260 | no |
| wide_trail_30_all | - | - | 0.2746 | -0.1414 | no |
| baseline_a3_trail25 | - | - | 0.2629 | -0.1531 | no |
| tight_trail_20_all | - | - | 0.1039 | -0.3121 | no |

## Hard Rules

- A3 production exit parameters (2.5×ATR14, max_hold=250) are locked unless
  this research shows MAR improvement ≥ +0.03 with a specific override
- Any accepted exit variant requires operator review before adoption
