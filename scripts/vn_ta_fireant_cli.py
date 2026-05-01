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
    horizon_days: int = 260
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

    return df


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
    # Minimal, conservative Wyckoff module: default to "unclear"
    return {
        "phase": "unclear",
        "schematic_guess": "unclear",
        "events": {
            "ps": {"present": False, "why": "not evaluated"},
            "sc": {"present": False, "why": "not evaluated"},
            "ar": {"present": False, "why": "not evaluated"},
            "st": {"present": False, "why": "not evaluated"},
            "spring": {"present": False, "why": "not evaluated"},
            "sos": {"present": False, "why": "not evaluated"},
            "lps": {"present": False, "why": "not evaluated"},
        },
        "logic": ["Wyckoff phase detection not yet implemented; treating as unclear to avoid overfitting."],
    }


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

    df_d = _ensure_ohlcv(df_d)
    df_w = _ensure_ohlcv(df_w)

    if df_d.empty:
        warnings.append("No daily OHLCV data; analysis is mostly unavailable.")

    df_d = _calc_indicators(df_d) if not df_d.empty else df_d

    data_meta = {
        "timeframes": {
            "D": {
                "bars": int(len(df_d)),
                "start": None if df_d.empty else df_d["date"].iloc[0].date().isoformat(),
                "end": None if df_d.empty else df_d["date"].iloc[-1].date().isoformat(),
                "adjusted": False,
            },
            "W": {
                "bars": int(len(df_w)),
                "start": None if df_w.empty else df_w["date"].iloc[0].date().isoformat(),
                "end": None if df_w.empty else df_w["date"].iloc[-1].date().isoformat(),
                "adjusted": False,
            },
        }
    }

    trend_daily = _trend_state(df_d) if not df_d.empty else _trend_state(df_d)
    trend_weekly = _trend_state(df_w) if not df_w.empty else _trend_state(df_w)
    regime_summary = "Trend structure unclear."
    if trend_daily["state"] == "uptrend" and trend_weekly["state"] == "uptrend":
        regime_summary = "Daily and weekly trends are aligned to the upside."
    elif trend_daily["state"] == "downtrend" and trend_weekly["state"] == "downtrend":
        regime_summary = "Daily and weekly trends are aligned to the downside."
    elif trend_daily["state"] != "range" or trend_weekly["state"] != "range":
        regime_summary = "Mixed trend signals between daily and weekly timeframes."

    tightness = _tightness_metrics(df_d)
    gaps = _detect_gaps(df_d)

    vp = _volume_profile(df_d, cfg)
    vp_read = _volume_profile_read(df_d, vp) if not df_d.empty else ["volume profile not available"]
    supports, resistances = _support_resistance_from_vp(df_d, vp)

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
        "ma20": None,
        "ma50": None,
        "ma100": None,
        "ma200": None,
        "slope_ma50": "flat",
    }
    if not df_d.empty:
        last = df_d.iloc[-1]
        for key in ("ma20", "ma50", "ma100", "ma200"):
            val = last.get(key)
            ma_section[key] = float(val) if val is not None and not pd.isna(val) else None
        ma_section["slope_ma50"] = _slope_state(df_d["ma50"])

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

    confidence_overall = "low"
    if not df_d.empty and integrity["liquidity_flag"] == "ok" and integrity["missing_pct"] < 30:
        confidence_overall = "med"

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
            "daily": trend_daily,
            "weekly": trend_weekly,
            "regime_summary": regime_summary,
        },
        "price_action": {
            "tightness": tightness,
            "bar_shape_notes": [],
            "gaps": gaps,
        },
        "volume_action": {
            "volume_context": vol_context,
            "vsa_signals_recent": vsa_recent,
            "distribution_score": dist_score,
        },
        "volume_profile": {
            "long_260d": vp["long_260d"],
            "mid_90d": vp["mid_90d"],
            "short_30d": vp["short_30d"],
            "vp_read": vp_read,
        },
        "indicators": {
            "ma": ma_section,
            "obv": obv_state,
            "cmf20": cmf_state,
            "macd_12_26_9": macd_state,
        },
        "wyckoff": wyckoff,
        "trade_plan_1_3m": trade_plan,
        "confidence": {
            "overall": confidence_overall,
            "why": ["data_integrity and basic confluence only; Wyckoff module minimal"],
        },
        "notes": [],
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

