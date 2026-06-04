"""Detect correction-leg anchor date from VNINDEX OHLCV."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class CorrectionAnchor:
    anchor_date: str
    anchor_close: float
    end_date: str
    end_close: float
    drawdown_pct: float
    lookback_bars: int
    detection_method: str


def detect_correction_anchor(
    vni: pd.DataFrame,
    *,
    as_of: Optional[str] = None,
    lookback: int = 60,
    min_drawdown_pct: float = 1.0,
    min_bars_after_peak: int = 3,
) -> CorrectionAnchor:
    """
    Anchor = most recent local peak (max close in lookback) before end, when
    drawdown from peak to as-of end >= min_drawdown_pct.
    """
    df = vni.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date")
    if as_of:
        df = df[df["date"] <= pd.Timestamp(as_of)]
    if df.empty:
        raise ValueError("VNINDEX series empty for anchor detection")

    end_row = df.iloc[-1]
    sub = df.tail(lookback)
    if len(sub) < min_bars_after_peak + 2:
        raise ValueError(f"insufficient VNINDEX history (need >= {min_bars_after_peak + 2} bars)")

    peak_idx = sub["close"].idxmax()
    peak_pos = sub.index.get_loc(peak_idx)
    if peak_pos >= len(sub) - min_bars_after_peak:
        sub_peak = sub.iloc[:-min_bars_after_peak]
        if sub_peak.empty:
            peak_row = sub.loc[peak_idx]
        else:
            peak_idx = sub_peak["close"].idxmax()
            peak_row = sub.loc[peak_idx]
    else:
        peak_row = sub.loc[peak_idx]

    peak_close = float(peak_row["close"])
    end_close = float(end_row["close"])
    dd_pct = (end_close / peak_close - 1.0) * 100.0 if peak_close > 0 else 0.0
    method = "peak_in_lookback"
    if dd_pct > -min_drawdown_pct:
        fallback = sub.iloc[-(min_bars_after_peak + 5)]
        peak_row = fallback
        peak_close = float(peak_row["close"])
        dd_pct = (end_close / peak_close - 1.0) * 100.0
        method = "fallback_fixed_offset"

    return CorrectionAnchor(
        anchor_date=pd.Timestamp(peak_row["date"]).strftime("%Y-%m-%d"),
        anchor_close=peak_close,
        end_date=pd.Timestamp(end_row["date"]).strftime("%Y-%m-%d"),
        end_close=end_close,
        drawdown_pct=round(dd_pct, 2),
        lookback_bars=len(sub),
        detection_method=method,
    )
