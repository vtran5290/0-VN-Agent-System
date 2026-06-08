# Cycle Robustness Report — Stock DNA (3-State Ordinal)

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE

**Generated:** 2026-06-07 01:04

## Council Ruling (Round 4, 2026-06-07)

3-state ordinal scheme (P0-2 fix — direction-aware edge comparison):
- `multi-cycle-confirmed`: line stable AND edge stable-or-improved (NONE<WEAK<MODERATE<STRONG)
  Edge improving = additional confirmation, not fragility.
- `cycle-edge-fading`: line stable, edge degraded ≥1 ordinal step. Monitor for decay.
- `cycle-line-shift`: primary support line changed between windows. Least confirmed.
- `no-2015-data`: symbol listed post-2015, single window only.

**Key operator implication:** effective high-confidence Tier A =
multi-cycle-confirmed + edge-improved-within-multi (both map to full research confidence).
Only cycle-edge-fading and cycle-line-shift warrant explicit caution notes.

## Summary

| Category | Count | % | Implication |
|---|---|---|---|
| multi-cycle-confirmed | **370** | 89.8% | Full confidence |
| cycle-edge-fading | **22** | 5.3% | Caution — monitor |
| cycle-line-shift | **20** | 4.9% | Lowest confidence |
| no-2015-data | 0 | 0.0% | Single window |
| **Total** | **412** | 100% | |

## Tier A (edge-verified) by Robustness

| Robustness | Count | Operator Rule |
|---|---|---|
| multi-cycle-confirmed | **24** | Full research confidence |
| cycle-edge-fading | **3** | Caution note required; watchlist with monitoring flag |
| cycle-line-shift | **1** | Do not feature without regime-dependency caveat |

## Tier A — Multi-Cycle Confirmed

| symbol | primary_support_line | edge_confidence | regime_obedience_bull | bounce_rate_20d | liquidity_bucket |
| --- | --- | --- | --- | --- | --- |
| HAX | sma150 | STRONG | 1.000 | 0.810 | LIQUID |
| CNG | sma100 | MODERATE | 0.933 | 0.767 | LIQUID |
| BVB | sma100 | MODERATE | 0.867 | 0.739 | LIQUID |
| TAR | ema20 | MODERATE | 0.839 | 0.722 | LIQUID |
| TTF | sma100 | STRONG | 0.833 | 0.747 | LIQUID |
| HQC | sma150 | STRONG | 0.821 | 0.695 | LIQUID |
| NLG | ema50 | MODERATE | 0.816 | 0.684 | VERY_LIQUID |
| FMC | sma150 | MODERATE | 0.778 | 0.654 | LIQUID |
| VND | sma100 | STRONG | 0.762 | 0.701 | VERY_LIQUID |
| LHG | sma100 | STRONG | 0.762 | 0.660 | SEMI_LIQUID |
| BWE | sma150 | STRONG | 0.737 | 0.598 | LIQUID |
| HT1 | sma150 | MODERATE | 0.733 | 0.691 | LIQUID |
| PVI | sma100 | STRONG | 0.724 | 0.590 | SEMI_LIQUID |
| NRC | sma100 | STRONG | 0.704 | 0.648 | SEMI_LIQUID |
| TV2 | sma50 | MODERATE | 0.676 | 0.576 | LIQUID |
| VGI | sma150 | MODERATE | 0.652 | 0.755 | LIQUID |
| MPC | sma150 | MODERATE | 0.648 | 0.570 | SEMI_LIQUID |
| AAA | sma100 | STRONG | 0.646 | 0.619 | LIQUID |
| HAG | sma150 | MODERATE | 0.642 | 0.625 | VERY_LIQUID |
| PLX | sma100 | STRONG | 0.633 | 0.599 | VERY_LIQUID |
| PVD | sma150 | STRONG | 0.632 | 0.639 | VERY_LIQUID |
| BMI | ema20 | MODERATE | 0.626 | 0.594 | SEMI_LIQUID |
| DPM | sma150 | MODERATE | 0.618 | 0.646 | VERY_LIQUID |
| NTL | sma150 | MODERATE | 0.606 | 0.592 | LIQUID |

## Tier A — Cycle-Edge-Fading (caution)

> Line stable but edge weakened vs 2015 window. Monitor for continued decay.
> Do NOT size up until edge stabilises.

| symbol | primary_support_line | edge_confidence | regime_obedience_bull | cycle_robustness_reason |
| --- | --- | --- | --- | --- |
| ANV | sma150 | MODERATE | 0.9310344827586208 | line=sma150 stable; edge STRONG→MODERATE (FADING) |
| TIG | sma150 | MODERATE | 0.8823529411764706 | line=sma150 stable; edge STRONG→MODERATE (FADING) |
| BSR | sma100 | MODERATE | 0.746268656716418 | line=sma100 stable; edge STRONG→MODERATE (FADING) |

## Tier A — Cycle-Line-Shift (lowest confidence)

> Primary support line changed between 2015 and 2018 windows.
> Support anchor is regime-dependent. Explicit caveat required.

| symbol | primary_support_line | edge_confidence | regime_obedience_bull | cycle_robustness_reason |
| --- | --- | --- | --- | --- |
| HSG | sma150 | STRONG | 0.8823529411764706 | line: sma100→sma150 |

## Regime Log Caveat (council P1 note)

> 2015-start 'confirmation' leans primarily on price/MA structure.
> Regime features (bull/bear labels) pre-2018 use the same regime log as 2018-start.
> Full regime-feature parity for 2015–2017 requires updated regime labeling for that period.
> This does not invalidate the robustness labels — the price/MA anchor is the primary signal.

## SMA50 Note

SMA50 added to v2 candidate lines (council 2026-06-06).
53 symbols (2018) / 54 symbols (2015) use sma50 as primary support line — consistent.
TV2 is Tier A exemplar (MODERATE edge, bull_obedience=0.676, 85 touches).

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE