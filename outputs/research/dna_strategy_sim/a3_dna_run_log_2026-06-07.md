# DNA x A3 Combined Sim Run Log
Date: 2026-06-07
SIMULATION ONLY -- NOT A LIVE SIGNAL

## Lookahead Disclosure
LOOKAHEAD DISCLOSURE: DNA profiles fit 2017-2026. Joining to historical A3 signals is in-sample. CAGR/MAR lift is in-sample lookahead signature, not confirmed alpha.

## A3 Frozen Contract (read-only)
- EMA cloud: fast=20, slow=100
- TP1: +18% on 50% of position
- T2 pullback: >=4% within 30 bars
- Trail: 2.5x ATR14 on remainder; max hold 250 bars
- Cost: 40 bps round-trip
- Min ADV: 2.0B VND/day

## Universe
- Panel symbols: 269
- DNA profiles: 412
- Tier A (MODERATE+ edge, bull_obed>0.6): 28
- DNA-to-A3 overlap: 257 / 269 panel symbols

## Signals
- Total: 2832
- BULL: 2059 | BEAR: 773
- With Tier A DNA: 374

## Pareto Table (SIMULATION — cross-sectional annual model)
| config        | cagr   | max_dd   |   mar | acceptance_bar   | red_flags   |
|:--------------|:-------|:---------|------:|:-----------------|:------------|
| a3_baseline   | 3.2%   | 18.4%    |  0.17 | FAIL             | none        |
| optA_priority | 3.2%   | 18.4%    |  0.17 | FAIL             | none        |
| optC_regime   | 1.9%   | 26.0%    |  0.07 | FAIL             | none        |
| optD_layered  | 1.9%   | 25.6%    |  0.07 | FAIL             | none        |

## Phase 25 Benchmarks (REFERENCE — different data state, NOT comparable directly)
| Config | Target CAGR | Target MaxDD | Target MAR |
|---|---|---|---|
| a3_baseline | 14.1% | 26.2% | 0.54 |
| optA_priority | ~13.5-14% | ~23-24% | ~0.56-0.60 |
| optC_regime | ~12-14% | ~16-20% | ~0.65-0.80 |
| optD_layered | ~13-14.5% | ~17-20% | ~0.68-0.82 |

Acceptance bar: CAGR >= 13%, MaxDD <= 20%, MAR >= 0.65
All configs FAIL acceptance bar. See Data State note and Methodology Limitations below.

## Data State Disclosure
FACT: Phase 25 (CAGR=14.1%) was generated from a prior snapshot of ohlcv_panel_ext2012.parquet.
FACT: Running Phase 25's own `_collect_a3_trades()` on the CURRENT parquet produces CAGR=2.82%.
FACT: 2021 example — current parquet: 212 signals, avg_ret=6.9%; Phase 25 state: 788 signals, avg_ret=+85.8%.
INTERPRETATION: The parquet has been backfilled/corrected since Phase 25. The old data state is gone.
CONCLUSION: The acceptance bar (CAGR>=13%) cannot be met with current data regardless of DNA overlay.
The absolute CAGR numbers are NOT comparable to Phase 25. The relative config comparison IS valid.

## Methodology Limitations — Critical Finding
The cross-sectional annual return model CANNOT test DNA priority fill (optA / optD-BULL leg):
- The model averages all accepted signals equally within each year
- Priority ordering (DNA fills first) only matters when slots are CONSTRAINED (N=15)
- In the cross-sectional model, every accepted signal is weighted equally
- RESULT: optA_priority = a3_baseline exactly (zero differentiation, as expected)

The cross-sectional model CAN only test hard EXCLUSION gates:
- optC_regime (BULL-only): excluded 771 bear signals -> CAGR fell 3.2% -> 1.9%
  FINDING: Bear exclusion is NOT free. Some bear-regime years had positive BULL signal returns.
  Removing them reduced annual averages in bear years, lowering overall CAGR.
- optD_layered (BULL + Tier-A T2 bear): accepted 72 extra bear signals -> trivially better than optC
  FINDING: Tier-A T2 rescue in bear is too small a set (72 trades / 15 years) to move the needle.

CONCLUSION: To test the DNA PRIORITIZATION hypothesis (the core of optA/optD), a
slot-constrained portfolio simulation is required — not the cross-sectional model.

## What This Run Proved
1. Script runs correctly: 2643 trade outcomes, 4 configs, all outputs generated cleanly.
2. Data state mismatch confirmed: current parquet -> CAGR~3%, not 14.1% (Phase 25 data is gone).
3. Bear exclusion (optC) reduces returns in current data — BULL-only gate is not obviously superior.
4. Cross-sectional model is insufficient for testing DNA fill priority. Need slot-constrained sim.
5. No lookahead bugs detected (no red flags, CAGR well under 30% ceiling).

## Relative Config Ranking (current data, cross-sectional)
| Rank | Config | CAGR | MaxDD | MAR | vs baseline |
|---|---|---|---|---|---|
| 1 | a3_baseline | 3.2% | 18.4% | 0.17 | -- |
| 1= | optA_priority | 3.2% | 18.4% | 0.17 | 0 (no differentiation) |
| 3 | optD_layered | 1.9% | 25.6% | 0.07 | -1.3pp CAGR |
| 4 | optC_regime | 1.9% | 26.0% | 0.07 | -1.3pp CAGR |

DNA overlay in cross-sectional model shows NO benefit. This is expected given model limitations above.

## Red Flags
None — all sanity checks passed.

## Files Output
- a3_dna_equity_curves_2026-06-07.csv
- a3_dna_metrics_pareto_2026-06-07.csv
- a3_dna_trade_log_2026-06-07.csv
- a3_dna_rejection_log_2026-06-07.csv

## Next Steps Required
1. DECISION (ChatGPT): Is the cross-sectional model finding (DNA = no benefit, bear exclusion hurts) sufficient to stop, or do we invest in a slot-constrained simulation?
2. IF slot-constrained sim: need to fix the slot model to use `exit_bar_offset` correctly (not max_hold=250). This was attempted in iteration 2 and produced 345 closed trades / 13 years — slot occupancy math needs review.
3. IF stop: document that DNA overlay provides no detectable edge in the available data, given data state mismatch. Status stays RESEARCH_ANNOTATION_ONLY.
4. SEPARATE: Stock DNA pipeline refresh (OOS edge effect fix + re-run). See 2026-06-06_SessionCompaction_StockDNA_PipelineRefresh.md.

## Suggested next prompt for ChatGPT
"DNA x A3 combined sim ran 4 configs on current parquet (2013-2026). Results:
- a3_baseline: CAGR=3.2%, MaxDD=18.4%, MAR=0.17 (Phase25 14.1% is from a different/older data state — unreproducible)
- optA_priority: CAGR=3.2% (identical to baseline — cross-sectional model cannot test priority fill)
- optC_regime: CAGR=1.9%, MaxDD=26.0% (BULL-only; bear exclusion costs 1.3pp CAGR)
- optD_layered: CAGR=1.9%, MaxDD=25.6% (72 Tier-A T2 bear fills, trivially better than optC)
Key finding: cross-sectional model cannot test DNA PRIORITIZATION. Only exclusion gates tested.
Decision needed: (a) build slot-constrained sim to test priority fill, or (b) stop here and declare DNA overlay inconclusive with current data?"
