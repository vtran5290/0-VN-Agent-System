# S3 Production Readiness Requirements

Date: 2026-05-17
Status: SPEC ONLY — pending paper-trade gate

---

## 1. S3 Final Candidate Definition

- Strategy: EMA21/55 cloud signal (S3)
- Universe: full (ex-VIN3 preferred for production; full universe for research)
- Max hold: 60 bars (3 trading months) — LOCKED
- TP1: 18% (sell 50% of position)
- Trail: 3.5×ATR14 after TP1
- Regime gate: VNINDEX EMA20 > EMA100 (same as A3 hard block)
- ADV filter: top 100 by ADV50 (or ≥ 20B VND floor)
- Cost assumption: 0.4% base, must survive 0.6% stress

## 2. Entry Rules

1. S3 cloud signal fires (EMA21 crosses above EMA55)
2. Next-bar entry at market open close price
3. Check VNINDEX regime gate (EMA20 > EMA100)
4. Check ADV cap: max 10% of ADV50 per position
5. Check max slots: 20 positions
6. T1 = 50% of slot allocation

## 3. Exit Rules

| Condition | Action |
|-----------|--------|
| Close ≥ ep1 × 1.18 (TP1) | Sell 50% of position |
| Trail stop: close < peak − 3.5×ATR14 | Exit remaining |
| Bars held ≥ 60 (LOCKED) | Force exit remaining |
| Bars held < 5 (T+3 lock) | No sells |

## 4. Regime Filters

- VNINDEX EMA20 > EMA100 = hard gate (same as A3)
- If bear: no new S3 entries, monitor existing positions only
- Breadth < 40% = advisory caution (not a hard S3 block)

## 5. Liquidity Filters

- ADV50 participation cap: 10% of ADV50 per entry
- Minimum ADV50: 20B VND (or top 100 symbols by ADV)
- Exclude symbols with < 150 bars of data

## 6. Max Capital

- S3 paper shadow: max 20 slots × allocated capital
- Real capital: NOT APPROVED — pending 3-month paper trade
- If used as sleeve: max 20% of total portfolio capital

## 7. Position Sizing

- Slot size = portfolio_VND / max_slots = 5B / 20 = 250M VND per slot
- T1 = 50% of slot = 125M VND
- ADV cap: min(slot_size, 10% × ADV50)
- GK5 confirmation: optional 1.25× size multiplier (paper only)

## 8. OMS final_action Enums

| final_action | Description |
|-------------|-------------|
| NEW_S3_SHADOW | New S3 paper entry — paper ledger only |
| S3_SHADOW_HOLD | Existing S3 shadow position, no action |
| S3_SHADOW_EXIT | Exit S3 shadow position — paper ledger update |
| SKIP_VNINDEX_BEAR | Regime gate blocked this S3 signal |
| SKIP_LIQUIDITY | ADV cap too low |

## 9. Paper Ledger Schema

Files: `data/trading/live/s3_shadow_paper_trades.csv` and `s3_shadow_positions.csv`

Required columns: symbol, entry_date, entry_price, exit_date, exit_price, hold_bars,
gross_return, net_return, exit_reason, s3_shadow_max_hold_remaining, s3_shadow_paper_pnl_pct

## 10. Live-Order Containment

- S3 strategy_classification = "S3_PAPER_SHADOW" in scan output
- Order router guard: if strategy_classification in S3_PAPER_SHADOW → PAPER_S3_SHADOW_INTENT_ONLY
- No DNSE route for any S3 order
- No A3 contamination: separate P&L files

## 11. Kill-Switch Requirements

- max_hold=60 is hard-coded, not a parameter
- Any s3_shadow_bars_since ≥ 60 must exit immediately
- VNINDEX bear → no new S3 entries (already enforced by regime gate)

## 12. Required Paper-Trade Period

| Gate | Minimum |
|------|---------|
| Duration | 3 months |
| S3 paper decisions | ≥ 30 |
| S3 exits | ≥ 10 |
| Ledger reconciliation | Clean — no scan/ledger mismatches |
| Drawdown | Within ±5% of expected band |
| Live-order check | Zero S3 orders reaching DNSE |

## 13. Promotion Criteria

S3 can only be promoted to real capital if ALL of the following pass:
1. Paper-trade gate above completed
2. MAR reproduced in live paper ≥ 0.30
3. No execution issues (ADV capping, slippage)
4. A3 performance not degraded during S3 paper period
5. Manual review by operator before any real-capital allocation

**DO NOT PROMOTE TO REAL CAPITAL WITHOUT COMPLETING PAPER GATE.**
