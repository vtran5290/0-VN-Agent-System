# Stock DNA Current-Cycle Obedience Screen

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE

**Generated:** 2026-06-06 23:01  
**Panel:** 2018-01-16 → 2026-06-05 (one bull-bear-bull cycle — NOT a decade screen)  
**Input:** `data/research/stock_dna/stock_dna_symbol_profiles.csv`  
**instability_penalty median:** 0.1300

## Council Notes (2026-06-06)

**Timeframe:** 2018–2026 covers ~8.4 years and one complete bull-bear-bull cycle. Rebrand as 'current-cycle obedience' — not a decade screen.

**Blue-chip absence:** FPT/HPG/MWG/MSN have `edge_confidence=NONE` despite `confidence=HIGH`. Council ruling: z-test is under-powered on liquid/arbitraged names — the null is harder to beat when price paths are more arbitraged. MWG (bull_obedience=0.867) is the key tell: real pattern failing z-test, not a weak pattern. **Tier BC** added as separate track — do not merge with Tier A.

**Line calibration:** MODERATE/STRONG edge_confidence stocks overwhelmingly prefer `sma150` (27) and `sma100` (21); only 3 use ema20/ema50. Line restriction removed from Tier A. Tier B preserves the EMA subset at relaxed thresholds.

## Summary

| Tier | Count | Description |
|---|---|---|
| A | 21 | High conviction: bull_obedience > 0.6, MODERATE/STRONG edge, statistically verified |
| B | 7 | EMA-line subset: bull_obedience > 0.5, ema20/ema50, any edge signal |
| BC | 10 | Blue-Chip Obedience: HIGH conf + bull_obedience > 0.8 — edge UNVERIFIED (z-test under-powered) |
| **WATCHLIST_PRIORITY** | **15** | **Top 15 Tier A by composite score** |

## Tier A — High Conviction

| symbol | composite_score | primary_support_line | edge_confidence | regime_obedience_bull | bounce_rate_20d | median_fwd_ret_20d | instability_penalty | liquidity_bucket | production_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HAX | 0.781 | sma150 | MODERATE | 1.000 | 0.810 | 0.048 | 0.245 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| ANV | 0.731 | sma150 | MODERATE | 0.931 | 0.764 | 0.073 | 0.210 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| TIG | 0.683 | sma150 | STRONG | 0.882 | 0.767 | 0.079 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| TTF | 0.632 | sma100 | STRONG | 0.833 | 0.747 | 0.071 | 0.221 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HQC | 0.536 | sma150 | MODERATE | 0.821 | 0.695 | 0.036 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HSG | 0.518 | sma150 | STRONG | 0.882 | 0.612 | 0.029 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| VND | 0.492 | sma100 | MODERATE | 0.762 | 0.701 | 0.036 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| FMC | 0.487 | sma150 | MODERATE | 0.778 | 0.654 | 0.052 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| HT1 | 0.479 | sma150 | STRONG | 0.733 | 0.691 | 0.054 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| LHG | 0.459 | sma100 | MODERATE | 0.762 | 0.660 | 0.033 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| VGI | 0.450 | sma150 | MODERATE | 0.652 | 0.755 | 0.043 | 0.250 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| NRC | 0.429 | sma100 | STRONG | 0.704 | 0.648 | 0.047 | 0.221 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| BSR | 0.403 | sma100 | STRONG | 0.746 | 0.594 | 0.039 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| BWE | 0.388 | sma150 | STRONG | 0.737 | 0.598 | 0.021 | 0.234 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| AAA | 0.378 | sma100 | MODERATE | 0.646 | 0.619 | 0.050 | 0.186 | LIQUID | RESEARCH_ANNOTATION_ONLY |
| PLX | 0.358 | sma100 | STRONG | 0.633 | 0.599 | 0.020 | 0.107 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| PVI | 0.356 | sma100 | STRONG | 0.724 | 0.590 | 0.012 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |
| PVD | 0.347 | sma150 | STRONG | 0.632 | 0.639 | 0.043 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| DPM | 0.327 | sma150 | MODERATE | 0.618 | 0.646 | 0.029 | 0.250 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| HHV | 0.316 | sma150 | MODERATE | 0.619 | 0.624 | 0.025 | 0.232 | VERY_LIQUID | RESEARCH_ANNOTATION_ONLY |
| MPC | 0.285 | sma150 | MODERATE | 0.648 | 0.570 | 0.019 | 0.250 | SEMI_LIQUID | RESEARCH_ANNOTATION_ONLY |

## Tier B — EMA Subset

| symbol | composite_score | primary_support_line | edge_confidence | regime_obedience_bull | bounce_rate_20d | instability_penalty | liquidity_bucket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YEG | 0.580 | ema50 | WEAK | 0.720 | 0.686 | 0.250 | LIQUID |
| BMI | 0.330 | ema20 | WEAK | 0.626 | 0.594 | 0.145 | SEMI_LIQUID |
| DPG | 0.314 | ema50 | WEAK | 0.639 | 0.576 | 0.185 | LIQUID |
| GIL | 0.284 | ema20 | WEAK | 0.574 | 0.580 | 0.169 | LIQUID |
| MST | 0.283 | ema50 | WEAK | 0.557 | 0.629 | 0.242 | SEMI_LIQUID |
| BVS | 0.253 | ema20 | MODERATE | 0.565 | 0.608 | 0.247 | LIQUID |
| KBC | 0.247 | ema20 | WEAK | 0.510 | 0.574 | 0.071 | VERY_LIQUID |

## Tier BC — Blue-Chip Obedience ⚠️ Edge Unverified

> Council ruling: z-test is under-powered on liquid/arbitraged names. HIGH confidence + bull_obedience > 0.8 is meaningful despite NONE edge_confidence. Do NOT treat as statistically equivalent to Tier A.

| symbol | composite_score | primary_support_line | confidence | edge_confidence | regime_obedience_bull | bounce_rate_20d | instability_penalty | liquidity_bucket |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TNH | 0.694 | sma150 | HIGH | NONE | 1.000 | 0.638 | 0.069 | SEMI_LIQUID |
| SCS | 0.662 | sma100 | HIGH | NONE | 1.000 | 0.694 | 0.250 | LIQUID |
| BVB | 0.610 | sma100 | HIGH | WEAK | 0.867 | 0.739 | 0.250 | LIQUID |
| KOS | 0.599 | sma100 | HIGH | NONE | 0.832 | 0.762 | 0.199 | LIQUID |
| TAR | 0.592 | ema20 | HIGH | NONE | 0.839 | 0.722 | 0.250 | LIQUID |
| FRT | 0.580 | sma150 | HIGH | WEAK | 0.833 | 0.712 | 0.250 | VERY_LIQUID |
| MWG | 0.568 | sma150 | HIGH | NONE | 0.867 | 0.681 | 0.250 | VERY_LIQUID |
| NLG | 0.521 | ema50 | HIGH | NONE | 0.816 | 0.684 | 0.250 | VERY_LIQUID |
| VCG | 0.452 | sma100 | HIGH | NONE | 0.828 | 0.539 | 0.116 | VERY_LIQUID |
| TVN | 0.409 | ema20 | HIGH | NONE | 0.889 | 0.405 | 0.018 | SEMI_LIQUID |

## Exclusion Diagnostics — Council Watchlist Symbols

> Council ruling 2026-06-06: log exclusion reasons per-symbol to diagnose ACP class gaps.

| Symbol | In Profiles | Confidence | EdgeConf | Bull_Obedience | Tier A | Tier BC | Verdict |
|---|---|---|---|---|---|---|---|
| ACP | ❌ MISSING | — | — | — | ✗ | ✗ | Not in 412-symbol universe — check SSOT parquet |
| FPT | ✓ | HIGH | NONE | 0.634 | ✗ | ✗ | Tier A: edge=NONE | Tier BC: bull=0.634≤0.8 |
| HPG | ✓ | HIGH | NONE | 0.559 | ✗ | ✗ | Tier A: bull=0.559≤0.6; edge=NONE | Tier BC: bull=0.559≤0.8 |
| VCB | ✓ | HIGH | MODERATE | 0.569 | ✗ | ✗ | Tier A: bull=0.569≤0.6 | Tier BC: bull=0.569≤0.8 |
| MWG | ✓ | HIGH | NONE | 0.867 | ✗ | ✓ | Tier A fails (edge=NONE) | Qualifies BC (edge unverified) |
| MSN | ✓ | HIGH | NONE | 0.613 | ✗ | ✗ | Tier A: edge=NONE | Tier BC: bull=0.613≤0.8 |
| ACB | ✓ | HIGH | NONE | 0.412 | ✗ | ✗ | Tier A: bull=0.412≤0.6; edge=NONE | Tier BC: bull=0.412≤0.8 |
| VNM | ✓ | HIGH | NONE | 0.436 | ✗ | ✗ | Tier A: bull=0.436≤0.6; edge=NONE | Tier BC: bull=0.436≤0.8 |
| VIC | ✓ | HIGH | MODERATE | 0.600 | ✗ | ✗ | Tier A: bull=0.600≤0.6 | Tier BC: bull=0.600≤0.8 |
| VHM | ✓ | HIGH | MODERATE | 0.565 | ✗ | ✗ | Tier A: bull=0.565≤0.6 | Tier BC: bull=0.565≤0.8 |
| SSI | ✓ | HIGH | NONE | 0.532 | ✗ | ✗ | Tier A: bull=0.532≤0.6; edge=NONE | Tier BC: bull=0.532≤0.8 |
| VND | ✓ | HIGH | MODERATE | 0.762 | ✓ | ✗ | QUALIFIES Tier A |
| HDB | ✓ | HIGH | NONE | 0.478 | ✗ | ✗ | Tier A: bull=0.478≤0.6; edge=NONE | Tier BC: bull=0.478≤0.8 |
| TCB | ✓ | HIGH | NONE | 0.494 | ✗ | ✗ | Tier A: bull=0.494≤0.6; edge=NONE | Tier BC: bull=0.494≤0.8 |
| MBB | ✓ | HIGH | NONE | 0.484 | ✗ | ✗ | Tier A: bull=0.484≤0.6; edge=NONE | Tier BC: bull=0.484≤0.8 |

## What This Screen Does NOT Do

- No changes to A3, OMS, DNSE, final_action, sizing, or live scan
- `STOCK_DNA_ANNOTATION_ENABLED` stays `false`
- No EMA5/EMA10 addition (council ruling stands)
- No T2-tight build (council ruling stands)
- No A3 ledger join (council ruling stands)
- `a3_true_ledger_used = False`

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE