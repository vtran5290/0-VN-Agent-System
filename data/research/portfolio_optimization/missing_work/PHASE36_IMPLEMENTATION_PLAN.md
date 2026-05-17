# Phase36 Implementation Plan

Generated: 2026-05-17 | Decision: evidence-driven only

## Gate: MAR improvement ≥ +0.03 required for adoption

Baseline A3 MAR = 0.416
Threshold = 0.446

## Accepted Variants

- No variants met MAR ≥ +0.03 threshold

## Implementation Steps (if ranking accepted)

### Step 1: Scan update (already done in Phase35)
- a3_rank_score field already in phase35_daily_scan_sample.csv
- s3_lead_bucket field already computed
- No additional scan changes required

### Step 2: Daily runbook update
- NEW_T1 same-day sort: use a3_rank_score DESC (vs current ema_dist)
- Already documented in UPDATED_FINAL_DAILY_RUNBOOK.md

### Step 3: Dashboard panel
- Add Panel 7 (lead-age distribution) to daily monitoring
- Add Panel 8 (A3/S3 coordination) to daily monitoring
- Implement DD correlation monitor (Panel 9)

### Step 4: Paper validation
- Track whether a3_rank_score correctly predicts better same-day picks
- Review at 30 trades / 3 months

## Implementation Steps (if sizing accepted)

- Add s3_size_flag column to scan (True if lead_11_20 or lead_21_30)
- Update order_intent.py: if s3_size_flag=True, increase slot by 25%
- Gate: max slot still subject to ADV cap

## What is NOT changing

- A3 EMA20/100 cloud entry
- TP=18%, trail=2.5×ATR14, max_hold=250
- VNINDEX bear hard block
- Breadth T2 gate
- S3 classification: PAPER_TRADE_SHADOW only
- S3 max_hold=60 hard rule
- A3 real capital gates (Gate 1-7)

## Timeline

No fixed timeline. Evidence-driven.
Next review: after 3 months of paper tracking with a3_rank_score.
