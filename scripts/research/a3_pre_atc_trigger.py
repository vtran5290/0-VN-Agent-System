"""
A3 Pre-ATC Trigger Price Helper.

For each symbol, computes the minimum close price that would trigger an A3 signal
on the current bar, given prior EMA20/EMA100 and the recent-bear-cloud condition.

A3 signal conditions:
  1. close > EMA20_today
  2. EMA20_today > EMA100_today (cloud_bull)
  3. cloud_was_bear_recent (prior min_bars_bear bars must have been bear)
  4. (from entry.py): signal = close > EMA_fast AND cloud_bull AND cloud_was_bear

EMA_fast_today = alpha * close_today + (1 - alpha) * EMA_fast_prev
  where alpha = 2 / (n + 1)

For cloud_bull: EMA_fast_today > EMA_slow_today
  alpha_fast * close + (1-alpha_fast)*EMA_fast_prev > alpha_slow * close + (1-alpha_slow)*EMA_slow_prev
  (alpha_fast - alpha_slow) * close > (1-alpha_slow)*EMA_slow_prev - (1-alpha_fast)*EMA_fast_prev
  close > [ (1-alpha_slow)*EMA_slow_prev - (1-alpha_fast)*EMA_fast_prev ] / (alpha_fast - alpha_slow)

For close > EMA_fast_today:
  close > alpha_fast * close + (1-alpha_fast)*EMA_fast_prev
  close * (1 - alpha_fast) > (1-alpha_fast)*EMA_fast_prev
  close > EMA_fast_prev

Trigger price = max(cloud_bull_threshold, EMA_fast_prev) when cloud_was_bear = True.

Output:
  data/research/cloud_timing/a3_pre_atc_trigger_levels.csv
"""
from __future__ import annotations

from pathlib import Path
import sys

_REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO))

import numpy as np
import pandas as pd

from pp_backtest.portfolio_optimization_final_steps import ema_cloud
from src.trading.intraday.panel_overlay import EOD_PANEL_DEFAULT, load_eod_panel

OUT = _REPO / "data" / "research" / "cloud_timing"
DOC = _REPO / "docs" / "trading" / "A3_PRE_ATC_TRIGGER_PRICE_HELPER.md"

_N_FAST = 20
_N_SLOW = 100
_MIN_BARS_BEAR = 3
_ALPHA_FAST = 2 / (_N_FAST + 1)
_ALPHA_SLOW = 2 / (_N_SLOW + 1)


def compute_trigger_price(ema_fast_prev: float, ema_slow_prev: float) -> float | None:
    """Minimum close price that makes EMA_fast_today > EMA_slow_today AND close > EMA_fast_today."""
    denom = _ALPHA_FAST - _ALPHA_SLOW
    if abs(denom) < 1e-10:
        return None
    cloud_bull_threshold = ((1 - _ALPHA_SLOW) * ema_slow_prev - (1 - _ALPHA_FAST) * ema_fast_prev) / denom
    close_above_fast_threshold = ema_fast_prev
    return max(cloud_bull_threshold, close_above_fast_threshold)


def run_pre_atc_trigger(symbols: list[str] | None = None) -> pd.DataFrame:
    panel = load_eod_panel(EOD_PANEL_DEFAULT)
    if panel.empty:
        print("EOD panel not found or empty")
        return pd.DataFrame()

    panel["date"] = pd.to_datetime(panel["date"])
    syms = symbols or sorted(panel["symbol"].unique())
    rows = []

    for sym in syms:
        sdf = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue

        c = sdf["close"].astype(float)
        a3 = ema_cloud(c, _N_FAST, _N_SLOW)
        ema_f = a3["ema_fast"]
        ema_s = a3["ema_slow"]
        cloud_b = a3["cloud_bull"]

        # cloud_was_bear: check last _MIN_BARS_BEAR bars before today were bear
        cloud_was_bear_recent = bool((~cloud_b).iloc[-_MIN_BARS_BEAR:].any())

        # If cloud is ALREADY bull today, signal might already have fired
        cloud_bull_now = bool(cloud_b.iloc[-1])
        cur_close = float(c.iloc[-1])
        cur_fast = float(ema_f.iloc[-1])
        cur_slow = float(ema_s.iloc[-1])

        # Prior-bar EMA values (for EMA update formula)
        ema_fast_prev = float(ema_f.iloc[-2]) if len(ema_f) >= 2 else cur_fast
        ema_slow_prev = float(ema_s.iloc[-2]) if len(ema_s) >= 2 else cur_slow

        trigger = compute_trigger_price(ema_fast_prev, ema_slow_prev)
        distance_pct = round((trigger / cur_close - 1) * 100, 2) if trigger and cur_close else None
        trigger_met = bool(cur_close >= trigger) if trigger else None

        # Determine trigger reason
        if not cloud_was_bear_recent:
            reason = "cloud_was_bear_condition_not_met"
        elif cloud_bull_now and cur_close > cur_fast:
            reason = "already_signaled_or_in_signal_zone"
        elif trigger is not None:
            reason = f"need_close>={round(trigger, 3)} for cloud_bull AND close>EMA20"
        else:
            reason = "undetermined"

        rows.append({
            "symbol": sym,
            "as_of_date": sdf["date"].iloc[-1].date(),
            "a3_current_price": round(cur_close, 3),
            "a3_trigger_close_price": round(trigger, 3) if trigger else None,
            "a3_distance_to_trigger_pct": distance_pct,
            "a3_trigger_met_if_close_now": trigger_met,
            "a3_recent_bear_ok": cloud_was_bear_recent,
            "a3_cloud_bull_now": cloud_bull_now,
            "ema20_prev": round(ema_fast_prev, 3),
            "ema100_prev": round(ema_slow_prev, 3),
            "a3_trigger_reason": reason,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "a3_pre_atc_trigger_levels.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df)} symbols)")

    near = df[(df["a3_recent_bear_ok"]) & df["a3_distance_to_trigger_pct"].notna()]
    near = near[near["a3_distance_to_trigger_pct"].abs() < 5].sort_values("a3_distance_to_trigger_pct")
    if not near.empty:
        print(f"\nNear-trigger candidates (<5% from trigger):")
        print(near[["symbol", "a3_current_price", "a3_trigger_close_price", "a3_distance_to_trigger_pct"]].to_string(index=False))

    return df


if __name__ == "__main__":
    run_pre_atc_trigger()
