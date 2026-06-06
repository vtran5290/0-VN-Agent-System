# Stock DNA Super-Performer Screen

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE

**Generated:** 2026-06-06 22:50  
**Input:** `data/research/stock_dna/stock_dna_symbol_profiles.csv`  
**instability_penalty median:** 0.1300

## Council Filter Calibration Note

Original council filter assumed `primary_support_line ∈ {ema20, ema50}` for quality stocks.
**Data finding:** MODERATE/STRONG edge_confidence stocks overwhelmingly prefer `sma150` (27) and
`sma100` (21); only 3 use ema20/ema50. Bull-obedient stocks (regime_obedience_bull > 0.6) also
prefer sma150 (27) / sma100 (22). Line restriction removed from Tier A.
Tier B preserves the EMA subset at relaxed thresholds for operators who prefer fast-moving support.

## Summary

| Tier | Count | Description |
|---|---|---|
| A | 21 | High conviction: bull_obedience > 0.6, low instability, MODERATE/STRONG edge |
| B | 7 | EMA-line subset: bull_obedience > 0.5, ema20/ema50, any edge signal |
| **WATCHLIST_PRIORITY** | **15** | **Top 15 Tier A by composite score** |

## Tier A — High Conviction

| symbol | composite_score | primary_support_line | edge_confidence | regime_obedience_bull | bounce_rate_20d | median_fwd_ret_20d | instability_penalty | liquidity_bucket | production_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HAX | 0.749 | sma150 | MODERATE | 1.000 | 0.810 | 0.048 | 0.245 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| ANV | 0.686 | sma150 | MODERATE | 0.931 | 0.764 | 0.073 | 0.210 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| TIG | 0.637 | sma150 | STRONG | 0.882 | 0.767 | 0.079 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| TTF | 0.576 | sma100 | STRONG | 0.833 | 0.747 | 0.071 | 0.221 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HQC | 0.442 | sma150 | MODERATE | 0.821 | 0.695 | 0.036 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| VND | 0.400 | sma100 | MODERATE | 0.762 | 0.701 | 0.036 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| VGI | 0.387 | sma150 | MODERATE | 0.652 | 0.755 | 0.043 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HT1 | 0.387 | sma150 | STRONG | 0.733 | 0.691 | 0.054 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HSG | 0.379 | sma150 | STRONG | 0.882 | 0.612 | 0.029 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| FMC | 0.375 | sma150 | MODERATE | 0.778 | 0.654 | 0.052 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| LHG | 0.344 | sma100 | MODERATE | 0.762 | 0.660 | 0.033 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| NRC | 0.316 | sma100 | STRONG | 0.704 | 0.648 | 0.047 | 0.221 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| BSR | 0.257 | sma100 | STRONG | 0.746 | 0.594 | 0.039 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| AAA | 0.256 | sma100 | MODERATE | 0.646 | 0.619 | 0.050 | 0.186 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| BWE | 0.241 | sma150 | STRONG | 0.737 | 0.598 | 0.021 | 0.234 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| PLX | 0.227 | sma100 | STRONG | 0.633 | 0.599 | 0.020 | 0.107 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| PVD | 0.225 | sma150 | STRONG | 0.632 | 0.639 | 0.043 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| DPM | 0.205 | sma150 | MODERATE | 0.618 | 0.646 | 0.029 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| PVI | 0.201 | sma100 | STRONG | 0.724 | 0.590 | 0.012 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| HHV | 0.184 | sma150 | MODERATE | 0.619 | 0.624 | 0.025 | 0.232 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| MPC | 0.122 | sma150 | MODERATE | 0.648 | 0.570 | 0.019 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |

## Tier B — EMA Subset

| symbol | composite_score | primary_support_line | edge_confidence | regime_obedience_bull | bounce_rate_20d | instability_penalty | liquidity_bucket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YEG | 0.517 | ema50 | WEAK | 0.720 | 0.686 | 0.250 | LIQUID |
| BMI | 0.192 | ema20 | WEAK | 0.626 | 0.594 | 0.145 | SEMI_LIQUID |
| DPG | 0.163 | ema50 | WEAK | 0.639 | 0.576 | 0.185 | LIQUID |
| MST | 0.157 | ema50 | WEAK | 0.557 | 0.629 | 0.242 | SEMI_LIQUID |
| GIL | 0.140 | ema20 | WEAK | 0.574 | 0.580 | 0.169 | LIQUID |
| BVS | 0.111 | ema20 | MODERATE | 0.565 | 0.608 | 0.247 | LIQUID |
| KBC | 0.107 | ema20 | WEAK | 0.510 | 0.574 | 0.071 | VERY_LIQUID |

## What This Screen Does NOT Do

- No changes to A3, OMS, DNSE, final_action, sizing, or live scan
- `STOCK_DNA_ANNOTATION_ENABLED` stays `false`
- No EMA5/EMA10 addition (council ruling stands)
- No T2-tight build (council ruling stands)
- No A3 ledger join (council ruling stands)
- `a3_true_ledger_used = False`

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE