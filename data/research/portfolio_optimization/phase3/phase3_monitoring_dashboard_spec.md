# Phase 3 — Monitoring Dashboard Spec
Generated: 2026-05-16

## Overview

Single-page dashboard for daily paper-trade monitoring of the A3/PTS strategy.
Data source: `phase3_daily_scan_sample.csv` + `data/paper_trade/positions.csv`.

## Panel 1 — Regime & Market Breadth

| Widget | Source | Alert |
|--------|--------|-------|
| VNINDEX vs EMA100 | ta_vnindex.parquet | RED if below (no new entries) |
| VNINDEX 5-day return | ta_vnindex | ≤-3% → yellow |
| % stocks above EMA20 | breadth_daily.csv | <35% → yellow, <25% → red |
| % stocks in cloud (EMA20>EMA100) | breadth_daily.csv | <40% → yellow |
| Active A3 signals today | daily_scan_sample | count, list of symbols |

## Panel 2 — Open Positions

| Column | Source | Alert |
|--------|--------|-------|
| Symbol | positions.csv | — |
| Entry date | positions.csv | hold_bars counter |
| ep1 / blended_ep | positions.csv | — |
| PTS state | daily_scan_sample | PB_HIT/STR_HIT in green |
| Current close | panel | — |
| P&L% | (close/blended_ep - 1) | ≥+18% → TP1 alert (green), ≤-12% → stop-loss alert (red) |
| Trail stop | positions.csv | Price < trail_stop → EXIT alert (red) |
| Hold bars | positions.csv | ≥240 → yellow, ≥250 → red (forced exit) |
| T2 added? | positions.csv | flag |
| GK10 at entry | positions.csv | flag |
| ADV50 B VND | panel | reference |
| Position VND M | computed | vs ADV participation |

## Panel 3 — Today's Actionable Signals

Filter: `recommended_sleeve` in (Growth, PTS, Defensive_PTS)
Sorted by sleeve rank → ema_dist descending.

| Column | Notes |
|--------|-------|
| Symbol | clickable to chart |
| Sleeve | colour-coded: Growth=green, PTS=blue, Defensive_PTS=yellow |
| PTS state | |
| Close | |
| EMA dist % | rank metric |
| GK10 | Y/N badge |
| T1 size (M VND) | at default portfolio size |
| Liq warning | OK=green, WARN=yellow, CRITICAL=red |
| PB trigger | |
| STR trigger (after bar30) | |
| TP1 guide | |

## Panel 4 — Portfolio Metrics

| Metric | Computation | Alert |
|--------|-------------|-------|
| Portfolio NAV (VND) | sum of position values + cash | — |
| Total return % | (NAV / initial) - 1 | — |
| Daily P&L | NAV today vs yesterday | — |
| Drawdown from peak | (NAV / peak_NAV) - 1 | ≤-10% → yellow, ≤-15% → red |
| Current exposure % | sum(pos_value) / NAV | >100% impossible, <50% → low |
| n_positions | count open | |
| Avg position age | avg hold_bars | |
| TP1 hit rate YTD | pct positions that hit TP1 | |
| Win rate YTD | pct closed with net_return>0 | |
| Mean net return (closed) | | |

## Panel 5 — PTS State Tracker

For each open position: show state machine progression.

```
Symbol  | Entry Date | Bars | Phase1 (PB_WAIT) | Phase2 (STR_WAIT) | Add Status
--------|------------|------|-----------------|-------------------|-------------
MSB     | 2026-04-22 |  14  | ████░░░░░░ (30b)| waiting           | NO_ADD_YET
GVR     | 2026-05-06 |   7  | ██░░░░░░░░ (30b)| not started       | PB_WAIT
VHM     | 2026-04-07 |  25  | ██████████ done | ████░░░░░░ (10b)  | STR_WAIT
```

## Alert Rules

| Alert | Trigger | Action |
|-------|---------|--------|
| PB_ADD | position.close ≤ pb_trigger AND cloud_bull | Enter T2 order immediately |
| STR_ADD | bars_since≥31 AND close≥str_trigger AND cloud+EMA | Enter T2 order |
| TP1 | close/blended_ep ≥ 1.18 | Sell 50%, activate trail |
| TRAIL_STOP | close < high_water - 2.5×ATR | Sell remaining |
| MAX_HOLD | hold_bars ≥ 250 | Force-exit all |
| CLOUD_BREAK | cloud turns bearish on open position | Consider early exit |
| REGIME_FLIP | VNINDEX < EMA100 | No new entries; review existing |
| GK_ALERT | GK buy fires on existing position (T1 only) | Consider adding T2 if STR_WAIT |

## Update Cadence

| Event | Frequency |
|-------|-----------|
| Panel data fetch | Daily at 7:00 AM |
| Scan run | Daily at 8:00 AM |
| Intraday alerts | Real-time via price alert app |
| Position update | End of day |
| Weekly review | Monday morning |
