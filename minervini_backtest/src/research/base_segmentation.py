"""
Base segmentation with stable base_id and PP rung counted within segment.

State machine (per symbol, per parameter set affecting transitions):
- Enter base when rolling geometry candidate turns true after inactive.
- While in base:
  - Invalidate if close < rolling_base_low * (1 - invalidation_buffer).
  - Exit on confirmed breakout: close > pivot*(1+entry_buffer) AND volume rule.
  - If candidate false for > grace_bars consecutive bars, exit base.
- pp_rung_in_base increments on each pocket-pivot day inside the segment (1st PP = 1, ...).

Assumptions (audit):
- Rolling base_high/base_low/pivot use the same window as geometry filters (base_days).
- Invalidation uses the same rolling base_low at i (not segment-local extrema).
- Breakout confirmation uses pivot[i] and volume at i; base ends same bar; no look-ahead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from research.event_study_features import anti_drift_ok, breakout_volume_ok, pp_bucket_accepts


@dataclass
class EventConfig:
    base_days: int
    min_base_depth: float
    max_base_depth: float
    min_base_pos: float
    max_dist_pivot: float
    anti_drift_mode: int
    pp_bucket: str
    entry_buffer: float
    breakout_vol_family: str
    breakout_vol_mult: float
    grace_bars: int = 3
    invalidation_buffer: float = 0.025
    breakout_lookforward_cap: int = 60


def collect_pp_and_breakout_events(
    *,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    open_: np.ndarray,
    vol: np.ndarray,
    vol_sma20: np.ndarray,
    vol_sma50: np.ndarray,
    vol_pct_rank: np.ndarray,
    pp: np.ndarray,
    candidate: np.ndarray,
    base_high: np.ndarray,
    base_low: np.ndarray,
    pivot: np.ndarray,
    ma20: np.ndarray,
    ma50: np.ndarray,
    adv20: np.ndarray,
    min_adv20: float,
    trend_ok: np.ndarray,
    cfg: EventConfig,
    dates: np.ndarray,
    symbol: str,
    start_i: int,
    end_i: int,
    param_set_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Walk forward [start_i, end_i) and emit PP / breakout event dicts.
    Arrays must be aligned numpy (float/bool).
    """
    pp_events: list[dict[str, Any]] = []
    br_events: list[dict[str, Any]] = []

    in_base = False
    grace = 0
    base_id = 0
    base_start_i = 0
    pp_rung = 0
    last_pp_in_base: int | None = None

    n = len(close)
    fam = cfg.breakout_vol_family.lower()
    use_pct = fam == "pct50"

    for i in range(max(start_i, 0), min(end_i, n)):
        # State machine advances every bar (no look-ahead). Liquidity/trend gates apply at emission only.
        if not in_base:
            if candidate[i]:
                in_base = True
                base_id += 1
                base_start_i = i
                pp_rung = 0
                last_pp_in_base = None
                grace = 0
            else:
                continue

        # in_base (includes the bar where we just transitioned)
        bl = base_low[i]
        if np.isfinite(bl) and bl > 0 and close[i] < bl * (1.0 - cfg.invalidation_buffer):
            in_base = False
            grace = 0
            continue

        piv = pivot[i]
        vol_ok = breakout_volume_ok(
            cfg.breakout_vol_family,
            i,
            vol,
            vol_sma20,
            vol_sma50,
            cfg.breakout_vol_mult,
            vol_pct_rank if use_pct else None,
        )
        if np.isfinite(piv) and piv > 0 and vol_ok and close[i] > piv * (1.0 + cfg.entry_buffer):
            if i + 1 < n and np.isfinite(adv20[i]) and adv20[i] >= min_adv20 and bool(trend_ok[i]):
                br_events.append(
                    {
                        "kind": "breakout",
                        "symbol": symbol,
                        "param_set_id": param_set_id,
                        "base_id": base_id,
                        "base_start_i": base_start_i,
                        "signal_i": i,
                        "signal_date": pd.Timestamp(dates[i]),
                        "entry_i": i + 1,
                        "pivot": float(piv),
                        "base_high_roll": float(base_high[i]) if np.isfinite(base_high[i]) else np.nan,
                        "base_low_roll": float(bl) if np.isfinite(bl) else np.nan,
                        "pp_rung_in_base": pp_rung,
                        "days_in_base": i - base_start_i,
                    }
                )
            in_base = False
            grace = 0
            continue

        if not candidate[i]:
            grace += 1
            if grace > cfg.grace_bars:
                in_base = False
                grace = 0
                continue
        else:
            grace = 0

        if pp[i]:
            pp_rung += 1
            rung = pp_rung
            if last_pp_in_base is None:
                days_since_last_pp = i - base_start_i
            else:
                days_since_last_pp = i - last_pp_in_base
            last_pp_in_base = i
            if not pp_bucket_accepts(cfg.pp_bucket, rung):
                continue
            if not anti_drift_ok(cfg.anti_drift_mode, i, close, ma20, ma50):
                continue
            if i + 1 >= n:
                continue
            if not (np.isfinite(adv20[i]) and adv20[i] >= min_adv20 and bool(trend_ok[i])):
                continue
            pp_events.append(
                {
                    "kind": "pp",
                    "symbol": symbol,
                    "param_set_id": param_set_id,
                    "base_id": base_id,
                    "base_start_i": base_start_i,
                    "signal_i": i,
                    "signal_date": pd.Timestamp(dates[i]),
                    "entry_i": i + 1,
                    "pp_rung_in_base": rung,
                    "pp_in_base_count": rung,
                    "days_since_last_pp": int(days_since_last_pp),
                    "pivot": float(pivot[i]) if np.isfinite(pivot[i]) else np.nan,
                    "base_high_roll": float(base_high[i]) if np.isfinite(base_high[i]) else np.nan,
                    "base_low_roll": float(base_low[i]) if np.isfinite(base_low[i]) else np.nan,
                }
            )

    return pp_events, br_events
