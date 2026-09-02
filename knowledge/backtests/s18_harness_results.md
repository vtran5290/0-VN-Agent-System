# S18 Sector Persistence Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_schwager_s18_gates_addendum.md`

**FINAL VERDICT (primary C2_thresh075):** FAIL
**Best candidate verdict:** FAIL (C1_thresh100)

S1 baseline OOS MAR: **1.7844** (locked 1.7844) | G1a floor: **1.844** | G2 continuation: **>=55%**

## Baseline verification
- S1-only OOS MAR: 1.7844 | N=1732 | drift=False

## OOS gate results

| Candidate | k | IS persist | OOS persist | OOS MAR | sub-A MAR | sub-B MAR | N_OOS | G2 | Verdict |
|-----------|---|------------|-------------|---------|-----------|-----------|-------|----|---------|
| C2_thresh075 | 0.75 | 55.6% (n=3248) | 59.4% (n=3013) | 0.4615 | 1.1935 | 0.2273 | 532 | PASS | FAIL |
| C1_thresh100 | 1.0 | 55.8% (n=2303) | 60.0% (n=2124) | 0.5675 | 1.1028 | 0.5675 | 424 | PASS | FAIL |

## Sector-level OOS continuation (primary C2)

| Sector | Rate | n |
|--------|------|---|
| Agri | 61.8% | 393 |
| BDS | 60.7% | 394 |
| Banks | 60.2% | 374 |
| Consumer | 63.5% | 362 |
| Logistics | 59.4% | 387 |
| Oil_Gas | 58.5% | 371 |
| Securities | 54.0% | 361 |
| Steel | 56.9% | 371 |

## Band limit check (report-only)
- Fraction of trigger days with >=20% members at +/-7% band: **3.2%**