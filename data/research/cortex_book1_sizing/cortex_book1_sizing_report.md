# Cortex Book #1 — Fixed-Fractional Risk-Per-Trade Sizing

**Generated:** 2026-07-04
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge\backtests\2026-07-04_cortex_book1_sizingrule_prereg.md`
**Gate addendum:** `knowledge\backtests\2026-07-04_cortex_book1_sizingrule_gates_addendum.md`

## Window

- Panel start (actual): **2012-01-03**
- Panel end: **2026-12-31**
- Primary OOS gates: **2020–2026**
- Stop rule: entry − 2.0×ATR14 (P1 honest initial stop)

## Baseline (A3 P1 honest + D4 + D3 @ 1.25/0.75 slot sizing)

- Full MAR **0.5321**
- Full MaxDD **-14.26%**
- Full CAGR **7.59%**
- OOS MAR **0.8386**
- OOS MaxDD **-12.24%**
- OOS 12m MAR (diagnostic) **-0.8907**

## Gate thresholds (pre-registered)

- G1a margin: **+0.050** MAR vs baseline OOS
- G1b floor: **0.400** absolute OOS MAR

## Candidate — risk_pct 1.25%

**Verdict: FAIL**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.3940 |
| Full MaxDD | -14.26% | -14.40% |
| Full CAGR | 7.59% | 5.67% |
| OOS MAR | 0.8386 | 0.6558 |
| OOS MaxDD | -12.24% | -12.48% |
| OOS CAGR | 10.26% | 8.18% |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline OOS MAR + 0.050 | FAIL |
| G1b | OOS MAR >= 0.400 absolute floor | PASS |
| Frozen-A3 | Entry stream identical to baseline | PASS |
| Neg-OOS-cap | Both baseline and candidate OOS MAR negative | PASS |

## Candidate — risk_pct 1.75%

**Verdict: FAIL**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.3940 |
| Full MaxDD | -14.26% | -14.40% |
| Full CAGR | 7.59% | 5.67% |
| OOS MAR | 0.8386 | 0.6558 |
| OOS MaxDD | -12.24% | -12.48% |
| OOS CAGR | 10.26% | 8.18% |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline OOS MAR + 0.050 | FAIL |
| G1b | OOS MAR >= 0.400 absolute floor | PASS |
| Frozen-A3 | Entry stream identical to baseline | PASS |
| Neg-OOS-cap | Both baseline and candidate OOS MAR negative | PASS |

## Candidate — risk_pct 2.50%

**Verdict: FAIL**

| Metric | Baseline | Candidate |
|--------|----------|-----------|
| Full MAR | 0.5321 | 0.3940 |
| Full MaxDD | -14.26% | -14.40% |
| Full CAGR | 7.59% | 5.67% |
| OOS MAR | 0.8386 | 0.6558 |
| OOS MaxDD | -12.24% | -12.48% |
| OOS CAGR | 10.26% | 8.18% |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | OOS MAR >= baseline OOS MAR + 0.050 | FAIL |
| G1b | OOS MAR >= 0.400 absolute floor | PASS |
| Frozen-A3 | Entry stream identical to baseline | PASS |
| Neg-OOS-cap | Both baseline and candidate OOS MAR negative | PASS |

### Notes
- Research-only simulation; does not import `sizing_policy.py`.
- Baseline uses operational D3 sector slot multipliers; candidates use fixed-fractional risk-per-trade only.
- Realism: P1 honest execution (T+2, floor/ceiling locks, ADV caps, 40bps RT costs).
- Does not advance vn-trading-advisor session counter (CALIBRATION activity).
