# C06 Paper Trade Operating Plan

Generated: 2026-05-04
OOS validation status: CONDITIONAL — review before starting

---

## 1. System Definition

| Parameter | Value |
|-----------|-------|
| Entry signal | GK_FAST (Len=100, Mult=2.0, ATR=14, Confirm=2) BUY flip |
| Volume filter | VolExp = today's value / ADV50 >= 1.2 |
| Liquidity gate | Lagged ADV50 >= VND 2B/day |
| Primary exit | GK_FAST SELL flip |
| Time stop | After 20 bars: if trade return <= 0%, exit next open |
| Regime sizing | VNINDEX close >= EMA50: full-size; below: half-size |
| Ranking | Descending ADV50 (most liquid first) |
| Max positions | 10 |
| Full slot size | Equity / 10 |
| Half slot size | (Equity / 10) x 0.5 |
| Universe | 271 symbols excl. VPL (pre-252 bars) |
| Costs (backtest) | 25 bps fee + 10 bps slippage per side |

---

## 2. Daily Signal Generation

Run after market close each day:

```
1. Fetch today's OHLCV for all 271 symbols
2. Compute GK_FAST signals (need 200+ bars warmup)
3. Compute ADV50_lagged for each symbol (prior 50 sessions trading value, VND)
4. Compute VolExp = today_value / (ADV50_lagged * 1e9)
5. Load VNINDEX close; compute EMA50 of VNINDEX
6. For each symbol with GK_BUY signal today:
   a. Pass ADV50_lagged >= 2.0 bn
   b. Pass VolExp >= 1.2
   c. Add to ENTRY candidates for tomorrow
7. For each open position, check exit conditions:
   a. GK_SELL signal today → exit at tomorrow's open
   b. Bars held >= 20 AND trade return <= 0 → exit at tomorrow's open
8. Determine VNINDEX regime: VNINDEX_close >= VNINDEX_EMA50 → full-size
9. Determine slot size for new entries:
   - Full regime: slot = portfolio_equity / 10
   - Below regime: slot = (portfolio_equity / 10) * 0.5
10. Rank entry candidates by ADV50 descending
    Take top N to fill available slots
```

---

## 3. Entry Execution

- Signal date: today (after close)
- Execution date: next morning open
- Execute at market open (ATC not recommended for VN)
- Log actual fill price vs assumed open
- Record slippage = (actual fill - open) / open

---

## 4. Exit Execution

- GK_SELL exits: execute next morning at market open
- Time stop exits: execute next morning if triggered at prior close
- Do NOT hold through weekends if time stop triggered Friday close
- Log actual fill price; record slippage

---

## 5. Position Sizing

| Condition | Slot size |
|-----------|-----------|
| VNINDEX >= EMA50 | Equity / 10 |
| VNINDEX < EMA50 | (Equity / 10) × 0.5 |

- Do not adjust existing positions when regime changes mid-hold
- Apply regime check at **entry bar only** (not retroactively)

---

## 6. Ranking

When more than (10 - current_positions) new signals appear on the same day:
- Rank by ADV50 descending (most liquid first)
- Take top N to fill available slots
- Ties: random or alphabetical (document which)

---

## 7. Trade Journal Fields

| Field | Notes |
|-------|-------|
| symbol | |
| signal_date | date GK_BUY fired |
| entry_date | next trading day |
| entry_open | AFL open price |
| actual_fill | real execution price |
| entry_slippage_bps | (actual_fill - entry_open) / entry_open * 10000 |
| slot_size_vnd | position value at entry |
| size_factor | 1.0 or 0.5 |
| vnx_regime | ON or OFF at entry |
| volexp_at_entry | today's volexp |
| adv50_at_entry | bn VND/day |
| exit_date | |
| exit_price | actual fill |
| exit_reason | GK_SELL / TSTOP / END |
| hold_bars | calendar bars held |
| gross_ret | exit_px / entry_px - 1 |
| net_ret | after 35 bps round-trip |
| actual_cost_bps | actual brokerage |
| mfe | max favorable excursion |
| mae | max adverse excursion |

---

## 8. Weekly Review Checklist

- [ ] Actual fill prices vs assumed open: compute avg slippage
- [ ] Python signal matches AFL chart for all entries/exits this week
- [ ] No data error in ADV50 or VolExp computation
- [ ] VNINDEX EMA50 regime check consistent with AFL
- [ ] Time stop triggers: verify 20-bar count and return threshold
- [ ] Running drawdown vs backtest expected drawdown
- [ ] Top-1 ticker concentration: has any ticker exceeded 30% of paper PnL?

---

## 9. Kill Criteria

Stop paper trading and escalate to research review if ANY of the following:

| # | Criterion | Action |
|---|-----------|--------|
| K1 | 10 consecutive losing trades, no winner > 5% | Pause, investigate entry quality |
| K2 | Realized slippage > 30 bps per side consistently | Adjust cost model, re-evaluate edge |
| K3 | Missed top winner due to implementation error (signal delay, order error) | Fix pipeline before resuming |
| K4 | Python vs AFL signal mismatch on any live entry | Halt until reconciled |
| K5 | Paper-trade drawdown > 1.5× backtest active MaxDD (-27.3%) = -40.9% | Stop, extend to full research |
| K6 | OOS 6-month MAR < 0.40 | Downgrade to research-only |
| K7 | CA event (split/rights) in top-3 PnL ticker — unverified contamination | Freeze PnL from that ticker |

---

## 10. Manual Override Rules

Ideally: NONE. Paper trading tests system discipline.

Permitted overrides (document every time):
- T+1 settlement constraint prevents entry: skip that signal, log it
- Circuit breaker / trading halt: defer exit to next open, log the delay
- Broker error / system outage: log missed trade as execution error, do not fabricate fill

NOT permitted:
- Override a GK_SELL or time stop because 'it looks like it will recover'
- Size up beyond the slot formula
- Hold beyond time stop because the trade has positive MFE

---

## 11. Transition to Live

Paper trade for minimum 6 months before live consideration.
Live criteria (all required):
- Paper MAR >= 0.50 over the 6-month period
- Paper slippage <= 15 bps per side on average
- Zero signal mismatch incidents
- OOS ex-top3 PnL concentration < 50%
- Walk-forward OOS MAR still > 0.50 (re-run Phase 5 with new data)
