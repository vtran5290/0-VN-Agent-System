# S3 Combo Test — TP10 + mom20≥0% + a3_breadth≥35% + max_hold=60

Date: 2026-05-17
Config: S3 EMA21/55, TP=10%, Trail=3.5×ATR14, max_hold=60, VNINDEX regime gate,
        a3_breadth≥35%, mom20_at_entry≥0
Baseline: A3 DP-First EMA20/100, TP=18%, Trail=2.5×ATR14, max_hold=250

DO NOT change A3 production logic.
DO NOT route S3 to real orders.

---

## 1. Overall Comparison

| Config | N | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Avg Hold |
|--------|---|-----|------|-------|----------|----------|----------|
| A3_DP | 9,031 | 0.2629 | 5.8% | -22.1% | 69.4% | 63.9% | 137b |
| S3_TP10_mom20_a3b35_max60 | 9,729 | 0.6402 | 11.2% | -17.5% | 58.3% | 35.4% | 51b |

---

## 2. Year-by-Year

| Year | A3_DP | S3_TP10_mom20_a3b35_max60 | S3 Better? |
|------|-------|---------------|------------|
| 2014 | 16.1% | 22.5% | ✓ |
| 2015 | -0.2% | -4.6% | ✗ |
| 2016 | -6.7% | -2.4% | ✓ |
| 2017 | 6.7% | 31.8% | ✓ |
| 2018 | -2.2% | -7.7% | ✗ |
| 2019 | -1.3% | 1.7% | ✓ |
| 2020 | 6.1% | 18.6% | ✓ |
| 2021 | 62.8% | 105.0% | ✓ |
| 2022 | 3.1% | -17.2% | ✗ |
| 2023 | -6.8% | 8.3% | ✓ |
| 2024 | -0.1% | 9.1% | ✓ |
| 2025 | 12.9% | 50.3% | ✓ |
| 2026 | 7.4% | 8.4% | ✓ |

---

## 3. OOS (Yearly Fold Pass Rate)

| Year | S3 N | S3 Avg Net | S3 Hit | S3 Pass | A3 N | A3 Avg Net | A3 Pass |
|------|------|-----------|--------|---------|------|-----------|---------|
| 2015 | 361 | -3.3% | 44.0% | ✗ | 351 | 0.0% | ✓ |
| 2016 | 577 | 0.7% | 49.7% | ✓ | 525 | 9.1% | ✓ |
| 2017 | 991 | 6.3% | 62.6% | ✓ | 848 | 8.0% | ✓ |
| 2018 | 426 | -7.7% | 36.6% | ✗ | 385 | -6.0% | ✗ |
| 2019 | 649 | -2.9% | 42.8% | ✗ | 675 | -3.8% | ✗ |
| 2020 | 729 | 13.3% | 82.2% | ✓ | 728 | 21.8% | ✓ |
| 2021 | 1053 | 14.7% | 73.4% | ✓ | 788 | 12.7% | ✓ |
| 2022 | 489 | -16.3% | 31.7% | ✗ | 339 | -24.6% | ✗ |
| 2023 | 373 | 0.6% | 54.4% | ✓ | 371 | -1.2% | ✗ |
| 2024 | 935 | -1.5% | 43.9% | ✗ | 1154 | 5.3% | ✓ |
| 2025 | 1231 | 9.0% | 69.2% | ✓ | 1127 | 11.8% | ✓ |
| 2026 | 483 | -2.6% | 46.6% | ✗ | 446 | -3.8% | ✗ |

**S3 OOS pass rate: 6/12 | A3 OOS pass rate: 7/12**

---

## 4. Liquidity Sensitivity

| ADV Floor | S3 N | % Kept | S3 MAR | S3 MaxDD | A3 MAR |
|-----------|------|--------|--------|----------|--------|
| ≥0B | 9,729 | 100.0% | 0.6402 | -17.5% | 0.2629 |
| ≥10B | 4,341 | 44.6% | 0.2141 | -39.4% | 0.1086 |
| ≥20B | 3,056 | 31.4% | 0.1393 | -48.0% | 0.0143 |
| ≥50B | 1,623 | 16.7% | 0.1440 | -35.5% | 0.0538 |
| ≥100B | 878 | 9.0% | 0.1476 | -34.1% | 0.0869 |

---

## 5. Cost Sensitivity

| Cost | S3 MAR | S3 CAGR | S3 MaxDD | A3 MAR | A3 CAGR |
|------|--------|---------|----------|--------|---------|
| 0.3% | 0.6630 | 11.5% | -17.3% | 0.2708 | 5.9% |
| 0.4% | 0.6402 | 11.2% | -17.5% | 0.2629 | 5.8% |
| 0.5% | 0.6178 | 10.9% | -17.6% | 0.2553 | 5.7% |
| 0.6% ← stress | 0.5960 | 10.6% | -17.8% | 0.2477 | 5.6% |
| 0.7% | 0.5747 | 10.3% | -18.0% | 0.2404 | 5.5% |
| 0.8% | 0.5538 | 10.1% | -18.2% | 0.2331 | 5.3% |

---

## 6. Bad-Year Drawdown (2018, 2019, 2022)

| Year | Config | N | Avg Net | Hit Rate | Worst Trade | % Losers |
|------|--------|---|---------|----------|-------------|----------|
| 2018 | A3_DP | 385 | -6.0% | 49.9% | -73.2% | 50.1% |
| 2018 | S3_TP10_mom20_a3b35_max60 | 426 | -7.7% | 36.6% | -59.4% | 63.4% |
| 2019 | A3_DP | 675 | -3.8% | 50.1% | -70.3% | 49.9% |
| 2019 | S3_TP10_mom20_a3b35_max60 | 649 | -2.9% | 42.8% | -44.4% | 57.2% |
| 2022 | A3_DP | 339 | -24.6% | 39.8% | -86.7% | 60.2% |
| 2022 | S3_TP10_mom20_a3b35_max60 | 489 | -16.3% | 31.7% | -71.5% | 68.3% |

---

## 7. Verdict

**PRODUCTION_CANDIDATE_PENDING_PAPER**

S3 combo MAR=0.6402 ≥ 0.40. Qualifies if OOS and paper gate pass.

| Gate | S3 Combo | A3 DP |
|------|----------|-------|
| MAR | 0.6402 | 0.2629 |
| MaxDD | -17.5% | -22.1% |
| MAR at 0.6% cost | 0.5960 | 0.2477 |
| OOS folds positive | 6/12 | 7/12 |

### What This Config Is

- TP1 = 10% (faster exit vs A3's 18%) — captures S3's fast momentum peak
- mom20≥0% = only enter when recent momentum is positive (removes 8% of bad setups)
- a3_breadth≥35% = only enter when A3 universe is not in deep defense (minimal filter)
- VNINDEX regime gate = unchanged from production rule

### What This Config Is NOT

- This is NOT a production promotion. Paper gate (3 months, 30 decisions, 10 exits) required.
- No real capital. No DNSE routing. S3 shadow ledger only.
- A3 logic is untouched.
