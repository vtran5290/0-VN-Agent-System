# p20 Baseline+ OOS Evaluation

## Executive conclusion
- PASS variants: ['B1_p_now_only']
- Baseline benchmark remains B0 unless a variant meets strict PASS rules.

## What beat baseline / what did not
- B1_p_now_only: PASS | hit_uplift_pp=2.2397855167983898
- B2_p_hist_only: WATCH | hit_uplift_pp=0.04468800715008159
- E1_p20_persistence: WATCH | hit_uplift_pp=0.1326807406533792
- E2_p20_accel: FAIL | hit_uplift_pp=-0.39273920944137286
- E3_p20_extension_penalty: FAIL | hit_uplift_pp=-0.3211881391643967
- F1_baseline_plus_fixed: FAIL | hit_uplift_pp=-0.7914075749010735

## Daily-pick vs episode-level
- Episode-level removes repeated same-symbol picks inside cooldown and is stricter.

## Recommended production score
- Keep `B0_baseline_p20` unless a variant is PASS under acceptance rules.

## Next research step
- Continue minimal ablations only; avoid complex models until episode-level OOS uplift is proven.

## Research references (not production)
- v2/v2.2/v2.3 scripts are retained as references only.