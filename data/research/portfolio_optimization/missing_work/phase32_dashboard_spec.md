# Phase32 Dashboard Specification

Generated: 2026-05-16

## Dashboard Panels

### Panel 1: Regime & Breadth
- VNINDEX regime state (bull/bear)
- A3 universe breadth: pct_cloud_bull_20_100
- S3 universe breadth: pct_cloud_bull_21_55
- Breadth thresholds: >60% = strong bull, <40% = defensive

### Panel 2: Active Setups
- Active A3 signals (within 40 bars): count, top 5 by liq_warn
- Active S3 signals (within 40 bars): count, top 5 by liq_warn
- GK10 flag count

### Panel 3: Liquidity Health
- Distribution of liq_warn_T1: OK/WARN_NEAR/WARN_OVER/CRITICAL
- Skip rate = pct(recommendation='skip')
- Mean adv50_B_VND for active setups

### Panel 4: Trade Candidates
- Table: symbol, a3_active, s3_active, gk10, adv50_B_VND, liq_warn_T1, recommendation
- Sorted by: recommendation=full_T1 first, then adv50 desc
- Filter: recommendation != skip AND regime_bull = True

## Alerts

- A3 breadth < 40%: reduce exposure / no new A3 entries
- S3 breadth < 40%: reduce exposure / no new S3 entries
- Regime bear: paper-trade only, no live entries
