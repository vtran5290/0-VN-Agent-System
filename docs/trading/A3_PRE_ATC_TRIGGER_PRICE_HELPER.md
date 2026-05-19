# A3 Pre-ATC Trigger Price Helper

**Script:** `scripts/research/a3_pre_atc_trigger.py`  
**Output:** `data/research/cloud_timing/a3_pre_atc_trigger_levels.csv`

---

## Purpose

Before ATC (14:30–15:00 HCM), the operator wants to know:

> "At what close price will the A3 cloud signal trigger today for symbol X?"

This allows the operator to:
1. Watch near-trigger symbols during the session.
2. Decide whether to enter an ATC order if price approaches the trigger level.
3. Prioritize attention before market close.

**This is a monitoring/diagnostic tool, not a live-order system.**  
`auto_order_allowed = False` always.

---

## Trigger Price Derivation

A3 signal conditions at bar T:
1. `close[T] > EMA20[T]`
2. `EMA20[T] > EMA100[T]` (cloud_bull)
3. `cloud_was_bear_recent` (prior ≥3 bars had bear cloud)

Given EMA values at T-1 (known before today's close):
```
EMA_fast[T] = alpha_fast * close[T] + (1 - alpha_fast) * EMA_fast[T-1]
EMA_slow[T] = alpha_slow * close[T] + (1 - alpha_slow) * EMA_slow[T-1]
```
where `alpha = 2 / (n + 1)`, `alpha_fast = 2/21`, `alpha_slow = 2/101`.

**Condition 2 (cloud_bull):**
```
EMA_fast[T] > EMA_slow[T]
(alpha_f - alpha_s) * close > (1-alpha_s)*EMA_slow[T-1] - (1-alpha_f)*EMA_fast[T-1]
close > threshold_cloud_bull
```

**Condition 1 (close > EMA_fast):**
```
close > alpha_f * close + (1-alpha_f) * EMA_fast[T-1]
close * (1 - alpha_f) > (1-alpha_f) * EMA_fast[T-1]
close > EMA_fast[T-1]
```

**Combined trigger price:**
```
a3_trigger_close_price = max(threshold_cloud_bull, EMA_fast[T-1])
```

---

## Output Fields

| Field | Description |
|---|---|
| `symbol` | Ticker |
| `as_of_date` | Date of prior-day EOD (EMA basis) |
| `a3_current_price` | Latest close (kVND) |
| `a3_trigger_close_price` | Minimum close to trigger A3 signal |
| `a3_distance_to_trigger_pct` | `(trigger / current - 1) * 100` |
| `a3_trigger_met_if_close_now` | True if current price already meets trigger |
| `a3_recent_bear_ok` | True if cloud_was_bear condition met |
| `a3_cloud_bull_now` | True if cloud already bull at last close |
| `a3_trigger_reason` | Human-readable explanation |

---

## Usage

```bash
python scripts/research/a3_pre_atc_trigger.py
```

Outputs `a3_pre_atc_trigger_levels.csv` and prints near-trigger candidates (within 5% of trigger).

---

## Integration with Intraday Preview

The intraday scan already computes a provisional signal using the current partial-day close. The pre-ATC trigger helper complements this by:
- Showing symbols that are NOT yet triggering but are close
- Giving the operator a specific price level to watch
- Requiring no code change to the intraday scan itself

**Do not auto-order based on trigger price.**  
Trigger price is informational. Final signal requires full-day close via EOD scan.

---

## Limitations

1. Trigger price assumes today's close is the ONLY input — no intraday OHLC path matters for EMA (EMA uses close only).
2. `cloud_was_bear_recent` is checked using prior-day data only — intraday does not change this condition.
3. If symbol has had recent A3 signals (within 40 bars), a new signal requires a fresh bear-cloud period of ≥3 bars before it would be valid.
4. Pre-ATC trigger is not guaranteed to result in a trade — operator must review regime, breadth, and liquidity gates before deciding.
