# Phase36D — T2 Policy Coordination

Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold=0.446

## Method

T2 exposure is modeled via `total_frac` column:
- total_frac=1.0: T1 (50%) + T2 (50%) — full slot filled
- total_frac=0.5: T1 only — half slot (T2 never executed)

This approximates dollar exposure impact. Actual return profile differs because
T2 pullback entry at a lower price is not modeled here (conservative estimate).

## Results

| Variant | MAR | Δ-MAR | Accept? |
|---------|-----|-------|---------|
| t2_only_if_good_lead | 0.4376 | 0.0216 | no |
| t2_blocked_for_chase | 0.3486 | -0.0674 | no |
| t2_always_baseline | 0.3462 | -0.0698 | no |
| t1_only_no_t2 | 0.2703 | -0.1457 | no |

## Hard Rules

- T2 policy does NOT block A3 T1 entries
- Breadth T2 block (pct_cloud_bull_a3 < 35%) remains unchanged
- VNINDEX bear block remains unchanged
- S3 lead affects T2 PRIORITY only, not T2 permission
