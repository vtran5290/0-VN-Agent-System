# Stock DNA Research Branch — Final Close-Out Memo
Date: 2026-06-07
Status: CLOSED — STOCK_DNA_RESEARCH_ANNOTATION_ONLY
a3_true_ledger_used = False | STOCK_DNA_ANNOTATION_ENABLED = False (permanent default)

---

## 1. Research Hypothesis

**Hypothesis**: Stock-level EMA/SMA support-line obedience ("DNA") predicts which A3 EMA-cloud-crossover signals will produce above-average returns, and can be used to either (a) rank candidates when portfolio slots are constrained, or (b) exclude signals near danger lines.

**Test path**:
- Phase 1: Discovery — score each symbol's historical obedience to its primary support line (EMA20, EMA50, SMA100, SMA150). Walk-forward scoring. Produce edge_confidence tiers.
- Phase 2: Overlay backtest — align DNA profiles to A3 signals; test whether DNA-positive signals outperform DNA-negative signals on proxy trade outcomes.
- Phase 3: Slot-constrained simulation — test whether DNA priority fill and danger exclusion improve returns when N_SLOTS=15 limits which signals actually enter the portfolio (correct test for priority hypothesis).

Both Phase 2 and Phase 3 were completed. Phase 3 is the decisive test.

---

## 2. Positive Findings

**A. Stock-level support-line behavior exists (FROM DISCOVERY PIPELINE — not A3 sim)**
- 83 symbols scored as RESEARCH_ANNOTATION_ONLY (confirmed obedience pattern).
- 28 Tier A symbols: MODERATE+ edge confidence AND regime_obedience_bull > 0.60.
- Symbols that hold EMA50 as primary support show statistically detectable bounce behavior in the discovery dataset (proxy 20d forward returns above null).
- ATTRIBUTION: This is a finding about stock price behavior, derived from the DNA discovery pipeline. The A3 slot simulation did NOT test this finding — it tested whether this behavior translates to A3 trade selection quality, and found it does not.

**B. SMA50 accepted as primary support line; SMA200 deferred (FROM DISCOVERY PIPELINE)**
- EMA20 and EMA50 produced the most consistent obedience scores across the scoring universe.
- SMA200 was deferred: too slow, insufficient touch events per walk-forward window for stable scoring.
- ATTRIBUTION: Discovery pipeline finding only.

**C. Cross-sectional discovery null is strong**
- Within the discovery pipeline's in-sample window (2017–2026), DNA-positive signals show proxy lift of +6.17pp over the null (4,715 aligned events).
- The cross-sectional null distribution (permutation test within discovery) is well-separated.
- CAVEAT: This is in-sample. DNA profiles were fit on the same 2017–2026 window in which this lift was measured.

---

## 3. Negative Findings

### 3a. Placebo beats real DNA priority on risk-adjusted return — strongest stop-signal
**FACT**: In the slot-constrained sim, randomly permuting DNA priority buckets (seed=42) produced MAR=0.22, MaxDD=32.0% — **better than all real DNA configs** (MAR 0.16–0.19, MaxDD 38.2–38.6%).
- The real DNA priority ordering provides no detectable signal above random noise in this dataset.
- This is the single most decisive finding. If a real signal existed, it should beat a random shuffle.

### 3b. DNA priority fill degrades CAGR by −1.1pp (full period and post-2017 robustness slice)
| Config | CAGR | MaxDD | MAR |
|---|---|---|---|
| a3_baseline_slot | 7.2% | 38.6% | 0.19 |
| dna_priority_slot | 6.1% | 38.2% | 0.16 |
| dna_priority_plus_danger_last | 6.1% | 38.2% | 0.16 |
- Degradation is consistent across both full-period (2013–2026) and post-2017 slice.
- ROOT CAUSE: DNA edge confidence (support-line obedience) does not correlate with EMA cloud-crossover trade quality. DNA was calibrated on bounce behavior after support tests; A3 profits from momentum continuation after EMA crossovers — a different mechanism.

### 3c. Danger exclusion is immaterial
- `dna_danger_exclude`: 3 filter rejections over 13 years (out of 2643 signals). Identical CAGR/MaxDD/MAR to baseline.
- `dna_danger_last`: identical to baseline (same 349 accepted trades, same returns).
- REJECT-status symbols almost never arrive at the marginal slot boundary in practice.

### 3d. OOS event-study confirmation is weak (z = 0.37, not significant)
- `stock_dna_oos_lift.json`: lift_vs_null = +0.36pp, z = 0.37, pass_fail = false.
- SEPARATE FROM the cross-sectional discovery null (which is strong — see 2C above). These are two different tests.
- The event-study OOS: signals from the last 12 months of the parquet, forward-window bounce rate vs null. z=0.37 is not significant.
- NOTE: OOS z may be partially an artifact — all 232 OOS events cluster near the parquet tail (2026), where the 20d forward window cannot complete. This edge effect should be fixed before drawing strong conclusions from the OOS number. But even if fixed, the slot-sim finding (3a–3b) is the authoritative stop-signal.

### 3e. In-sample lookahead throughout
- DNA profiles fit on 2017–2026. Applied to A3 signals from 2013.
- All reported CAGR/MAR numbers carry full in-sample bias. Not predictive estimates.

### 3f. Regime instability in underlying DNA scoring
- Bounce rates are materially different by regime: BULL_NARROW ~0.67 vs NEUTRAL ~0.30.
- DNA scores reflect historical regime composition, not forward regime.
- No walk-forward refit was done for the slot simulation. A 2013-trained profile does not exist; all profiles are from the single 2017–2026 fit.

---

## 4. Final Decision

**Stock DNA does NOT improve A3 candidate selection.**

DNA explains stock-level support behavior. It does not allocate capital better than A3.
That is the correct outcome of this research branch.

**Final status: STOCK_DNA_RESEARCH_ANNOTATION_ONLY**

Do NOT promote to:
- PAPER_SHADOW_CANDIDATE
- A3 ranking layer or priority filter
- A3 binary gate
- Sizing input
- OMS / live-routing / DNSE input
- final_action modifier

**Rationale**: Both tests failed independently. The slot-sim is the decisive test (correct architecture for the priority hypothesis). Placebo beat real DNA on MAR — there is no detectable signal to promote.

**Remaining valid use**: DNA profiles can remain as operator-facing annotation context in the daily scan narrative (e.g., "AAA has confirmed EMA50 obedience — note for context"). This is informational only. It does not change any signal, action, or position size.

---

## 5. Guardrails (permanent)

- `A3 final_action` remains the sole source of truth for trade decisions.
- `STOCK_DNA_ANNOTATION_ENABLED` stays `false` (default). No change without explicit written approval.
- `a3_true_ledger_used = False` on all DNA metrics. Do not claim A3 production improvement.
- No changes to OMS, DNSE, live routing, sizing, or order_intent from DNA status.
- `data/research/stock_dna/` outputs are research artifacts — do not surface in production reports.

---

## 6. Re-Entry Conditions (falsifiable)

Only revisit DNA as a signal if ALL THREE conditions are met:
1. **True A3 ledger join**: Live A3 fills are logged with DNA status at fill time (not reconstructed post-hoc). Requires 2+ years of real fill data.
2. **Walk-forward refit**: DNA profiles refitted on expanding windows; applied only out-of-sample. Removes the 2013–2016 lookahead.
3. **Real DNA beats placebo on MAR**: In the above clean test, the real DNA priority must beat a random-permute null by a material margin (MAR delta ≥ 0.05).

If any condition is not met, the research remains closed.

---

## 7. Research Archive

### Sims run
| Date | Script | Finding |
|---|---|---|
| 2026-06-07 | run_dna_a3_combined_sim.py | Cross-sectional model; optA=baseline (model limitation, not finding); bear exclusion costs 1.3pp CAGR |
| 2026-06-07 | run_dna_a3_slot_priority_sim.py | Slot-constrained; DNA priority −1.1pp CAGR; placebo beats real DNA; STOP |

### Key artifacts
- `data/research/stock_dna/stock_dna_symbol_profiles.csv` — 412 symbols, 83 RAA, 28 Tier A
- `data/research/stock_dna/stock_dna_oos_lift.json` — z=0.37, pass_fail=false (edge effect pending fix)
- `outputs/research/dna_strategy_sim/slot_sim_pareto_2026-06-07.csv` — decisive pareto table
- `review_outputs/dna_a3_slot_priority_2026-06-07.zip` — full run package
- `00. Command Center/05_AI_Handoffs/2026-06-07_ReviewPack_DNA_A3_SlotSim.md` — ChatGPT review pack

### Session compaction reference
`00. Command Center/05_AI_Handoffs/2026-06-06_SessionCompaction_StockDNA_PipelineRefresh.md`

---

*Close-out approved by ChatGPT review of `a3_dna_combined_2026-06-07.zip` and `dna_a3_slot_priority_2026-06-07.zip`.*
*Stock DNA explains behavior. It does not allocate capital better than A3.*
