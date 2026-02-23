# Setup Quality Score (0–100)
# Weights: Trend 40%, Tightness 30%, Volume behavior 30%
# Deterministic from OHLCV only; tune later via config if needed.
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Any

# Fixed weights (logged in file)
WEIGHT_TREND = 0.40
WEIGHT_TIGHTNESS = 0.30
WEIGHT_VOLUME = 0.30
WEIGHTS = {"trend": WEIGHT_TREND, "tightness": WEIGHT_TIGHTNESS, "volume": WEIGHT_VOLUME}

# Lookbacks
ATR_PERCENTILE_BARS = 126
UGLY_COUNT_BARS = 10
SLOPE_BARS = 3
# Warm-up: ATR14≥14, MA50+slope≥50+slope_bars, tightness 126 → need ≥126 bars (pre-registered)
WARMUP_BARS = 126
# Ugly bar params (aligned with sell_v4 style)
UGLY_ATR_MULT = 1.20
UGLY_CLOSE_POS = 0.25
HEAVY_VOL_X_MA50 = 1.50
# Low liquidity: below this avg vol (10d) → volume_score forced to 50 (neutral), no ugly-bar penalty
LIQ_THRESHOLD = 200_000  # shares/day; tune later


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def setup_quality(df: pd.DataFrame, bar_index: int | None = None) -> dict[str, Any]:
    """
    Deterministic setup quality from OHLCV. Uses last bar if bar_index is None.
    Requires columns: open, high, low, close, volume.
    Returns: setup_quality_score (0–100), subscores (trend_score, tightness_score, volume_score),
             weights, notes.
    """
    if df.empty or len(df) < WARMUP_BARS:
        return {
            "setup_quality_score": None,
            "subscores": {"trend_score": 0, "tightness_score": 0, "volume_score": 0},
            "weights": WEIGHTS,
            "notes": ["Insufficient bars (warmup)"],
        }
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    df["ma20"] = _sma(c, 20)
    df["ma50"] = _sma(c, 50)
    a14 = _atr(df, 14)
    df["atr14"] = a14
    df["atr_pct"] = (a14 / c).replace(0, np.nan)
    df["vol_ma50"] = _sma(v, 50)
    rng = (h - l).clip(lower=1e-6)
    close_pos = (c - l) / rng
    down_day = c < c.shift(1)
    wide_spread = (h - l) >= UGLY_ATR_MULT * a14
    close_near_low = close_pos <= UGLY_CLOSE_POS
    heavy_vol = v >= df["vol_ma50"] * HEAVY_VOL_X_MA50
    ugly_bar = down_day & wide_spread & close_near_low & heavy_vol
    df["ugly_bar"] = ugly_bar

    i = bar_index if bar_index is not None else len(df) - 1
    i = max(0, min(i, len(df) - 1))
    if i < WARMUP_BARS - 1:
        return {
            "setup_quality_score": None,
            "subscores": {"trend_score": 0, "tightness_score": 0, "volume_score": 0},
            "weights": WEIGHTS,
            "notes": ["Insufficient bars (warmup)"],
        }
    row = df.iloc[i]
    notes = []

    # —— Trend (0–100) ——
    close_i = float(row["close"])
    ma20_i = row["ma20"]
    ma50_i = row["ma50"]
    if pd.isna(ma20_i) or pd.isna(ma50_i):
        trend_score = 30
        notes.append("MA20/MA50 NaN")
    else:
        ma20_i, ma50_i = float(ma20_i), float(ma50_i)
        # MA50 slope (over SLOPE_BARS)
        ma50_slope_ok = False
        if i >= SLOPE_BARS:
            ma50_prev = df.iloc[i - SLOPE_BARS]["ma50"]
            if pd.notna(ma50_prev) and ma50_prev != 0:
                ma50_slope_ok = ma50_i > float(ma50_prev)
        if close_i > ma20_i > ma50_i and ma50_slope_ok:
            trend_score = 100
        elif close_i > ma20_i and ma20_i > ma50_i:
            trend_score = 60
            notes.append("MA50 slope flat")
        elif close_i < ma50_i:
            trend_score = 30
            notes.append("Below MA50")
        else:
            trend_score = 50
            notes.append("Trend mixed")

    # —— Tightness (0–100): ATR% percentile vs last 126 ——
    atr_pct_series = df["atr_pct"].iloc[max(0, i - ATR_PERCENTILE_BARS + 1) : i + 1]
    atr_pct_series = atr_pct_series.dropna()
    if atr_pct_series.empty or pd.isna(row["atr_pct"]):
        tightness_score = 50
        notes.append("ATR% NaN")
    else:
        current_atr_pct = float(row["atr_pct"])
        pct_rank = (atr_pct_series <= current_atr_pct).mean()
        if pct_rank <= 0.30:
            tightness_score = 90
        elif pct_rank <= 0.60:
            tightness_score = 60
        else:
            tightness_score = 30
            notes.append("ATR% high")
    subscores = {"trend_score": trend_score, "tightness_score": tightness_score, "volume_score": 0}

    # —— Volume behavior (0–100): ugly bar count in last 10 ——
    start = max(0, i - UGLY_COUNT_BARS + 1)
    ugly_count_10 = int(df["ugly_bar"].iloc[start : i + 1].sum())
    avg_volume_10d = float(v.iloc[start : i + 1].mean()) if (i - start) >= 0 else 0.0
    if ugly_count_10 == 0:
        volume_score = 80
    elif ugly_count_10 == 1:
        volume_score = 55
    else:
        volume_score = 25
        notes.append("Selling pressure")
    if avg_volume_10d < LIQ_THRESHOLD:
        volume_score = 50
        notes.append("low_liquidity_fallback")
    subscores["volume_score"] = volume_score

    # Weighted composite (0–100)
    composite = (
        trend_score * WEIGHT_TREND
        + tightness_score * WEIGHT_TIGHTNESS
        + volume_score * WEIGHT_VOLUME
    ) / (WEIGHT_TREND + WEIGHT_TIGHTNESS + WEIGHT_VOLUME)
    setup_quality_score = int(round(max(0, min(100, composite))))

    return {
        "setup_quality_score": setup_quality_score,
        "subscores": subscores,
        "weights": WEIGHTS,
        "notes": notes,
    }
