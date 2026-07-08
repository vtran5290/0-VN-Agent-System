# PA-007 v2 — ATR Sizing on A3_RS+S2@1.4×

**Generated:** 2026-07-08
**Pre-reg:** `knowledge/backtests/2026-07-08_pa007_atrsizing_s2base_prereg.md`
**Overall verdict:** FAIL

## Baseline (A3_RS+S2@1.4× flat cap)

- OOS MAR: **2.5233** (locked 2.5233)
- OOS MaxDD: **-5.57%** (locked -5.57%)
- N_OOS: **2383**
- Flags: none

## ATR distribution check (council-mandated)

- Full A3_RS atr10 mean: **0.831679** (n=8890)
- S2-surviving atr10 mean: **0.858985** (n=4146)
- Ratio S2/full: **1.033**
- Flag: **none**

## k calibration (S2-filtered IS only)

- k_atr20: **0.02300000** (n=1762)
- k_atr10: **0.02600000** (n=1762)

## C1_atr20_s2

- OOS MAR: **2.3296** | MaxDD: **-5.57%**
- sub-A: **4.0740** | sub-B: **1.2220**
- G1a (>=2.2710): **PASS**
- G1b (>=-0.0585): **PASS**
- G2 fill (>=80%): **PASS** (97.53%)
- G3 turnover (<=120%): **PASS** (0.753)
- G5 2021 (>=85%): **FAIL** (0.258)
- **Verdict: FAIL**

## C2_atr10_s2

- OOS MAR: **2.3081** | MaxDD: **-5.72%**
- sub-A: **4.0161** | sub-B: **1.3716**
- G1a (>=2.2710): **PASS**
- G1b (>=-0.0585): **PASS**
- G2 fill (>=80%): **PASS** (97.88%)
- G3 turnover (<=120%): **PASS** (0.746)
- G5 2021 (>=85%): **FAIL** (0.255)
- **Verdict: FAIL**

RESEARCH_ONLY_NOT_PRODUCTION