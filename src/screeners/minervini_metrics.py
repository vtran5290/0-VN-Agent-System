from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class ScreenerConfig:
    min_avg_value: float = 2_000_000_000.0
    daily_lookback: int = 260
    weekly_lookback: int = 156
    vp_bins: int = 100
    value_area_pct: float = 0.70


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except Exception:
        return None


def _safe_ratio(a: float, b: float) -> float:
    if b == 0 or not np.isfinite(b):
        return np.nan
    return a / b


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "open", "high", "low", "close", "volume"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out = out[cols]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    return out.reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = normalize_ohlcv(df)
    if x.empty:
        return x
    c, h, l, o, v = x["close"], x["high"], x["low"], x["open"], x["volume"]
    x["value"] = c * v
    for n in [20, 50, 100, 150, 200]:
        x[f"ma{n}"] = c.rolling(n, min_periods=n).mean()
    x["volma20"] = v.rolling(20, min_periods=20).mean()
    x["volma50"] = v.rolling(50, min_periods=50).mean()
    x["avg_value_50"] = x["value"].rolling(50, min_periods=50).mean()

    prev_close = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    x["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    x["atr14_pct"] = x["atr14"] / c.replace(0, np.nan)

    sma20 = c.rolling(20, min_periods=20).mean()
    std20 = c.rolling(20, min_periods=20).std(ddof=0)
    x["bb_upper20"] = sma20 + 2 * std20
    x["bb_lower20"] = sma20 - 2 * std20
    x["bb_width20"] = (x["bb_upper20"] - x["bb_lower20"]) / c.replace(0, np.nan)
    x["bb_width20_pctile120"] = x["bb_width20"].rolling(120, min_periods=30).apply(
        lambda s: float(pd.Series(s).rank(pct=True).iloc[-1] * 100.0), raw=False
    )

    x["range10_pct"] = (h.rolling(10, min_periods=10).max() - l.rolling(10, min_periods=10).min()) / c.replace(0, np.nan)
    x["range5_pct"] = (h.rolling(5, min_periods=5).max() - l.rolling(5, min_periods=5).min()) / c.replace(0, np.nan)
    x["close_stdev5_pct"] = c.rolling(5, min_periods=5).std(ddof=0) / c.replace(0, np.nan)

    # OBV
    sign = np.sign(c.diff().fillna(0.0))
    x["obv"] = (sign * v.fillna(0.0)).cumsum()

    # CMF20
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    mfv = mfm * v
    x["cmf20"] = mfv.rolling(20, min_periods=20).sum() / v.rolling(20, min_periods=20).sum().replace(0, np.nan)

    # MACD
    ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
    x["macd"] = ema12 - ema26
    x["signal"] = x["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    x["histogram"] = x["macd"] - x["signal"]

    rng = (h - l).replace(0, np.nan)
    x["close_position"] = ((c - l) / rng).fillna(0.5)
    x["bar_range"] = (h - l).fillna(0.0)
    x["ret1"] = c.pct_change()
    x["down_day"] = c < c.shift(1)
    x["up_day"] = c > c.shift(1)
    x["red_day"] = c < o
    x["green_day"] = c > o
    return x


def compute_rs(stock_df: pd.DataFrame, vni_df: pd.DataFrame) -> pd.DataFrame:
    s = stock_df[["date", "close"]].rename(columns={"close": "close_stock"})
    b = vni_df[["date", "close"]].rename(columns={"close": "close_vni"})
    x = s.merge(b, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if x.empty:
        return x
    x["rs_line"] = x["close_stock"] / x["close_vni"].replace(0, np.nan)
    x["ret20_s"] = x["close_stock"] / x["close_stock"].shift(20) - 1
    x["ret60_s"] = x["close_stock"] / x["close_stock"].shift(60) - 1
    x["ret20_b"] = x["close_vni"] / x["close_vni"].shift(20) - 1
    x["ret60_b"] = x["close_vni"] / x["close_vni"].shift(60) - 1
    x["rs_20"] = x["ret20_s"] - x["ret20_b"]
    x["rs_60"] = x["ret60_s"] - x["ret60_b"]
    x["rs_line_slope20"] = x["rs_line"] / x["rs_line"].shift(20) - 1
    x["near_rs_high_60"] = x["rs_line"] / x["rs_line"].rolling(60, min_periods=20).max().replace(0, np.nan)
    return x


def _vp_window(df: pd.DataFrame, bars: int, vp_bins: int, value_area_pct: float) -> Dict[str, Any]:
    out = {"poc": None, "val": None, "vah": None, "hvns": [], "lvns": []}
    if df.empty:
        return out
    w = df.tail(bars).copy()
    tp = ((w["high"] + w["low"] + w["close"]) / 3.0).to_numpy(dtype=float)
    vol = w["volume"].to_numpy(dtype=float)
    if len(tp) < 5 or not np.isfinite(tp).any():
        return out
    pmin, pmax = np.nanmin(tp), np.nanmax(tp)
    if not np.isfinite(pmin) or not np.isfinite(pmax) or pmax <= pmin:
        return out
    hist, edges = np.histogram(tp, bins=vp_bins, range=(pmin, pmax), weights=vol)
    if hist.sum() <= 0:
        return out
    idx_poc = int(np.argmax(hist))
    out["poc"] = float((edges[idx_poc] + edges[idx_poc + 1]) / 2.0)

    target = float(hist.sum() * value_area_pct)
    included = {idx_poc}
    total = float(hist[idx_poc])
    l, r = idx_poc - 1, idx_poc + 1
    while total < target and (l >= 0 or r < len(hist)):
        lv = hist[l] if l >= 0 else -1
        rv = hist[r] if r < len(hist) else -1
        if rv >= lv:
            if r < len(hist):
                included.add(r)
                total += float(hist[r])
                r += 1
            else:
                included.add(l)
                total += float(hist[l])
                l -= 1
        else:
            if l >= 0:
                included.add(l)
                total += float(hist[l])
                l -= 1
            else:
                included.add(r)
                total += float(hist[r])
                r += 1
    lo_idx, hi_idx = min(included), max(included)
    out["val"] = float(edges[lo_idx])
    out["vah"] = float(edges[hi_idx + 1])

    # local nodes
    peaks: List[Tuple[int, float]] = []
    troughs: List[Tuple[int, float]] = []
    avg_hist = float(np.mean(hist))
    for i in range(1, len(hist) - 1):
        if hist[i] > hist[i - 1] and hist[i] > hist[i + 1] and hist[i] >= avg_hist:
            peaks.append((i, float(hist[i])))
        if hist[i] < hist[i - 1] and hist[i] < hist[i + 1]:
            troughs.append((i, float(hist[i])))
    peaks = sorted(peaks, key=lambda x: x[1], reverse=True)[:3]
    troughs = sorted(troughs, key=lambda x: x[1])[:3]
    out["hvns"] = [float((edges[i] + edges[i + 1]) / 2.0) for i, _ in peaks]
    out["lvns"] = [float((edges[i] + edges[i + 1]) / 2.0) for i, _ in troughs]
    return out


def compute_volume_profile_metrics(df: pd.DataFrame, vp_bins: int, value_area_pct: float) -> Dict[str, Any]:
    short_vp = _vp_window(df, 30, vp_bins, value_area_pct)
    mid_vp = _vp_window(df, 90, vp_bins, value_area_pct)
    long_vp = _vp_window(df, 260, vp_bins, value_area_pct)
    close = _to_float(df["close"].iloc[-1]) if not df.empty else None
    hvn_over_3 = False
    hvn_over_5 = False
    if close and close > 0:
        for p in (short_vp["hvns"] + mid_vp["hvns"] + long_vp["hvns"]):
            diff = (p - close) / close
            if 0 < diff <= 0.03:
                hvn_over_3 = True
            if 0 < diff <= 0.05:
                hvn_over_5 = True
    return {
        "short": short_vp,
        "mid": mid_vp,
        "long": long_vp,
        "price_above_short_poc": bool(close and short_vp["poc"] and close > short_vp["poc"]),
        "price_above_mid_poc": bool(close and mid_vp["poc"] and close > mid_vp["poc"]),
        "short_poc_above_mid_poc": bool(short_vp["poc"] and mid_vp["poc"] and short_vp["poc"] > mid_vp["poc"]),
        "major_hvn_overhead_within_3pct": hvn_over_3,
        "major_hvn_overhead_within_5pct": hvn_over_5,
    }


def detect_best_base(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    wins = [30, 40, 50, 60, 80]
    rows: List[Dict[str, Any]] = []
    for w in wins:
        d = df.tail(w).copy()
        if len(d) < w:
            continue
        base_high = float(d["high"].max())
        base_low = float(d["low"].min())
        if base_high <= 0:
            continue
        depth = (base_high - base_low) / base_high
        close = float(d["close"].iloc[-1])
        volma20 = d["volma20"]
        heavy_down = ((d["ret1"] < -0.03) & (d["volume"] > 1.5 * volma20)).sum()
        pivot_slice = df.tail(30).iloc[:-1]
        if len(pivot_slice) < 10:
            pivot = np.nan
        else:
            pivot = float(pivot_slice["high"].tail(30).max())
        dist = (pivot - close) / close if close > 0 and np.isfinite(pivot) else np.nan
        close_below_ma50 = int((d["close"] < d["ma50"]).sum())
        upper_quarter_ok = close >= base_low + 0.75 * (base_high - base_low)
        rows.append(
            {
                "window": w,
                "base_high": base_high,
                "base_low": base_low,
                "base_depth_pct": depth,
                "base_duration": w,
                "close_below_MA50_count": close_below_ma50,
                "heavy_down_count": int(heavy_down),
                "pivot": pivot,
                "distance_to_pivot": dist,
                "upper_quarter_ok": bool(upper_quarter_ok),
            }
        )
    if not rows:
        return {}
    ranked = sorted(
        rows,
        key=lambda r: (
            r["base_depth_pct"],
            r["heavy_down_count"],
            0 if r["upper_quarter_ok"] else 1,
            -r["base_duration"],
        ),
    )
    return ranked[0]


def score_ticker(
    df: pd.DataFrame,
    rs_df: pd.DataFrame,
    weekly: pd.DataFrame,
    vp: Dict[str, Any],
    base: Dict[str, Any],
    profile: str = "strict",
) -> Dict[str, Any]:
    warnings: List[str] = []
    if df.empty:
        return {"scores": {k: 0 for k in ["trend", "base", "tightness", "volume_dryup", "pivot", "rs", "vsa", "obv_cmf", "macd", "vp"]}, "total_score": 0, "grade": "Avoid", "warnings": ["insufficient_data"]}
    row = df.iloc[-1]
    close = float(row["close"])
    ma50, ma150, ma200 = row["ma50"], row["ma150"], row["ma200"]
    high52 = float(df["high"].tail(252).max()) if len(df) >= 100 else np.nan
    low52 = float(df["low"].tail(252).min()) if len(df) >= 100 else np.nan
    ma50_slope_20 = _safe_ratio(float(row["ma50"]), float(df["ma50"].shift(20).iloc[-1])) - 1 if len(df) > 70 else np.nan
    ma200_slope_20 = _safe_ratio(float(row["ma200"]), float(df["ma200"].shift(20).iloc[-1])) - 1 if len(df) > 230 else np.nan

    trend_conditions = [
        close > ma50 if pd.notna(ma50) else False,
        ma50 > ma150 if pd.notna(ma50) and pd.notna(ma150) else False,
        ma150 > ma200 if pd.notna(ma150) and pd.notna(ma200) else False,
        ma200_slope_20 > 0 if np.isfinite(ma200_slope_20) else False,
        close > 1.10 * ma200 if pd.notna(ma200) else False,
        close >= 0.75 * high52 if np.isfinite(high52) and high52 > 0 else False,
        close >= 1.30 * low52 if np.isfinite(low52) and low52 > 0 else False,
    ]
    trend_2 = 6 if profile == "strict" else 5 if profile == "balanced" else 4
    trend_1 = 4 if profile == "strict" else 3 if profile == "balanced" else 2
    trend_score = 2 if sum(trend_conditions) >= trend_2 else 1 if sum(trend_conditions) >= trend_1 else 0

    base_depth = base.get("base_depth_pct", np.nan)
    base_duration = base.get("base_duration", 0)
    heavy_down = base.get("heavy_down_count", 99)
    base_score = 2 if (np.isfinite(base_depth) and base_depth <= 0.15 and base_duration >= 20 and heavy_down <= 1) else 1 if (np.isfinite(base_depth) and base_depth <= 0.25 and heavy_down <= 3) else 0

    atr_decline = False
    if len(df) >= 11 and df["atr14_pct"].notna().iloc[-11] and df["atr14_pct"].notna().iloc[-1]:
        atr_decline = bool(df["atr14_pct"].iloc[-1] < df["atr14_pct"].iloc[-11])
    atr_med60 = float(df["atr14_pct"].tail(60).median()) if len(df) >= 20 else np.nan
    tight_conditions = [
        atr_decline,
        row["atr14_pct"] < atr_med60 if np.isfinite(atr_med60) and pd.notna(row["atr14_pct"]) else False,
        row["range10_pct"] < 0.08 if pd.notna(row["range10_pct"]) else False,
        row["close_stdev5_pct"] < 0.02 if pd.notna(row["close_stdev5_pct"]) else False,
        row["bb_width20_pctile120"] < 30 if pd.notna(row["bb_width20_pctile120"]) else False,
    ]
    tightness_score = 2 if sum(tight_conditions) >= 4 else 1 if sum(tight_conditions) >= 2 else 0

    tail10 = df.tail(10).copy()
    dryup_days10 = int((tail10["volume"] < 0.7 * tail10["volma20"]).sum())
    down_vol_ratio10 = _to_float(tail10.loc[tail10["down_day"], "volume"].mean() / row["volma20"]) if pd.notna(row["volma20"]) and row["volma20"] > 0 else None
    volma20_slope_10 = _safe_ratio(float(row["volma20"]), float(df["volma20"].shift(10).iloc[-1])) - 1 if len(df) > 40 else np.nan
    dry_conditions = [dryup_days10 >= 4, bool(np.isfinite(volma20_slope_10) and volma20_slope_10 <= 0), (down_vol_ratio10 is not None and down_vol_ratio10 < 1.0)]
    volume_dryup_score = 2 if sum(dry_conditions) == 3 else 1 if sum(dry_conditions) == 2 else 0

    pivot = base.get("pivot")
    dist_to_pivot = base.get("distance_to_pivot")
    breakout_condition = (
        np.isfinite(pivot) and close > 1.01 * pivot and pd.notna(row["volma20"]) and row["volma20"] > 0 and row["volume"] > 1.5 * row["volma20"] and row["close_position"] > 0.7
    )
    pivot_near_thr = 0.03 if profile == "strict" else 0.05 if profile == "balanced" else 0.07
    setup_near = (
        dist_to_pivot is not None and np.isfinite(dist_to_pivot) and dist_to_pivot <= pivot_near_thr and pd.notna(row["range5_pct"]) and row["range5_pct"] < 0.06 and (np.isfinite(volma20_slope_10) and volma20_slope_10 <= 0 or dryup_days10 >= 3)
    )
    pivot_score = 2 if breakout_condition else 1 if setup_near else 0

    rs_row = rs_df.iloc[-1] if not rs_df.empty else None
    rs_20 = _to_float(rs_row["rs_20"]) if rs_row is not None else None
    rs_60 = _to_float(rs_row["rs_60"]) if rs_row is not None else None
    rs_slope = _to_float(rs_row["rs_line_slope20"]) if rs_row is not None else None
    near_rs_high_60 = _to_float(rs_row["near_rs_high_60"]) if rs_row is not None else None
    rs_high_thr = 0.95 if profile == "strict" else 0.93 if profile == "balanced" else 0.90
    rs_conditions = [rs_20 is not None and rs_20 > 0, rs_60 is not None and rs_60 > 0, rs_slope is not None and rs_slope > 0, near_rs_high_60 is not None and near_rs_high_60 >= rs_high_thr]
    rs_need2 = 3 if profile == "strict" else 2
    rs_need1 = 2 if profile == "strict" else 1
    rs_score = 2 if sum(rs_conditions) >= rs_need2 else 1 if sum(rs_conditions) >= rs_need1 else 0
    if rs_row is None:
        warnings.append("missing_benchmark_alignment")

    tail20 = df.tail(20)
    demand = (tail20["green_day"] & (tail20["volume"] > 1.5 * tail20["volma20"]) & (tail20["close_position"] > 0.7))
    supply = (tail20["red_day"] & (tail20["volume"] > 1.5 * tail20["volma20"]) & (tail20["close_position"] < 0.3))
    no_supply = (tail20["red_day"] & (tail20["volume"] < 0.8 * tail20["volma20"]) & (tail20["bar_range"] < 0.8 * tail20["atr14"]))
    no_demand = (tail20["green_day"] & (tail20["volume"] < 0.8 * tail20["volma20"]) & (tail20["bar_range"] < 0.8 * tail20["atr14"]))
    demand_count, supply_count = int(demand.sum()), int(supply.sum())
    vsa_score = 2 if (demand_count > supply_count and supply_count <= 1) else 1 if (supply_count <= demand_count + 1) else 0

    obv_slope20 = _to_float(row["obv"] - df["obv"].shift(20).iloc[-1]) if len(df) >= 25 else None
    obv60 = df["obv"].tail(60)
    if len(obv60) >= 10 and pd.notna(row["obv"]):
        obv_high = float(obv60.max())
        if obv_high > 0:
            obv_60_ratio = float(row["obv"] / obv_high)
        else:
            obv_60_ratio = float((obv60.rank(pct=True).iloc[-1]))
    else:
        obv_60_ratio = None
    cmf20 = _to_float(row["cmf20"])
    cmf20_prev10 = _to_float(df["cmf20"].shift(10).iloc[-1]) if len(df) > 30 else None
    cmf_improving = cmf20 is not None and cmf20_prev10 is not None and cmf20 > cmf20_prev10
    obv_cmf_score = 2 if (obv_slope20 is not None and obv_slope20 > 0 and obv_60_ratio is not None and obv_60_ratio >= 0.95 and cmf20 is not None and cmf20 > 0) else 1 if (obv_slope20 is not None and obv_slope20 > 0 and ((cmf20 is not None and cmf20 >= -0.1) or cmf_improving)) else 0

    hist_rising_3 = bool(len(df) >= 3 and pd.notna(df["histogram"].iloc[-1]) and df["histogram"].iloc[-1] > df["histogram"].iloc[-2] > df["histogram"].iloc[-3])
    macd_score = 2 if (pd.notna(row["macd"]) and pd.notna(row["signal"]) and pd.notna(row["histogram"]) and row["macd"] > row["signal"] and row["histogram"] > 0 and hist_rising_3) else 1 if (hist_rising_3 or (profile != "strict" and pd.notna(row["macd"]) and pd.notna(row["signal"]) and row["macd"] > row["signal"])) else 0

    short_vp, mid_vp = vp["short"], vp["mid"]
    vp_conditions = [
        vp["price_above_short_poc"],
        vp["price_above_mid_poc"],
        vp["short_poc_above_mid_poc"],
        not vp["major_hvn_overhead_within_3pct"],
        bool(short_vp["val"] is not None and close > short_vp["val"]),
    ]
    vp_score = 2 if sum(vp_conditions) >= 4 else 1 if sum(vp_conditions) >= 2 else 0

    scores = {
        "trend": trend_score,
        "base": base_score,
        "tightness": tightness_score,
        "volume_dryup": volume_dryup_score,
        "pivot": pivot_score,
        "rs": rs_score,
        "vsa": vsa_score,
        "obv_cmf": obv_cmf_score,
        "macd": macd_score,
        "vp": vp_score,
    }
    total = int(sum(scores.values()))
    grade = "A+" if total >= 17 else "A" if total >= 14 else "B" if total >= 11 else "C" if total >= 8 else "Avoid"
    return {
        "scores": scores,
        "total_score": total,
        "grade": grade,
        "warnings": warnings,
        "extras": {
            "ma50_slope_20": _to_float(ma50_slope_20),
            "ma200_slope_20": _to_float(ma200_slope_20),
            "dryup_days10": dryup_days10,
            "down_vol_ratio10": down_vol_ratio10,
            "volma20_slope_10": _to_float(volma20_slope_10),
            "demand_count_20": demand_count,
            "supply_count_20": supply_count,
            "no_supply_count_20": int(no_supply.sum()),
            "no_demand_count_20": int(no_demand.sum()),
            "obv_slope20": obv_slope20,
            "obv_60d_high_ratio": obv_60_ratio,
            "cmf20_improving": cmf_improving,
            "rs_20": rs_20,
            "rs_60": rs_60,
            "rs_line_slope20": rs_slope,
            "near_rs_high_60": near_rs_high_60,
            "hist_rising_3": hist_rising_3,
        },
    }

