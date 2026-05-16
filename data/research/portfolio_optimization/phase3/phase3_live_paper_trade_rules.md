# Phase 3 — Live Paper-Trade Rules
Generated: 2026-05-16

## Strategy Configuration

| Parameter | Value |
|-----------|-------|
| Base signal | A3 (EMA20/100 cloud breakout) |
| Universe | HOSE ex-VIN3, ≥252 bars history |
| Entry mode | T1=50% at close of signal day+1 (open next morning) |
| Pullback add | T2=50% if price drops ≥4% from entry within 30 bars (cloud must stay bullish) |
| Strength add | T2=50% if price rises ≥6% from entry after bar 30, within bar 40, cloud+EMA bullish |
| GK boost | If GK buy signal within 10 days: position size ×1.25 (capped at 2×base) |
| TP1 | +18% from blended entry → sell 50% of position |
| Trail | After TP1: 2.5×ATR trailing stop on remaining 50% |
| Max hold | 250 bars (~1 year) |
| VNINDEX gate | No new entries if VNINDEX below EMA100 |
| Cost assumption | 0.4% round-trip (adjust for your broker) |

## Sleeves

| Sleeve | When | Size | Notes |
|--------|------|------|-------|
| **Growth** | GK10 confirmed + cloud bull + regime bull + near-entry ≤+8% | 1.25× base | Priority fill |
| **PTS** | A3 signal, no GK, cloud bull, regime bull, PB_WAIT or STR_WAIT | 1.0× base | Standard |
| **Defensive_PTS** | PB_WAIT + price at ideal pullback (−3% to −8%) | 1.0× base | Wait for PB confirmation |
| **Watch_only** | Cloud broken, regime bear, or stretched >+8% | 0 | Do not enter |

## Portfolio Construction

```
max_positions = 15 (A3_pos15 sleeve)
max_positions = 20 (PTS/DP sleeve — smaller per-position weight)
base_position_weight = 1/max_positions of portfolio
GK boost: effective_weight = min(1.25 × base_w, adv50 × participation / portfolio_vnd)
participation_cap: position_vnd ≤ ADV50 × participation_rate
  aggressive: 20% ADV50
  standard:   10% ADV50  ← default
  conservative: 5% ADV50
min_position_vnd = 100,000 VND (skip if below)
```

## Portfolio Size Feasibility

| Portfolio | At 10% ADV | Recommendation |
|-----------|-----------|----------------|
| 3B VND | Most trades fit | Full strategy |
| 5B VND | ~60-70% fit | Reduce to top 12 ranks |
| 10B VND | ~45-55% fit | Cap at 5B VND or accept partial fills |

## Daily Run Workflow

```
Before 9:00 AM:
  1. python scripts/run_weekly_full_fetch.py   # or daily_fetch
  2. python pp_backtest/daily_three_strategy_scan.py  # check regime + signals
  3. python pp_backtest/portfolio_optimization_phase3.py --phase scan  # Phase3 enrichment

9:00–9:15 AM (pre-market):
  4. Review phase3_daily_scan_sample.csv — filter sleeve=Growth/PTS
  5. Check liquidity_warning: skip CRITICAL, scale WARN_OVER
  6. Compute T1 share count: shares = (portfolio_B × 1e9 / max_pos × 0.5) / close
  7. Round to nearest 100 shares (lot size)

9:15–9:20 AM (order entry):
  8. Enter T1 orders at ATC price (or limit at signal close × 1.005)
  9. Set price alert for pb_trigger_price (pullback add) and str_trigger_price (strength add)
 10. Set stop-loss alert at entry × 0.85 (initial hard stop before ATR trail kicks in)

During session:
 11. Monitor PTS alerts. If pb_trigger hit: enter T2 order
 12. After bar 30: if no pullback, switch to STR_WAIT. If str_trigger hit: enter T2
 13. TP1 alert: if +18% from blended entry → sell 50%, activate trail stop
```

## Paper-Trade Checklist (daily)

```
[ ] 1. VNINDEX regime: BULL? (gate for new entries)
[ ] 2. Run scan — note any new Growth/PTS signals
[ ] 3. For each new signal:
        [ ] ADV50 × 10% ≥ target T1 size?
        [ ] Cloud bull AND price > EMA20?
        [ ] GK10 confirmed? (→ 1.25× size)
        [ ] Sleeve = Growth/PTS? (not Watch_only)
        [ ] Record: symbol, date, ep1, T1_size, pb_trigger, str_trigger
[ ] 4. For open positions:
        [ ] PTS state update (PB_WAIT → PB_HIT? STR_WAIT → STR_HIT?)
        [ ] TP1 hit? → log partial exit, activate trail
        [ ] Trail stop breached? → log full exit
        [ ] Hold ≥250 bars? → log forced exit
[ ] 5. Update positions.csv and daily P&L log
```

## Exit Decision Tree

```
Entry at ep1 (T1=50%):
  → Pullback ≥4% within 30 bars AND cloud bullish?
       YES → Add T2=50% at pullback price. Blended entry recalculated.
       NO  → After bar 30: watch for strength add
             → Strength ≥6% AND cloud+EMA bullish within bars 31-40?
                  YES → Add T2=50% at strength price. Blended entry recalculated.
                  NO  → Remain at T1 only (50% position)

Post-add or T1-only exit:
  → Blended entry set. Start exit clock.
  → Close ≥ blended_entry × 1.18?   → Sell 50% (TP1). Activate 2.5×ATR trail on rest.
  → Close < high_water − 2.5×ATR?   → Sell remaining (trail triggered)
  → Hold ≥250 bars?                  → Force-sell everything (max hold)
```
