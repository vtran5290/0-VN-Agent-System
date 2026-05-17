# Phase36 Dashboard Proposal

Generated: 2026-05-17 | Extends UPDATED_PHASE35_DASHBOARD_SPEC.md

## New / Updated Panels

### Panel 2 — A3 Production (updated)
- Sort NEW_T1 by a3_rank_score DESC (Phase36 standard)
- Show s3_lead_bucket column (lead_11_20 highlighted)
- Show a3_rank_score, ed_score, quality_boost separately
- a3_priority_boost_from_s3 flag column

### Panel 7 — Lead-Age Distribution (Phase36)
- Bar chart: count of active setups by s3_lead_bucket
- Target zone: lead_11_20 + lead_21_30 as % of NEW_T1
- Chase alert: if same_bar_0 > 30% of NEW_T1, flag "Chase risk"

### Panel 8 — A3/S3 Coordination Monitor (Phase36)
- Columns: symbol, a3_rank_score, s3_lead_bucket, s3_lead_bdays, ed_score
- Sorted by a3_rank_score DESC for current-day NEW_T1 signals
- Color: green for lead_11_20/lead_21_30, yellow for neutral, red for same_bar_0

### Panel 9 — DD Correlation Monitor (Phase36G)
- A3 portfolio rolling 20-day DD vs S3 shadow rolling 20-day DD
- Alert threshold: both DD > 10% → "Correlated drawdown"

## Existing Panels (Phase35, unchanged)
- Panel 1: Data health / as-of
- Panel 2: A3 production (updated above)
- Panel 3: S3 paper shadow (max_hold=60)
- Panel 4: S3 research monitor (GK5+top100)
- Panel 5: Legacy satellite (not production SSOT)
- Panel 6: Warnings
- Panel 10: S3 combo paper (Phase36, TP=10%)
