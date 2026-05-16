# Phase33 Dashboard Specification

Generated: 2026-05-16

## Panel 1: Regime & Breadth
- VNINDEX regime: bull / bear
- A3 breadth (EMA20/100): current value + 20-bar trend
- Breadth zone: normal / caution / defense
- S3 breadth (EMA21/55): reference only (research)

## Panel 2: Sector L4 Stress
- Per active sector: name, count of active signals, breadth within sector
- Flag: WARN if >2 same-L4 names recently broke below EMA20
- Alert: sector concentration >30% of portfolio

## Panel 3: Liquidity Health
- Distribution liq_warn_T1: OK | WARN_NEAR | WARN_OVER | CRITICAL
- Skip rate (recommendation=skip)
- Mean adv50_B_VND for active setups

## Panel 4: Active A3 DP Setups
- Table: symbol, a3_bars_since, gk10, adv50_B_VND, liq_warn_T1, final_action
- Sort: final_action=NEW_T1 first, then adv50 desc
- Filter: in_a3_universe AND regime_bull AND recommendation != skip

## Panel 5: PTS Shadow Setups
- Same as Panel 4 but PTS mode tracking (no capital)
- Label: SHADOW — no real capital allocation

## Panel 6: S3 Research-Only Setups
- Label: RESEARCH_ONLY — no capital, no position size shown
- Table: symbol, s3_bars_since, s3_cloud_bull, sector_l4

## Panel 7: Open Positions
- Current live trades: symbol, entry_date, ep1, current_p&l, trail_stop

## Panel 8: Paper Trade P&L
- Running equity curve vs benchmark
- Monthly return table

## Panel 9: Data Health
- Last panel update date
- adv50 unit check status (ratio = 1000 confirmed)
- Missing adv50_value count
- Missing sector_l4 count
