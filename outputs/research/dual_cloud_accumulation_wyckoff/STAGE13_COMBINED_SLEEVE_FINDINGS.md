# Stage 13 — Combined A3/S3 Sleeve Portfolio Simulation

## 1. Executive Summary

A3 simulated trades: 2855 signals (ex-VIN, ADV ≥ 2B VND, matured only for returns)
A3 year span: 15 calendar years

S3 annual returns sourced from Stage 12B `stage12b_s3_maxhold_by_year.csv`.

**Research question:** Does a small S3 sleeve (5%–20%) improve A3 portfolio MAR?

**Guardrails:**
- S3_GATES_A3 = False — S3 does not gate A3 signals.
- S3 P&L tracked completely separately before combination.
- Forbidden classifications: ['PAPER_TRADE_PRIMARY', 'PRODUCTION_CANDIDATE']

## 2. A3 Contract Parameters

- Signal: EMA20/100 cloud transition (ex-VIN, ADV ≥ 2B)
- T1 (50%): entry = open[t+1], TP1 = +18%, trail = 2.5×ATR14, max_hold = 250
- T2 (50%): fills when low ≤ T1_entry × (1 − 4%) within 30 bars

## 3. Portfolio Summary

| portfolio                          |   w_a3 |   w_s3 |   n_overlap_years |   a3_cagr |   s3_cagr |   combined_cagr |   a3_maxdd |   combined_maxdd |   a3_mar |   s3_mar |   combined_mar | classification   |
|:-----------------------------------|-------:|-------:|------------------:|----------:|----------:|----------------:|-----------:|-----------------:|---------:|---------:|---------------:|:-----------------|
| A3_ONLY                            |  1.000 |  0.000 |                15 |     0.029 |   nan     |           0.029 |     -0.180 |           -0.180 |    0.158 |  nan     |          0.158 | NEUTRAL_SLEEVE   |
| A3_95__S3_MAX60_OFFICIAL_SHADOW_5  |  0.950 |  0.050 |                15 |     0.029 |    -0.006 |           0.027 |     -0.180 |           -0.183 |    0.158 |   -0.022 |          0.147 | DILUTES_A3       |
| A3_90__S3_MAX60_OFFICIAL_SHADOW_10 |  0.900 |  0.100 |                15 |     0.029 |    -0.006 |           0.025 |     -0.180 |           -0.186 |    0.158 |   -0.022 |          0.136 | DILUTES_A3       |
| A3_85__S3_MAX60_OFFICIAL_SHADOW_15 |  0.850 |  0.150 |                15 |     0.029 |    -0.006 |           0.024 |     -0.180 |           -0.189 |    0.158 |   -0.022 |          0.125 | DILUTES_A3       |
| A3_80__S3_MAX60_OFFICIAL_SHADOW_20 |  0.800 |  0.200 |                15 |     0.029 |    -0.006 |           0.022 |     -0.180 |           -0.192 |    0.158 |   -0.022 |          0.115 | DILUTES_A3       |
| A3_95__S3_MAX105_RESEARCH_ONLY_5   |  0.950 |  0.050 |                15 |     0.029 |     0.012 |           0.028 |     -0.180 |           -0.182 |    0.158 |    0.047 |          0.153 | NEUTRAL_SLEEVE   |
| A3_90__S3_MAX105_RESEARCH_ONLY_10  |  0.900 |  0.100 |                15 |     0.029 |     0.012 |           0.027 |     -0.180 |           -0.184 |    0.158 |    0.047 |          0.147 | DILUTES_A3       |
| A3_85__S3_MAX105_RESEARCH_ONLY_15  |  0.850 |  0.150 |                15 |     0.029 |     0.012 |           0.026 |     -0.180 |           -0.186 |    0.158 |    0.047 |          0.141 | DILUTES_A3       |
| A3_80__S3_MAX105_RESEARCH_ONLY_20  |  0.800 |  0.200 |                15 |     0.029 |     0.012 |           0.025 |     -0.180 |           -0.188 |    0.158 |    0.047 |          0.136 | DILUTES_A3       |

## 4. A3 vs S3 Annual Return Correlation

| s3_variant               |   n_overlap_years |   pearson_correlation |   p_value | diversification_benefit   |
|:-------------------------|------------------:|----------------------:|----------:|:--------------------------|
| S3_MAX60_OFFICIAL_SHADOW |                15 |                 0.667 |     0.007 | False                     |
| S3_MAX105_RESEARCH_ONLY  |                15 |                 0.824 |     0.000 | False                     |

**S3_MAX60_OFFICIAL_SHADOW**: correlation = 0.667 — high correlation — limited diversification benefit (r ≥ 0.5).

**S3_MAX105_RESEARCH_ONLY**: correlation = 0.824 — high correlation — limited diversification benefit (r ≥ 0.5).

## 5. Sleeve Classification

| s3_variant               |   w_s3 |   combined_mar |   a3_mar |   mar_delta_pp |   n_overlap_years | classification   | action                                                 |
|:-------------------------|-------:|---------------:|---------:|---------------:|------------------:|:-----------------|:-------------------------------------------------------|
| S3_MAX60_OFFICIAL_SHADOW |  0.050 |          0.147 |    0.158 |         -1.128 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX60_OFFICIAL_SHADOW |  0.100 |          0.136 |    0.158 |         -2.227 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX60_OFFICIAL_SHADOW |  0.150 |          0.125 |    0.158 |         -3.298 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX60_OFFICIAL_SHADOW |  0.200 |          0.115 |    0.158 |         -4.344 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX105_RESEARCH_ONLY  |  0.050 |          0.153 |    0.158 |         -0.574 |                15 | NEUTRAL_SLEEVE   | combined MAR within ±5% of A3-only — negligible effect |
| S3_MAX105_RESEARCH_ONLY  |  0.100 |          0.147 |    0.158 |         -1.140 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX105_RESEARCH_ONLY  |  0.150 |          0.141 |    0.158 |         -1.700 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |
| S3_MAX105_RESEARCH_ONLY  |  0.200 |          0.136 |    0.158 |         -2.253 |                15 | DILUTES_A3       | combined MAR < A3-only − 5% — S3 sleeve dilutes A3     |

## 6. Safety Confirmation

- **S3_GATES_A3 = False** — S3 regime does not filter A3 signals. ✓
- **A3 production contract parameters unchanged.** ✓
- **S3 P&L tracked completely separately.** ✓
- No PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY classification made. ✓
- No modification to OMS / live / DNSE. ✓
- `final_action` not modified. ✓

## 7. Limitations

- Annual-average return conflates diversified multi-stock portfolio with individual trades.
- S3 annual returns from Stage 12B use ALL signals (BASE_REGIME + ADV ≥ 2B) — not filtered to only co-occur with A3 signals.
- T2 fill assumes intraday execution at bar's open (gap risk not modeled for T2).
- Correlation computed on overlapping years only — sample size limited.

## 8. Recommended Next Step

S3 sleeve dilutes A3 MAR in some configurations. No further action recommended.
Re-evaluate if S3 base performance improves over next 12 months of live paper trading.
