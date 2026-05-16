# Phase32 Paper Trade Rules

Generated: 2026-05-16

## A3 (EMA20/100) — Primary / DP-First

**Entry:**
- Cloud breakout (EMA20 cross above EMA100 + price above both)
- Universe: ex-VIN3 (exclude VIN, VPL)
- Regime gate: VNINDEX must be in bull regime
- Breadth gate: pct_cloud_bull_a3_universe > 40%

**Position sizing (DP-first):**
- T1 = 50% of intended slot at entry
- T2 = 50% on pullback ≥4% within 30 bars (pb_only mode)
- Slot size = portfolio / 20 (× 1.25 if GK10)
- ADV cap: effective_T1 = min(T1, adv50_B × 10%)

**Exit:**
- TP1: +18% (sell 50% of position)
- Trail: 2.5× ATR14 from highest close since entry
- Max hold: 250 bars

## S3 (EMA21/55) — Shadow / Paper Trade

**Entry:**
- Cloud breakout (EMA21 cross above EMA55 + price above both)
- Universe: full (all 272 symbols)
- Regime gate: VNINDEX must be in bull regime
- Breadth gate: pct_cloud_bull_s3_universe > 40%

**Position sizing:**
- T1 = best_t1_frac × slot at entry (see s3_dp_screening_pass.csv)
- T2 = (1-t1_frac) × slot on pullback
- Slot size = portfolio / 20 (× 1.25 if GK10)
- ADV cap: effective_T1 = min(T1, adv50_B × 10%)

**Exit:**
- TP1: +18% (sell 50% of position)
- Trail: 3.5× ATR14 from highest close since entry
- Max hold: 250 bars

## Concurrent Position Limits

- A3 book: max 20 active positions
- S3 book: max 20 active positions (paper only)
- Combined: A3 is primary; S3 paper trades do not consume real capital
- Vietnam settlement: T+3; min sell lock = 5 bars

## Risk Controls

- Stop adding if A3 breadth < 35% (bear territory)
- Stop all S3 entries if S3 breadth < 35%
- Regime flip to bear: close T1 tranches on next available day
