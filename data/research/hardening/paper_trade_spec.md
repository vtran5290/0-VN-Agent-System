# Paper Trade Specification — B_cloud20_100_partial
## VN Equities Cloud Strategy — Production Candidate

**Version:** 1.0
**Date:** 2026-05-13
**Status:** Ready for paper trading. Small live deployment requires drawdown resolution first.

---

## 1. Exact Entry Rule

**Signal fires when all conditions are true at bar T (signal fires for T+1 entry):**

1. `close[T] > ema_fast[T]`  where ema_fast = EMA(close, span=20)
2. `cloud_bull[T]`  where cloud_bull = (ema_fast > ema_slow) = EMA(20) > EMA(100)
3. Cloud was bearish for at least 3 bars before turning: `ema_fast < ema_slow` for ≥ 3 bars in prior window
4. Past warmup period (first max(105, 60) bars per symbol excluded)

**Entry execution:** Enter at close of bar T+1 (day after signal).
In live/paper trading: use next-day open as entry price (conservative) or T+1 close if intraday monitoring is available. Use T+1 open for more realistic fills.

---

## 2. Exact Exit Rule

**Exit mode: partial_tp**

- **First lot (50%):** Exit when `close >= entry_price * 1.15` (+15% target). Record this return as `tp_ret`.
- **Remaining lot (50%):** Trail with stop at `high_water - 2.5 * ATR(14)`. Exit when close breaches the trailing stop.
- **Blended net return:** `0.5 * tp_ret + 0.5 * trailing_return - cost`
- **Max hold:** 250 trading days. Force-exit both lots if neither condition fires within 250 bars.
- **Cost assumption:** 40 bps round-trip. If actual execution cost exceeds 100 bps, strategy still delivers ~9.6% CAGR (see cost sensitivity results).

---

## 3. Universe Rule

**Base universe:** 272 liquid VN equities (ADV50 >= 2B VND as of last screening).

**Apply:**
- Exclude VPL until 252 bars of trading history
- Exclude any symbol with < 100 bars of data
- Rescreen universe quarterly for ADV compliance

---

## 4. Exclusion Rule — VIN Treatment

**Exclude: VIC, VHM, VRE (ex-VIN3)**

Rationale:
- VIC alone reduces maxDD from -43.4% to -33.9% (full→ex_vic delta)
- Adding VHM, VRE further reduces maxDD to -30.1% and improves Sharpe (1.094→1.136)
- Primary strategy (20/100) is not meaningfully hurt by VIN3 exclusion (-0.4pp CAGR)
- VIN names carry restructuring/event risk independent of EMA cloud behavior

If VHM/VRE are later confirmed free of structural distortion, test ex_vic only (see vin_sensitivity_results.csv for the delta: maxDD improves +3.8pp vs ex_vin3).

---

## 5. Ranking Rule (Fill Selection)

**When multiple entry signals fire on the same day and available slots < pending signals:**

Rank by **EMA distance at entry**, descending:
```
ema_dist = (entry_price - EMA_100[entry_day]) / EMA_100[entry_day]
```
Take the highest ema_dist signals first until slots fill.

Rationale: ema_dist ranked fill improves CAGR from 10.7% (FIFO) to 12.3% and Sharpe from 1.136 to 1.202 with no additional signal complexity.

**Tie-break:** If ema_dist scores are within 0.5pp of each other, prefer higher liquidity (higher volume on entry day).

---

## 6. Max Positions

**Maximum simultaneous open positions: 20**

Equal weight: each position = 5% of portfolio.

Sensitivity tested:
- max_pos=10: Sharpe=0.810, maxDD=-36.4% — materially worse
- max_pos=15: Sharpe=1.026, maxDD=-30.2% — acceptable fallback if capital is small
- max_pos=20: Sharpe=1.136, maxDD=-30.1% — production setting

Do not run fewer than 15 positions. Concentration risk at 10 positions is unacceptable.

---

## 7. Rebalance / Execution Timing

**Frequency:** Daily monitoring, end-of-day execution.

**Signal generation:** Run after market close each day on updated OHLCV.
**Entry:** Next morning open (or T+1 close if system can submit end-of-day orders).
**Exit:** Same — compute exit trigger on T close, execute at T+1 open.

**Rebalance:** No forced rebalance. Positions exit naturally via partial_tp or max_hold. Equal weight applies only to new entries; existing positions are not resized.

---

## 8. Risk Limits

| Limit | Value | Rationale |
|---|---|---|
| Max single-name allocation | 5% (1/20 portfolio) | Equal weight enforced at entry |
| Max simultaneous open positions | 20 | Portfolio parameter |
| Max hold per position | 250 trading days | Hard cap to prevent indefinite holds |
| Portfolio stop-loss (monitoring) | -35% drawdown from NAV peak | Above the -30.1% historical maxDD |
| Single-name stop-loss | None systematic | Exit rules handle this |
| Leverage | 1x (no leverage) | Research conducted on unleveraged basis |
| Minimum position size | 5% (implicit) | Do not run with < 5% positions |

**Drawdown note:** The strategy is currently IN a ~30% drawdown from its 2022 NAV peak (per subperiod analysis). Portfolio-level CAGR for 2023-2026 is -2.3%, despite individual trade OOS returns being +6.3% avg with 67.9% hit rate. Starting paper trade now means entering at the drawdown trough, not at the peak. This is factual context, not a disqualifier.

---

## 9. Reporting Metrics (Weekly)

Track and report:
- Portfolio NAV (starting base = 1.0)
- Daily P&L and rolling drawdown from peak
- Open positions: symbol, entry date, entry price, current EMA distance, partial_tp status
- Trades closed this week: symbol, entry/exit dates, gross/net return, hold_bars
- Signal count: new entries fired this week, how many filled vs skipped (capacity)
- EMA distance at entry for new positions (confirm ranking is working)
- Running CAGR, Sharpe (rolling 52-week), current maxDD

**Monthly comparison:** OOS avg_trade_ret vs backtest baseline (6.3% / 67.9% hit rate).

---

## 10. Daily Monitoring Checklist

**Morning (before open):**
- [ ] Price data updated for all universe symbols
- [ ] EMA(20) and EMA(100) recalculated
- [ ] Cloud status (bull/bear) and bars-in-state computed
- [ ] New entry signals identified: list of (symbol, ema_dist_at_entry)
- [ ] Capacity check: how many slots are open?
- [ ] Rank new signals by ema_dist, fill available slots

**End of day:**
- [ ] Check exit triggers for all open positions:
  - Partial TP hit? (close >= entry * 1.15)
  - Trailing stop breached? (close < high_water - 2.5 * ATR14)
  - Max hold reached? (hold_bars = 250)
- [ ] Log any positions that closed today (net_return, hold_bars)
- [ ] Update portfolio NAV
- [ ] Flag if portfolio drawdown > 25% from peak (early warning threshold)

---

## 11. Signal Generation Script (Production)

```python
# Pseudocode for daily signal generation
def daily_scan(panel: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    """
    Run at end of day on updated panel.
    Returns signals_df: columns = [symbol, ema_dist, signal_date]
    """
    signals = []
    for sym in universe:
        sdf = panel[panel["symbol"] == sym].copy()
        cloud = ema_cloud(sdf["close"], fast=20, slow=100)
        fast, slow, bull = cloud["ema_fast"], cloud["ema_slow"], cloud["cloud_bull"]
        sig = cloud_only_entry(sdf["close"], fast, bull, min_bars_bear=3, warmup=105)
        if sig.iloc[-1]:   # signal fires today
            ema_dist = (sdf["close"].iloc[-1] - slow.iloc[-1]) / slow.iloc[-1]
            signals.append({"symbol": sym, "ema_dist": ema_dist,
                            "entry_price_tomorrow": sdf["close"].iloc[-1]})
    return pd.DataFrame(signals).sort_values("ema_dist", ascending=False)
```

The live version of this scan is in `pp_backtest/ema_portfolio_sim.py` → `sim_symbol()` + `compute_all_trades()`.

---

## Key Parameters Summary

```yaml
strategy:
  name: B_cloud20_100_partial
  entry_type: cloud_only
  ema_fast: 20
  ema_slow: 100
  exit_mode: partial_tp
  tp_pct: 0.15
  trail_atr_mult: 2.5
  atr_period: 14
  max_hold_bars: 250
  min_bars_bear: 3
  warmup_bars: 105

portfolio:
  max_positions: 20
  position_weight: 0.05      # 5% equal weight
  fill_mode: ema_dist        # ranked by EMA distance at entry
  cost_bps: 40               # assumed round-trip; robust to 100 bps

universe:
  base: vn_liquid_272
  exclude_permanent: [VPL]
  exclude_vin: [VIC, VHM, VRE]
  min_history_bars: 100

benchmarks:
  backtest_cagr_exvin3: 0.107       # FIFO fill; production fill should reach ~12.3%
  backtest_sharpe_exvin3: 1.136     # FIFO; production fill ~1.20
  backtest_maxdd: -0.301
  oos_avg_trade_ret: 0.063          # 2023+ period
  oos_hit_rate: 0.679
```
