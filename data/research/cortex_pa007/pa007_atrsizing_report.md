# PA-007 ATR-Adjusted Position Sizing Report

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_pa007_atrsizing_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_pa007_atrsizing_gates_addendum.md`

**Overall verdict:** PASS

## Baseline verification (S1-flat)

- OOS MAR: **1.7844** (expected 1.7844 +/- 0.05)
- OOS MaxDD: **-8.17%** (expected -8.17% +/- 0.50%)
- Baseline flags: none

## Locked k_val (IS-derived)

- k_val_atr20: **0.024775** (n=1305)
- k_val_atr10: **0.028000** (n=1299)

## C1_atr20

- OOS MAR: **2.5792** | MaxDD: **-5.59%**
- Sub-A MAR: **6.1098** | Sub-B MAR: **0.9798**
- G1a (>= 1.8736): **PASS** margin=0.7056
- G1b (>= 0.516): **PASS**
- G2 (MaxDD >= -8.99%): **PASS**
- G3 (fill >= 80%): **PASS** (98.69%)
- G4 (turnover <= 120%): **PASS** (ratio 0.706)
- G5 (2021 capture >= 90%): **FAIL** (ratio 0.779)
- **Verdict: FAIL**

## C2_atr10

- OOS MAR: **2.2571** | MaxDD: **-6.37%**
- Sub-A MAR: **5.7258** | Sub-B MAR: **0.8571**
- G1a (>= 1.8736): **PASS** margin=0.3835
- G1b (>= 0.516): **PASS**
- G2 (MaxDD >= -8.99%): **PASS**
- G3 (fill >= 80%): **PASS** (98.62%)
- G4 (turnover <= 120%): **PASS** (ratio 0.715)
- G5 (2021 capture >= 90%): **PASS** (ratio 0.955)
- **Verdict: PASS**

RESEARCH_ONLY_NOT_PRODUCTION