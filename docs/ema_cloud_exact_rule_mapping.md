# EMA Cloud + Price Level — Exact Rule Mapping (AFL → Python)

**Status**: No AFL source files found in repo. Python rules are derived from the strategy specification provided, with implementation decisions documented below.

**Research baseline:** Vingroup / return-distortion / VNINDEX caveats for this pipeline → `docs/research/VIN_EMA_CLOUD_BASELINE.md`.

---

## How to Read This Document

Each row maps one logical rule from the AFL specification to the corresponding Python implementation in `scripts/research/ema_cloud_level_research.py`. For each rule:
- **AFL intent**: what the AFL/specification calls for
- **Python implementation**: the exact code or function
- **Status**: `exact`, `approximated`, or `assumption documented`
- **Notes**: any deviation or clarification

---

## A. EMA Cloud

| # | AFL Intent | Python Function / Code | Status | Notes |
|---|-----------|----------------------|--------|-------|
| A1 | `FastEMA = EMA(Close, fastPeriod)` | `df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()` | exact | `adjust=False` matches AFL's recursive EMA formula |
| A2 | `SlowEMA = EMA(Close, slowPeriod)` | `df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()` | exact | same |
| A3 | Bull cloud: `FastEMA > SlowEMA` | `df["bull_cloud"] = df["ema_fast"] > df["ema_slow"]` | exact | |
| A4 | Bear cloud: `FastEMA < SlowEMA` | `~df["bull_cloud"]` | exact | not used as signal gate — only bull_cloud required |
| A5 | Price above cloud: `Close > FastEMA AND Close > SlowEMA` | `df["above_cloud"] = df["close"] > df[["ema_fast","ema_slow"]].max(axis=1)` | exact | equivalent to Close > both EMAs |

### EMA seed value
AFL EMA starts from the first bar's close. pandas `ewm(adjust=False)` also initializes from the first observation. The warm-up period behavior is equivalent.

---

## B. Price Levels

| # | AFL Intent | Python Function / Code | Status | Notes |
|---|-----------|----------------------|--------|-------|
| B1 | Resistance from repeated highs | `cluster_prices(lh_prices, pct_diff, min_matches)` | exact | |
| B2 | Support from repeated lows | `cluster_prices(ll_prices, pct_diff, min_matches)` | exact | |
| B3 | Group nearby prices using % tolerance | `if (p - group[0]) / group[0] * 100 <= pct_diff` in `cluster_prices()` | exact | greedy ascending merge: compare each price to the group's first (lowest) member |
| B4 | Require minimum match count | `if len(g) >= min_matches` in `cluster_prices()` | exact | |
| B5 | Remove levels too close to one another | `thin_levels(levels, min_dist_pct)` | exact | keeps lower of each too-close pair |
| B6 | Nearest active resistance = closest resistance above current price | `res_above = sorted([l for l in res_levels if l > close])[0]` | exact | |
| B7 | Nearest active support = closest support below current price | `sup_below = sorted([l for l in sup_levels if l < close], reverse=True)[0]` | exact | |
| B8 | Local high definition | `high[i] > high[i-1] AND high[i] > high[i+1]` | exact | strict 1-bar adjacency, vectorized in `precompute_local_extrema()` |
| B9 | Lookback window | `bars [max(0, t - max_candles), t-1)` | exact | upper bound t-1 ensures no leakage from bar t's data |

### AFL grouping algorithm approximation
AFL typically scans from highest to lowest price and merges within a band. The Python implementation sorts ascending and merges upward. The result is equivalent for symmetric tolerance (the same prices will group together either way), but the AFL implementation might anchor the group to the highest vs. the Python anchoring to the lowest. **This could produce slightly different mean level prices** when groups span a wide range. The difference is at most `pct_diff` percent (e.g., ≤ 0.86% by default). This is a known, minor approximation.

---

## C. Breakout

| # | AFL Intent | Python Code | Status | Notes |
|---|-----------|------------|--------|-------|
| C1 | Signal when price breaks above **previous bar's** nearest active resistance | `prev_res = all_res[t-1]` then `close[t] > prev_res * (1 + close_buffer/100)` | exact | `all_res[t-1]` = resistance from data through bar t-2 |
| C2 | Require close above that level by configurable buffer | `close[t] > prev_res * (1.0 + sp.close_buffer / 100.0)` | exact | |
| C3 | Require bullish EMA cloud | `bull_cloud[t] == True` | exact | |
| C4 | Require close above cloud | `above_cloud[t] == True` | exact | |
| C5 | Optional volume confirmation | `volume[t] >= vol_ma20[t] * vol_mult_breakout` | exact | default enabled (vol_mult=1.2×) |

---

## D. Retest

| # | AFL Intent | Python Code | Status | Notes |
|---|-----------|------------|--------|-------|
| D1 | After breakout, price returns near the breakout level | State machine: `state["type"] == "post_breakout"` and `0 < t - state["bar"] <= retest_window` | exact | |
| D2 | Allow small undercut tolerance | `low[t] >= breakout_level * (1.0 - undercut_tolerance / 100.0)` | exact | |
| D3 | Close must hold back above breakout level | `close[t] >= breakout_level * (1.0 - undercut_tolerance / 100.0)` | exact | uses same threshold; close must not be below undercut |
| D4 | Prefer price staying above fast EMA | `close[t] > ema_fast[t]` | exact | hard requirement (not optional) |
| D5 | Bullish cloud required | `bull_cloud[t] == True` | exact | |
| D6 | Low must reach near the level | `low[t] <= breakout_level * (1.0 + touch_tolerance / 100.0)` | exact | ensures the pullback actually touched the level zone |
| D7 | Optional lighter-volume retest | `volume[t] <= vol_ma20[t] * retest_vol_max` | exact | default enabled |

### Retest vs. continuation distinction
If price never touches the level (low stays well above it), no retest signal fires even if the stock continues upward. The `touch_tolerance` gate enforces that the pullback must actually reach the level zone.

---

## E. Reclaim

| # | AFL Intent | Python Code | Status | Notes |
|---|-----------|------------|--------|-------|
| E1 | After breakout, price loses the breakout level | `close[t] < breakout_level` → switch to `state["type"] = "post_loss"` | exact | |
| E2 | Then regains it with strong close above level and above cloud | `close[t] > L * (1.0 + close_buffer/100)` AND `bull_cloud[t]` AND `above_cloud[t]` | exact | uses same close_buffer as breakout |
| E3 | Within reclaim_lookback bars of the level loss | `0 < t - state["loss_bar"] <= reclaim_lookback` | exact | |
| E4 | Optional volume confirmation | `volume[t] >= vol_ma20[t] * vol_mult_breakout` | exact | same breakout volume gate |

---

## F. Sell / Failure Side

| # | AFL Intent | Python Implementation | Status | Notes |
|---|-----------|----------------------|--------|-------|
| F1 | Breakdown below key support | Tracked via `mae_Xd` and `trade_success_Xd` metrics | approximated | Not modeled as an intra-trade exit — captured as MAE (max adverse excursion) |
| F2 | Failed retest | If after retest signal, MAE shows -8%+ drawdown, trade_success = 0 | approximated | Intra-trade failure reflected in forward return distribution |
| F3 | Failure exit after bullish setup breaks | trade_success = hit +15% before -8%; captures failure side implicitly | approximated | Full exit-rule state machine not implemented in research harness |

**Note on failure side**: The research harness uses fixed holding periods and the trade_success metric to proxy failure exits. A full live system should add explicit failure exits (e.g., close below support for 2+ bars, close below ema_slow). The research intentionally holds fixed to measure the signal quality independent of exit rules.

---

## G. Recent-Base-Only Mode (Extension to AFL Spec)

This mode has no direct AFL counterpart in the existing code — it is a research extension to test whether anchor-aware levels outperform broad lookback.

| # | Logic | Python Code | Notes |
|---|-------|------------|-------|
| G1 | Find lowest low in recent_base_window bars | `np.argmin(low[t-recent_base_window:t])` | strictly uses bars before t |
| G2 | Anchor scan start to base_low + min_bars_after_base | `window_start = base_low_abs + min_bars_after_base` | avoids using the base itself as a "level" |
| G3 | Combined with max_candles upper bound | `window_start = max(max_candles_start, recent_base_start)` | most restrictive start wins |

---

## H. Volume MA

| # | AFL Intent | Python Code | Status |
|---|-----------|------------|--------|
| H1 | Volume MA20 | `df["vol_ma20"] = df["volume"].rolling(20, min_periods=10).mean()` | exact |
| H2 | Volume ratio at signal bar | `vol_ratio = volume[t] / vol_ma[t]` | exact |

---

## I. Walk-Forward OOS (Research Extension)

No AFL equivalent — this is a research validation framework added to test parameter robustness.

- Expanding window from 2023-01-01
- Monthly test folds
- Param selection on train data only (no future information)
- Implementation: `run_walk_forward_oos()` in research script

---

## J. Parameter Cross-Reference (AFL name → Python key)

| AFL Conceptual Name | Python `ResearchParams` path | CLI flag (if any) |
|--------------------|-----------------------------|--------------------|
| FastPeriod | `ema.fast` | — |
| SlowPeriod | `ema.slow` | — |
| MaxCandles | `level.max_candles` | — |
| UseRecentBase | `level.use_recent_base` | — |
| RecentBaseWindow | `level.recent_base_window` | — |
| MinBarsAfterBase | `level.min_bars_after_base` | — |
| PctDiff | `level.pct_diff` | — |
| NumMatches | `level.min_matches` | — |
| MinDistBetweenLevels | `level.min_dist_pct` | — |
| NumLevels | `level.n_levels` | — |
| CloseBuffer | `signal.close_buffer` | — |
| RetestWindow | `signal.retest_window` | — |
| ReclaimLookback | `signal.reclaim_lookback` | — |
| TouchTolerance | `signal.touch_tolerance` | — |
| UndercutTolerance | `signal.undercut_tolerance` | — |
| VolMultiplierBBO | `signal.vol_mult_breakout` | — |
| RetestVolMax | `signal.retest_vol_max` | — |
| ADV50MinBn | `signal.adv50_min_bn` | `--adv-filter` |

---

## K. Known Approximations Summary

| Item | Approximation | Impact |
|------|---------------|--------|
| Level grouping anchor | Python anchors to lowest price in group; AFL may anchor differently | Minor: ≤ pct_diff% difference in level price |
| Entry timing | Research uses next-bar open; AFL would typically use a buy-stop order | Minor: open is a reasonable proxy for stop-entry fill |
| Local high definition | Strict 1-bar adjacency only; AFL may use wider neighborhood or ATR-based filters | Possibly more extrema than AFL; test with min_matches gate |
| Sell side | Not modeled as explicit exit rule; captured via trade_success metric only | Results are "signal quality" not "strategy P&L" |
| T+2.5 settlement | Not modeled | Not relevant for research signal quality; critical for live sizing |
| Single state machine | Only one active setup per symbol | May undercount signals in strong trending markets |
