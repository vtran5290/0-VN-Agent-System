# P0 Implementation Report — Sector L4 Causality

**Date:** 2026-05-25
**Run duration:** ~90 seconds (panels cached after first run)
**Output dir:** `data/research/sector_l4_causality/`

---

## Files Changed / Created

### New code (all new, no production files touched)
- `docs/research/SECTOR_L4_CLOUD_CAUSALITY_TEST_PLAN.md` — patched plan saved to repo
- `scripts/research/sector_l4_causality/__init__.py`
- `scripts/research/sector_l4_causality/config.py`
- `scripts/research/sector_l4_causality/io.py`
- `scripts/research/sector_l4_causality/cloud.py`
- `scripts/research/sector_l4_causality/coverage.py`
- `scripts/research/sector_l4_causality/regimes.py`
- `scripts/research/sector_l4_causality/l4_events.py`
- `scripts/research/sector_l4_causality/stock_events.py`
- `scripts/research/sector_l4_causality/lead_lag.py`
- `scripts/research/sector_l4_causality/leader.py`
- `scripts/research/sector_l4_causality/filter_value.py`
- `scripts/research/sector_l4_causality/placebo.py`
- `scripts/research/sector_l4_causality/adoption_gates.py`
- `scripts/research/sector_l4_causality/report.py`
- `scripts/research/sector_l4_causality/run_all.py`

### No production files modified
- A3 production contract: UNCHANGED
- OMS: UNCHANGED
- `final_action`: UNCHANGED
- Phase36 daily scan: UNCHANGED
- S3: UNCHANGED

---

## Run Statistics

| Item | Value |
|---|---|
| Panel rows | 743,189 |
| Panel symbols | 272 |
| Panel date range | 2012-01-03 to 2026-05-25 |
| Sector map symbols | 273 |
| Unknown L4 | 69 (25.3%) |
| Eligible headline symbols | 46 (n_bars ≥ min, n≥5 per L4, non-Unknown) |
| Eligible L4 sectors (n≥5) | 3 (Private Bank, Small Broker, Small Developer) |
| L4 turn events (primary 40/35) | 84 |
| L4 turn events (all definitions) | 423 |
| Stock cloud turn events | 4,539 |
| Placebo iterations | 200 |

---

## Key P0 Findings (FACTS)

| Finding | Value | Gate |
|---|---|---|
| Median excess stock turns t+1→t+10 | +0.79 turns (+116.7% lift) | G1: PASS (>15%) |
| Δhit_rate_60d (L4≥40% gate, full) | +1.63pp | G2: FAIL (<3pp) |
| Δmean_ret_60d (L4≥40% gate, full) | +0.76% | G2: FAIL (<1%) |
| Δhit_rate_60d (ex-VIN) | +1.67pp | G6: PASS (positive sign) |
| Placebo percentile | 99.5th | G7: PASS (>95th) |
| Leader-before-sector | 54.8% | → LEADER_DRIVEN |
| Unknown L4 fraction | 25.3% | G8: PASS (<30%) |
| A3 ledger ΔMAR | N/A — sector_l4 col missing in ledger | G3: FAIL |
| Adoption verdict | **RANKING_FEATURE_ONLY** | 5/10 gates |

---

## Open Issues

### OI-1 (HIGH): A3 ledger has no sector_l4 column
`data/research/portfolio_optimization/phase25/phase25a_dp_trade_ledger.csv` does not contain a `sector_l4` column.
G3 (ΔMAR gate) and G4 (retention gate) could not be evaluated.
**Fix required before hard-filter gate can be assessed:** Add `sector_l4` to ledger by joining on `symbol` from sector map at entry date. This must be done in a separate, explicitly-approved step.

### OI-2 (HIGH): Coverage collapse — only 3 eligible L4 sectors
After applying `min_l4_symbols=5` and excluding Unknown, only 3 sectors qualify for headline tests.
This is a fundamental Vietnam market structure constraint: most formal L4 labels have <5 liquid symbols.
**Recommendation:** Operator must decide whether to (a) lower threshold to n≥3 for descriptive evidence, (b) use L3 groupings, or (c) build custom theme buckets.

### OI-3 (MEDIUM): Lead/lag qualified only on 3 sectors
The 116.7% excess lift result is based on only Small Broker + Small Developer (2 sectors with "sector_leads" classification). Private Bank is "coincident". 
**Risk:** 2-sector result with 28–30 events each has limited statistical power.

### OI-4 (LOW): Placebo shuffle uses ArrowStringArray
numpy shuffle on pyarrow string columns triggers a warning. The placebo still ran correctly (converted to numpy internally), but this should be fixed with `.astype(str).values` before shuffle.

### OI-5 (LOW): G5/G9 gates require operator review
G5 (regime stratification) and G9 (stability) were defaulted to 0 (conservative). Operator must review `regime_stratified_full_vs_ex_vin.csv` and `threshold_sweep_summary.csv` to assign pass/fail manually.

---

## Verdict

**RANKING_FEATURE_ONLY** (5/10 hard-filter gates passed)

The sector L4 layer shows a real signal above placebo (99.5th percentile), with meaningful excess stock turn clustering after sector events (+116.7% lift). However:
- Forward return improvement (+1.63pp hit rate at 60d) is below the hard-filter threshold (+3pp).
- A3 ledger ΔMAR cannot be computed without adding sector_l4 to the ledger.
- Coverage is very thin (3 eligible sectors only).
- Leader-before-sector is 54.8% — borderline T2 (leader drag).

**Allowed action:** Use sector L4 turn as operator review-priority / watchlist booster for Small Broker and Small Developer sectors. Not a trade signal. No OMS/A3/final_action changes.

---

## Skipped Tests (P1)
- Granger causality (A03, A04)
- Matched-control non-leader spillover (C03)
- FDR correction (D04)
- Structural break full analysis (D05) — partially visible in threshold_sweep_summary.csv

## Missing Fields
See `missing_fields_to_add.md` for full list.
