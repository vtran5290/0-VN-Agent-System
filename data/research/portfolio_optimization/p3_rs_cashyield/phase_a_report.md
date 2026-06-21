# Phase A Results — P3 RS Ranking + Cash-Yield Accounting

Generated: 2026-06-21

## A2: P3 RS Ranking Test

**Pre-registered formula (DO NOT TUNE):**
- 40% × 3-month RS vs liquid universe
- 30% × 6-month RS vs liquid universe
- 20% × distance to 52-week high (proximity = better)
- 10% × ADV50 liquidity percentile

### Results

| Mode | MAR | CAGR | MaxDD | 2021 Return | n_trades |
|------|-----|------|-------|-------------|----------|
| FIFO baseline | 0.2314 | 0.0498 | -0.2152 | +90.55% | 8780 |
| RS ranked (40/30/20/10) | 0.3808 | 0.0695 | -0.1826 | +111.60% | 8780 |

### Kill Criteria Check

| Criterion | Required | Actual | Pass? |
|-----------|----------|--------|-------|
| Honest MAR | ≥ 0.27 | 0.3808 | YES |
| 2021 capture | ≥ 85% | 123.2% | YES |

**Decision: PASS — proceed**

### Annual Returns

| Year | FIFO | RS Ranked |
|------|------|-----------|
| 2012 | -5.63% | -5.63% |
| 2013 | -0.34% | -0.34% |
| 2014 | +7.30% | +8.80% |
| 2015 | +2.42% | +6.11% |
| 2016 | -3.54% | +1.33% |
| 2017 | +7.63% | +7.18% |
| 2018 | +6.15% | +5.19% |
| 2019 | -4.42% | -1.34% |
| 2020 | -12.09% | -13.36% |
| 2021 | +90.55% | +111.60% |
| 2022 | +8.76% | +15.69% |
| 2023 | +0.00% | +0.00% |
| 2024 | +9.10% | +9.55% |
| 2025 | -0.86% | -1.09% |
| 2026 | -5.60% | -5.64% |

## A3: Cash-Yield Accounting

Cash earned on idle capital (FIFO baseline, varying deposit rate).
Label: **portfolio accounting / cash drag reduction** — not trading alpha.

| Cash Yield | MAR | CAGR | MaxDD |
|------------|-----|------|-------|
| 0% | 0.2314 | 0.0498 | -0.2152 |
| 2% | 0.2948 | 0.0602 | -0.2041 |
| 3% | 0.3295 | 0.0654 | -0.1986 |
| 4% | 0.3663 | 0.0707 | -0.1930 |

VN deposit rate reference: ~5.1-6.5% for 12-24 months (VietinBank Jan 2026).
Conservative haircut applied: testing 2-4% (short-tenor proxy).

## Source

- Canonical engine: `phase_exit_sweep_core.py` (FIFO + EMA20>EMA100)
- P0 realism: `p0_realism_p1_winner.py` (next-bar fills, floor/ceiling, T+2, 0.40% RT)
- RS weights: pre-registered, not tuned
- Config: tp1=none, trail=3.5×ATR, stop=2.0×ATR
