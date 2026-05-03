# EMA Cloud + Price Level Strategy Specification

**Market:** Vietnam equities (HOSE/HNX/UPCoM)
**Horizon:** 90–180 days (quarterly to half-year swing hold)
**Universe:** ADV50 ≥ 2B VND/day (configurable)
**Research script:** `scripts/research/ema_cloud_level_research.py`

**Interpretation / robustness baseline (Vingroup, dual universe, VNINDEX):** `docs/research/VIN_EMA_CLOUD_BASELINE.md` — material conclusions should not rely on a single full-sample cut without checking **ex-VIN** (`--ex-vin`) and **VPL** bar-count policy.

---

## 1. What the Setup Is

A trend-continuation swing entry system that combines:
1. **EMA cloud** to confirm the stock is in a bullish trend regime
2. **Repeat-tested price levels** (resistance and support derived from market structure) to identify high-probability zones
3. **Three entry triggers** — breakout, retest, reclaim — ranked by quality and timing

The core thesis: a stock that is above a rising EMA cloud AND breaks above a price level that has been tested multiple times has demonstrated institutional acceptance of that level. The signal becomes higher-probability when the stock then retests or reclaims that level rather than immediately continuing (lower-quality momentum, higher-quality structure).

---

## 2. EMA Cloud

### What it is
Two exponential moving averages computed on the daily close:
- **Fast EMA**: shorter-period EMA (default: 21-bar)
- **Slow EMA**: longer-period EMA (default: 55-bar)

The "cloud" is the region between the two EMAs.

### Parameters
| Parameter | Default | Tested Range | Meaning |
|-----------|---------|--------------|---------|
| `ema_fast` | 21 | [10, 20, 21] | Faster EMA period |
| `ema_slow` | 55 | [30, 50, 55, 60] | Slower EMA period |

### Conditions derived from the cloud
| Condition | Formula | Meaning |
|-----------|---------|---------|
| `bull_cloud` | `ema_fast > ema_slow` | EMA cloud is bullish (fast above slow) |
| `above_cloud` | `close > max(ema_fast, ema_slow)` | Price is above the cloud entirely |

Both `bull_cloud` AND `above_cloud` must be true for any signal to fire.

### Implementation note (no-leakage)
`pandas.Series.ewm(span=N, adjust=False).mean()` at bar `t` uses only close values from bar 0 through bar `t`. No future data is used. The EMA at bar `t` is fully determined by close[0:t+1].

---

## 3. Price Levels

### What they are
Resistance and support levels derived from repeated price touches in the historical window. These are NOT arbitrary pivot points — they require multiple touches (configurable minimum) to qualify.

- **Resistance levels**: built from local high points
- **Support levels**: built from local low points

A "local high" at bar `i` requires: `high[i] > high[i-1]` AND `high[i] > high[i+1]`.
A "local low" at bar `i` requires: `low[i] < low[i-1]` AND `low[i] < low[i+1]`.

### Parameters
| Parameter | Default | Tested Range | Meaning |
|-----------|---------|--------------|---------|
| `max_candles` | 240 | [80, 120, 180, 240, 480] | How many bars back to scan for levels |
| `use_recent_base` | False | [False, True] | Whether to anchor the scan to the most recent base |
| `recent_base_window` | 120 | [60, 80, 100, 120, 180] | Bars to scan for the lowest low (recent-base mode) |
| `min_bars_after_base` | 20 | [15, 20, 25, 30] | Skip levels too close to the base low itself |
| `pct_diff` | 0.50 | [0.30, 0.50, 0.70, 0.86] | % tolerance to group nearby highs/lows into one level |
| `min_matches` | 4 | [3, 4, 5, 7] | Minimum touches to qualify as a level |
| `min_dist_pct` | 2.0 | [1.5, 2.0, 2.5, 3.2] | Minimum % gap between two adjacent levels |
| `n_levels` | 5 | [3, 4, 5] | Max levels to keep each side of current price |

### Level detection algorithm (step by step)

1. **Define the scan window**: bars from `max(0, t - max_candles)` to `t - 1` (exclusive of bar `t` — strict no-leakage).

2. **Recent-base mode** (if enabled):
   - Find the lowest low in `low[t - recent_base_window : t]`
   - Call this bar `base_low_idx`
   - Restrict scan start to `base_low_idx + min_bars_after_base`
   - This focuses levels on the current base/consolidation, not ancient history

3. **Find local extrema** within the window (pre-computed once per symbol, then filtered by window bounds)

4. **Cluster nearby prices**:
   - Sort local high prices
   - Greedily merge adjacent prices within `pct_diff %` of each group's first member
   - Keep groups with `>= min_matches` members (this is the "must be touched multiple times" gate)
   - Level price = mean of the group

5. **Thin out close levels**: remove levels within `min_dist_pct %` of each other (keep the lower one in each pair)

6. **Select nearest**:
   - `nearest_resistance` = lowest resistance level above current close (within `n_levels` top candidates)
   - `nearest_support` = highest support level below current close

### No-leakage guarantee
All level computation uses only `data[0 : t-1]`. The local high at bar `i` requires knowing bar `i+1`, so local highs can only be confirmed through bar `t-2` at bar `t`'s close. The scan window upper bound is `t-1`, ensuring no bar `t` data enters the levels.

---

## 4. Signal Types

All signals require both `bull_cloud = True` AND `above_cloud = True` at the signal bar.

### A. Breakout

**Definition**: Price closes convincingly above the previous bar's nearest resistance level.

**Logic at bar `t`**:
1. `prev_res` = nearest_resistance computed at bar `t-1` (using data through `t-2`)
2. `prev_res` must exist (there is a qualified resistance level above close[t-1])
3. `close[t] > prev_res × (1 + close_buffer / 100)` — close must clear the level by the buffer
4. `bull_cloud[t]` and `above_cloud[t]`
5. Optional volume: `volume[t] >= vol_ma20[t] × vol_mult_breakout`

**Entry**: `open[t+1]` (next bar's open)

**State after breakout**: Enter "watching for retest or reclaim" state for this level

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `close_buffer` | 0.30% | [0.15, 0.20, 0.30, 0.40] | % above level for breakout close |
| `vol_mult_breakout` | 1.2× | [1.0, 1.2, 1.5] | Minimum volume vs MA20 |

### B. Retest

**Definition**: After a breakout, price pulls back near the breakout level and holds above it.

**Logic at bar `t`** (while in post-breakout state, within `retest_window` bars):
1. `low[t] <= breakout_level × (1 + touch_tolerance / 100)` — low must reach down near the level
2. `low[t] >= breakout_level × (1 - undercut_tolerance / 100)` — but not too far below (shake-out allowed)
3. `close[t] >= breakout_level × (1 - undercut_tolerance / 100)` — close must hold
4. `close[t] > ema_fast[t]` — still above the fast EMA
5. `bull_cloud[t]` — cloud still bullish
6. Optional: `volume[t] <= vol_ma20[t] × retest_vol_max` — lighter volume on pullback preferred

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `retest_window` | 8 | [5, 8, 10, 15] | Max bars after breakout to watch for retest |
| `touch_tolerance` | 0.50% | [0.3, 0.5, 0.6, 0.8] | How close low must get to the level |
| `undercut_tolerance` | 0.80% | [0.5, 0.8, 1.0] | Max % low can go below the level |
| `retest_vol_max` | 1.3× | [1.0, 1.2, 1.3, 1.5] | Max volume vs MA20 on retest bar |

### C. Reclaim

**Definition**: After a breakout, price loses the breakout level (closes below it), then re-establishes above it with a strong close and volume.

**Logic**:
1. After breakout at bar `t_break`: watch for price to close below `breakout_level`
2. When `close[t_loss] < breakout_level`: enter "post_loss" state
3. At bar `t` (within `reclaim_lookback` bars after `t_loss`):
   - `close[t] > breakout_level × (1 + close_buffer / 100)`
   - `bull_cloud[t]` and `above_cloud[t]`
   - Optional volume: `volume[t] >= vol_ma20[t] × vol_mult_breakout`

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `reclaim_lookback` | 8 | [5, 8, 10, 15] | Max bars after level-loss to watch for reclaim |

### Signal quality hierarchy
Quality ranking (highest to lowest): **Reclaim > Retest > Breakout**

Reasoning:
- **Reclaim**: structure has been tested and rejected, then re-accepted. This is the clearest institutional commitment.
- **Retest**: breakout confirmed, pullback absorbed at the level. Clean structure.
- **Breakout**: momentum entry. Depends heavily on whether the level is genuine.

### State machine rules
- Only one active setup state per symbol at a time
- A new breakout resets any existing state
- State expires after the relevant window (retest_window or reclaim_lookback) elapses without a matching signal

---

## 5. Recent-Base-Only Mode

### What it means
Instead of scanning all highs/lows in the past `max_candles` bars, restrict the level scan to the current "base" — defined by the most recent significant low.

**Algorithm**:
1. Find the lowest close/low in the last `recent_base_window` bars
2. This is the "base low" — the start of the current consolidation or accumulation
3. Scan for levels only in the `min_bars_after_base` to `t-1` range starting from the base

### Why it matters
Broad-lookback levels may include ancient support/resistance that is no longer relevant to the current consolidation. Recent-base levels reflect the current structure the stock is building from.

### When recent-base wins
Expected to improve signal quality when:
- The stock has had a clear consolidation after a pullback
- The base is recent (< 6 months)
- The breakout is from a well-defined flat or ascending base

### When broad wins
Expected to perform better when:
- The consolidation is long-duration
- Historical S/R from 6-18 months ago is still relevant (major structural levels)
- Few local extrema exist in the recent base (thin recent structure)

---

## 6. Sell / Failure Side

The research tracks failures but does not implement full sell logic. The following exits are tracked:
- **Fixed holding period**: position held for the full horizon (63d, 126d, 90cal, 180cal) regardless
- **Trade success metric**: whether `+15% was hit before -8%` within the horizon

For live trading, consider these failure exits:
- Close below nearest support level
- Close below ema_fast for 2+ consecutive bars
- Failed retest: after retest signal, close goes below level by > undercut_tolerance

---

## 7. Leakage Prevention Summary

| Data element | How leakage is prevented |
|---|---|
| EMA at bar t | ewm() uses only close[0:t] — pandas default |
| Local high at bar i | Requires high[i+1]; only confirmed through bar t-2 at bar t's close |
| Price levels at bar t | Scan window upper bound = t-1 (exclusive) |
| `prev_res` for breakout | Uses levels computed at bar t-1 (data through t-2) |
| Entry price | open[t+1] — strictly future relative to signal bar t |
| Forward returns | Computed from entry_price = open[t+1] forward |
| Walk-forward OOS | Param selection on train months only; evaluation on test month only |

---

## 8. Walk-Forward OOS Design

- **Type**: Expanding window
- **Train start**: 2023-01-01
- **Train end**: rolls forward monthly
- **Test**: next calendar month after train end
- **Embargo**: 1 month between train and test
- **Param selection**: pick the param combo with the highest `0.6 × success_rate_63d + 0.2 × win_rate_63d + 0.2 × mean_ret_63d` on the train slice (min 30 trades required)
- **Evaluation**: apply the selected combo to the test slice, record all forward return statistics

---

## 9. Primary Decision Criterion

**Rank setups by:**
1. OOS success rate at 63d horizon (`hit +15% before -8%`) — primary
2. OOS success rate at 126d horizon — secondary
3. Median return, mean return — tertiary
4. Sample size (prefer ≥ 30 trades in the test window)
5. Stability across adjacent parameter values — prefer combos that appear in multiple OOS folds

**Prefer:**
- Simpler logic over complex
- Recent-base mode IF it shows ≥ 2 percentage points improvement in OOS success rate
- Higher sample count when success rates are within 3 percentage points

---

## 10. Known Approximations and Caveats

1. **No tick data**: OHLCV is end-of-day; intraday behavior within a bar is unknown.
2. **No T+2.5 settlement**: VN market has T+2.5 settlement; position sizing and re-entry timing must account for this in live trading.
3. **No slippage model**: Entry is at open price; slippage on illiquid names could be significant.
4. **Price scale**: All data is in thousands of VND (FireAnt API). Percentage calculations are scale-invariant.
5. **ADV50 computed from available data**: For stocks with < 50 bars of history, ADV50 uses `min_periods=25`.
6. **Local extrema definition**: Strict 1-bar adjacency (no minimum distance requirement between extrema). This may generate more extrema in volatile or choppy periods.
7. **Single active state**: Only one breakout/retest/reclaim state tracked per symbol. Back-to-back breakouts reset the state; this may under-count signals in strong trending periods.
