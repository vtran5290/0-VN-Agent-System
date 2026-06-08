# DNA x A3 Slot-Constrained Priority Sim — Run Log
Date: 2026-06-07
SIMULATION ONLY -- NOT A LIVE SIGNAL
STOCK_DNA_RESEARCH_ANNOTATION_ONLY

## Disclosures
IN-SAMPLE LOOKAHEAD: DNA profiles fit 2017-2026. Signals from 2013 carry full in-sample bias. CAGR/MAR are not predictive estimates.
Priority taxonomy: SUPPORT_ALIGNED proxied by production_status=RESEARCH_ANNOTATION_ONLY + edge_confidence tier.
Danger proxied by production_status=REJECT. No price-vs-support-line geometry computed.
Baseline ordering: symbol alpha (no DNA). All configs use identical stable tiebreak.
Exit dates: resolved via actual calendar date per symbol (not bar-count assumption).
Placebo config: DNA buckets randomly permuted (seed=42) -- null distribution.

## A3 Frozen Contract
- EMA cloud: fast=20, slow=100
- TP1: +18% on 50% | T2: >=4% within 30 bars
- Trail: 2.5x ATR14 | max_hold 250 bars | cost 40bps rt
- Min ADV: 2.0B VND | N_SLOTS=15 | pos=1/15

## Universe
- Panel: 269 symbols | DNA profiles: 412 | Bucket map: 412
- Trade outcomes pre-computed: 2643

## Full-Period Pareto Table (2013-2026, IN-SAMPLE)
| config                        | cagr   | max_dd   |   mar |   n_trades |   win_rate | avg_ret   | median_ret   |   avg_util_pct |   pct_days_full |   cash_drag_pct |   cap_rejections |   filter_rejections | and_gate   | soft_gate   | red_flags   |
|:------------------------------|:-------|:---------|------:|-----------:|-----------:|:----------|:-------------|---------------:|----------------:|----------------:|-----------------:|--------------------:|:-----------|:------------|:------------|
| a3_baseline_slot              | 7.2%   | 38.6%    |  0.19 |        349 |     0.7106 | 4.2%      | 14.5%        |          98.79 |           94.04 |            1.21 |             2294 |                   0 | N/A        | N/A         | none        |
| dna_priority_slot             | 6.1%   | 38.2%    |  0.16 |        340 |     0.6971 | 3.7%      | 14.2%        |          98.92 |           94.51 |            1.08 |             2303 |                   0 | FAIL       | FAIL        | none        |
| dna_danger_last               | 7.2%   | 38.6%    |  0.19 |        349 |     0.7106 | 4.2%      | 14.5%        |          98.79 |           94.04 |            1.21 |             2294 |                   0 | PASS       | FAIL        | none        |
| dna_danger_exclude            | 7.2%   | 38.6%    |  0.19 |        349 |     0.7106 | 4.2%      | 14.5%        |          98.79 |           93.98 |            1.21 |             2291 |                   3 | PASS       | FAIL        | none        |
| dna_priority_plus_danger_last | 6.1%   | 38.2%    |  0.16 |        340 |     0.6971 | 3.7%      | 14.2%        |          98.92 |           94.51 |            1.08 |             2303 |                   0 | FAIL       | FAIL        | none        |
| dna_random_permute            | 7.0%   | 32.0%    |  0.22 |        340 |     0.7088 | 4.2%      | 14.3%        |          98.81 |           93.91 |            1.19 |             2303 |                   0 | N/A        | N/A         | none        |

## Post-2017 Robustness Slice (DNA fit window starts 2017)
| config                               | cagr   | max_dd   |   mar |   n_trades |   win_rate | avg_ret   | median_ret   |   avg_util_pct |   pct_days_full |   cash_drag_pct |   cap_rejections |   filter_rejections | and_gate   | soft_gate   | red_flags   |
|:-------------------------------------|:-------|:---------|------:|-----------:|-----------:|:----------|:-------------|---------------:|----------------:|----------------:|-----------------:|--------------------:|:-----------|:------------|:------------|
| a3_baseline_slot_post17              | 7.0%   | 35.8%    |  0.19 |        266 |     0.7368 | 5.3%      | 15.1%        |          98.64 |           94.32 |            1.36 |             1951 |                   0 | --         | --          | --          |
| dna_priority_slot_post17             | 5.9%   | 34.9%    |  0.17 |        258 |     0.7403 | 4.6%      | 15.1%        |          98.84 |           95    |            1.16 |             1959 |                   0 | --         | --          | --          |
| dna_danger_last_post17               | 7.0%   | 35.8%    |  0.19 |        266 |     0.7368 | 5.3%      | 15.1%        |          98.64 |           94.32 |            1.36 |             1951 |                   0 | --         | --          | --          |
| dna_danger_exclude_post17            | 7.0%   | 35.8%    |  0.2  |        266 |     0.7368 | 5.3%      | 15.1%        |          98.63 |           94.23 |            1.37 |             1948 |                   3 | --         | --          | --          |
| dna_priority_plus_danger_last_post17 | 5.9%   | 34.9%    |  0.17 |        258 |     0.7403 | 4.6%      | 15.1%        |          98.84 |           95    |            1.16 |             1959 |                   0 | --         | --          | --          |
| dna_random_permute_post17            | 5.4%   | 34.6%    |  0.16 |        256 |     0.7266 | 4.3%      | 14.7%        |          98.69 |           94.4  |            1.31 |             1961 |                   0 | --         | --          | --          |

## By-Year Returns (selected configs)
|   year | a3_baseline_slot   | dna_danger_exclude   | dna_priority_slot   | dna_random_permute   |
|-------:|:-------------------|:---------------------|:--------------------|:---------------------|
|   2013 | 25.3%              | 25.3%                | 26.5%               | 30.0%                |
|   2014 | 20.8%              | 20.8%                | 22.1%               | 25.8%                |
|   2015 | -0.7%              | -0.7%                | -1.2%               | -1.2%                |
|   2016 | -12.4%             | -12.4%               | -8.0%               | -8.1%                |
|   2017 | 19.4%              | 19.4%                | 11.3%               | 5.2%                 |
|   2018 | -0.8%              | -0.8%                | 9.0%                | -3.3%                |
|   2019 | -14.4%             | -14.4%               | -13.8%              | -7.2%                |
|   2020 | -5.4%              | -5.4%                | -7.4%               | -3.6%                |
|   2021 | 60.6%              | 60.6%                | 40.5%               | 53.4%                |
|   2022 | -8.4%              | -8.4%                | -5.7%               | -7.6%                |
|   2023 | -19.9%             | -19.9%               | -19.8%              | -14.4%               |
|   2024 | -5.5%              | -5.5%                | -10.1%              | -4.7%                |
|   2025 | 38.2%              | 38.2%                | 28.7%               | 21.6%                |
|   2026 | 31.3%              | 31.5%                | 31.9%               | 30.4%                |

## Acceptance Rule
AND-gate: CAGR >= baseline AND MaxDD <= baseline (primary)
Soft-gate: CAGR >= baseline*0.97 AND MAR >= baseline*1.15 AND MaxDD <= baseline (secondary)
Baseline: a3_baseline_slot
Placebo benchmark: dna_random_permute -- DNA must materially beat permutation null.

## Files
- slot_sim_pareto_2026-06-07.csv
- slot_sim_pareto_post17_2026-06-07.csv
- slot_sim_equity_2026-06-07.csv
- slot_sim_annual_2026-06-07.csv
- slot_sim_trades_2026-06-07.csv
- slot_sim_rejected_2026-06-07.csv
- slot_sim_bucket_breakdown_2026-06-07.csv

## Suggested Next Prompt for ChatGPT
"DNA slot-priority sim complete. 6 configs + post-2017 robustness slice + placebo.
Pareto: [paste table]. AND-gate results: [list]. Placebo (dna_random_permute) vs real DNA: [compare CAGR/MAR].
Decision: if real DNA configs fail to beat placebo materially, stop DNA promotion path.
If any config passes AND-gate AND beats placebo: proceed to walk-forward refit discussion."
