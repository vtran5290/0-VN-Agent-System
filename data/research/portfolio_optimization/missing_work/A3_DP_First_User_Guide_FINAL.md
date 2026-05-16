# A3 DP-First — User Guide

Version: FINAL | Date: 2026-05-16 | Classification: PRODUCTION_CANDIDATE

---

## What This Strategy Does

EMA20/100 cloud breakout strategy with dual-path pullback-only entry.  
When price breaks above both EMA20 and EMA100 (cloud turns bull), buy T1 immediately.  
Wait for a ≥4% pullback within 30 bars to add T2. If pullback never comes, hold T1 only.

---

## Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| EMA Fast | 20 | Short-term trend |
| EMA Slow | 100 | Long-term trend |
| Cloud breakout | EMA20 > EMA100 + price above both | Entry condition |
| Min bars bear | 3 | Require ≥3 bars in bear cloud before signal is valid |
| T1 fraction | 50% of slot | First entry tranche |
| T2 fraction | 50% of slot | Add tranche on pullback |
| Pullback depth | ≥4% below ep1 | T2 trigger |
| Pullback window | 30 bars | T2 window |
| TP1 | +18% | Sell T1 tranche |
| Trail multiplier | 2.5× ATR14 | Trailing stop from peak |
| Max hold | 250 bars | Hard exit |
| Min sell lock | 5 bars | T+3 settlement |
| Max slots | 20 concurrent | Portfolio capacity |
| ADV participation | 10% (reference) | Liquidity cap |
| GK10 mult | 1.25× optional | Garman-Klass size boost |

---

## Entry Rules

1. Cloud turns bullish (EMA20 crosses above EMA100)
2. Price is above both EMAs at entry bar
3. At least 3 consecutive bear bars before the breakout
4. VNINDEX is in bull regime (EMA20 > EMA100 on index)
5. breadth_t1_permission = True (only VNINDEX bear hard-blocks T1; breadth is advisory)
6. recommendation = full_T1 or partial_T1 (liquidity check)

**Position size:**
```
slot_VND      = portfolio_VND / max_slots × gk_mult
T1_VND        = slot_VND × 0.50
effective_T1  = min(T1_VND, adv50_VND × participation_rate)
```

---

## T2 Add Rules

After T1 entry, monitor 30 bars:
- If close drops ≥4% below ep1 → add T2 = 50% of slot (capped by ADV)
- If 30 bars expire with no pullback → no T2, hold T1 only
- Do not add T2 when breadth < 40% (breadth_t2_permission = False in caution/defense)

---

## Exit Rules

| Condition | Action |
|-----------|--------|
| Price ≥ ep1 × 1.18 (TP1) | Sell T1 tranche (50% of position) |
| Close < (peak − 2.5×ATR14) | Exit remaining position |
| Held 250 bars | Exit remaining position |
| Within 5 bars of entry | No sells (T+3 lock) |

---

## Liquidity Rule (Corrected, Phase 3.1)

```python
adv50_VND      = panel["value"].rolling(50).mean()          # preferred
                 or (close_kVND × volume_shares × 1000).rolling(50).mean()
effective_T1   = min(T1_target_VND, adv50_VND × participation_rate)
```

**Never use `close × volume` without `× 1000` — that's a 1000× understatement.**  
See Phase 3.1 audit: `phase31/PHASE31_LIQUIDITY_AUDIT.md`

---

## AFL Usage

Open `Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` in AmiBroker.

Parameters panel:
- **EMA Fast / EMA Slow**: 20/100 (do not change for production)
- **PTS Shadow ON**: 0 = DP default (recommended), 1 = PTS shadow mode
- **Portfolio B VND**: set to your actual portfolio size in billion VND
- **ADV Participation**: 10% default; lower = more conservative
- **Max Slots**: 20 default

Chart shows:
- Blue cloud = A3 bull regime
- Red cloud = A3 bear regime
- Green up arrows = entry signals
- Red down arrows = exit signals
- Blue circles = pullback hit (T2 trigger)
- Dashed red = trailing stop
- Dashed green = TP1 level
- Yellow star = GK10 present at entry

Title shows: ADV50, T1 target, max T1 (10% ADV), fill ratio, liquidity warning.

---

## What PTS Shadow Mode Does

When `PTS Shadow ON = 1`:
- After T1 entry, if no pullback in 30 bars:
- Watch 10 more bars for strength add (price ≥ ep1+6%, cloud + EMA bullish)
- Adds T2 on strength signal
- Orange squares mark strength-add events

Default is OFF. PTS mode is PAPER_TRADE_SHADOW classification (no real capital without paper validation).

---

## Performance Reference

| Portfolio | Participation | MAR | CAGR | MaxDD |
|-----------|--------------|-----|------|-------|
| 1B VND | 10% | ~0.38 | ~5.2% | ~-13.5% |
| 3B VND | 10% | ~0.41 | ~5.6% | ~-13.8% |
| 5B VND | 10% | 0.416 | 5.81% | -13.99% |
| 10B VND | 10% | ~0.39 | ~5.4% | ~-13.8% |

Source: Phase 3.1 corrected-liquidity analysis, 2012–2026 backtest.

---

## Key Decisions Made

| Question | Answer |
|----------|--------|
| DP or PTS as default? | DP — PTS MAR dropped to 0.343 after corrected liquidity |
| Breadth gate hard block? | NO — hard gate hurts MAR. Use as T2-soft block only. |
| S3 paper trade? | NO — MAR=0.190, RESEARCH_ONLY |
| Sector cap as trade filter? | NO — hurts MAR, use as dashboard warning |
| Performance throttle? | NO — doesn't improve MAR, rejected |
| GK10 overlay? | OPTIONAL — adds CAGR but increases MaxDD slightly |
