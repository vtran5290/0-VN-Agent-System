# Cortex Book #2 — S1 — O'Neil 52-Week High Proximity Filter

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Filter type:** S1_52wk_proximity
**Pre-registration:** `knowledge/backtests/2026-07-04_cortex_book2_s1_52wkhi_prereg.md`

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

## Candidate — within_15pct

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 1.4435 |
| Full MaxDD | -14.26% | -8.17% |
| Full CAGR | 7.59% | 11.79% |
| OOS MAR | 0.8386 | 1.7844 |
| OOS MaxDD | -12.24% | -8.17% |
| OOS CAGR | 10.26% | 14.57% |
| N trades (full) | 8876 | 3040 |
| N trades (OOS) | 4889 | 1732 |
| N trades (OOS sub-A) | — | 612 |
| N trades (OOS sub-B) | — | 1120 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline + 0.066 (0.9044) | PASS ✓ |
| G1b | OOS MAR >= 0.516 (absolute floor, k-adjusted) | PASS ✓ |
| N_OOS_full | >= 30 trades in full OOS (2020-2026) | PASS ✓ |
| N_OOS_sub_A | >= 12 trades in OOS sub-window A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades in OOS sub-window B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | Both baseline and candidate OOS MAR positive | PASS ✓ |

## Candidate — within_20pct

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 1.1066 |
| Full MaxDD | -14.26% | -9.14% |
| Full CAGR | 7.59% | 10.11% |
| OOS MAR | 0.8386 | 1.7273 |
| OOS MaxDD | -12.24% | -7.39% |
| OOS CAGR | 10.26% | 12.77% |
| N trades (full) | 8876 | 4760 |
| N trades (OOS) | 4889 | 2790 |
| N trades (OOS sub-A) | — | 987 |
| N trades (OOS sub-B) | — | 1803 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline + 0.066 (0.9044) | PASS ✓ |
| G1b | OOS MAR >= 0.516 (absolute floor, k-adjusted) | PASS ✓ |
| N_OOS_full | >= 30 trades in full OOS (2020-2026) | PASS ✓ |
| N_OOS_sub_A | >= 12 trades in OOS sub-window A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades in OOS sub-window B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | Both baseline and candidate OOS MAR positive | PASS ✓ |

## Candidate — within_25pct

**Verdict: ADVANCE**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.5025 |
| Full MaxDD | -14.26% | -15.10% |
| Full CAGR | 7.59% | 7.59% |
| OOS MAR | 0.8386 | 1.1811 |
| OOS MaxDD | -12.24% | -9.91% |
| OOS CAGR | 10.26% | 11.70% |
| N trades (full) | 8876 | 6066 |
| N trades (OOS) | 4889 | 3510 |
| N trades (OOS sub-A) | — | 1230 |
| N trades (OOS sub-B) | — | 2280 |

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
