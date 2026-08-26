from __future__ import annotations

"""
CLI helper to run FireAnt-based VN technical analysis for one or more tickers.

Usage (from repo root):
    python -m scripts.vn_ta_fireant_cli VCI HCM MBS ...

Prints a JSON array with one object per ticker following the vn-ta-fireant skill schema.
"""

import json
import math
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from src.canslim.fireant_fetcher import fetch_ohlcv


@dataclass
class TAConfig:
    horizon_days: int = 1260  # ≈5y so monthly SMA50/100 + multi-year pivots are feasible
    vp_bins: int = 100
    value_area_pct: float = 0.7
    risk_mode: str = "standard"


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    cols = ["date", "open", "high", "low", "close", "volume"]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = losses.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def _calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    df["ma20"] = _sma(c, 20)
    df["ma50"] = _sma(c, 50)
    df["ma100"] = _sma(c, 100)
    df["ma200"] = _sma(c, 200)
    df["ma10"] = _sma(c, 10)
    df["ema10"] = _ema(c, 10)
    df["ema20"] = _ema(c, 20)
    df["rsi14"] = _rsi(c, 14)

    atr14 = _atr(df, 14)
    df["atr14"] = atr14

    # OBV
    direction = np.sign(c.diff().fillna(0.0))
    df["obv"] = (direction * v).cumsum()

    # CMF20
    money_flow_multiplier = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    money_flow_volume = money_flow_multiplier * v
    df["cmf20"] = money_flow_volume.rolling(20, min_periods=20).sum() / v.rolling(
        20, min_periods=20
    ).sum()

    # MACD 12,26,9
    ema12 = _ema(c, 12)
    ema26 = _ema(c, 26)
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    hist = macd - signal
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = hist

    # Volume SMAs
    df["vol_sma20"] = _sma(v, 20)
    df["vol_sma50"] = _sma(v, 50)

    # RSI14 (Wilder-style via ewm)
    delta = c.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))

    return df


def _ma_cluster_from_members(
    members: Dict[str, float | None],
    *,
    core_keys: Tuple[str, ...],
    close: float | None,
    slope_bias: str,
) -> Dict[str, Any]:
    """Shared MA compression metrics for weekly/monthly clusters."""
    core_vals = [members[k] for k in core_keys if members.get(k) is not None]
    cluster_width_pct = None
    confluence_label = "none"
    zone_low = zone_high = rep = None
    if len(core_vals) >= 2:
        mx, mn, mean_v = max(core_vals), min(core_vals), float(np.mean(core_vals))
        cluster_width_pct = (mx - mn) / mean_v * 100.0 if mean_v else None
        if cluster_width_pct is not None:
            if cluster_width_pct < 2:
                confluence_label = "exceptional"
            elif cluster_width_pct < 4:
                confluence_label = "strong"
            elif cluster_width_pct < 7:
                confluence_label = "moderate"
            else:
                confluence_label = "weak"
        pad = mean_v * 0.005
        zone_low = mn - pad
        zone_high = mx + pad
        rep = mean_v

    if slope_bias == "down" and confluence_label in ("exceptional", "strong", "very_tight"):
        confluence_label = f"{confluence_label}_declining"

    price_vs_cluster = "unknown"
    if close is not None and zone_low is not None and zone_high is not None:
        if close > zone_high:
            price_vs_cluster = "above"
        elif close < zone_low:
            price_vs_cluster = "below"
        else:
            price_vs_cluster = "inside"

    return {
        "members": members,
        "cluster_width_pct": float(cluster_width_pct) if cluster_width_pct is not None else None,
        "confluence_label": confluence_label,
        "slope_bias": slope_bias,
        "price_vs_cluster": price_vs_cluster,
        "zone_low": float(zone_low) if zone_low is not None else None,
        "zone_high": float(zone_high) if zone_high is not None else None,
        "representative_level": float(rep) if rep is not None else None,
    }


def _weekly_ma_cluster(df_w: pd.DataFrame) -> Dict[str, Any]:
    """Weekly MA compression (SMA20/50/100 core + optional EMA/SMA200)."""
    empty_members = {
        "sma20": None,
        "sma50": None,
        "sma100": None,
        "sma200": None,
        "ema10": None,
        "ema20": None,
    }
    if df_w.empty:
        return _ma_cluster_from_members(empty_members, core_keys=("sma20", "sma50", "sma100"), close=None, slope_bias="flat")

    last = df_w.iloc[-1]
    members = {
        "sma20": float(last["ma20"]) if "ma20" in df_w.columns and not pd.isna(last.get("ma20")) else None,
        "sma50": float(last["ma50"]) if "ma50" in df_w.columns and not pd.isna(last.get("ma50")) else None,
        "sma100": float(last["ma100"]) if "ma100" in df_w.columns and not pd.isna(last.get("ma100")) else None,
        "sma200": float(last["ma200"]) if "ma200" in df_w.columns and not pd.isna(last.get("ma200")) else None,
        "ema10": float(last["ema10"]) if "ema10" in df_w.columns and not pd.isna(last.get("ema10")) else None,
        "ema20": float(last["ema20"]) if "ema20" in df_w.columns and not pd.isna(last.get("ema20")) else None,
    }
    slope_bias = _slope_state(df_w["ma50"]) if "ma50" in df_w.columns else "flat"
    close = float(last["close"])
    return _ma_cluster_from_members(
        members, core_keys=("sma20", "sma50", "sma100"), close=close, slope_bias=slope_bias
    )


def _monthly_ma_cluster(df_m: pd.DataFrame) -> Dict[str, Any]:
    """Monthly MA compression (SMA10/20/50 core)."""
    empty_members = {"sma10": None, "sma20": None, "sma50": None, "sma100": None}
    if df_m.empty:
        return _ma_cluster_from_members(empty_members, core_keys=("sma10", "sma20", "sma50"), close=None, slope_bias="flat")

    last = df_m.iloc[-1]
    members = {
        "sma10": float(last["ma10"]) if "ma10" in df_m.columns and not pd.isna(last.get("ma10")) else None,
        "sma20": float(last["ma20"]) if "ma20" in df_m.columns and not pd.isna(last.get("ma20")) else None,
        "sma50": float(last["ma50"]) if "ma50" in df_m.columns and not pd.isna(last.get("ma50")) else None,
        "sma100": float(last["ma100"]) if "ma100" in df_m.columns and not pd.isna(last.get("ma100")) else None,
    }
    slope_bias = _slope_state(df_m["ma50"]) if "ma50" in df_m.columns else "flat"
    close = float(last["close"])
    return _ma_cluster_from_members(
        members, core_keys=("sma10", "sma20", "sma50"), close=close, slope_bias=slope_bias
    )


def _partial_trend_quality_score(df_d: pd.DataFrame) -> Tuple[int | None, Dict[str, Any]]:
    """Heuristic partial Trend Quality (Axis B) from daily MAs only — RS/structure left to agent."""
    breakdown = {
        "price_vs_mas": None,
        "structure": None,
        "relative_strength": None,
        "volume_money_flow": None,
        "momentum_entry": None,
    }
    if df_d.empty or len(df_d) < 50:
        return None, breakdown
    last = df_d.iloc[-1]
    c = float(last["close"])
    mas = []
    pts = 0
    for k in ("ma20", "ma50", "ma100", "ma200"):
        v = last.get(k)
        if v is not None and not pd.isna(v):
            mas.append(float(v))
            if c >= float(v):
                pts += 2  # up to 8 of the 10 "above MAs" budget
    # alignment: ma20 > ma50 > ma100 when available
    align = 0
    if "ma20" in last and "ma50" in last and not pd.isna(last.get("ma20")) and not pd.isna(last.get("ma50")):
        if float(last["ma20"]) >= float(last["ma50"]):
            align += 5
    if "ma50" in last and "ma100" in last and not pd.isna(last.get("ma50")) and not pd.isna(last.get("ma100")):
        if float(last["ma50"]) >= float(last["ma100"]):
            align += 5
    long_rising = 5 if _slope_state(df_d["ma50"]) == "up" else 0
    price_vs = min(10, pts) + min(10, align) + long_rising  # cap conceptually at 25
    price_vs = min(25, price_vs)
    breakdown["price_vs_mas"] = price_vs
    # Partial total: only Axis A of trend score filled; others null → total = price_vs only as provisional
    return price_vs, breakdown


def _matrix_2x2(support_score: int | None, trend_score: int | None) -> str:
    def side(score: int | None, strong_label: str, weak_label: str) -> str:
        if score is None:
            return "Unknown"
        if score >= 70:
            return strong_label
        return weak_label  # mid-band treated as Weak for matrix per doctrine

    s = side(support_score, "Strong Support", "Weak Support")
    t = side(trend_score, "Strong Trend", "Weak Trend")
    if "Unknown" in (s, t):
        return f"{s} + {t}"
    return f"{s} + {t}"


def _slope_state(series: pd.Series, window: int = 5) -> str:
    if series.dropna().empty:
        return "flat"
    last = series.iloc[-1]
    if len(series.dropna()) < window + 1:
        return "flat"
    prev = series.dropna().iloc[-(window + 1)]
    if last > prev:
        return "up"
    if last < prev:
        return "down"
    return "flat"


def _weekly_ma_cluster_from_values(
    values: Dict[str, Any],
    *,
    slopes: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    selected: Dict[str, float] = {}
    for key in ("ma20", "ma50", "ma100"):
        value = values.get(key)
        if value is None or pd.isna(value):
            continue
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            continue
        selected[key] = numeric

    if len(selected) < 2:
        return {
            "available": False,
            "count": len(selected),
            "selected_mas": selected,
            "mean": None,
            "representative_level": None,
            "price_low": None,
            "price_high": None,
            "width_pct": None,
            "classification": "not_available",
            "slopes": slopes or {},
            "flat_or_rising": None,
            "trend_quality": "not_available",
        }

    ma_values = list(selected.values())
    mean_value = float(np.mean(ma_values))
    price_low = float(min(ma_values))
    price_high = float(max(ma_values))
    width_pct = (price_high - price_low) / mean_value * 100.0
    if width_pct < 2.0:
        classification = "very_tight"
    elif width_pct < 4.0:
        classification = "strong"
    elif width_pct < 7.0:
        classification = "moderate"
    else:
        classification = "weak"

    slope_map = {key: value for key, value in (slopes or {}).items() if key in selected}
    flat_or_rising: bool | None = None
    trend_quality = "slope_not_available"
    if slope_map:
        non_declining = sum(value in {"flat", "up"} for value in slope_map.values())
        flat_or_rising = non_declining >= math.ceil(len(slope_map) / 2)
        if all(value == "down" for value in slope_map.values()):
            trend_quality = "declining_cluster_caution"
        elif flat_or_rising:
            trend_quality = "flat_or_rising"
        else:
            trend_quality = "mixed"

    return {
        "available": True,
        "count": len(selected),
        "selected_mas": selected,
        "mean": mean_value,
        "representative_level": mean_value,
        "price_low": price_low,
        "price_high": price_high,
        "width_pct": float(width_pct),
        "classification": classification,
        "slopes": slope_map,
        "flat_or_rising": flat_or_rising,
        "trend_quality": trend_quality,
    }


def _classify_weekly_close_test(
    *,
    low: float,
    close: float,
    volume_ratio: float | None,
    zone_low: float,
    zone_high: float,
    next_close: float | None = None,
) -> Dict[str, Any]:
    if zone_low > zone_high:
        zone_low, zone_high = zone_high, zone_low
    wick_below_zone = float(low) < zone_low
    close_below_zone = float(close) < zone_low
    close_above_zone = float(close) > zone_high
    expanding_volume = volume_ratio is not None and float(volume_ratio) >= 1.3
    failed_reclaim = next_close is not None and float(next_close) < zone_low
    decisive_failure = close_below_zone and expanding_volume and failed_reclaim

    if decisive_failure:
        state = "support_failure"
    elif close_below_zone and expanding_volume:
        state = "breakdown_awaiting_reclaim_test"
    elif wick_below_zone and not close_below_zone:
        state = "support_test_held"
    elif close_above_zone:
        state = "support_reclaimed"
    elif close_below_zone:
        state = "below_zone_unconfirmed"
    else:
        state = "support_under_test"

    return {
        "state": state,
        "weekly_close": float(close),
        "weekly_low": float(low),
        "volume_ratio": None if volume_ratio is None else float(volume_ratio),
        "wick_below_zone": wick_below_zone,
        "close_below_zone": close_below_zone,
        "close_above_zone": close_above_zone,
        "next_close": None if next_close is None else float(next_close),
        "failed_reclaim": failed_reclaim,
        "decisive_failure": decisive_failure,
        "confirmation_close": float(zone_high),
        "invalidation_close": float(zone_low),
        "doctrine": "Weekly close and next-week confirmation outweigh an isolated intrawweek wick.",
    }


def _weekly_structural_assessment(df: pd.DataFrame) -> Dict[str, Any]:
    empty_score = {
        "ma_confluence": None,
        "horizontal_pivot": None,
        "role_reversal": None,
        "prior_base_origin_markup": None,
        "volume_absorption": None,
        "momentum_invalidation": None,
    }
    weekly = _ensure_ohlcv(df)
    if weekly.empty:
        cluster = _weekly_ma_cluster_from_values({})
    else:
        required = {"ma20", "ma50", "ma100", "atr14", "vol_sma20", "rsi14"}
        if not required.issubset(weekly.columns):
            weekly = _calc_indicators(weekly)
        slopes = {
            key: _slope_state(weekly[key])
            for key in ("ma20", "ma50", "ma100")
            if key in weekly.columns and not weekly[key].dropna().empty
        }
        last = weekly.iloc[-1] if not weekly.empty else pd.Series(dtype=float)
        cluster = _weekly_ma_cluster_from_values(
            {key: last.get(key) for key in ("ma20", "ma50", "ma100")},
            slopes=slopes,
        )

    if not cluster["available"]:
        return {
            "status": "not_available",
            "trend": "not_confirmed",
            "current_range_base": "not_confirmed",
            "ma_cluster": cluster,
            "representative_level": None,
            "actual_zone": {"price_low": None, "price_high": None},
            "label": "STRUCTURAL_PIVOT_ZONE",
            "polarity": None,
            "horizontal_pivot": {"state": "not_confirmed", "evidence": {}},
            "role_reversal": {"state": "not_confirmed", "current_role": "Unconfirmed", "evidence": {}},
            "prior_base": {"state": "not_confirmed", "evidence": {}},
            "origin_of_markup": {"state": "not_confirmed", "evidence": {}},
            "volume_supply_demand": {
                "status": "unresolved",
                "supply": "not_confirmed",
                "demand": "not_confirmed",
                "evidence_for_absorption": [],
                "evidence_against_absorption": [],
            },
            "weekly_close_test": {
                "state": "not_available",
                "confirmation_close": None,
                "invalidation_close": None,
            },
            "momentum_reset": {"state": "not_confirmed", "rsi14w": None},
            "wyckoff_phase": "not_confirmed",
            "wyckoff_events": {
                "spring": "not_confirmed",
                "sos": "not_confirmed",
                "lps": "not_confirmed",
                "phase_e": "not_confirmed",
            },
            "score_breakdown": empty_score,
            "structural_support_score": None,
            "score_classification": "not_available",
            "final_verdict": "Weak support",
            "confidence": "Low",
            "warnings": ["At least two of SMA20W/SMA50W/SMA100W are required."],
        }

    representative = float(cluster["representative_level"])
    band = representative * 0.0075
    zone_low = float(cluster["price_low"] - band)
    zone_high = float(cluster["price_high"] + band)
    last = weekly.iloc[-1]
    history = weekly.iloc[:-1].tail(156).copy()
    close_tolerance = representative * 0.02
    close_near = (history["close"] - representative).abs() <= close_tolerance
    body_low = history[["open", "close"]].min(axis=1)
    body_high = history[["open", "close"]].max(axis=1)
    body_overlap = (body_low <= zone_high) & (body_high >= zone_low)
    wick_only = (
        (history["low"] <= zone_high)
        & (history["high"] >= zone_low)
        & ~body_overlap
    )
    reaction_count = int(body_overlap.sum())
    close_cluster_count = int(close_near.sum())
    wick_only_count = int(wick_only.sum())
    closes_below = int((history["close"] < zone_low).sum())
    closes_above = int((history["close"] > zone_high).sum())
    repeated_reactions = reaction_count >= 3
    multiple_closes = close_cluster_count >= 4
    prior_significance = closes_below >= 2 and closes_above >= 2
    horizontal_state = (
        "confirmed" if sum((repeated_reactions, multiple_closes, prior_significance)) >= 2 else "not_confirmed"
    )

    breakout_index: int | None = None
    for i in range(8, max(len(weekly) - 2, 8)):
        prior = weekly.iloc[max(0, i - 8) : i]
        if int((prior["close"] <= zone_high).sum()) >= 3 and float(weekly.iloc[i]["close"]) > zone_high:
            breakout_index = i
    retest_count = 0
    successful_retest = False
    if breakout_index is not None:
        after = weekly.iloc[breakout_index + 1 :]
        retests = after[(after["low"] <= zone_high) & (after["high"] >= zone_low)]
        retest_count = int(len(retests))
        successful_retest = bool(
            not retests.empty and (retests["close"] >= zone_low).any()
        )

    breakdown_index: int | None = None
    for i in range(8, max(len(weekly) - 2, 8)):
        prior = weekly.iloc[max(0, i - 8) : i]
        if int((prior["close"] >= zone_low).sum()) >= 3 and float(weekly.iloc[i]["close"]) < zone_low:
            breakdown_index = i
    bear_retest_count = 0
    successful_bear_retest = False
    if breakdown_index is not None:
        after_bd = weekly.iloc[breakdown_index + 1 :]
        bear_retests = after_bd[(after_bd["low"] <= zone_high) & (after_bd["high"] >= zone_low)]
        bear_retest_count = int(len(bear_retests))
        successful_bear_retest = bool(
            not bear_retests.empty and (bear_retests["close"] <= zone_high).any()
        )

    last_close = float(last["close"])
    closes_after_break = 0
    acceptance_breakout = False
    if breakout_index is not None:
        after_bo = weekly.iloc[breakout_index + 1 :]
        closes_after_break = int((after_bo["close"] > zone_high).sum())
        acceptance_breakout = closes_after_break >= 2 and last_close > zone_low

    closes_after_breakdown = 0
    acceptance_breakdown = False
    if breakdown_index is not None:
        after_bd2 = weekly.iloc[breakdown_index + 1 :]
        closes_after_breakdown = int((after_bd2["close"] < zone_low).sum())
        acceptance_breakdown = closes_after_breakdown >= 2 and last_close < zone_high

    # Failed breakout: was above briefly, now back below without successful support retest
    failed_breakout = bool(
        breakout_index is not None
        and last_close < zone_low
        and not successful_retest
    )
    failed_breakdown = bool(
        breakdown_index is not None
        and last_close > zone_high
        and not successful_bear_retest
    )

    if last_close > zone_high:
        approach_direction = "from_above"
        default_role = "Support candidate"
    elif last_close < zone_low:
        approach_direction = "from_below"
        default_role = "Resistance candidate"
    else:
        approach_direction = "inside_zone"
        default_role = "Equilibrium/pivot"

    if failed_breakout:
        role_reversal_state = "FAILED_BREAKOUT"
        current_role = "Resistance"
    elif failed_breakdown:
        role_reversal_state = "FAILED_BREAKDOWN"
        current_role = "Support"
    elif (
        breakout_index is not None
        and acceptance_breakout
        and successful_retest
        and last_close >= zone_low
    ):
        role_reversal_state = "ROLE_REVERSAL_SUPPORT"
        current_role = "Role-reversal support"
    elif (
        breakdown_index is not None
        and acceptance_breakdown
        and successful_bear_retest
        and last_close <= zone_high
    ):
        role_reversal_state = "ROLE_REVERSAL_RESISTANCE"
        current_role = "Role-reversal resistance"
    elif last_close > zone_high and closes_above >= 3:
        role_reversal_state = "not_confirmed"
        current_role = "Support"
    elif last_close < zone_low and closes_below >= 3:
        role_reversal_state = "not_confirmed"
        current_role = "Resistance"
    elif approach_direction == "inside_zone":
        role_reversal_state = "EQUILIBRIUM_PIVOT"
        current_role = "Equilibrium/pivot"
    else:
        role_reversal_state = "not_confirmed"
        current_role = "Unconfirmed"

    base_weeks = int((body_overlap | close_near).tail(52).sum())
    prior_base_state = "confirmed" if base_weeks >= 6 else "not_confirmed"
    markup_dates: List[str] = []
    for i in range(0, max(len(weekly) - 8, 0)):
        start_close = float(weekly.iloc[i]["close"])
        if start_close <= 0 or abs(start_close - representative) / representative > 0.03:
            continue
        forward_max = float(weekly.iloc[i + 1 : i + 9]["close"].max())
        if forward_max >= start_close * 1.15:
            markup_dates.append(weekly.iloc[i]["date"].date().isoformat())
    origin_markup_state = "confirmed" if markup_dates else "not_confirmed"

    recent = weekly.tail(8).copy()
    recent["down_week"] = recent["close"].diff() < 0
    down_weeks = recent[recent["down_week"]]
    sell_volume_ratio = None
    downside_spread_ratio = None
    if not down_weeks.empty:
        ratios = down_weeks["volume"] / down_weeks["vol_sma20"].replace(0.0, np.nan)
        valid_ratios = ratios.dropna()
        if not valid_ratios.empty:
            sell_volume_ratio = float(valid_ratios.median())
        spreads = (down_weeks["high"] - down_weeks["low"]) / down_weeks["atr14"].replace(0.0, np.nan)
        valid_spreads = spreads.dropna()
        if not valid_spreads.empty:
            downside_spread_ratio = float(valid_spreads.median())
    sell_volume_contracting = sell_volume_ratio is not None and sell_volume_ratio < 0.9
    downside_spreads_narrow = downside_spread_ratio is not None and downside_spread_ratio < 0.9
    last_vol_sma20 = last.get("vol_sma20")
    last_volume_ratio = (
        float(last["volume"] / last_vol_sma20)
        if last_vol_sma20 is not None and not pd.isna(last_vol_sma20) and last_vol_sma20 != 0
        else None
    )
    recent_return = (
        float(recent["close"].iloc[-1] / recent["close"].iloc[0] - 1.0)
        if len(recent) >= 2 and float(recent["close"].iloc[0]) != 0
        else None
    )
    limited_downside_result = (
        last_volume_ratio is not None
        and last_volume_ratio >= 1.2
        and recent_return is not None
        and recent_return > -0.03
    )
    up_weeks = recent[recent["close"].diff() > 0]
    rebound_volume_improves = False
    if not up_weeks.empty and not down_weeks.empty:
        rebound_volume_improves = float(up_weeks.iloc[-1]["volume"]) > float(
            down_weeks.iloc[-1]["volume"]
        )
    weak_no_demand = (
        sell_volume_contracting
        and recent_return is not None
        and recent_return < -0.05
        and not rebound_volume_improves
    )
    next_close = None
    close_test = _classify_weekly_close_test(
        low=float(last["low"]),
        close=float(last["close"]),
        volume_ratio=last_volume_ratio,
        zone_low=zone_low,
        zone_high=zone_high,
        next_close=next_close,
    )
    if close_test["state"] in {"support_failure", "breakdown_awaiting_reclaim_test"}:
        volume_status = "support_failure_risk"
    elif weak_no_demand:
        volume_status = "weak_no_demand"
    elif sell_volume_contracting or downside_spreads_narrow or limited_downside_result:
        volume_status = "possible_absorption"
    else:
        volume_status = "unresolved"

    rsi_current = last.get("rsi14")
    rsi_value = None if rsi_current is None or pd.isna(rsi_current) else float(rsi_current)
    prior_rsi = weekly["rsi14"].iloc[:-4].tail(52).dropna()
    prior_overbought = bool(not prior_rsi.empty and float(prior_rsi.max()) >= 65.0)
    rsi_reset = bool(
        prior_overbought
        and rsi_value is not None
        and 40.0 <= rsi_value <= 55.0
        and not close_test["close_below_zone"]
    )

    lower_lows = history[history["low"] < zone_low]["low"]
    next_lower_zone = None
    if not lower_lows.empty:
        lower_level = float(lower_lows.tail(104).min())
        next_lower_zone = {
            "price_low": lower_level * 0.98,
            "price_high": lower_level * 1.02,
        }

    ma_overlap = cluster["width_pct"] is not None and cluster["width_pct"] < 7.0
    ma_score = 8 if ma_overlap else 0
    if cluster["width_pct"] is not None and cluster["width_pct"] < 4.0:
        ma_score += 5
    if ma_overlap and cluster["flat_or_rising"] is True:
        ma_score += 4
    previous_close = float(weekly.iloc[-2]["close"]) if len(weekly) >= 2 else None
    price_reclaiming = (
        previous_close is not None
        and previous_close < zone_low
        and float(last["close"]) >= zone_low
    )
    if ma_overlap and price_reclaiming:
        ma_score += 3

    horizontal_score = (
        (8 if repeated_reactions else 0)
        + (6 if multiple_closes else 0)
        + (6 if prior_significance else 0)
    )
    role_score = 0
    if breakout_index is not None or breakdown_index is not None:
        role_score += 8
    if successful_retest or successful_bear_retest:
        role_score += 7
    if failed_breakout or failed_breakdown:
        role_score = max(0, role_score - 5)
    base_markup_score = (7 if prior_base_state == "confirmed" else 0) + (
        8 if origin_markup_state == "confirmed" else 0
    )
    volume_score = (
        (6 if sell_volume_contracting else 0)
        + (4 if downside_spreads_narrow else 0)
        + (4 if limited_downside_result else 0)
        + (6 if rebound_volume_improves else 0)
    )
    momentum_score = (4 if rsi_reset else 0) + 3 + (3 if next_lower_zone else 0)
    score_breakdown = {
        "ma_confluence": ma_score,
        "horizontal_pivot": horizontal_score,
        "role_reversal": role_score,
        "prior_base_origin_markup": base_markup_score,
        "volume_absorption": volume_score,
        "momentum_invalidation": momentum_score,
    }
    total_score = int(sum(score_breakdown.values()))
    if total_score >= 85:
        score_classification = "Exceptional weekly support"
    elif total_score >= 70:
        score_classification = "Strong weekly support"
    elif total_score >= 55:
        score_classification = "Moderate / under test"
    elif total_score >= 40:
        score_classification = "Weak"
    else:
        score_classification = "Not meaningful"

    if close_test["state"] in {"support_failure", "breakdown_awaiting_reclaim_test"}:
        verdict = "Failed support"
    elif role_reversal_state == "FAILED_BREAKOUT":
        verdict = "Failed breakout"
    elif role_reversal_state == "ROLE_REVERSAL_RESISTANCE":
        verdict = "Role-reversal resistance"
    elif role_reversal_state == "ROLE_REVERSAL_SUPPORT" and total_score >= 70:
        verdict = "Role-reversal support"
    elif role_reversal_state == "EQUILIBRIUM_PIVOT":
        verdict = "Equilibrium/pivot"
    elif total_score >= 70:
        verdict = "Strong weekly support"
    elif total_score >= 55:
        verdict = "Support under test"
    else:
        verdict = "Weak support"
    confidence = "High" if total_score >= 85 else "Medium" if total_score >= 55 else "Low"

    # Role-reversal quality score (§7 polarity doctrine) — partial auto
    hist_imp = (
        (8 if repeated_reactions else 0)
        + (6 if prior_significance else 0)
        + (6 if multiple_closes else 0)
    )
    hist_imp = min(20, hist_imp)
    break_q = 0
    if breakout_index is not None or breakdown_index is not None:
        break_q += 8
    if last_volume_ratio is not None and last_volume_ratio >= 1.2 and (
        breakout_index is not None or breakdown_index is not None
    ):
        break_q += 6
    if closes_after_break >= 2 or closes_after_breakdown >= 2:
        break_q += 6
    break_q = min(20, break_q)
    accept_q = 0
    if acceptance_breakout or acceptance_breakdown:
        accept_q += 8
    if (last_close > zone_high and acceptance_breakout) or (
        last_close < zone_low and acceptance_breakdown
    ):
        accept_q += 7
    accept_q = min(15, accept_q)
    retest_q = 0
    if retest_count > 0 or bear_retest_count > 0:
        retest_q += 5
    if sell_volume_contracting and successful_retest:
        retest_q += 7
    if successful_retest or successful_bear_retest:
        retest_q += 6
    if rebound_volume_improves and successful_retest:
        retest_q += 7
    retest_q = min(25, retest_q)
    htf_q = (
        (6 if ma_overlap else 0)
        + (5 if prior_base_state == "confirmed" else 0)
        + (5 if origin_markup_state == "confirmed" else 0)
        + (4 if role_reversal_state == "ROLE_REVERSAL_SUPPORT" else 0)
    )
    htf_q = min(20, htf_q)
    rr_breakdown = {
        "historical_importance": hist_imp,
        "break_quality": break_q,
        "acceptance": accept_q,
        "retest_quality": retest_q,
        "htf_confluence": htf_q,
    }
    rr_score = int(sum(rr_breakdown.values()))
    if rr_score >= 85:
        rr_class = "Exceptional role reversal"
    elif rr_score >= 70:
        rr_class = "Strong"
    elif rr_score >= 55:
        rr_class = "Moderate"
    elif rr_score >= 40:
        rr_class = "Unconfirmed"
    else:
        rr_class = "Weak / noise"

    polarity = {
        "label": "STRUCTURAL_PIVOT_ZONE",
        "representative_level": representative,
        "price_low": zone_low,
        "price_high": zone_high,
        "timeframe": "W",
        "historical_significance": horizontal_state,
        "current_role": current_role,
        "default_role_from_approach": default_role,
        "approach_direction": approach_direction,
        "break_history": {
            "breakout_date": None
            if breakout_index is None
            else weekly.iloc[breakout_index]["date"].date().isoformat(),
            "breakdown_date": None
            if breakdown_index is None
            else weekly.iloc[breakdown_index]["date"].date().isoformat(),
            "failed_breakout": failed_breakout,
            "failed_breakdown": failed_breakdown,
        },
        "acceptance": {
            "breakout": acceptance_breakout,
            "breakdown": acceptance_breakdown,
            "closes_above_after_break": closes_after_break,
            "closes_below_after_breakdown": closes_after_breakdown,
        },
        "retest": {
            "bullish_retest_count": retest_count,
            "bullish_retest_success": successful_retest,
            "bearish_retest_count": bear_retest_count,
            "bearish_retest_success": successful_bear_retest,
        },
        "volume_behavior": volume_status,
        "htf_confluence": {
            "ma_cluster": cluster.get("classification") or cluster.get("confluence_label"),
            "prior_base": prior_base_state,
            "origin_markup": origin_markup_state,
        },
        "role_reversal_state": role_reversal_state,
        "role_reversal_quality_score": rr_score,
        "role_reversal_score_classification": rr_class,
        "role_reversal_score_breakdown": rr_breakdown,
        "confirmation": (
            f"weekly close defended above ~{zone_high:.2f} with demand response"
            if approach_direction == "from_above"
            else f"weekly rejection below ~{zone_low:.2f} without accepted reclaim"
            if approach_direction == "from_below"
            else "directional closes establishing control outside the equilibrium band"
        ),
        "invalidation": (
            f"decisive weekly close below ~{zone_low:.2f} with expanding volume / failed reclaim"
            if current_role in {"Support", "Role-reversal support", "Support candidate"}
            else f"decisive weekly close above ~{zone_high:.2f} with acceptance"
            if current_role in {"Resistance", "Role-reversal resistance", "Resistance candidate"}
            else "accepted break and hold on either side of the pivot zone"
        ),
        "doctrine": "Zone is structural; support/resistance is contextual. Cross ≠ role reversal.",
    }

    ma50_slope = cluster.get("slopes", {}).get("ma50")
    if last_close > zone_high and ma50_slope == "up":
        trend = "uptrend"
    elif last_close < zone_low and ma50_slope == "down":
        trend = "downtrend"
    else:
        trend = "range_or_repair"

    evidence_for: List[str] = []
    evidence_against: List[str] = []
    if sell_volume_contracting:
        evidence_for.append("weekly sell volume is contracting")
    if downside_spreads_narrow:
        evidence_for.append("weekly downside spreads are narrowing")
    if limited_downside_result:
        evidence_for.append("elevated selling effort produced limited downside result")
    if rebound_volume_improves:
        evidence_for.append("rebound volume improved")
    if weak_no_demand:
        evidence_against.append("price fell easily despite lower volume; demand is absent")
    if close_test["close_below_zone"]:
        evidence_against.append("weekly close is below the candidate zone")
    if cluster["trend_quality"] == "declining_cluster_caution":
        evidence_against.append("tight MA cluster is steeply declining")

    return {
        "status": "evaluated",
        "trend": trend,
        "current_range_base": prior_base_state,
        "ma_cluster": cluster,
        "representative_level": representative,
        "actual_zone": {"price_low": zone_low, "price_high": zone_high},
        "label": "STRUCTURAL_PIVOT_ZONE",
        "polarity": polarity,
        "horizontal_pivot": {
            "state": horizontal_state,
            "evidence": {
                "weekly_body_reactions": reaction_count,
                "weekly_close_clusters": close_cluster_count,
                "wick_only_touches": wick_only_count,
                "closes_below_zone": closes_below,
                "closes_above_zone": closes_above,
            },
        },
        "role_reversal": {
            "state": role_reversal_state,
            "current_role": current_role,
            "quality_score": rr_score,
            "quality_classification": rr_class,
            "evidence": {
                "breakout_date": None
                if breakout_index is None
                else weekly.iloc[breakout_index]["date"].date().isoformat(),
                "breakdown_date": None
                if breakdown_index is None
                else weekly.iloc[breakdown_index]["date"].date().isoformat(),
                "successful_retest": successful_retest,
                "retest_count": retest_count,
                "successful_bear_retest": successful_bear_retest,
                "bear_retest_count": bear_retest_count,
                "acceptance_breakout": acceptance_breakout,
                "acceptance_breakdown": acceptance_breakdown,
                "failed_breakout": failed_breakout,
                "failed_breakdown": failed_breakdown,
            },
        },
        "prior_base": {
            "state": prior_base_state,
            "evidence": {"acceptance_weeks_last_52": base_weeks},
        },
        "origin_of_markup": {
            "state": origin_markup_state,
            "evidence": {"launch_dates": markup_dates[-5:]},
        },
        "volume_supply_demand": {
            "status": volume_status,
            "supply": "contracting" if sell_volume_contracting else "not_contracting_or_unknown",
            "demand": "confirmed" if rebound_volume_improves else "absent_or_not_confirmed",
            "sell_volume_ratio": sell_volume_ratio,
            "downside_spread_ratio": downside_spread_ratio,
            "effort_vs_result": "possible_absorption" if limited_downside_result else "not_confirmed",
            "evidence_for_absorption": evidence_for,
            "evidence_against_absorption": evidence_against,
        },
        "weekly_close_test": close_test,
        "momentum_reset": {
            "state": "confirmed" if rsi_reset else "not_confirmed",
            "rsi14w": rsi_value,
            "prior_rsi_at_least_65": prior_overbought,
            "doctrine": "RSI is context only; oversold does not equal bottom.",
        },
        "next_lower_structural_zone": next_lower_zone,
        "wyckoff_phase": "not_confirmed",
        "wyckoff_events": {
            "spring": "candidate" if failed_breakdown else "not_confirmed",
            "sos": "not_confirmed",
            "lps": "candidate" if role_reversal_state == "ROLE_REVERSAL_SUPPORT" and volume_status == "possible_absorption" else "not_confirmed",
            "phase_e": "not_confirmed",
        },
        "score_breakdown": score_breakdown,
        "score_details": {
            "price_reclaiming_ma_cluster": price_reclaiming,
            "two_or_more_weekly_mas_overlap": ma_overlap,
            "repeated_weekly_reactions": repeated_reactions,
            "multiple_historical_closes": multiple_closes,
            "prior_support_resistance_significance": prior_significance,
            "rsi_reset_without_structural_damage": rsi_reset,
            "clear_invalidation": True,
        },
        "structural_support_score": total_score,
        "score_classification": score_classification,
        "final_verdict": verdict,
        "confidence": confidence,
        "warnings": [
            "Automated weekly structure is heuristic; ambiguous Wyckoff events remain not confirmed."
        ],
    }


def _trend_state(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"state": "range", "ma_stack": "n/a", "price_vs_ma": {}}
    row = df.iloc[-1]
    c = float(row["close"])
    ma20, ma50, ma100, ma200 = (
        row.get("ma20"),
        row.get("ma50"),
        row.get("ma100"),
        row.get("ma200"),
    )
    state = "range"
    ma_stack = "n/a"
    if all(pd.notna(x) for x in (ma20, ma50, ma100, ma200)):
        ma_stack = f"{ma20:.2f}>{ma50:.2f}>{ma100:.2f}>{ma200:.2f}"
        if c > ma20 > ma50 > ma100 > ma200:
            state = "uptrend"
        elif c < ma20 < ma50 < ma100 < ma200:
            state = "downtrend"
        else:
            state = "range"
    price_vs_ma = {
        "close_vs_ma20": None if pd.isna(ma20) else c - float(ma20),
        "close_vs_ma50": None if pd.isna(ma50) else c - float(ma50),
        "close_vs_ma100": None if pd.isna(ma100) else c - float(ma100),
        "close_vs_ma200": None if pd.isna(ma200) else c - float(ma200),
    }
    return {"state": state, "ma_stack": ma_stack, "price_vs_ma": price_vs_ma}


def _tightness_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df) < 10:
        return {
            "last_10d_range_pct": None,
            "last_5d_close_stdev_pct": None,
            "interpretation": "not_available",
        }
    tail10 = df.iloc[-10:]
    tail5 = df.iloc[-5:]
    high10 = tail10["high"].max()
    low10 = tail10["low"].min()
    close_last = float(df["close"].iloc[-1])
    last_10d_range_pct = (
        (high10 - low10) / close_last * 100 if close_last else None
    )
    last_5d_close_stdev_pct = (
        tail5["close"].std(ddof=0) / close_last * 100 if close_last else None
    )
    interp = "normal"
    if last_10d_range_pct is not None:
        if last_10d_range_pct < 6 and last_5d_close_stdev_pct is not None and last_5d_close_stdev_pct < 2:
            interp = "tight"
        elif last_10d_range_pct > 15:
            interp = "loose"
    return {
        "last_10d_range_pct": float(last_10d_range_pct) if last_10d_range_pct is not None else None,
        "last_5d_close_stdev_pct": float(last_5d_close_stdev_pct)
        if last_5d_close_stdev_pct is not None
        else None,
        "interpretation": interp,
    }


def _detect_gaps(df: pd.DataFrame) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    if len(df) < 2:
        return gaps
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        cur = df.iloc[i]
        if pd.isna(prev["high"]) or pd.isna(prev["low"]) or pd.isna(cur["high"]) or pd.isna(
            cur["low"]
        ):
            continue
        if cur["low"] > prev["high"]:
            gap_pct = (cur["low"] - prev["close"]) / prev["close"] * 100 if prev["close"] else None
            gaps.append(
                {
                    "date": cur["date"].date().isoformat(),
                    "type": "gap_up",
                    "gap_pct": float(gap_pct) if gap_pct is not None else None,
                    "follow_through": "yes" if cur["close"] > cur["open"] else "no",
                }
            )
        elif cur["high"] < prev["low"]:
            gap_pct = (prev["close"] - cur["high"]) / prev["close"] * 100 if prev["close"] else None
            gaps.append(
                {
                    "date": cur["date"].date().isoformat(),
                    "type": "gap_down",
                    "gap_pct": float(gap_pct) if gap_pct is not None else None,
                    "follow_through": "yes" if cur["close"] < cur["open"] else "no",
                }
            )
    return gaps


def _vsa_signals(df: pd.DataFrame, lookback: int = 30) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if df.empty:
        return out
    tail = df.iloc[-lookback:].copy()
    v = tail["volume"]
    vol_sma20 = tail["vol_sma20"]
    atr14 = tail["atr14"]
    c, h, l = tail["close"], tail["high"], tail["low"]
    prev_c = c.shift(1)

    for i in range(len(tail)):
        row = tail.iloc[i]
        if i == 0:
            continue
        date_str = row["date"].date().isoformat()
        vol = row["volume"]
        vsma20 = row["vol_sma20"]
        bar_atr = row["atr14"]
        if pd.isna(vsma20) or pd.isna(bar_atr):
            continue
        rng = row["high"] - row["low"]
        if rng <= 0:
            continue
        close_pos = (row["close"] - row["low"]) / rng
        up = row["close"] > tail["close"].iloc[i - 1]
        down = row["close"] < tail["close"].iloc[i - 1]
        spread_narrow = rng < 0.8 * bar_atr
        vol_heavy = vol > 1.5 * vsma20
        vol_light = vol < 0.8 * vsma20

        if down and vol_heavy and close_pos <= 0.3:
            out.append(
                {
                    "date": date_str,
                    "signal": "supply",
                    "evidence": "down bar, heavy volume, close in lower 30% of range",
                }
            )
        elif up and vol_heavy and close_pos >= 0.7:
            out.append(
                {
                    "date": date_str,
                    "signal": "demand",
                    "evidence": "up bar, heavy volume, close in upper 30% of range",
                }
            )
        elif down and vol_light and spread_narrow:
            out.append(
                {
                    "date": date_str,
                    "signal": "no_supply",
                    "evidence": "down bar, light volume, narrow spread",
                }
            )
        elif up and vol_light and spread_narrow:
            out.append(
                {
                    "date": date_str,
                    "signal": "no_demand",
                    "evidence": "up bar, light volume, narrow spread",
                }
            )
    return out


def _distribution_score(df: pd.DataFrame, lookback_days: int = 25) -> Dict[str, Any]:
    if len(df) < lookback_days + 1:
        return {
            "lookback_days": lookback_days,
            "heavy_down_days": 0,
            "heavy_up_days": 0,
            "interpretation": "not_available",
        }
    tail = df.iloc[-lookback_days - 1 :].copy()
    c = tail["close"]
    v = tail["volume"]
    v_sma50 = tail["vol_sma50"]
    down = c.diff() < 0
    up = c.diff() > 0
    heavy = v > 1.5 * v_sma50
    heavy_down = int(((down) & heavy).sum())
    heavy_up = int(((up) & heavy).sum())
    if heavy_down >= heavy_up + 2:
        interp = "distribution"
    elif heavy_up >= heavy_down + 2:
        interp = "accumulation"
    else:
        interp = "neutral"
    return {
        "lookback_days": lookback_days,
        "heavy_down_days": heavy_down,
        "heavy_up_days": heavy_up,
        "interpretation": interp,
    }


def _volume_profile_window(
    df: pd.DataFrame, bars: int, cfg: TAConfig
) -> Dict[str, Any]:
    if df.empty:
        return {
            "poc": [None, None],
            "vah": [None, None],
            "val": [None, None],
            "hvn": [],
            "lvn": [],
        }
    tail = df.iloc[-bars:].copy() if len(df) >= bars else df.copy()
    typical_price = (tail["high"] + tail["low"] + tail["close"]) / 3.0
    volume = tail["volume"]
    if typical_price.isna().all() or volume.isna().all():
        return {
            "poc": [None, None],
            "vah": [None, None],
            "val": [None, None],
            "hvn": [],
            "lvn": [],
        }
    prices = typical_price.values.astype(float)
    vols = volume.values.astype(float)
    p_min, p_max = prices.min(), prices.max()
    if not math.isfinite(p_min) or not math.isfinite(p_max) or p_min == p_max:
        return {
            "poc": [None, None],
            "vah": [None, None],
            "val": [None, None],
            "hvn": [],
            "lvn": [],
        }
    hist, edges = np.histogram(prices, bins=cfg.vp_bins, range=(p_min, p_max), weights=vols)
    total_vol = hist.sum()
    if total_vol <= 0:
        return {
            "poc": [None, None],
            "vah": [None, None],
            "val": [None, None],
            "hvn": [],
            "lvn": [],
        }
    poc_idx = int(hist.argmax())
    poc_range = [float(edges[poc_idx]), float(edges[poc_idx + 1])]

    # Value area around POC
    target_vol = total_vol * cfg.value_area_pct
    included = np.zeros_like(hist, dtype=bool)
    included[poc_idx] = True
    cur_vol = hist[poc_idx]
    left = poc_idx - 1
    right = poc_idx + 1
    while cur_vol < target_vol and (left >= 0 or right < len(hist)):
        left_vol = hist[left] if left >= 0 else -1
        right_vol = hist[right] if right < len(hist) else -1
        if right_vol >= left_vol:
            if right < len(hist):
                included[right] = True
                cur_vol += right_vol
                right += 1
            else:
                left_vol = hist[left]
                included[left] = True
                cur_vol += left_vol
                left -= 1
        else:
            if left >= 0:
                included[left] = True
                cur_vol += left_vol
                left -= 1
            else:
                right_vol = hist[right]
                included[right] = True
                cur_vol += right_vol
                right += 1
    included_idxs = np.where(included)[0]
    val_low_edge = edges[included_idxs.min()]
    vah_high_edge = edges[included_idxs.max() + 1]
    val_range = [float(val_low_edge), float(edges[included_idxs.min() + 1])]
    vah_range = [float(edges[included_idxs.max()]), float(vah_high_edge)]

    # HVN/LVN detection (simple prominence heuristic)
    vols_arr = hist.astype(float)
    hvn_candidates: List[Tuple[int, float]] = []
    lvn_candidates: List[Tuple[int, float]] = []
    if len(vols_arr) >= 3:
        base = vols_arr.min()
        for i in range(1, len(vols_arr) - 1):
            v_i = vols_arr[i]
            v_l, v_r = vols_arr[i - 1], vols_arr[i + 1]
            if v_i > v_l and v_i > v_r and v_i > base * 1.2:
                hvn_candidates.append((i, v_i))
            if v_i < v_l and v_i < v_r and v_i < vols_arr.mean() * 0.8:
                lvn_candidates.append((i, v_i))
    hvn_candidates = sorted(hvn_candidates, key=lambda x: x[1], reverse=True)[:2]
    lvn_candidates = sorted(lvn_candidates, key=lambda x: x[1])[:2]

    def _idx_to_range(idx: int) -> List[float]:
        return [float(edges[idx]), float(edges[idx + 1])]

    hvn_ranges = [_idx_to_range(i) for i, _ in hvn_candidates]
    lvn_ranges = [_idx_to_range(i) for i, _ in lvn_candidates]

    return {
        "poc": poc_range,
        "vah": vah_range,
        "val": val_range,
        "hvn": hvn_ranges,
        "lvn": lvn_ranges,
    }


def _volume_profile(df: pd.DataFrame, cfg: TAConfig) -> Dict[str, Any]:
    return {
        "long_260d": _volume_profile_window(df, 260, cfg),
        "mid_90d": _volume_profile_window(df, 90, cfg),
        "short_30d": _volume_profile_window(df, 30, cfg),
    }


def _volume_profile_read(df: pd.DataFrame, vp: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    if df.empty:
        return ["volume profile not available (no data)"]
    last_close = float(df["close"].iloc[-1])

    long_vp = vp.get("long_260d", {})
    poc = long_vp.get("poc") or [None, None]
    vah = long_vp.get("vah") or [None, None]
    val = long_vp.get("val") or [None, None]

    if all(x is not None for x in poc):
        if last_close > poc[1]:
            notes.append(
                f"Price {last_close:.2f} is trading above long-term POC [{poc[0]:.2f}-{poc[1]:.2f}], suggesting prior acceptance below and potential overhead clearing."
            )
        elif last_close < poc[0]:
            notes.append(
                f"Price {last_close:.2f} is trading below long-term POC [{poc[0]:.2f}-{poc[1]:.2f}], indicating overhead supply from higher-volume region."
            )
        else:
            notes.append(
                f"Price {last_close:.2f} is rotating near long-term POC [{poc[0]:.2f}-{poc[1]:.2f}], typical of balance/mean reversion."
            )
    if all(x is not None for x in vah + val):
        if last_close > vah[1]:
            notes.append(
                f"Current price is above long-term VAH [{vah[0]:.2f}-{vah[1]:.2f}], favouring breakout/expansion if supported by trend and volume."
            )
        elif last_close < val[0]:
            notes.append(
                f"Current price is below long-term VAL [{val[0]:.2f}-{val[1]:.2f}], often a discount zone but can indicate breakdown risk."
            )
        else:
            notes.append(
                f"Current price is inside long-term value area [{val[0]:.2f}-{vah[1]:.2f}], mean reversion more likely unless trend is strong."
            )
    if not notes:
        notes.append("volume profile available but could not derive clear narrative")
    return notes


def _support_resistance_from_vp(
    df: pd.DataFrame, vp: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    supports: List[Dict[str, Any]] = []
    resistances: List[Dict[str, Any]] = []
    if df.empty:
        return supports, resistances
    last_close = float(df["close"].iloc[-1])
    long_vp = vp.get("long_260d", {})
    poc = long_vp.get("poc") or [None, None]
    vah = long_vp.get("vah") or [None, None]
    val = long_vp.get("val") or [None, None]

    if all(x is not None for x in val):
        supports.append(
            {
                "price_low": float(val[0]),
                "price_high": float(val[1]),
                "basis": ["VP:VAL"],
                "confidence": "med",
            }
        )
    if all(x is not None for x in poc):
        zone = {
            "price_low": float(poc[0]),
            "price_high": float(poc[1]),
            "basis": ["VP:POC"],
            "confidence": "med",
        }
        if last_close >= poc[1]:
            supports.append(zone)
        else:
            resistances.append(zone)
    if all(x is not None for x in vah):
        resistances.append(
            {
                "price_low": float(vah[0]),
                "price_high": float(vah[1]),
                "basis": ["VP:VAH"],
                "confidence": "med",
            }
        )
    return supports, resistances


def _obv_state(df: pd.DataFrame) -> Dict[str, Any]:
    if df["obv"].dropna().empty:
        return {"state": "flat", "divergence": "none", "evidence": "OBV not available"}
    obv = df["obv"].dropna()
    recent = obv.iloc[-20:]
    if len(recent) < 2:
        return {"state": "flat", "divergence": "none", "evidence": "insufficient OBV history"}
    state = _slope_state(recent, window=min(10, len(recent) - 1))
    # Simple divergence: compare last swing in price vs OBV over same period
    price = df["close"].loc[recent.index]
    price_state = _slope_state(price, window=min(10, len(recent) - 1))
    divergence = "none"
    if state == "up" and price_state == "down":
        divergence = "bull"
    elif state == "down" and price_state == "up":
        divergence = "bear"
    return {
        "state": state,
        "divergence": divergence,
        "evidence": f"OBV {state} while price {price_state} over last ~20 bars",
    }


def _cmf_state(df: pd.DataFrame) -> Dict[str, Any]:
    val = df["cmf20"].iloc[-1] if not df["cmf20"].dropna().empty else np.nan
    if pd.isna(val):
        return {"value": None, "state": "neutral"}
    if val > 0.1:
        state = "inflow"
    elif val < -0.1:
        state = "outflow"
    else:
        state = "neutral"
    return {"value": float(val), "state": state}


def _macd_state(df: pd.DataFrame) -> Dict[str, Any]:
    if df["macd"].dropna().empty:
        return {"macd": None, "signal": None, "hist": None, "state": "turning", "notes": "MACD not available"}
    row = df.iloc[-1]
    macd = row["macd"]
    sig = row["macd_signal"]
    hist = row["macd_hist"]
    if pd.isna(macd) or pd.isna(sig) or pd.isna(hist):
        return {"macd": None, "signal": None, "hist": None, "state": "turning", "notes": "MACD NaN"}
    if macd > sig and hist > 0:
        state = "bullish"
    elif macd < sig and hist < 0:
        state = "bearish"
    else:
        state = "turning"
    return {
        "macd": float(macd),
        "signal": float(sig),
        "hist": float(hist),
        "state": state,
        "notes": "",
    }


def _wyckoff_stub() -> Dict[str, Any]:
    # Minimal, conservative Wyckoff module: default to "unclear"; primary TF = weekly
    return {
        "primary_timeframe": "W",
        "phase": "unclear",
        "schematic_guess": "unclear",
        "events": {
            "ps": {"present": False, "why": "not confirmed"},
            "sc": {"present": False, "why": "not confirmed"},
            "ar": {"present": False, "why": "not confirmed"},
            "st": {"present": False, "why": "not confirmed"},
            "spring": {"present": False, "why": "not confirmed"},
            "sos": {"present": False, "why": "not confirmed"},
            "lps": {"present": False, "why": "not confirmed"},
        },
        "logic": [
            "Wyckoff phase detection not fully automated; weekly is primary TF; treat as unclear without ≥2 confirming signals."
        ],
    }


def _ma_block(df: pd.DataFrame, keys: Tuple[str, ...]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: None for k in keys}
    out["slope_ma50"] = "flat"
    if df.empty:
        return out
    last = df.iloc[-1]
    for key in keys:
        if key not in df.columns:
            continue
        val = last.get(key)
        out[key] = float(val) if val is not None and not pd.isna(val) else None
    if "ma50" in df.columns:
        out["slope_ma50"] = _slope_state(df["ma50"])
    return out


def _enrich_zones(
    zones: List[Dict[str, Any]],
    *,
    timeframe_origin: str,
    zone_role: str,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for z in zones:
        item = dict(z)
        item.setdefault("timeframe_origin", timeframe_origin)
        item.setdefault("zone_role", zone_role)
        item.setdefault("status", "under_test")
        item.setdefault("structural_support_score", None)
        item.setdefault(
            "score_breakdown",
            {
                "htf_ma": None,
                "horizontal": None,
                "markup_base": None,
                "volume": None,
                "momentum_trend": None,
                "invalidation_clarity": None,
            },
        )
        item.setdefault(
            "confluence",
            {
                "ma": "not scored in CLI; agent must apply reference-mtf-structural-support.md",
                "horizontal_pivot": "not scored in CLI",
                "origin_of_markup": "not scored in CLI",
                "prior_base": "not scored in CLI",
                "volume_behavior": "not scored in CLI",
            },
        )
        enriched.append(item)
    return enriched


def _trade_plan(df: pd.DataFrame, vp: Dict[str, Any], atr14: float | None) -> Dict[str, Any]:
    if df.empty:
        return {
            "bias": "neutral",
            "trigger": {"type": "breakout", "price": None, "conditions": ["no data"]},
            "invalidations": [],
            "risk": {
                "atr14": None,
                "suggested_stop_atr_mult": 1.5,
                "position_size_hint": "risk 0.5%-1% equity",
            },
            "targets": [],
            "what_to_watch_next": ["wait for sufficient price history"],
            "setup_type": "base_breakout",
            "entry_model": "stop_order",
            "stop_model": "atr_trailing",
            "add_on_rules": [],
            "sell_signals": [],
        }
    close = float(df["close"].iloc[-1])
    long_vp = vp.get("long_260d", {})
    vah = long_vp.get("vah") or [None, None]
    val = long_vp.get("val") or [None, None]
    poc = long_vp.get("poc") or [None, None]
    bias = "neutral"
    if poc[0] is not None:
        if close > poc[1]:
            bias = "long"
        elif close < poc[0]:
            bias = "short"
    trigger_price = None
    trigger_type = "breakout"
    conditions: List[str] = []
    targets: List[Dict[str, Any]] = []
    if vah[1] is not None:
        trigger_price = float(vah[1])
        conditions.append("daily close above VAH with volume > 1.5x VolSMA20")
        targets.append(
            {
                "price": float(vah[1]),
                "basis": ["VP HVN", "prior swing high"],
            }
        )
    invalidations: List[Dict[str, Any]] = []
    if val[0] is not None:
        invalidations.append(
            {
                "price": float(val[0]),
                "why": "decisive close below VAL undercuts current value area support",
            }
        )
    risk_atr = atr14 if atr14 is not None and not pd.isna(atr14) else None
    return {
        "bias": bias,
        "trigger": {"type": trigger_type, "price": trigger_price, "conditions": conditions},
        "invalidations": invalidations,
        "risk": {
            "atr14": float(risk_atr) if risk_atr is not None else None,
            "suggested_stop_atr_mult": 1.5,
            "position_size_hint": "risk 0.5%-1% equity",
        },
        "targets": targets,
        "what_to_watch_next": [
            "behaviour around VAH/VAL and POC",
            "volume signature on breakouts/breakdowns",
        ],
        "setup_type": "base_breakout",
        "entry_model": "stop_order",
        "stop_model": "atr_trailing",
        "add_on_rules": ["add only on strength with volume confirmation"],
        "sell_signals": ["failed breakout with close back into value on heavy volume"],
    }


def _data_integrity(df: pd.DataFrame, horizon_days: int) -> Dict[str, Any]:
    if df.empty:
        return {
            "missing_bars": horizon_days,
            "missing_pct": 100.0,
            "median_value_traded": 0.0,
            "liquidity_flag": "very_thin",
            "adjusted": False,
            "adjustment_notes": "no data; series unavailable",
        }
    bars = len(df)
    missing = max(0, horizon_days - bars)
    missing_pct = missing / max(horizon_days, 1) * 100.0
    median_value = float((df["close"] * df["volume"]).median())
    liquidity_flag = "ok"
    if median_value < 1e9:
        liquidity_flag = "thin"
    if median_value < 2e8:
        liquidity_flag = "very_thin"
    return {
        "missing_bars": missing,
        "missing_pct": missing_pct,
        "median_value_traded": median_value,
        "liquidity_flag": liquidity_flag,
        "adjusted": False,
        "adjustment_notes": "assumed unadjusted FireAnt series; splits/dividends not verified",
    }


def _evidence_map(df: pd.DataFrame, vp: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if df.empty:
        return items
    last = df.iloc[-1]
    items.append(
        {
            "type": "last_bar",
            "date": last["date"].date().isoformat(),
            "value": {
                "close": float(last["close"]),
                "volume": float(last["volume"]),
            },
            "comment": "last available daily bar",
        }
    )
    if "atr14" in df.columns and not pd.isna(last.get("atr14")):
        items.append(
            {
                "type": "atr14",
                "date": last["date"].date().isoformat(),
                "value": float(last["atr14"]),
                "comment": "current ATR14",
            }
        )
    for ma_key in ("ma20", "ma50"):
        if ma_key in df.columns and not pd.isna(last.get(ma_key)):
            items.append(
                {
                    "type": ma_key,
                    "date": last["date"].date().isoformat(),
                    "value": float(last[ma_key]),
                    "comment": f"{ma_key} at last bar",
                }
            )
    long_vp = vp.get("long_260d", {})
    for key in ("poc", "vah", "val"):
        rng = long_vp.get(key)
        if rng and all(x is not None for x in rng):
            items.append(
                {
                    "type": f"vp_{key}",
                    "date": last["date"].date().isoformat(),
                    "value": [float(rng[0]), float(rng[1])],
                    "comment": f"long-term volume profile {key.upper()} range",
                }
            )
    return items


def analyze_ticker(ticker: str, asof: date, cfg: TAConfig) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    start = asof - timedelta(days=cfg.horizon_days * 2)
    start_str = start.isoformat()
    end_str = asof.isoformat()

    try:
        df_d = fetch_ohlcv(ticker, start=start_str, end=end_str, resolution="D")
    except Exception as e:
        df_d = pd.DataFrame()
        errors.append(f"fetch_ohlcv daily failed: {e}")

    try:
        df_w = fetch_ohlcv(ticker, start=start_str, end=end_str, resolution="W")
    except Exception as e:
        df_w = pd.DataFrame()
        errors.append(f"fetch_ohlcv weekly failed: {e}")

    try:
        df_m = fetch_ohlcv(ticker, start=start_str, end=end_str, resolution="M")
    except Exception as e:
        df_m = pd.DataFrame()
        errors.append(f"fetch_ohlcv monthly failed: {e}")

    df_d = _ensure_ohlcv(df_d)
    df_w = _ensure_ohlcv(df_w)
    df_m = _ensure_ohlcv(df_m)

    if df_d.empty:
        warnings.append("No daily OHLCV data; analysis is mostly unavailable.")

    df_d = _calc_indicators(df_d) if not df_d.empty else df_d
    df_w = _calc_indicators(df_w) if not df_w.empty else df_w
    df_m = _calc_indicators(df_m) if not df_m.empty else df_m
    if not df_w.empty:
        df_w["ema10"] = _ema(df_w["close"], 10)
        df_w["ema20"] = _ema(df_w["close"], 20)

    data_meta = {
        "timeframes": {
            "M": {
                "bars": int(len(df_m)),
                "start": None if df_m.empty else df_m["date"].iloc[0].date().isoformat(),
                "end": None if df_m.empty else df_m["date"].iloc[-1].date().isoformat(),
                "adjusted": False,
            },
            "W": {
                "bars": int(len(df_w)),
                "start": None if df_w.empty else df_w["date"].iloc[0].date().isoformat(),
                "end": None if df_w.empty else df_w["date"].iloc[-1].date().isoformat(),
                "adjusted": False,
            },
            "D": {
                "bars": int(len(df_d)),
                "start": None if df_d.empty else df_d["date"].iloc[0].date().isoformat(),
                "end": None if df_d.empty else df_d["date"].iloc[-1].date().isoformat(),
                "adjusted": False,
            },
        }
    }

    trend_daily = _trend_state(df_d) if not df_d.empty else _trend_state(df_d)
    trend_weekly = _trend_state(df_w) if not df_w.empty else _trend_state(df_w)
    trend_monthly = _trend_state(df_m) if not df_m.empty else _trend_state(df_m)
    if not df_m.empty and "ma50" in df_m.columns:
        last_m = df_m.iloc[-1]
        close_m = float(last_m["close"])
        ma50_m = last_m.get("ma50")
        trend_monthly["secular_trend_intact"] = (
            bool(close_m >= float(ma50_m)) if ma50_m is not None and not pd.isna(ma50_m) else None
        )
    else:
        trend_monthly["secular_trend_intact"] = None

    regime_summary = (
        "Monthly defines structure; weekly Wyckoff/absorption; daily timing only."
    )
    if trend_monthly.get("state") == "uptrend" and trend_daily.get("state") == "downtrend":
        regime_summary = (
            "Monthly uptrend intact while daily is corrective — do not let daily alone "
            "invalidate monthly demand without evidence."
        )
    elif trend_monthly.get("state") == "downtrend":
        regime_summary = "Monthly trend is down — treat rallies as suspect until structure reclaims."

    tightness = _tightness_metrics(df_d)
    gaps = _detect_gaps(df_d)

    vp = _volume_profile(df_d, cfg)
    vp_read = _volume_profile_read(df_d, vp) if not df_d.empty else ["volume profile not available"]
    supports_raw, resistances_raw = _support_resistance_from_vp(df_d, vp)
    supports = _enrich_zones(supports_raw, timeframe_origin="D", zone_role="tactical")
    resistances = _enrich_zones(resistances_raw, timeframe_origin="D", zone_role="tactical")
    if len(df_m) >= 50 and "ma50" in df_m.columns:
        ma50m = df_m["ma50"].iloc[-1]
        if ma50m is not None and not pd.isna(ma50m):
            band = float(ma50m) * 0.03
            supports.insert(
                0,
                {
                    "price_low": float(ma50m) - band,
                    "price_high": float(ma50m) + band,
                    "timeframe_origin": "M",
                    "zone_role": "structural",
                    "basis": ["MA50M", "zone_not_line"],
                    "status": "under_test",
                    "structural_support_score": None,
                    "score_breakdown": {
                        "htf_ma": None,
                        "horizontal": None,
                        "markup_base": None,
                        "volume": None,
                        "momentum_trend": None,
                        "invalidation_clarity": None,
                    },
                    "confluence": {
                        "ma": f"Monthly SMA50 ≈ {float(ma50m):.2f}; treat as zone, not exact line",
                        "horizontal_pivot": "agent must verify multi-year pivot overlap",
                        "origin_of_markup": "agent must verify markup origin overlap",
                        "prior_base": "agent must verify prior base overlap",
                        "volume_behavior": "agent must score on decline into zone",
                    },
                    "confidence": "low",
                },
            )
            warnings.append(
                "MA50M zone seeded as structural candidate only — full confluence score requires agent review."
            )

    vol_context = {"vol_vs_sma20": None, "vol_vs_sma50": None}
    if not df_d.empty:
        last = df_d.iloc[-1]
        v = last["volume"]
        vs20 = last.get("vol_sma20")
        vs50 = last.get("vol_sma50")
        vol_context["vol_vs_sma20"] = float(v / vs20) if vs20 and not pd.isna(vs20) else None
        vol_context["vol_vs_sma50"] = float(v / vs50) if vs50 and not pd.isna(vs50) else None

    vsa_recent = _vsa_signals(df_d)
    dist_score = _distribution_score(df_d)

    ma_section = {
        "D": _ma_block(df_d, ("ma20", "ma50", "ma100", "ma200")),
        "W": {
            "sma20": None,
            "sma50": None,
            "sma100": None,
            "sma200": None,
            "ema10": None,
            "ema20": None,
            "slope_sma50": "flat",
        },
        "M": {
            "sma10": None,
            "sma20": None,
            "sma50": None,
            "sma100": None,
            "slope_sma50": "flat",
        },
    }
    ma_cluster = _weekly_ma_cluster(df_w)
    weekly_assessment = _weekly_structural_assessment(df_w)
    m_cluster = _monthly_ma_cluster(df_m)
    if not df_w.empty:
        last_w = df_w.iloc[-1]
        for src, dst in (
            ("ma20", "sma20"),
            ("ma50", "sma50"),
            ("ma100", "sma100"),
            ("ma200", "sma200"),
            ("ema10", "ema10"),
            ("ema20", "ema20"),
        ):
            val = last_w.get(src)
            ma_section["W"][dst] = float(val) if val is not None and not pd.isna(val) else None
        ma_section["W"]["slope_sma50"] = _slope_state(df_w["ma50"]) if "ma50" in df_w.columns else "flat"
    if not df_m.empty:
        last_m2 = df_m.iloc[-1]
        for src, dst in (("ma10", "sma10"), ("ma20", "sma20"), ("ma50", "sma50"), ("ma100", "sma100")):
            val = last_m2.get(src)
            ma_section["M"][dst] = float(val) if val is not None and not pd.isna(val) else None
        ma_section["M"]["slope_sma50"] = _slope_state(df_m["ma50"]) if "ma50" in df_m.columns else "flat"

    rsi_w = None
    if not df_w.empty and "rsi14" in df_w.columns and not pd.isna(df_w["rsi14"].iloc[-1]):
        rsi_w = float(df_w["rsi14"].iloc[-1])
    rsi_d = None
    if not df_d.empty and "rsi14" in df_d.columns and not pd.isna(df_d["rsi14"].iloc[-1]):
        rsi_d = float(df_d["rsi14"].iloc[-1])
    rsi_m = None
    if not df_m.empty and "rsi14" in df_m.columns and not pd.isna(df_m["rsi14"].iloc[-1]):
        rsi_m = float(df_m["rsi14"].iloc[-1])

    if len(df_m) < 50:
        warnings.append("Fewer than 50 monthly bars — monthly SMA50 may be unavailable or weak.")

    # Add a measured weekly structural candidate when sufficient MA history exists.
    weekly_zones: List[Dict[str, Any]] = []
    weekly_actual_zone = weekly_assessment.get("actual_zone", {})
    if weekly_assessment.get("status") == "evaluated":
        zone_low = weekly_actual_zone.get("price_low")
        zone_high = weekly_actual_zone.get("price_high")
        weekly_cluster = weekly_assessment["ma_cluster"]
        weekly_zones.append(
            {
                "representative_level": weekly_assessment["representative_level"],
                "price_low": zone_low,
                "price_high": zone_high,
                "tags": ["MA_CLUSTER", weekly_assessment["role_reversal"]["state"]],
                "ma_cluster": weekly_cluster,
                "horizontal_pivot": weekly_assessment["horizontal_pivot"],
                "role_reversal": weekly_assessment["role_reversal"],
                "prior_base": weekly_assessment["prior_base"],
                "origin_of_markup": weekly_assessment["origin_of_markup"],
                "volume_supply_demand": weekly_assessment["volume_supply_demand"],
                "weekly_structural_support_score": weekly_assessment[
                    "structural_support_score"
                ],
                "score_breakdown": weekly_assessment["score_breakdown"],
                "status": weekly_assessment["final_verdict"],
                "weekly_close_test": weekly_assessment["weekly_close_test"],
                "weekly_close_confirm": zone_high,
                "weekly_close_invalidate": zone_low,
            }
        )
        supports.insert(
            0,
            {
                "price_low": zone_low,
                "price_high": zone_high,
                "representative_level": weekly_assessment["representative_level"],
                "timeframe_origin": "W",
                "zone_role": "structural",
                "basis": [
                    "MA_CLUSTER_W",
                    "WEEKLY_CLOSE",
                    "HORIZONTAL_MEMORY",
                    "zone_not_line",
                ],
                "status": weekly_assessment["final_verdict"],
                "structural_support_score": weekly_assessment[
                    "structural_support_score"
                ],
                "score_breakdown": weekly_assessment["score_breakdown"],
                "confluence": {
                    "ma": weekly_cluster,
                    "horizontal_pivot": weekly_assessment["horizontal_pivot"],
                    "role_reversal": weekly_assessment["role_reversal"],
                    "origin_of_markup": weekly_assessment["origin_of_markup"],
                    "prior_base": weekly_assessment["prior_base"],
                    "volume_behavior": weekly_assessment["volume_supply_demand"],
                },
                "weekly_close_test": weekly_assessment["weekly_close_test"],
                "confidence": weekly_assessment["confidence"].lower(),
            },
        )
        warnings.extend(weekly_assessment.get("warnings", []))

    obv_state = _obv_state(df_d)
    cmf_state = _cmf_state(df_d)
    macd_state = _macd_state(df_d)

    wyckoff = _wyckoff_stub()
    if wyckoff["phase"] == "unclear":
        warnings.append("Wyckoff phase kept as 'unclear' to avoid over-interpretation.")

    atr_last = None
    if not df_d.empty and "atr14" in df_d.columns:
        atr_last = df_d["atr14"].iloc[-1]
        if pd.isna(atr_last):
            atr_last = None

    trade_plan = _trade_plan(df_d, vp, atr_last)
    integrity = _data_integrity(df_d, cfg.horizon_days)
    evidence = _evidence_map(df_d, vp)
    if weekly_assessment.get("representative_level") is not None:
        weekly_cluster = weekly_assessment["ma_cluster"]
        actual_zone = weekly_assessment["actual_zone"]
        evidence.append(
            {
                "type": "weekly_ma_cluster",
                "date": None if df_w.empty else df_w["date"].iloc[-1].date().isoformat(),
                "value": {
                    "width_pct": weekly_cluster.get("width_pct"),
                    "zone": [actual_zone.get("price_low"), actual_zone.get("price_high")],
                    "label": weekly_cluster.get("classification"),
                    "score": weekly_assessment.get("structural_support_score"),
                },
                "comment": "Weekly SMA20/50/100 compression and structural evidence (zone, not exact line)",
            }
        )

    confidence_overall = "low"
    if not df_d.empty and integrity["liquidity_flag"] == "ok" and integrity["missing_pct"] < 30:
        confidence_overall = "med"

    trend_score_partial, trend_breakdown = _partial_trend_quality_score(df_d)
    weekly_score = weekly_assessment.get("structural_support_score")
    weekly_breakdown = weekly_assessment.get("score_breakdown", {})
    dual_axis = {
        "support_quality_score": weekly_score,
        "support_score_breakdown": {
            "market_memory": weekly_breakdown.get("horizontal_pivot"),
            "ma_confluence": weekly_breakdown.get("ma_confluence"),
            "role_reversal_reclaim": weekly_breakdown.get("role_reversal"),
            "base_markup": weekly_breakdown.get("prior_base_origin_markup"),
            "volume_absorption": weekly_breakdown.get("volume_absorption"),
            "momentum_invalidation": weekly_breakdown.get("momentum_invalidation"),
        },
        "trend_quality_score": trend_score_partial,
        "trend_score_breakdown": trend_breakdown,
        "trend_score_note": "CLI fills price-vs-MAs partial only; structure/RS/volume/momentum require agent",
        "matrix_2x2": _matrix_2x2(weekly_score, trend_score_partial),
        "support_status": weekly_assessment.get("final_verdict", "Support under test")
        .upper()
        .replace(" ", "_"),
        "reclaim_quality": "not_applicable",
        "zone_tier": (
            "Tier1" if weekly_score is not None and weekly_score >= 70 else "Tier2" if weekly_zones else "Tier3"
        ),
        "market_memory": {
            "acceptance_vs_rejection": weekly_assessment.get("horizontal_pivot", {}).get(
                "state", "not_confirmed"
            ),
            "notes": "Weekly bodies/closes outweigh wick-only touches; do not upgrade failed support without reclaim.",
        },
        "ma_clusters": {
            "weekly": weekly_assessment.get("ma_cluster", {}),
            "weekly_legacy": ma_cluster,
            "monthly": m_cluster,
        },
    }
    if weekly_score is None:
        warnings.append(
            "dual_axis.support_quality_score is null because weekly MA history is insufficient."
        )

    weekly_structure = {
        **weekly_assessment,
        "monthly_ma_cluster": m_cluster,
        "legacy_ma_cluster": ma_cluster,
        "zones": weekly_zones,
        "phase_interpretation": {
            "phase": weekly_assessment.get("wyckoff_phase", "not_confirmed"),
            "sos": weekly_assessment.get("wyckoff_events", {}).get("sos", "not_confirmed"),
            "lps": weekly_assessment.get("wyckoff_events", {}).get("lps", "not_confirmed"),
            "breakout_status": weekly_assessment.get("wyckoff_events", {}).get(
                "phase_e", "not_confirmed"
            ),
        },
    }

    result: Dict[str, Any] = {
        "ticker": ticker,
        "asof": asof.isoformat(),
        "data": data_meta,
        "levels": {
            "support_zones": supports,
            "resistance_zones": resistances,
            "key_inflection_levels": [],
        },
        "trend_regime": {
            "monthly": trend_monthly,
            "weekly": trend_weekly,
            "daily": trend_daily,
            "regime_summary": regime_summary,
            "zoom_discipline": {
                "monthly_answers": "structural supply/demand",
                "weekly_answers": "Wyckoff phase / institutional support / MA cluster",
                "daily_answers": "trade trigger / stop",
            },
        },
        "weekly_structure": weekly_structure,
        "dual_axis": dual_axis,
        "pivot_zones": (
            [weekly_assessment["polarity"]]
            if weekly_assessment.get("polarity")
            else []
        ),
        "price_action": {
            "tightness": tightness,
            "bar_shape_notes": [],
            "gaps": gaps,
        },
        "volume_action": {
            "volume_context": vol_context,
            "vsa_signals_recent": vsa_recent,
            "distribution_score": dist_score,
            "supply_absorption": {
                "status": weekly_assessment.get("volume_supply_demand", {}).get(
                    "status", "unresolved"
                ),
                "evidence_for": weekly_assessment.get("volume_supply_demand", {}).get(
                    "evidence_for_absorption", []
                ),
                "evidence_against": weekly_assessment.get("volume_supply_demand", {}).get(
                    "evidence_against_absorption", []
                ),
                "effort_vs_result": weekly_assessment.get(
                    "volume_supply_demand", {}
                ).get("effort_vs_result", "not_confirmed"),
            },
        },
        "volume_profile": {
            "long_260d": vp["long_260d"],
            "mid_90d": vp["mid_90d"],
            "short_30d": vp["short_30d"],
            "vp_read": vp_read,
        },
        "indicators": {
            "ma": ma_section,
            "rsi": {
                "D": {"value": rsi_d, "note": "context only; oversold ≠ bottom"},
                "W": {"value": rsi_w, "note": "RSI14W context; reset ≠ buy signal"},
                "M": {"value": rsi_m},
            },
            "obv": obv_state,
            "cmf20": cmf_state,
            "macd_12_26_9": macd_state,
        },
        "wyckoff": wyckoff,
        "entry_quality": {
            "good_chart": None,
            "good_entry_now": None,
            "better_entry": "await weekly absorption / LPS confirmation near structural zone",
            "trigger": trade_plan.get("trigger"),
            "invalidation": trade_plan.get("invalidations"),
        },
        "trade_plan_1_3m": trade_plan,
        "final_verdict": {
            "label": weekly_assessment.get("final_verdict", "Support under test"),
            "confidence": weekly_assessment.get("confidence", "Low"),
            "why": [
                f"Weekly structural score: {weekly_assessment.get('structural_support_score')} / 100.",
                "Strong support ≠ strong stock; evaluate the separate trend-quality axis before ranking.",
            ],
        },
        "confidence": {
            "overall": confidence_overall,
            "why": [
                "data integrity plus measured weekly MA, market-memory, volume, and close evidence",
                "ambiguous Wyckoff events remain not confirmed",
            ],
        },
        "notes": [
            "Support strength and trend quality are separate. Failed support stays FAILED until reclaim+retest.",
        ],
        "evidence_map": evidence,
        "data_integrity": integrity,
        "warnings": warnings,
        "errors": errors,
    }
    return result


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m scripts.vn_ta_fireant_cli TICKER1 [TICKER2 ...]", file=sys.stderr)
        return 1
    tickers = [a.upper() for a in argv[1:]]
    asof = date.today()
    cfg = TAConfig()
    results: List[Dict[str, Any]] = []
    for t in tickers:
        results.append(analyze_ticker(t, asof, cfg))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

