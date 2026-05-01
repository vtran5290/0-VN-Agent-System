from __future__ import annotations

"""
signal_feature_log.py

Lightweight feature logger for weekly Pocket Pivot candidate entries.

For each (symbol, week) row in the weekly DataFrame, we can log:
- symbol, entry_date
- regime_ftd, no_new_positions
- basic PP trigger flags (weekly_pp)
- EMA21, MA10, MA50, extension vs MA10 and EMA21
- base length / depth and 3-week tightness (computed on weekly closes)
- adtv20/50 approximated from daily value series if provided
- chosen_flag: whether the engine actually entered a trade on this signal
- reject_reason: optional free-text for why it was not selected

This module is intentionally self-contained and does not import sector/RS
metadata yet; those fields can be added later once a sector/RS source is wired in.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_PP = Path(__file__).resolve().parent


def _compute_base_features(wdf: pd.DataFrame, idx: int, max_lookback_weeks: int = 26) -> tuple[int, float, float]:
    """
    Approximate base_length, base_depth, tightness_3w using weekly closes.

    - base_length: number of weeks in lookback window where close stayed below
      current close and within a 30% band above the rolling min.
    - base_depth: (peak - trough)/peak over lookback window.
    - tightness_3w: (max(high_3w) - min(low_3w))/close.
    """
    if idx == 0:
        return 0, np.nan, np.nan
    lo = max(0, idx - max_lookback_weeks)
    sl = wdf.iloc[lo : idx + 1]
    c = sl["close"].astype(float).values
    h = sl["high"].astype(float).values
    l = sl["low"].astype(float).values
    if len(c) < 3:
        return len(c), np.nan, np.nan
    trough = float(c.min())
    peak = float(c.max())
    base_depth = (peak - trough) / peak if peak > 0 else np.nan

    # Tightness over last 3 weeks
    h3 = h[-3:]
    l3 = l[-3:]
    tightness_3w = (h3.max() - l3.min()) / c[-1] if c[-1] > 0 else np.nan

    base_length = len(c)
    return base_length, base_depth, tightness_3w


def append_weekly_features(
    sym: str,
    wdf: pd.DataFrame,
    feature_rows: list[dict],
    chosen_dates: Optional[set[str]] = None,
    regime_cols: tuple[str, str] = ("regime_ftd", "no_new_positions"),
) -> None:
    """
    For a symbol's weekly DataFrame, append one feature row per week.

    chosen_dates: set of ISO date strings where a position was entered
                  (to flag chosen_flag). This can be wired later when
                  integrating with the portfolio engine.
    """
    chosen_dates = chosen_dates or set()
    c = wdf["close"].astype(float).values
    h = wdf["high"].astype(float).values
    l = wdf["low"].astype(float).values
    ma10 = pd.Series(c).rolling(10, min_periods=1).mean().values
    ema21 = pd.Series(c).ewm(span=21, adjust=False, min_periods=1).mean().values
    ma50 = pd.Series(c).rolling(50, min_periods=1).mean().values

    dates = pd.to_datetime(wdf["date"]).dt.strftime("%Y-%m-%d").tolist()
    weekly_pp = wdf.get("weekly_pp", pd.Series(False, index=wdf.index)).astype(bool).values
    reg_ftd = wdf.get(regime_cols[0], pd.Series(False, index=wdf.index)).astype(bool).values
    no_new = wdf.get(regime_cols[1], pd.Series(False, index=wdf.index)).astype(bool).values

    for i, dt in enumerate(dates):
        base_length, base_depth, tight3 = _compute_base_features(wdf, i)
        close = c[i]
        ext_10w = (close - ma10[i]) / ma10[i] if ma10[i] else np.nan
        ext_ema21 = (close - ema21[i]) / ema21[i] if ema21[i] else np.nan

        feature_rows.append(
            {
                "symbol": sym,
                "entry_date": dt,
                "exchange": None,  # to be filled from metadata later
                "sector": None,  # to be filled from metadata later
                "regime_ftd": bool(reg_ftd[i]),
                "no_new_positions": bool(no_new[i]),
                "weekly_pp": bool(weekly_pp[i]),
                "close": float(close),
                "ma10": float(ma10[i]),
                "ema21": float(ema21[i]),
                "ma50": float(ma50[i]),
                "ext_vs_ma10": float(ext_10w) if np.isfinite(ext_10w) else np.nan,
                "ext_vs_ema21": float(ext_ema21) if np.isfinite(ext_ema21) else np.nan,
                "base_length_weeks": int(base_length),
                "base_depth_pct": float(base_depth) if np.isfinite(base_depth) else np.nan,
                "tightness_3w_pct": float(tight3) if np.isfinite(tight3) else np.nan,
                "adtv20": None,  # placeholder, can be joined from monthly_universe later
                "adtv50": None,
                "rs_score": None,
                "rs_rank": None,
                "chosen_flag": dt in chosen_dates,
                "reject_reason": None,
                "realized_ret": None,
            }
        )


def write_feature_log(feature_rows: list[dict], label: str = "ema21_pp") -> Path:
    if not feature_rows:
        return _PP / f"feature_log_{label}_empty.csv"
    df = pd.DataFrame(feature_rows)
    out_path = _PP / f"feature_log_{label}.csv"
    df.to_csv(out_path, index=False)
    return out_path


