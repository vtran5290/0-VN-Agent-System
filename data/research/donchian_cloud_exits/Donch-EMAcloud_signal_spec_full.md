# Donchian + EMA Cloud — Complete Buy/Sell Signal Specification

**Market:** Vietnam equity (HOSE/HNX)  
**Purpose:** Full implementation reference — entry logic, exit logic, filters, production recommendations  
**Research basis:** 272 symbols, 2023–2024 train, 2025+ OOS, 80 exit variants tested  

---

## 1. Universe & Data Requirements

- **Symbols:** All liquid HOSE/HNX stocks
- **Excluded forever:** `VPL` (structural distortion — exclude until 252 bars of history exist)
- **Excluded from entry:** Symbols with 50-day avg daily trading value < 2.0 billion VND
- **Sensitive symbols:** `VIC`, `VHM`, `VRE` — cap-weight distort VNINDEX; track results with/without
- **OHLCV columns needed:** `date`, `open`, `high`, `low`, `close`, `value` (VND turnover)
- **Minimum history before signalling:** `max(EMA_SLOW + 10, DON_LOOKBACK + 1)` = 61 bars

---

## 2. Indicator Definitions

All indicators are **causal** — computed on data available at close of bar `t`, no lookahead.

### EMA (Exponential Moving Average)
```python
# ewm(adjust=False) — each value depends only on prior values
alpha = 2.0 / (span + 1)
ema[0] = close[0]
ema[i] = alpha * close[i] + (1 - alpha) * ema[i-1]
```
- `EMA10` = span 10
- `EMA20` = span 20  (used in exits only)
- `EMA50` = span 50

### ADV50 (50-day average daily value)
```python
adv50[i] = mean(value[i-49 : i+1]) / 1e9   # result in billions VND
# NaN for bars 0–48
```

### ATR14 (Average True Range, 14-bar EWM)
```python
tr[0] = high[0] - low[0]
tr[i] = max(high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i]  - close[i-1]))
atr14 = ewm(tr, span=14)   # same causal EWM formula as above
```

### Donchian High (20-bar)
```python
don_high[t] = max(high[t-20 : t])   # excludes current bar t
# This is the highest high of the PRIOR 20 bars, not including today
```

---

## 3. Buy Signal (Entry)

### Three conditions — ALL must be true on signal bar `t`

```python
# Condition 1: EMA Cloud is bullish
bull_cloud = ema10[t] > ema50[t]

# Condition 2: Price is above both EMAs
above_cloud = close[t] > max(ema10[t], ema50[t])

# Condition 3: Donchian 20-bar breakout with 0.3% buffer
donchian_break = close[t] > max(high[t-20 : t]) * 1.003

# Liquidity filter (NOT a signal condition — it's a pre-filter)
liquid = adv50[t] >= 2.0   # billion VND; skip symbol entirely if False

# Full signal
signal[t] = bull_cloud AND above_cloud AND donchian_break AND liquid
```

### Entry execution
```
entry_price = open[t+1]   # next bar's open, NOT the signal bar's close
```

### What this means in plain English
- Stock must be in an uptrend: faster EMA (10) above slower EMA (50)
- Stock must be trading above both EMAs — i.e. "above the cloud"
- Stock must close above the highest high of the prior 20 bars by at least 0.3%
- Volume/liquidity check: must trade ≥ 2bn VND avg daily over 50 days
- You BUY at the open the next morning after signal

### Why 0.3% buffer
The buffer (`* 1.003`) prevents signals on marginal closes that are effectively at the 20-bar high. Without it, too many signals are noise around flat resistance.

### Critical implementation notes
- `don_high = max(high[t-20 : t])` — the slice is **exclusive of bar t** (prior 20 bars only)
- Do NOT use `close[t]` to compute the Donchian high — use `high`
- EMA is strictly causal: `ewm(adjust=False)` in pandas, or the loop implementation above
- `above_cloud` uses `max(ema10, ema50)` — price must be above whichever EMA is higher
- Warmup: skip first 61 bars of each symbol's history before emitting any signals

---

## 4. Signal Quality (from OOS research, 2025+)

| Metric | Value |
|--------|-------|
| Success rate (reach +15% before -8%) | **39.0%** [37.2%, 40.8%] |
| Win rate (close at 63d > entry) | 49.5% |
| Mean 63d return | +5.5% |
| Median 63d return | -0.1% |
| Signals per year (full universe) | ~2,800 |

**Benchmark comparison:** Level-breakout model (same universe) = 23.5% success, -2.0% mean_ret. Donchian is decisively better (non-overlapping CIs).

**Key insight:** The success distribution is right-skewed — a minority of trades produce large gains. Mean > median means winners are larger than losers. Do NOT cut winners early.

---

## 5. Sell Signal (Exit) — Research Findings

### 5.1 Benchmark: Fixed 63-day exit

```
exit_bar = entry_bar + 63
exit_price = close[exit_bar]   # or open[exit_bar + 1] for next-day open
```

OOS results (2025): Calmar 0.34, max_dd -15.1%, CAGR 5.2%, win 47.4%

---

### 5.2 RECOMMENDED PRIMARY EXIT: Regime Filter (I_50_sn)

**Rule:** Do not open new positions when VNINDEX is trading below its 50-day EMA. Positions already open ride to fixed 63d exit unchanged.

```python
# Compute daily on VNINDEX index itself (not individual stocks)
vn_ema50[t] = ewm(vnindex_close, span=50)[t]   # causal EWM

# Gate — checked on signal bar t BEFORE entering
regime_ok = vnindex_close[t] > vn_ema50[t]

# Only take new signals when regime is OK
if signal[t] AND regime_ok:
    enter at open[t+1]
```

**Do NOT force-close open positions** when regime turns bad. `stop_new` mode only.

OOS results (2025): **Calmar 2.51**, max_dd -5.3%, CAGR 13.3%, win 50.0%, 50 trades

This is 7× better Calmar than fixed 63d baseline. The regime filter simply stops you from entering in bear market conditions — existing positions ride to 63d.

---

### 5.3 RECOMMENDED SECONDARY EXIT: Chandelier ATR Trailing Stop (E_chan3.0_act10)

Use this when VNINDEX regime data is unavailable, or as an additional exit for open positions.

```python
# Parameters: k=3.0, activation_threshold=10% gain
k = 3.0
activate_at = 0.10   # only activate stop after +10% gain from entry

# Per-bar tracking
highest_close = max(close[entry_bar : t+1])   # highest close since entry

# Compute stop level
if current_return >= activate_at:
    chandelier_stop = highest_close - k * atr14[t]
    if close[t] < chandelier_stop:
        exit at open[t+1]
```

OOS results (2025): Calmar 1.58, max_dd -6.8%, CAGR 10.7%, 37 trades

**Critical:** The `activate_at=10%` threshold is mandatory. Without activation, the trailing stop fires too early on normal pullbacks (Chandelier 3.0x no-activation = Calmar 0.28 only).

---

### 5.4 HIGH-VOLUME ALTERNATIVE: Gil Morales EMA10 (D_ema10_cc_h10)

Best choice if you want more trades (141 vs 50). Trade-off: higher max_dd.

```python
# Parameters: ma=EMA10, mode=close_vs_close, min_hold=10 bars
gm_min_hold = 10       # don't check exit in first 10 bars after entry
gm_viol_bar = None     # state: bar of first violation
gm_viol_close = None   # state: close on violation bar

# Per-bar check (only after hold > gm_min_hold)
ema10_val = ema10[t]
if gm_viol_bar is None:
    # Looking for first violation
    if close[t] < ema10_val:
        gm_viol_bar = t
        gm_viol_close = close[t]
else:
    # Violation bar recorded — look for confirmation OR reclaim
    if close[t] > ema10_val:
        # Price reclaimed EMA — reset, violation cancelled
        gm_viol_bar = None
        gm_viol_close = None
    elif t > gm_viol_bar:
        # Confirmation: second close below EMA10 that is LOWER than violation close
        if close[t] < gm_viol_close:
            exit at open[t+1]   # next morning open
```

OOS results (2025): Calmar 1.31, max_dd -10.8%, CAGR 14.1%, win 41.8%, 141 trades

**Two-bar rule:** violation bar ≠ exit bar. Need 2 consecutive closes below EMA10 (second close lower than first). Reset on any close back above EMA10.

---

### 5.5 PARTIAL EXIT: 50% at +15%, remainder on Chandelier (F_tp15_chan)

Best win rate (69.5%). Use when you want to lock in profits while letting remainder ride.

```python
# Parameters: tp1=15%, frac1=50%, remainder=chandelier_3.5x
partial1_done = False

# Per-bar check (intraday — uses high[t], executed at tp1_price)
tp1_px = entry_px * 1.15
if not partial1_done and high[t] >= tp1_px:
    sell 50% of position at tp1_px   # intraday fill
    partial1_done = True

# Remaining 50% — chandelier 3.5x (no activation threshold)
if partial1_done:
    highest_close = max(close[entry_bar : t+1])
    chan_stop = highest_close - 3.5 * atr14[t]
    if close[t] < chan_stop:
        sell remaining 50% at open[t+1]

# Fallback: fixed max hold 126 days on remainder
if hold >= 126:
    sell all remaining at open[t+1]
```

OOS results (2025): Calmar 1.05, max_dd -11.2%, CAGR 11.7%, win 69.5%, 82 trades

---

## 6. What Does NOT Work — Critical Findings

### Hard stops (families B, J_H1, J_H2)
**Do not use tight initial stops on this universe.**

```
B4: Stop -8%  → Calmar -0.27, max_dd -27.2%
B5: Stop -10% → Calmar -0.20, max_dd -34.8%
B6: Stop -12% → Calmar -0.14, max_dd -22.3%
```

VN stocks frequently dip through -8% to -12% before recovering and trending. Hard initial stops destroy value. The right-tail winners that make this system work are cut before they develop.

### Breakout failure exits (family C)
**Do not sell in the first 10–20 bars on pullbacks.**

```
CC7: BF n=10 lvl=0.97 → Calmar -0.23
CC8: BF n=10 lvl=0.95 → Calmar -0.30
C15_95: BF n=15 lvl=0.95 → Calmar -0.31
C20_95: BF n=20 lvl=0.95 → Calmar -0.32
```

Selling when price pulls back to 97%/95%/93% of breakout level in the first N bars is the single worst family tested. These exits fire on almost every trade (VN breakouts oscillate) and eliminate all winners.

### Dynamic exits without activation (E_chan3.0_act0)
Chandelier without activation threshold = Calmar 0.28 (worse than fixed 63d).

---

## 7. Portfolio Construction

```
max_positions = 10                    # concurrent open positions
position_sizing = equal_weight        # 1/max_pos per trade
one_position_per_symbol = True        # no pyramiding
transaction_cost = 0.15% per side     # realistic for retail VN
```

### Signal ranking (when > max_positions signals on same day)
Priority order:
1. `don_strength` = (close / don_high_20bar) - 1  (how far above 20-bar high)
2. `vol_ratio` = today's value / 20-day avg value
3. `RS20` = (close[t] / close[t-20]) / (vnindex[t] / vnindex[t-20])  (relative strength)

Take top N by composite score.

---

## 8. Complete Production System (Primary Recommendation)

### Entry
```
signal_t = (ema10[t] > ema50[t])                          # bull cloud
        AND (close[t] > max(ema10[t], ema50[t]))          # above cloud
        AND (close[t] > max(high[t-20:t]) * 1.003)        # donchian break
        AND (adv50[t] >= 2.0)                              # liquidity
        AND (vnindex_close[t] > vnindex_ema50[t])          # regime OK

entry_price = open[t+1]
```

### Exit
```
exit_price = open[t+1] where t is the first bar where:
  1. hold >= 63 bars → fixed time exit
  (no hard stop, no chandelier on first-generation system)
```

For more sophisticated exits, layer on Chandelier 3.0× with +10% activation AFTER establishing the regime-filtered baseline.

### Expected OOS performance (2025 data)
```
Calmar:     2.51
max_dd:    -5.3%
CAGR:      13.3%
win_rate:  50.0%
n_trades:  ~50/year (regime filter reduces from ~2,800 signals to ~50 portfolio slots)
```

---

## 9. Signal Generation Code (Minimal, Self-Contained)

```python
import numpy as np
import pandas as pd

EMA_FAST, EMA_SLOW = 10, 50
DON_LB = 20
ADV50_MIN = 2.0     # billion VND
BUFFER = 0.003      # 0.3%

def ewm_causal(arr, span):
    """Causal EWM — no lookahead, matches pandas ewm(adjust=False)."""
    alpha = 2.0 / (span + 1)
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            continue
        prev = out[i-1] if i > 0 else np.nan
        out[i] = arr[i] if np.isnan(prev) else alpha * arr[i] + (1-alpha) * prev
    return out

def adv50(value_arr):
    out = np.full(len(value_arr), np.nan)
    for i in range(49, len(value_arr)):
        out[i] = np.mean(value_arr[i-49:i+1]) / 1e9
    return out

def donchian_signals(df, vnindex_close=None, vnindex_dates=None):
    """
    df: DataFrame with columns [date, open, high, low, close, value]
    Returns list of signal dicts: {signal_date, entry_price, symbol}
    """
    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].values.astype(float)
    high  = df["high"].values.astype(float)
    open_ = df["open"].values.astype(float)
    value = df["value"].values.astype(float)
    dates = pd.to_datetime(df["date"].values)
    n     = len(df)

    ema10  = ewm_causal(close, EMA_FAST)
    ema50  = ewm_causal(close, EMA_SLOW)
    adv    = adv50(value)
    warmup = max(EMA_SLOW + 10, DON_LB + 1)

    # Regime: VNINDEX close vs EMA50 (optional)
    vn_regime = {}
    if vnindex_close is not None and vnindex_dates is not None:
        vn_ema50 = ewm_causal(vnindex_close, 50)
        for i, d in enumerate(vnindex_dates):
            vn_regime[pd.Timestamp(d)] = bool(vnindex_close[i] > vn_ema50[i])

    signals = []
    for t in range(warmup, n - 1):
        # Liquidity filter
        if not np.isnan(adv[t]) and adv[t] < ADV50_MIN:
            continue
        # EMA cloud
        if not (ema10[t] > ema50[t]):
            continue
        if not (close[t] > max(ema10[t], ema50[t])):
            continue
        # Donchian breakout
        don_high = float(np.max(high[t - DON_LB : t]))   # PRIOR bars, exclude t
        if close[t] <= don_high * (1 + BUFFER):
            continue
        # Regime gate (skip if VNINDEX below EMA50)
        if vn_regime and not vn_regime.get(dates[t], True):
            continue
        # Signal fires
        signals.append({
            "signal_date":  dates[t],
            "entry_price":  float(open_[t + 1]),   # next open
            "don_strength": float(close[t] / don_high - 1.0),
        })
    return signals
```

---

## 10. Common Mistakes to Avoid

| Mistake | Correct |
|---------|---------|
| `close[t] > max(high[t-20:t+1])` (includes today) | `close[t] > max(high[t-20:t])` (excludes today) |
| `ewm(adjust=True)` | `ewm(adjust=False)` — causal only |
| Enter at signal bar close | Enter at NEXT bar open |
| Hard stop -8% on entry | No initial stop (research shows it destroys returns) |
| Chandelier trailing from bar 1 | Chandelier only activates after +10% gain |
| Force-close positions when regime turns bad | Only block NEW entries; let open positions ride |
| `adv50 = mean(value[-50:])` in pandas rolling | Use causal loop or `.rolling(50).mean()` — both OK, check alignment |
| Donchian on close prices | Donchian uses `high` prices, breakout vs `close` |

---

## 11. File Reference

```
scripts/research/ema_cloud_donchian_oos.py      ← clean signal generation (220 lines)
scripts/research/ema_cloud_exit_research.py     ← full exit simulation framework (1400 lines)
scripts/research/ema_cloud_step8_levers.py      ← L0–L4 lever tests
data/research/donchian_cloud_exits/
  exit_strategy_summary.csv                    ← 80 exits × IS/OOS, all metrics
  exit_trade_ledger.csv                        ← 18,082 trades
  exit_research_summary.md                     ← executive summary
data/research/ema_cloud/
  donchian_signals_full.csv                    ← full signal log
  step8_levers.md                              ← lever research results
  donchian_vs_level_oos.md                     ← Donchian vs level model comparison
```
