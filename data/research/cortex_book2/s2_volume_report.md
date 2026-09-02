# Cortex Book #2 — S2 — O'Neil Breakout Volume Filter

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Filter type:** S2_volume_filter
**Pre-registration:** `knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md`

## Window

- Panel start (actual): **2012-01-03**
- Panel end: **2026-12-31**
- Primary OOS window: **2020–2026**
- OOS sub-window A: **2020–2022**
- OOS sub-window B: **2023–2026**

## Baseline (A3 P1 honest + D4 + D3 @ 1.25/0.75 slot sizing)

- Full MAR: **0.5321**
- Full MaxDD: **-14.26%**
- OOS MAR: **0.8386**
- OOS MaxDD: **-12.24%**
- Baseline OOS trade count: **4889**

## Gate thresholds (pre-registered, locked before run)

- G1a: candidate OOS MAR >= baseline + 0.066 = **0.9044**
  (base margin 0.050 + k=3 adj 0.016)
- G1b: candidate OOS MAR >= **0.516** (floor 0.500 + k-adj 0.016)
- N_OOS (full): >= 30 | Sub-window each: >= 12

## Candidate — vol_1_2x

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.8097 |
| Full MaxDD | -14.26% | -10.90% |
| Full CAGR | 7.59% | 8.83% |
| OOS MAR | 0.8386 | 2.3608 |
| OOS MaxDD | -12.24% | -5.48% |
| OOS CAGR | 10.26% | 12.95% |
| N trades (full) | 8876 | 4900 |
| N trades (OOS) | 4889 | 2834 |
| N trades (OOS sub-A) | — | 1047 |
| N trades (OOS sub-B) | — | 1787 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline + 0.066 (0.9044) | PASS ✓ |
| G1b | OOS MAR >= 0.516 (absolute floor, k-adjusted) | PASS ✓ |
| N_OOS_full | >= 30 trades in full OOS (2020-2026) | PASS ✓ |
| N_OOS_sub_A | >= 12 trades in OOS sub-window A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades in OOS sub-window B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | Both baseline and candidate OOS MAR positive | PASS ✓ |

## Candidate — vol_1_3x

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.8729 |
| Full MaxDD | -14.26% | -10.64% |
| Full CAGR | 7.59% | 9.28% |
| OOS MAR | 0.8386 | 2.4804 |
| OOS MaxDD | -12.24% | -5.44% |
| OOS CAGR | 10.26% | 13.50% |
| N trades (full) | 8876 | 4492 |
| N trades (OOS) | 4889 | 2591 |
| N trades (OOS sub-A) | — | 959 |
| N trades (OOS sub-B) | — | 1632 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline + 0.066 (0.9044) | PASS ✓ |
| G1b | OOS MAR >= 0.516 (absolute floor, k-adjusted) | PASS ✓ |
| N_OOS_full | >= 30 trades in full OOS (2020-2026) | PASS ✓ |
| N_OOS_sub_A | >= 12 trades in OOS sub-window A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades in OOS sub-window B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | Both baseline and candidate OOS MAR positive | PASS ✓ |

## Candidate — vol_1_4x

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.9080 |
| Full MaxDD | -14.26% | -10.91% |
| Full CAGR | 7.59% | 9.91% |
| OOS MAR | 0.8386 | 2.5447 |
| OOS MaxDD | -12.24% | -5.57% |
| OOS CAGR | 10.26% | 14.17% |
| N trades (full) | 8876 | 4138 |
| N trades (OOS) | 4889 | 2375 |
| N trades (OOS sub-A) | — | 874 |
| N trades (OOS sub-B) | — | 1501 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline + 0.066 (0.9044) | PASS ✓ |
| G1b | OOS MAR >= 0.516 (absolute floor, k-adjusted) | PASS ✓ |
| N_OOS_full | >= 30 trades in full OOS (2020-2026) | PASS ✓ |
| N_OOS_sub_A | >= 12 trades in OOS sub-window A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades in OOS sub-window B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | Both baseline and candidate OOS MAR positive | PASS ✓ |

## Notes
- Filter applies on SIGNAL BAR (close of bar before entry). Entry is next-open (T+1).
- 52w high: rolling max of prior 252 high bars (inclusive of signal bar).
- Vol 50d avg: rolling mean of prior 50 volume bars (EXCLUDING signal bar — point-in-time).
- Sizing: unchanged D3 sector slot sizing (1.25x leading / 0.75x lagging).
- Realism: P1 honest execution (T+2 settlement, floor/ceiling locks, ADV caps, 40bps RT costs).
- RESEARCH_ONLY_NOT_PRODUCTION — does not touch live signal modules or sizing_policy.py.
- Does not advance vn-trading-advisor session counter (CALIBRATION activity).
