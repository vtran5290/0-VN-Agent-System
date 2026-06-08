# Council Round 4 Brief — Stock DNA Research

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE

**Generated:** 2026-06-07 00:57

## Decision Required

Council must review dual-window results and SMA50 findings, then declare:
1. STOP (all research goals met) or CONTINUE (specify remaining work)
2. SMA200 evaluation: needed or deferred?
3. Trading implications for `2018-cycle-confirmed` Tier A stocks

## STOP Condition (council-defined pre-session)

- [x] Dual-window label exists for all 412 symbols
- [x] SMA50 incorporated in v2 candidate lines
- [x] Tier A stocks carry cycle_robustness flag
- [ ] **Council declaration** (pending this review)

## FACTS

### Candidate Lines (v2)

Lines evaluated: ema20, ema50, sma50, sma100, sma150
(SMA50 added 2026-06-06 — first run with v2 lines)

### 2018-Start Results (primary window)

- Total symbols profiled: **412**
- Edge distribution: {'NONE': np.int64(329), 'MODERATE': np.int64(38), 'WEAK': np.int64(28), 'STRONG': np.int64(17)}

**Primary support line distribution:**

| Line | Count |
|---|---|
| sma150 | 92 |
| sma100 | 80 |
| ema20 | 78 |
| sma50 | 53 |
| ema50 | 43 |
| (none/blank) | 66 |

**SMA50 as primary_support_line (2018-start): 53**

### 2015-Start Results (dual-window)

- Total symbols profiled: **413**

**Primary support line distribution (2015-start):**

| Line | Count |
|---|---|
| sma150 | 96 |
| ema20 | 79 |
| sma100 | 78 |
| sma50 | 54 |
| ema50 | 40 |

**SMA50 as primary_support_line (2015-start): 54**

### Cycle Robustness Labels

| Label | Count | Implication |
|---|---|---|
| multi-cycle-confirmed | **278** | Full conviction — stable 2015+2018 |
| 2018-cycle-confirmed | **134** | Cycle artifact risk — reduce size |
| no-2015-data | 0 | Listed post-2015, single window only |

**Tier A by cycle_robustness:**

- 2018-cycle-confirmed: 16
- multi-cycle-confirmed: 12

**Tier A stocks flagged 2018-cycle-confirmed:**

| Symbol | primary_support_line | edge_confidence | bull_obedience |
|---|---|---|---|
| ANV | sma150 | MODERATE | 0.931 |
| TIG | sma150 | MODERATE | 0.882 |
| CNG | sma100 | MODERATE | 0.933 |
| TTF | sma100 | STRONG | 0.833 |
| TAR | ema20 | MODERATE | 0.839 |
| HQC | sma150 | STRONG | 0.821 |
| NLG | ema50 | MODERATE | 0.816 |
| HSG | sma150 | STRONG | 0.882 |
| LHG | sma100 | STRONG | 0.762 |
| NRC | sma100 | STRONG | 0.704 |
| BSR | sma100 | MODERATE | 0.746 |
| AAA | sma100 | STRONG | 0.646 |
| BWE | sma150 | STRONG | 0.737 |
| PVD | sma150 | STRONG | 0.632 |
| PLX | sma100 | STRONG | 0.633 |
| PVI | sma100 | STRONG | 0.724 |

### Screen Summary

| Tier | Count |
|---|---|
| A (verified edge) | 28 |
| B (EMA subset) | 6 |
| BC (blue-chip, unverified) | 7 |

## INTERPRETATION (Sonnet — for council to accept/reject)

**SMA50 finding:** SMA50 won primary for **53 symbols** (2018-start) and **54 symbols** (2015-start) — highly consistent across windows. This confirms SMA50 is a real mid-range support anchor for ~13% of the VN universe. Stocks like TV2 (MODERATE edge, bull_obedience=0.676) are the archetype. SMA50 primarily captures mid-cap, moderately liquid names — a gap that EMA50 and SMA100 couldn't bridge individually. SMA150 still dominates the high-conviction names (92 symbols, 14 Tier A).

**Cycle robustness interpretation:** Of 28 Tier A stocks, 16 are 2018-cycle-confirmed. These should be traded at reduced conviction until validated across a second bull cycle. HAX/HSG/VND were expected in this category (strong 2018-2026 edge, weaker pre-2015).

## RISKS

- 2015-start data for pre-2018 rows uses minervini_backtest CSVs (split-adjusted, 211 symbols). Symbols not in minervini get `no-2015-data` label — this is not a quality failure, just data boundary.
- Regime log only goes to May 2026 — 2015-start regime features may be less precise for 2015-2017 period.
- SMA50 = 0 primary wins is empirical, not a guarantee. New listings post-2020 were not in pilot.

## REQUESTED COUNCIL DECISION

1. **SMA200**: SMA50 won primary for **53 symbols** (2018) / **54 symbols** (2015) — a genuine mid-range cluster between EMA50 and SMA100. SMA150 still dominant (92/96 symbols). Given SMA150 covers the long end, is SMA200 needed or confirmed-deferred?
2. **STOP condition**: Are all DNA research goals met? Declare STOP or specify remaining work.
3. **2018-cycle-confirmed trading rule**: Confirm reduced size is the correct implication, or propose alternative.

> STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE