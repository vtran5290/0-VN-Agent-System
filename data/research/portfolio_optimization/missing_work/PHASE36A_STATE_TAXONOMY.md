# Phase36A — State Taxonomy

Generated: 2026-05-17 | Symbols: 267 | Universe: A3 ex-VIN3

## Signal Totals

| Metric | Count |
|--------|-------|
| A3 signals (all years) | 12,917 |
| S3 signals (all years) | 17,329 |
| S3/A3 signal ratio | 1.34× |

## A3 Lead-Bucket Distribution (regime-bull bars only)

| Bucket | Count | Pct of A3 |
|--------|-------|-----------|
| same_bar_0 (chase) | 0 | 0.0% |
| lead_1_5 (neutral) | 4,748 | 36.8% |
| lead_6_10 (neutral) | 1,215 | 9.4% |
| lead_11_20 (best +2.0) | 776 | 6.0% |
| lead_21_30 (good +1.0) | 330 | 2.6% |
| no_s3_lead | 1,970 | 15.3% |

## Implications

- S3 fires ~1.3× more often than A3 (EMA21/55 faster than EMA20/100)
- ~8.6% of A3 signals have a lead_11_30 S3 precursor (prime ranking zone)
- ~0.0% of A3 signals fire same-bar as S3 (chase, ranked below)
- ~15.3% of A3 signals have no recent S3 precursor

## Key Finding

FACT: S3 EMA21/55 provides a materially earlier signal than A3 EMA20/100 in
8.6% of cases. These are the prime candidates
for ranking boost.

INTERPRETATION: If lead_11_20 and lead_21_30 A3 trades perform better than no_s3_lead
trades at the portfolio level, ranking by a3_rank_score should improve slot-constrained MAR.
See Phase36B for evidence.
