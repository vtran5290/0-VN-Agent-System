"""
Point-in-time features for base / PP / breakout event study (no future leak within bar).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def enrich_event_study_columns(d: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns used by scoring and anti-drift (call once per symbol)."""
    out = d.copy()
    c = out["close"].replace(0, np.nan)
    out["atr_pct_14"] = out["atr"] / c
    ap = out["atr_pct_14"]
    out["atr_pct_vs_20d_ago"] = ap / ap.shift(20).replace(0, np.nan)

    ma20 = out["ma20"]
    out["ma20_slope_10d"] = (ma20 - ma20.shift(10)) / ma20.shift(10).replace(0, np.nan)
    ma50 = out["ma50"]
    out["ma50_slope_20d"] = (ma50 - ma50.shift(20)) / ma50.shift(20).replace(0, np.nan)

    out["close_above_ma20"] = (out["close"] > out["ma20"]).fillna(False)
    out["close_above_ma50"] = (out["close"] > out["ma50"]).fillna(False)
    out["ma20_gt_ma50"] = (out["ma20"] > out["ma50"]).fillna(False)

    vol = out["volume"]
    vs10 = out["vol_sma10"].replace(0, np.nan)
    vs20 = out["vol_sma20"].replace(0, np.nan)
    out["vol_dryup_ratio_10d"] = vol / vs10
    out["vol_dryup_ratio_20d"] = vol / vs20

    # Contraction: lower atr_pct vs 20d ago = more contraction
    ratio = out["atr_pct_vs_20d_ago"]
    out["volatility_contraction_raw"] = np.where(np.isfinite(ratio) & (ratio > 0), 1.0 / ratio, np.nan)

    def _tightness(n: int) -> pd.Series:
        cs = out["close"].rolling(n, min_periods=n)
        rng = (cs.max() - cs.min()) / cs.mean().replace(0, np.nan)
        return 1.0 - np.clip(rng / 0.12, 0.0, 1.0)

    out["close_tightness_5d"] = _tightness(5)
    out["close_tightness_10d"] = _tightness(10)

    # Right-side repair proxy: recent vol vs longer rolling median (auditable heuristic)
    volr = vol / out["vol_sma50"].replace(0, np.nan)
    quiet = volr.rolling(25, min_periods=10).median()
    recent5 = volr.rolling(5, min_periods=5).mean()
    out["right_side_repair_raw"] = recent5 / quiet.replace(0, np.nan)

    # Volume percentile rank vs prior 50 closes (exclusive current bar for ranking base)
    def _vol_pct_rank(s: pd.Series) -> float:
        if len(s) < 51:
            return np.nan
        cur = float(s.iloc[-1])
        hist = s.iloc[-51:-1].astype(float)
        hist = hist[np.isfinite(hist)]
        if len(hist) == 0 or not np.isfinite(cur):
            return np.nan
        return float((hist < cur).mean())

    out["vol_pct_rank_50_prior"] = out["volume"].rolling(51, min_periods=51).apply(_vol_pct_rank, raw=False)

    return out


def anti_drift_ok(mode: int, i: int, close: np.ndarray, ma20: np.ndarray, ma50: np.ndarray) -> bool:
    """
    mode 0 = off; 1 = close>close20d; 2 = + ma20_slope_10d>0; 3 = + close>ma20 & ma20>ma50.
    Slopes use precomputed series aligned at i.
    """
    if mode == 0:
        return True
    if i < 20:
        return False
    if not (np.isfinite(close[i]) and np.isfinite(close[i - 20])):
        return False
    m1 = close[i] > close[i - 20]
    if mode == 1:
        return m1
    if i < 10:
        return False
    s20 = (ma20[i] - ma20[i - 10]) / ma20[i - 10] if np.isfinite(ma20[i - 10]) and ma20[i - 10] > 0 else np.nan
    m2 = m1 and np.isfinite(s20) and (s20 > 0)
    if mode == 2:
        return m2
    m3 = m2 and np.isfinite(ma20[i]) and np.isfinite(ma50[i]) and (close[i] > ma20[i]) and (ma20[i] > ma50[i])
    return bool(m3)


def pp_bucket_accepts(bucket: str, rung: int) -> bool:
    b = bucket.lower().strip()
    if b == "rung2":
        return rung == 2
    if b == "rung3":
        return rung == 3
    if b == "ge2":
        return rung >= 2
    return False


def breakout_volume_ok(
    family: str,
    i: int,
    vol: np.ndarray,
    vol_sma20: np.ndarray,
    vol_sma50: np.ndarray,
    mult: float,
    vol_pct_rank: np.ndarray | None = None,
) -> bool:
    fam = family.lower().strip()
    v = float(vol[i]) if np.isfinite(vol[i]) else np.nan
    if not np.isfinite(v) or v <= 0:
        return False
    if fam == "sma20":
        s = float(vol_sma20[i])
        return np.isfinite(s) and s > 0 and v >= mult * s
    if fam == "sma50":
        s = float(vol_sma50[i])
        return np.isfinite(s) and s > 0 and v >= mult * s
    if fam == "pct50":
        r = float(vol_pct_rank[i]) if vol_pct_rank is not None else np.nan
        return np.isfinite(r) and r >= mult
    return False


def feature_row_at(
    ed: pd.DataFrame,
    i: int,
    base_days: int,
    base_start_i: int,
    base_high_roll: float,
    base_low_roll: float,
    pivot: float,
) -> dict[str, float | bool | int]:
    """Single-row feature dict at bar index i (signal context)."""
    row = ed.iloc[i]
    bh, bl = float(base_high_roll), float(base_low_roll)
    if bh <= 0 or bh <= bl:
        return {}
    depth = (bh - bl) / bh
    pos = (float(row["close"]) - bl) / (bh - bl)
    piv = float(pivot)
    dist = (piv - float(row["close"])) / piv if piv > 0 else np.nan
    width = bh - bl

    bi = int(i - base_start_i)
    in_right = bi >= (base_days // 2)

    out: dict[str, float | bool | int] = {
        "base_depth": float(depth),
        "base_pos_in_base": float(pos),
        "dist_to_pivot": float(dist) if np.isfinite(dist) else np.nan,
        "base_width": float(width),
        "atr_pct": float(row["atr_pct_14"]) if pd.notna(row.get("atr_pct_14")) else np.nan,
        "atr_pct_vs_20d_ago": float(row["atr_pct_vs_20d_ago"]) if pd.notna(row.get("atr_pct_vs_20d_ago")) else np.nan,
        "volatility_contraction_raw": float(row["volatility_contraction_raw"])
        if pd.notna(row.get("volatility_contraction_raw"))
        else np.nan,
        "vol_dryup_ratio_10d": float(row["vol_dryup_ratio_10d"]) if pd.notna(row.get("vol_dryup_ratio_10d")) else np.nan,
        "vol_dryup_ratio_20d": float(row["vol_dryup_ratio_20d"]) if pd.notna(row.get("vol_dryup_ratio_20d")) else np.nan,
        "close_tightness_5d": float(row["close_tightness_5d"]) if pd.notna(row.get("close_tightness_5d")) else np.nan,
        "close_tightness_10d": float(row["close_tightness_10d"]) if pd.notna(row.get("close_tightness_10d")) else np.nan,
        "right_side_repair_raw": float(row["right_side_repair_raw"]) if pd.notna(row.get("right_side_repair_raw")) else np.nan,
        "close_above_ma20": bool(row["close_above_ma20"]),
        "close_above_ma50": bool(row["close_above_ma50"]),
        "ma20_gt_ma50": bool(row["ma20_gt_ma50"]),
        "ma20_slope_10d": float(row["ma20_slope_10d"]) if pd.notna(row.get("ma20_slope_10d")) else np.nan,
        "ma50_slope_20d": float(row["ma50_slope_20d"]) if pd.notna(row.get("ma50_slope_20d")) else np.nan,
        "days_in_base": bi,
        "in_right_half_of_base": bool(in_right),
        "pp_in_right_half_of_base": bool(in_right),
    }
    return out


def pp_day_features(ed: pd.DataFrame, t: int) -> dict[str, float]:
    row = ed.iloc[t]
    c, h, l = float(row["close"]), float(row["high"]), float(row["low"])
    rng = h - l if h > l else np.nan
    cir = (c - l) / rng if np.isfinite(rng) and rng > 0 else np.nan
    v = float(row["volume"])
    vs20 = float(row["vol_sma20"]) if pd.notna(row.get("vol_sma20")) else np.nan
    vs50 = float(row["vol_sma50"]) if pd.notna(row.get("vol_sma50")) else np.nan
    return {
        "pp_day_vol_ratio_20": v / vs20 if np.isfinite(vs20) and vs20 > 0 else np.nan,
        "pp_day_vol_ratio_50": v / vs50 if np.isfinite(vs50) and vs50 > 0 else np.nan,
        "pp_day_close_in_range": float(cir) if np.isfinite(cir) else np.nan,
    }


def breakout_day_features(
    ed: pd.DataFrame,
    j: int,
    pivot: float,
    entry_buffer: float,
) -> dict[str, float]:
    row = ed.iloc[j]
    c, h, l = float(row["close"]), float(row["high"]), float(row["low"])
    rng = h - l if h > l else np.nan
    cir = (c - l) / rng if np.isfinite(rng) and rng > 0 else np.nan
    ma20 = float(row["ma20"]) if pd.notna(row.get("ma20")) else np.nan
    ext = (c / ma20 - 1.0) if np.isfinite(ma20) and ma20 > 0 else np.nan
    pivf = float(pivot)
    gap = (c / (pivf * (1.0 + entry_buffer)) - 1.0) if pivf > 0 else np.nan
    v = float(row["volume"])
    vs20 = float(row["vol_sma20"]) if pd.notna(row.get("vol_sma20")) else np.nan
    vs50 = float(row["vol_sma50"]) if pd.notna(row.get("vol_sma50")) else np.nan
    pct = float(row["vol_pct_rank_50_prior"]) if pd.notna(row.get("vol_pct_rank_50_prior")) else np.nan
    return {
        "breakout_vol_ratio_20": v / vs20 if np.isfinite(vs20) and vs20 > 0 else np.nan,
        "breakout_vol_ratio_50": v / vs50 if np.isfinite(vs50) and vs50 > 0 else np.nan,
        "breakout_vol_percentile_50": pct,
        "breakout_close_in_range": float(cir) if np.isfinite(cir) else np.nan,
        "breakout_gap_from_pivot": float(gap) if np.isfinite(gap) else np.nan,
        "breakout_extension_from_ma20": float(ext) if np.isfinite(ext) else np.nan,
    }


def compute_forward_labels(
    close: np.ndarray,
    open_: np.ndarray,
    entry_i: int,
) -> dict[str, float]:
    """
    Next-open entry at open[entry_i]. Forward closes use same indexing as legacy edge script:
    ret_H = close[entry_i + H] / entry_open - 1.
    Path stats over the next H bars use closes at entry_i+1 .. entry_i+H (H closes).
    """
    eo = float(open_[entry_i])
    out: dict[str, float] = {}
    n = len(close)
    if not np.isfinite(eo) or eo <= 0:
        for k in ("ret_5d", "ret_10d", "ret_15d", "ret_20d", "max_close_drawdown_10d", "max_close_drawdown_20d", "best_close_runup_10d", "best_close_runup_20d"):
            out[k] = np.nan
        return out

    def ret_at(h: int) -> float:
        j = entry_i + h
        if j >= n:
            return np.nan
        return float(close[j] / eo - 1.0)

    out["ret_5d"] = ret_at(5)
    out["ret_10d"] = ret_at(10)
    out["ret_15d"] = ret_at(15)
    out["ret_20d"] = ret_at(20)

    def path_extremes(h: int) -> tuple[float, float]:
        lo = entry_i + 1
        hi = min(entry_i + h, n - 1)
        if lo > hi:
            return np.nan, np.nan
        rel = close[lo : hi + 1] / eo - 1.0
        return float(np.nanmin(rel)), float(np.nanmax(rel))

    mdd10, run10 = path_extremes(10)
    mdd20, run20 = path_extremes(20)
    out["max_close_drawdown_10d"] = mdd10
    out["best_close_runup_10d"] = run10
    out["max_close_drawdown_20d"] = mdd20
    out["best_close_runup_20d"] = run20
    return out


def compute_candidate_mask(
    close: np.ndarray,
    base_high: np.ndarray,
    base_low: np.ndarray,
    pivot: np.ndarray,
    min_depth: float,
    max_depth: float,
    min_base_pos: float,
    max_dist_pivot: float,
) -> np.ndarray:
    """Boolean mask: rolling geometry passes filters (finite checks)."""
    bh, bl = base_high, base_low
    ok = np.isfinite(bh) & np.isfinite(bl) & (bh > 0) & (bh > bl)
    depth = (bh - bl) / np.where(bh > 0, bh, np.nan)
    pos = (close - bl) / np.where((bh - bl) > 0, (bh - bl), np.nan)
    piv = pivot
    dist = (piv - close) / np.where(np.isfinite(piv) & (piv > 0), piv, np.nan)
    ok &= np.isfinite(depth) & (depth >= min_depth) & (depth <= max_depth)
    ok &= np.isfinite(pos) & (pos >= min_base_pos)
    ok &= np.isfinite(dist) & (dist >= -0.02) & (dist <= max_dist_pivot)
    return ok & np.isfinite(piv) & (piv > 0)


def rolling_base_arrays(high: np.ndarray, low: np.ndarray, close: np.ndarray, bd: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rolling base_high, base_low, pivot=shifted prior base_high (numpy)."""
    n = len(close)
    bh = pd.Series(high).rolling(bd, min_periods=bd).max().to_numpy()
    bl = pd.Series(low).rolling(bd, min_periods=bd).min().to_numpy()
    pivot = np.roll(bh, 1)
    pivot[0] = np.nan
    return bh, bl, pivot
