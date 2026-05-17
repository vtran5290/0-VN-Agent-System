# Phase36 Scan Schema Proposal

Generated: 2026-05-17 | Based on Phase36A-H research findings

## New Fields vs Phase35 Schema (58 fields)

| Field | Type | Description | Phase |
|-------|------|-------------|-------|
| s3_lead_bdays | int | Business days since last S3 signal (≤35, else NaN) | 36 |
| s3_lead_bucket | str | Bucket: same_bar_0/lead_1_5/lead_6_10/lead_11_20/lead_21_30/no_s3_lead | 36 |
| ed_score | float | EMA proximity score: max(0, 1-abs(ema_dist_pct)/0.20) | 36 |
| a3_rank_score | float | ed_score + quality_boost(s3_lead_bucket) | 36 |
| a3_s3_lead_5d | bool | True if s3_lead_bdays in [1,5] (legacy boolean) | 35 |
| a3_priority_boost_from_s3 | bool | True if lead_11_20 or lead_21_30 | 36 |

## Total fields after Phase36: 64

## Ranking Rules

Multiple NEW_T1 same day → sort by a3_rank_score DESC.
Best variant from Phase36B research: ed_score_only

- lead_11_20 + good ed_score → highest a3_rank_score
- same_bar_0 (chase) → penalized by -0.5 boost
- no_s3_lead → neutral (0.0 boost), ed_score only

## Hard Rules (unchanged)

- a3_rank_score does NOT block any A3 signal
- Ranking applies only when slot capacity is binding (>MAX_SLOTS NEW_T1 same day)
- S3 shadow fields remain PAPER_TRADE_SHADOW — never route to live orders
