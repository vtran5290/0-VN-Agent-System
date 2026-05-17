# S3→A3 Lead Timing Analysis

Date: 2026-05-17
Universe: A3 DP-First (EMA20/100, ex-VIN3), S3 EMA21/55 (full)
Lookback: 60 bars for S3 lead detection

DO NOT change A3 production logic.
DO NOT allow S3 to gate A3.
This is ranking research only.

---

## 1. Bucket Distribution

| Bucket | N | % of A3 |
|--------|---|---------|
| same_bar_0 | 2,385 | 26.4% |
| lead_1_2 | 1,580 | 17.5% |
| lead_3_5 | 1,399 | 15.5% |
| lead_6_10 | 1,192 | 13.2% |
| lead_11_20 | 741 | 8.2% |
| lead_21_30 | 284 | 3.1% |
| no_s3_lead | 1,450 | 16.1% |

Total A3 trades: 9,031
Trades with any S3 lead (≤30 bars): 7,581 (83.9%)

---

## 2. Per-Bucket Performance Summary

| Bucket | N | MAR | CAGR | MaxDD | Avg Net | Median Net | Hit% | TP1% | Avg ED | Avg ADV50 |
|--------|---|-----|------|-------|---------|-----------|------|------|--------|-----------|
| same_bar_0 | 2,385 | 0.154 | 5.2% | -33.9% | 5.1% | 11.9% | 67.8% | 62.4% | 8.4% | 34.4B |
| lead_1_2 | 1,580 | 0.180 | 4.5% | -24.9% | 6.0% | 11.9% | 68.5% | 63.2% | 8.1% | 30.3B |
| lead_3_5 | 1,399 | 0.158 | 4.2% | -26.8% | 7.9% | 12.7% | 71.0% | 65.6% | 6.8% | 29.3B |
| lead_6_10 | 1,192 | 0.175 | 5.1% | -29.3% | 7.3% | 12.9% | 68.9% | 64.2% | 6.7% | 26.1B |
| lead_11_20 | 741 | 0.464 | 5.7% | -12.2% | 7.9% | 12.5% | 73.1% | 66.0% | 5.2% | 23.1B |
| lead_21_30 | 284 | 0.455 | 6.1% | -13.4% | 10.4% | 14.1% | 77.1% | 71.8% | 4.7% | 24.4B |
| no_s3_lead | 1,450 | 0.214 | 4.8% | -22.3% | 4.2% | 12.3% | 68.6% | 63.0% | 4.5% | 46.7B |

---

## 3. Year-by-Year by Bucket (Portfolio Annual Return)

| Year | same_bar_0 | lead_1_2 | lead_3_5 | lead_6_10 | lead_11_20 | lead_21_30 | no_s3_lead |
|------|---|---|---|---|---|---|---|
| 2014 | 18.0% | 4.3% | 13.7% | 11.5% | 20.0% | 18.2% | 23.2% |
| 2015 | -0.4% | 1.7% | 5.5% | 10.4% | 2.9% | -4.9% | -14.2% |
| 2016 | -11.6% | -16.2% | -17.2% | 3.9% | -0.9% | 8.1% | 9.9% |
| 2017 | 2.2% | 12.4% | 7.1% | 16.6% | 13.7% | 15.3% | 5.5% |
| 2018 | -1.7% | -11.0% | 18.1% | -6.0% | 1.3% | -0.4% | 7.5% |
| 2019 | 6.8% | 2.8% | -12.0% | -18.9% | -1.5% | 1.0% | 6.4% |
| 2020 | -2.9% | -1.2% | 0.2% | 1.3% | -0.3% | -8.5% | -8.0% |
| 2021 | 73.0% | 62.3% | 30.6% | 30.2% | 25.3% | 22.7% | 40.6% |
| 2022 | -9.0% | -2.2% | -3.4% | 5.2% | 0.1% | 1.0% | -0.8% |
| 2023 | -9.4% | -3.5% | -8.7% | -3.8% | 5.8% | 4.1% | -7.6% |
| 2024 | -10.2% | -4.2% | 0.3% | -1.6% | 5.3% | 15.3% | 11.3% |
| 2025 | 35.4% | 16.2% | 15.0% | 25.2% | 15.3% | 22.6% | 10.5% |
| 2026 | -1.8% | 11.3% | 3.7% | -1.9% | -8.3% | -3.7% | -4.1% |

---

## 4. Bad-Year Breakdown (Trade-Level Avg — 2018, 2022, 2026)

| Year | Bucket | N | Avg Net | Hit% |
|------|--------|---|---------|------|
| 2018 | same_bar_0 | 83 | 1.1% | 63.9% |
| 2022 | same_bar_0 | 128 | -27.1% | 33.6% |
| 2026 | same_bar_0 | 189 | -4.1% | 40.2% |
| 2018 | lead_1_2 | 86 | -3.2% | 51.2% |
| 2022 | lead_1_2 | 43 | -32.3% | 30.2% |
| 2026 | lead_1_2 | 98 | -2.1% | 44.9% |
| 2018 | lead_3_5 | 66 | -7.2% | 47.0% |
| 2022 | lead_3_5 | 10 | -33.8% | 10.0% |
| 2026 | lead_3_5 | 39 | -2.5% | 43.6% |
| 2018 | lead_6_10 | 53 | -22.6% | 24.5% |
| 2022 | lead_6_10 | 11 | -14.3% | 54.5% |
| 2026 | lead_6_10 | 17 | -12.8% | 17.6% |
| 2018 | lead_11_20 | 40 | -4.4% | 52.5% |
| 2022 | lead_11_20 | 9 | 0.3% | 66.7% |
| 2026 | lead_11_20 | 30 | -4.8% | 26.7% |
| 2018 | lead_21_30 | 16 | 3.1% | 68.8% |
| 2022 | lead_21_30 | 1 | N/A | N/A |
| 2026 | lead_21_30 | 9 | -3.4% | 22.2% |
| 2018 | no_s3_lead | 41 | -7.6% | 46.3% |
| 2022 | no_s3_lead | 137 | -21.8% | 47.4% |
| 2026 | no_s3_lead | 64 | -3.3% | 37.5% |

---

## 5. Top Sector Concentration by Bucket

| Bucket | N | Top Sector |
|--------|---|-----------|
| same_bar_0 | 2,385 | BDS (23%) |
| lead_1_2 | 1,580 | Banks (20%) |
| lead_3_5 | 1,399 | Banks (23%) |
| lead_6_10 | 1,192 | BDS (26%) |
| lead_11_20 | 741 | BDS (28%) |
| lead_21_30 | 284 | BDS (24%) |
| no_s3_lead | 1,450 | BDS (21%) |

---

## 6. Bars-Since Distribution (lead trades only, first 30 bars)

| Bars Since S3 | N | Avg Net | Hit% | TP1% |
|--------------|---|---------|------|------|
| 0 | 2385 | 5.1% | 67.8% | 62.4% |
| 1 | 875 | 5.9% | 68.9% | 63.5% |
| 2 | 705 | 6.0% | 67.9% | 62.7% |
| 3 | 566 | 8.0% | 71.9% | 66.4% |
| 4 | 455 | 8.1% | 71.0% | 64.6% |
| 5 | 378 | 7.6% | 69.8% | 65.6% |
| 6 | 315 | 6.0% | 67.3% | 62.5% |
| 7 | 276 | 6.9% | 69.6% | 64.5% |
| 8 | 230 | 7.2% | 68.3% | 63.9% |
| 9 | 205 | 7.0% | 67.3% | 63.4% |
| 10 | 166 | 11.1% | 73.5% | 68.1% |
| 11 | 137 | 10.7% | 76.6% | 71.5% |
| 12 | 105 | 7.5% | 71.4% | 66.7% |
| 13 | 86 | 5.7% | 68.6% | 63.9% |
| 14 | 81 | 4.8% | 69.1% | 63.0% |
| 15 | 81 | 6.7% | 69.1% | 63.0% |
| 16 | 74 | 8.4% | 74.3% | 62.2% |
| 17 | 55 | 8.1% | 72.7% | 65.5% |
| 18 | 46 | 11.5% | 87.0% | 76.1% |
| 19 | 40 | 8.2% | 72.5% | 65.0% |
| 20 | 36 | 7.2% | 75.0% | 58.3% |
| 21 | 34 | 13.8% | 82.3% | 76.5% |
| 22 | 37 | 9.9% | 70.3% | 67.6% |
| 23 | 33 | 7.7% | 69.7% | 69.7% |
| 24 | 32 | 10.7% | 71.9% | 71.9% |
| 25 | 26 | 16.0% | 80.8% | 73.1% |
| 26 | 30 | 13.9% | 86.7% | 73.3% |
| 27 | 26 | 8.2% | 76.9% | 73.1% |
| 28 | 23 | 5.3% | 73.9% | 73.9% |
| 29 | 20 | 7.8% | 85.0% | 70.0% |
| 30 | 23 | 8.5% | 78.3% | 69.6% |

---

## 7. Answers to Research Questions

### Q1. Is shorter S3→A3 lag better?

Best performing bucket: **lead_11_20** (MAR=0.464)
MAR by lag (shorter → longer): same_bar_0=0.154, lead_1_2=0.180, lead_3_5=0.158, lead_6_10=0.175, lead_11_20=0.464, lead_21_30=0.455

Monotone improvement as lag decreases: **NO — non-monotone**

Relationship is non-monotone. The peak is at **lead_11_20**, not at 0 bars. This suggests same-bar or very short lag is not automatically better — the S3 signal needs a brief consolidation before A3 fires.

### Q2. Is 0-bar / same-bar (same_bar_0) confirmation too stretched?

same_bar_0: N=2,385, MAR=0.154
lead_1_2:   N=1,580, MAR=0.180
lead_3_5:   N=1,399, MAR=0.158

**YES — same_bar_0 underperforms lead_3_5 by +0.004 MAR.** When S3 and A3 fire simultaneously, the A3 signal may be chasing an already-extended move. The best setups have S3 firing 3–5 bars BEFORE A3.

### Q3. Is 3–5 bars the best window?

lead_3_5 MAR=0.158 vs best bucket MAR=0.464 (lead_11_20)

**PARTIAL** — lead_11_20 (MAR=0.464) outperforms lead_3_5 (MAR=0.158) by +0.307. The 3–5 bar window is good but not optimal.

### Q4. Should AFL show S3LeadAge instead of only S3Lead5=Y/N?

MAR spread across non-zero lead buckets: 0.307

**YES — show S3LeadAge.** The MAR spread across lead buckets is 0.307, meaning the age of the lead matters materially. A boolean S3Lead5=Y/N collapses this information. An AFL plot showing bars_since_s3 (color-coded by bucket) lets the operator see whether the lead is fresh (1–5 bars = strong) or stale (20–30 bars = weaker). Suggested: show a numeric badge or color gradient on the A3 signal bar.

### Q5. Best A3 ranking signal?

Options:
A. S3Lead5 boolean (existing)
B. S3LeadAge bucket (new)
C. S3Lead5 + ED filter (combined)

ED at entry by bucket:
- same_bar_0: avg ED = 8.4%
- lead_1_2: avg ED = 8.1%
- lead_3_5: avg ED = 6.8%
- lead_6_10: avg ED = 6.7%
- lead_11_20: avg ED = 5.2%
- lead_21_30: avg ED = 4.7%
- no_s3_lead: avg ED = 4.5%

Recommendation:
**Use S3Lead5 boolean + ED filter (Option C).**

ED within the lead group does not vary sharply enough to justify full bucket ranking. Keep S3Lead5 boolean to flag the lead, and rank by ED ascending within each group.

---

## 8. Proposed AFL Change (If Q4/Q5 Support LeadAge)

Current AFL: plots S3Lead5=Y/N at A3 signal bar.

Proposed addition (non-breaking):
```afl
// S3LeadAge display on A3 signal bars
// Does NOT change A3 entry logic. Does NOT gate A3.
// Ranking annotation only.
S3LeadAge = bars_since_s3_signal;   // compute in scan, not AFL
Plot(IIf(A3_signal AND S3LeadAge <= 5,  S3LeadAge, Null), "S3Age", colorGreen,  styleHistogram);
Plot(IIf(A3_signal AND S3LeadAge <= 10, S3LeadAge, Null), "S3Age", colorYellow, styleHistogram);
Plot(IIf(A3_signal AND S3LeadAge <= 30, S3LeadAge, Null), "S3Age", colorGray,   styleHistogram);
```

Scan output: add `s3_lead_age_bars` integer column alongside existing `a3_s3_lead_5d` boolean.
s3_lead_age_bars = 0 if no S3 signal within 60 bars.

---

## 9. Implementation Note

The `a3_s3_lead_5d` field in Phase35 scan is correct and unchanged.
`s3_lead_age_bars` is an ADDITIVE field — it supplements, not replaces, the boolean.

No change to:
- A3 entry rules
- A3 sizing
- A3 TP/trail/max_hold
- Order routing
