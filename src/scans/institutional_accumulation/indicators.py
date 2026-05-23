from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.screeners.minervini_metrics import add_indicators, compute_rs, normalize_ohlcv

from .filters import _value_vnd_series


def slice_through(df: pd.DataFrame, as_of: str) -> pd.DataFrame:
    if df.empty:
        return df
    end = pd.Timestamp(as_of)
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    return x.loc[x["date"] <= end].reset_index(drop=True)


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.set_index("date").sort_index()
    w = pd.DataFrame(
        {
            "open": g["open"].resample("W-FRI").first(),
            "high": g["high"].resample("W-FRI").max(),
            "low": g["low"].resample("W-FRI").min(),
            "close": g["close"].resample("W-FRI").last(),
            "volume": g["volume"].resample("W-FRI").sum(),
        }
    ).dropna(subset=["close"])
    return w.reset_index()


def _lin_slope_norm(series: pd.Series, window: int) -> Optional[float]:
    s = series.dropna().tail(window)
    if len(s) < max(5, window // 2):
        return None
    x = np.arange(len(s), dtype=float)
    coef = np.polyfit(x, s.values.astype(float), 1)[0]
    denom = float(np.nanmean(np.abs(s.values))) or 1.0
    return float(coef / denom)


def chaikin_adl(df: pd.DataFrame) -> pd.Series:
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = (((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl).fillna(0.0)
    mfv = mfm * df["volume"].fillna(0.0)
    return mfv.cumsum()


def price_volume_trend(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].pct_change().fillna(0.0)
    return (df["volume"].fillna(0.0) * pc).cumsum()


def up_down_volume_ratio(df: pd.DataFrame, n: int = 20) -> Optional[float]:
    w = df.tail(n + 1)
    if len(w) < n + 1:
        return None
    up_vol = w.loc[w["close"] > w["close"].shift(1), "volume"].sum()
    dn_vol = w.loc[w["close"] < w["close"].shift(1), "volume"].sum()
    if dn_vol <= 0:
        return None if up_vol <= 0 else 99.0
    return float(up_vol / dn_vol)


def hv_up_down_counts(df: pd.DataFrame, n: int = 20) -> Tuple[int, int]:
    w = df.tail(n + 1).copy()
    if len(w) < 5:
        return 0, 0
    w["volma20"] = w["volume"].rolling(20, min_periods=10).mean()
    hv = w["volume"] > 1.5 * w["volma20"]
    up = (w["close"] > w["close"].shift(1)) & hv
    dn = (w["close"] < w["close"].shift(1)) & hv
    return int(up.tail(n).sum()), int(dn.tail(n).sum())


def distribution_day_count(df: pd.DataFrame, lb: int = 25) -> Optional[int]:
    if len(df) < lb + 2:
        return None
    w = df.tail(lb + 2)
    cnt = 0
    for i in range(1, len(w)):
        prev, cur = w.iloc[i - 1], w.iloc[i]
        if cur["close"] < prev["close"] and cur["volume"] > prev["volume"]:
            cnt += 1
    return cnt


def distribution_week_count(weekly: pd.DataFrame, weeks: int = 6) -> Optional[int]:
    """Weekly distribution weeks: down close on rising volume in last N weeks."""
    if weekly.empty or len(weekly) < weeks + 1:
        return None
    w = weekly.tail(weeks + 1)
    cnt = 0
    for i in range(1, len(w)):
        prev, cur = w.iloc[i - 1], w.iloc[i]
        if cur["close"] < prev["close"] and cur["volume"] > prev["volume"]:
            cnt += 1
    return cnt


def turnover_acceleration_ratio(daily: pd.DataFrame) -> Optional[float]:
    """5d avg turnover vs 50d baseline (OHLCV only, VND-scaled value)."""
    val, _, _, _ = _value_vnd_series(daily)
    if len(val) < 50:
        return None
    t5 = float(val.tail(5).mean())
    t50 = float(val.tail(50).mean())
    if t50 <= 0:
        return None
    return float(t5 / t50 - 1.0)


def cmf_daily_weekly_conflict(money: Dict[str, Any]) -> bool:
    d = money.get("cmf20_daily")
    w = money.get("cmf20_weekly")
    if d is None or w is None:
        return False
    return bool((d > 0.05 and w < 0) or (w > 0.05 and d < 0))


def weak_flow_confirmation(money: Dict[str, Any]) -> bool:
    obv = money.get("obv_slope_20")
    adl = money.get("adl_slope_20")
    obv_weak = obv is None or obv <= 0
    adl_weak = adl is None or adl <= 0
    return bool(obv_weak and adl_weak)


def volatility_contraction_flag(df: pd.DataFrame) -> bool:
    if len(df) < 130 or "bb_width20_pctile120" not in df.columns:
        return False
    row = df.iloc[-1]
    cmf = row.get("cmf20")
    pct = row.get("bb_width20_pctile120")
    if pd.isna(cmf) or pd.isna(pct):
        return False
    return bool(float(pct) <= 35.0 and float(cmf) > 0.0)


def pullback_quality_flag(df: pd.DataFrame) -> bool:
    if len(df) < 30:
        return False
    tail = df.tail(30)
    c = tail["close"]
    ret20 = float(c.iloc[-1] / c.iloc[-21] - 1) if len(c) >= 21 else np.nan
    ret10 = float(c.iloc[-1] / c.iloc[-11] - 1) if len(c) >= 11 else np.nan
    if not np.isfinite(ret20) or ret20 < 0.05:
        return False
    if not np.isfinite(ret10) or ret10 > -0.02:
        return False
    pb = tail.tail(10)
    up_v = pb.loc[pb["close"] > pb["close"].shift(1), "volume"].sum()
    dn_v = pb.loc[pb["close"] < pb["close"].shift(1), "volume"].sum()
    return bool(dn_v < up_v * 0.85)


def close_strength_score(df: pd.DataFrame, n: int = 10) -> Optional[float]:
    w = df.tail(n)
    if w.empty or "close_position" not in w.columns:
        return None
    vol_ok = w["volume"] >= w["volma20"]
    sub = w.loc[vol_ok]
    if sub.empty:
        return None
    return float(sub["close_position"].mean())


def extension_penalty_pct(df: pd.DataFrame) -> Optional[float]:
    row = df.iloc[-1]
    ma20, ma50 = row.get("ma20"), row.get("ma50")
    close = row.get("close")
    if pd.isna(ma20) or pd.isna(close) or float(ma20) <= 0:
        return None
    ext20 = (float(close) / float(ma20) - 1.0) * 100.0
    ext50 = (float(close) / float(ma50) - 1.0) * 100.0 if pd.notna(ma50) and float(ma50) > 0 else ext20
    return max(ext20, ext50)


def vingroup_distortion_diagnosis(
    symbol: str,
    money: Dict[str, Any],
    price: Dict[str, Any],
    vin_symbols: list[str],
) -> tuple[bool, Optional[str]]:
    """
    Flag VIN-led extension without robust multi-horizon flow confirmation.
    Returns (flag, short diagnosis) — does not auto-reject.
    """
    from .config import VIN_CMF_WEEKLY_WEAK, VIN_EXTENSION_PCT, VIN_RS_STRONG

    if symbol.upper() not in {s.upper() for s in vin_symbols}:
        return False, None

    rs20 = price.get("rs_vs_vnindex_20")
    ext = price.get("extension_pct_above_ma20")
    cmf_w = money.get("cmf20_weekly")
    cmf_d = money.get("cmf20_daily")

    rs_strong = rs20 is not None and rs20 >= VIN_RS_STRONG
    extended = ext is not None and ext >= VIN_EXTENSION_PCT
    if not (rs_strong and extended):
        return False, None

    reasons: list[str] = []
    if rs_strong:
        reasons.append(f"RS_vs_VNINDEX_20d={rs20:.1%}")
    if extended:
        reasons.append(f"extension={ext:.1f}%")
    if cmf_d is None or (isinstance(cmf_d, float) and not np.isfinite(cmf_d)):
        reasons.append("daily_CMF_missing")
    if cmf_w is None:
        reasons.append("weekly_CMF_missing")
    elif cmf_w <= VIN_CMF_WEEKLY_WEAK:
        reasons.append(f"weekly_CMF_weak={cmf_w:.3f}")
    if cmf_daily_weekly_conflict(money):
        reasons.append("daily_weekly_CMF_conflict")
    if weak_flow_confirmation(money):
        reasons.append("OBV_ADL_no_multi_horizon_confirmation")
    if cmf_d is not None and cmf_d > 0.05 and (cmf_w is None or cmf_w < 0):
        reasons.append("price-led_daily_CMF_only")

    if len(reasons) < 3:
        return False, None
    return True, "; ".join(reasons[:6])


def vingroup_distortion_flag(
    symbol: str,
    money: Dict[str, Any],
    price: Dict[str, Any],
    vin_symbols: list[str],
) -> bool:
    flag, _ = vingroup_distortion_diagnosis(symbol, money, price, vin_symbols)
    return flag


def compute_money_flow_metrics(daily: pd.DataFrame) -> Dict[str, Any]:
    d = add_indicators(daily)
    if d.empty:
        return {}
    w = add_indicators(resample_weekly(d))
    adl = chaikin_adl(d)
    pvt = price_volume_trend(d)
    obv = d["obv"]
    out: Dict[str, Any] = {
        "cmf20_daily": _f(d["cmf20"].iloc[-1]),
        "cmf20_weekly": _f(w["cmf20"].iloc[-1]) if not w.empty else None,
        "cmf20_daily_slope_10": _lin_slope_norm(d["cmf20"], 10),
        "cmf20_weekly_slope_8": _lin_slope_norm(w["cmf20"], 8) if not w.empty else None,
        "obv_slope_20": _lin_slope_norm(obv, 20),
        "obv_slope_50": _lin_slope_norm(obv, 50),
        "obv_vs_ma20": _f(obv.iloc[-1] / obv.rolling(20, min_periods=10).mean().iloc[-1] - 1)
        if len(obv) >= 10
        else None,
        "adl_slope_20": _lin_slope_norm(adl, 20),
        "pvt_slope_20": _lin_slope_norm(pvt, 20),
        "pvt_slope_50": _lin_slope_norm(pvt, 50),
        "up_down_volume_ratio_20": up_down_volume_ratio(d, 20),
        "hv_up_days_20": None,
        "hv_down_days_20": None,
        "adl_price_divergence_bearish": False,
        "cmf_flow_conflict": cmf_daily_weekly_conflict({}),
        "turnover_accel_ratio_5d50d": turnover_acceleration_ratio(d),
        "distribution_weeks_6": distribution_week_count(w, 6) if not w.empty else None,
    }
    out["cmf_flow_conflict"] = cmf_daily_weekly_conflict(out)
    up_hv, dn_hv = hv_up_down_counts(d, 20)
    out["hv_up_days_20"] = up_hv
    out["hv_down_days_20"] = dn_hv
    price_ret20 = float(d["close"].iloc[-1] / d["close"].iloc[-21] - 1) if len(d) >= 21 else np.nan
    adl_ret20 = float(adl.iloc[-1] / adl.iloc[-21] - 1) if len(adl) >= 21 and adl.iloc[-21] != 0 else np.nan
    if np.isfinite(price_ret20) and np.isfinite(adl_ret20):
        out["adl_price_divergence_bearish"] = bool(price_ret20 > 0.03 and adl_ret20 < 0)
    return out


def compute_price_structure_metrics(daily: pd.DataFrame, bench: pd.DataFrame) -> Dict[str, Any]:
    d = add_indicators(daily)
    rs_df = compute_rs(d, bench)
    out: Dict[str, Any] = {
        "rs_vs_vnindex_20": None,
        "rs_vs_vnindex_60": None,
        "rs_line_slope_20": None,
        "volatility_contraction_flag": False,
        "pullback_quality_flag": False,
        "close_strength_10d": None,
        "extension_pct_above_ma20": None,
        "holds_ma20": False,
        "holds_ma50": False,
        "distribution_days_25": None,
    }
    if not rs_df.empty:
        last = rs_df.iloc[-1]
        out["rs_vs_vnindex_20"] = _f(last.get("rs_20"))
        out["rs_vs_vnindex_60"] = _f(last.get("rs_60"))
        out["rs_line_slope_20"] = _f(last.get("rs_line_slope20"))
    out["volatility_contraction_flag"] = volatility_contraction_flag(d)
    out["pullback_quality_flag"] = pullback_quality_flag(d)
    out["close_strength_10d"] = close_strength_score(d, 10)
    out["extension_pct_above_ma20"] = extension_penalty_pct(d)
    row = d.iloc[-1]
    out["holds_ma20"] = bool(pd.notna(row.get("ma20")) and row["close"] >= row["ma20"])
    out["holds_ma50"] = bool(pd.notna(row.get("ma50")) and row["close"] >= row["ma50"])
    out["distribution_days_25"] = distribution_day_count(d, 25)
    return out


def _f(v: Any) -> Optional[float]:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
