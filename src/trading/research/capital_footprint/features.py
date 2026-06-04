"""
Capital Footprint Feature Engineering
======================================
Builds a daily ticker-level feature panel for the VN Capital Footprint research.

Data sources (all read-only):
  - data/fireant_ssot/ta_ohlcv_panel.parquet  (OHLCV + value traded, 2017-05-18+)
  - data/fireant_ssot/ta_vnindex.parquet       (VNINDEX daily, 2012+)
  - data/fireant_ssot/fa_quarterly.parquet     (FA quarterly, 2016+)
  - data/master/sector_map.csv                 (115-symbol sector map)
  - data/combined_regime_log_2012_now.csv      (market regime log)

NOT AVAILABLE (skipped cleanly):
  - Foreign institutional flow
  - Index/ETF membership / FTSE candidate lists
  - Broker revisions / target prices
  - Margin data (macro proxy only)

Lookahead guards:
  - All rolling features shift the rolling computation by 1 bar
  - FA features use 45-day publication lag (quarter-end + 45 days)
  - Forward returns use negative shifts (future data) — labels only, never features

Pandas 3.0 compatibility: uses groupby().transform() instead of groupby().apply()
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

DATA_DIR = Path("data")
SSOT_DIR = DATA_DIR / "fireant_ssot"
MASTER_DIR = DATA_DIR / "master"
CF_DIR = DATA_DIR / "research" / "capital_footprint"

FEATURE_START_DATE = "2018-01-01"
FA_PUB_LAG_DAYS = 45


# ── Data loaders ─────────────────────────────────────────────────────────────

def load_ohlcv(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = data_dir / "fireant_ssot" / "ta_ohlcv_panel.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def load_vnindex(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = data_dir / "fireant_ssot" / "ta_vnindex.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_sector_map(data_dir: Path = DATA_DIR, fa: Optional[pd.DataFrame] = None) -> dict:
    """Return symbol -> sector_primary. ICB fallback for unmatched symbols."""
    sm_path = data_dir / "master" / "sector_map.csv"
    sm = pd.read_csv(sm_path)
    result: dict = sm.set_index("symbol")["primary_sector"].to_dict()
    if fa is not None:
        icb_map = (
            fa[["symbol", "icbName"]]
            .dropna(subset=["icbName"])
            .drop_duplicates("symbol")
            .set_index("symbol")["icbName"]
            .to_dict()
        )
        for sym, icb in icb_map.items():
            if sym not in result:
                result[sym] = icb
    return result


def load_regime_log(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = data_dir / "combined_regime_log_2012_now.csv"
    df = pd.read_csv(path, low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_fa_quarterly(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = data_dir / "fireant_ssot" / "fa_quarterly.parquet"
    return pd.read_parquet(path)


# ── Rolling helper via transform (pandas 3.0 compatible) ─────────────────────

def _sym_transform(panel: pd.DataFrame, col: str, fn) -> pd.Series:
    """Apply fn to each symbol group of col. Returns aligned Series."""
    return panel.groupby("symbol")[col].transform(fn)


def _roll_mean_s(s: pd.Series, w: int, min_p: Optional[int] = None) -> pd.Series:
    if min_p is None:
        min_p = max(1, w // 2)
    return s.rolling(w, min_periods=min_p).mean().shift(1)


def _roll_std_s(s: pd.Series, w: int, min_p: Optional[int] = None) -> pd.Series:
    if min_p is None:
        min_p = max(2, w // 2)
    return s.rolling(w, min_periods=min_p).std().shift(1)


def _roll_max_s(s: pd.Series, w: int, min_p: Optional[int] = None) -> pd.Series:
    if min_p is None:
        min_p = max(1, w // 2)
    return s.rolling(w, min_periods=min_p).max().shift(1)


def _roll_sum_s(s: pd.Series, w: int, min_p: Optional[int] = None) -> pd.Series:
    if min_p is None:
        min_p = max(1, w // 2)
    return s.rolling(w, min_periods=min_p).sum()  # no shift for accumulation counts


def _ema_s(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean().shift(1)


# ── Section A: Liquidity ─────────────────────────────────────────────────────

def add_liquidity_features(panel: pd.DataFrame) -> pd.DataFrame:
    """ADV, turnover z-scores, cross-sectional liquidity ranks."""
    for w, col in [(20, "adv20_vnd"), (50, "adv50_vnd"), (120, "adv120_vnd")]:
        min_p = max(1, w // 2)
        panel[col] = _sym_transform(panel, "value",
                                    lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).mean().shift(1))

    for w, z_col in [(20, "turnover_z_20d"), (60, "turnover_z_60d")]:
        min_p = max(2, w // 2)
        mu = _sym_transform(panel, "value",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).mean().shift(1))
        sd = _sym_transform(panel, "value",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).std().shift(1))
        panel[z_col] = (panel["value"] - mu) / sd.replace(0.0, np.nan)

    panel["liquidity_rank_market"] = panel.groupby("date")["adv50_vnd"].rank(pct=True, na_option="bottom")
    if "sector_primary" in panel.columns:
        panel["liquidity_rank_sector"] = panel.groupby(["date", "sector_primary"])["adv50_vnd"].rank(
            pct=True, na_option="bottom"
        )
    else:
        panel["liquidity_rank_sector"] = panel["liquidity_rank_market"]

    return panel


# ── Section B: Relative Strength ─────────────────────────────────────────────

def add_rs_features(panel: pd.DataFrame, vnindex: pd.DataFrame) -> pd.DataFrame:
    """Return series, market/sector RS, ranks, persistence score."""
    # Stock returns (no shift needed — pct_change uses past data)
    for d in [20, 60, 120, 252]:
        panel[f"ret_{d}d"] = _sym_transform(panel, "close", lambda s, d=d: s.pct_change(d))

    # VNINDEX returns
    vni = vnindex[["date", "close"]].copy()
    for d in [20, 60, 120]:
        vni[f"vni_ret_{d}d"] = vni["close"].pct_change(d)
    vni_rets = vni[["date", "vni_ret_20d", "vni_ret_60d", "vni_ret_120d"]].copy()
    panel = panel.merge(vni_rets, on="date", how="left")

    for d in [20, 60, 120]:
        panel[f"rel_ret_vnindex_{d}d"] = panel[f"ret_{d}d"] - panel[f"vni_ret_{d}d"]

    # Sector median returns
    if "sector_primary" in panel.columns:
        for d in [20, 60, 120]:
            sector_med = panel.groupby(["date", "sector_primary"])[f"ret_{d}d"].transform("median")
            panel[f"sector_ret_{d}d"] = sector_med
            panel[f"rel_ret_sector_{d}d"] = panel[f"ret_{d}d"] - sector_med
    else:
        for d in [20, 60, 120]:
            panel[f"sector_ret_{d}d"] = np.nan
            panel[f"rel_ret_sector_{d}d"] = np.nan

    # Cross-sectional RS ranks
    for d in [20, 60, 120]:
        panel[f"rs_rank_market_{d}d"] = panel.groupby("date")[f"ret_{d}d"].rank(pct=True, na_option="bottom")
        if "sector_primary" in panel.columns:
            panel[f"rs_rank_sector_{d}d"] = panel.groupby(["date", "sector_primary"])[f"ret_{d}d"].rank(
                pct=True, na_option="bottom"
            )

    panel["rs_persistence_score"] = panel[["rs_rank_market_20d", "rs_rank_market_60d", "rs_rank_market_120d"]].mean(axis=1)
    return panel


# ── Section C: Price-Volume Accumulation ─────────────────────────────────────

def add_price_volume_features(panel: pd.DataFrame) -> pd.DataFrame:
    """CLV, accumulation/distribution counts, up/down value ratio, breakout flags."""
    # Close location value
    rng = (panel["high"] - panel["low"]).replace(0.0, np.nan)
    panel["close_location_value"] = ((panel["close"] - panel["low"]) / rng).clip(0, 1).fillna(0.5)
    panel["weekly_close_location_value"] = _sym_transform(
        panel, "close_location_value", lambda s: s.rolling(5, min_periods=3).mean()
    )

    # Value z-scores
    for w, col in [(20, "value_z_20d"), (60, "value_z_60d")]:
        min_p = max(2, w // 2)
        mu = _sym_transform(panel, "value",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).mean().shift(1))
        sd = _sym_transform(panel, "value",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).std().shift(1))
        panel[col] = (panel["value"] - mu) / sd.replace(0.0, np.nan)

    # ADV for accumulation/distribution day definition
    adv20 = _sym_transform(panel, "value",
                           lambda s: s.rolling(20, min_periods=10).mean().shift(1))
    adv50 = _sym_transform(panel, "value",
                           lambda s: s.rolling(50, min_periods=25).mean().shift(1))

    # Breakout volume: value > 1.5*ADV50 AND close > prior 60d high
    high60 = _sym_transform(panel, "high",
                            lambda s: s.rolling(60, min_periods=30).max().shift(1))
    panel["breakout_volume_flag"] = ((panel["value"] > 1.5 * adv50) & (panel["close"] > high60)).astype(int)

    # Up/down classification (compare to prior close within symbol group)
    prev_close = _sym_transform(panel, "close", lambda s: s.shift(1))
    up = (panel["close"] > prev_close).astype(float)
    dn = (panel["close"] < prev_close).astype(float)

    # Accumulation / distribution days
    acc = (up.astype(bool)) & (panel["close_location_value"] >= 0.65) & (panel["value"] >= 1.2 * adv20)
    dist = (dn.astype(bool)) & (panel["close_location_value"] <= 0.35) & (panel["value"] >= 1.2 * adv20)
    panel["accumulation_day"] = acc.astype(int)
    panel["distribution_day"] = dist.astype(int)

    panel["accumulation_day_count_20d"] = _sym_transform(
        panel, "accumulation_day", lambda s: s.rolling(20, min_periods=10).sum()
    )
    panel["distribution_day_count_20d"] = _sym_transform(
        panel, "distribution_day", lambda s: s.rolling(20, min_periods=10).sum()
    )
    panel["net_accumulation_score"] = panel["accumulation_day_count_20d"] - panel["distribution_day_count_20d"]

    # Up/down value sums (need per-symbol rolling)
    panel["_up_val"] = panel["value"] * up
    panel["_dn_val"] = panel["value"] * dn
    for w, suffix in [(20, "20d"), (60, "60d")]:
        min_p = max(1, w // 2)
        up_sum = _sym_transform(panel, "_up_val",
                                lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).sum())
        dn_sum = _sym_transform(panel, "_dn_val",
                                lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).sum())
        panel[f"up_day_value_sum_{suffix}"] = up_sum
        panel[f"down_day_value_sum_{suffix}"] = dn_sum
        panel[f"up_down_value_ratio_{suffix}"] = up_sum / dn_sum.replace(0.0, np.nan)
    panel.drop(columns=["_up_val", "_dn_val"], inplace=True)

    # Dry-up pullback: price within 8% of prior 20d high + volume < 0.7x ADV20
    high20 = _sym_transform(panel, "high", lambda s: s.rolling(20, min_periods=10).max().shift(1))
    pullback_pct = ((high20 - panel["close"]) / high20.replace(0.0, np.nan)).fillna(1.0)
    panel["dry_up_pullback_flag"] = ((pullback_pct < 0.08) & (panel["value"] < 0.7 * adv20)).astype(int)

    # ATR14-based flags
    prev_c = _sym_transform(panel, "close", lambda s: s.shift(1))
    tr = pd.concat([
        panel["high"] - panel["low"],
        (panel["high"] - prev_c).abs(),
        (panel["low"] - prev_c).abs(),
    ], axis=1).max(axis=1)
    atr14 = _sym_transform(
        pd.DataFrame({"symbol": panel["symbol"], "tr": tr}),
        "tr",
        lambda s: s.rolling(14, min_periods=7).mean().shift(1)
    )
    panel["tight_close_flag"] = ((panel["high"] - panel["low"]) < 1.5 * atr14).astype(int)
    panel["range_expansion_flag"] = ((panel["high"] - panel["low"]) > 2.0 * atr14).astype(int)

    return panel


# ── Section D: Trend Features ─────────────────────────────────────────────────

def add_trend_features(panel: pd.DataFrame) -> pd.DataFrame:
    """EMA clouds, base tightness, near-high flags."""
    for span in [20, 50, 100, 200]:
        e = _sym_transform(panel, "close",
                           lambda s, sp=span: s.ewm(span=sp, adjust=False).mean().shift(1))
        panel[f"ema{span}"] = e
        panel[f"above_ema{span}"] = (panel["close"] > e).astype(int)
        panel[f"distance_to_ema{span}"] = (panel["close"] - e) / e.replace(0.0, np.nan)

    panel["cloud_bull_20_100"] = (panel["ema20"] > panel["ema100"]).astype(int)
    panel["ema20_above_ema100"] = panel["cloud_bull_20_100"]
    panel["ema50_above_ema200"] = (panel["ema50"] > panel["ema200"]).astype(int)

    for w in [20, 60]:
        min_p = max(2, w // 2)
        mu = _sym_transform(panel, "close",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).mean().shift(1))
        sd = _sym_transform(panel, "close",
                            lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).std().shift(1))
        panel[f"base_tightness_{w}d"] = (sd / mu.replace(0.0, np.nan))

    for w in [60, 120]:
        min_p = max(1, w // 2)
        roll_h = _sym_transform(panel, "high",
                                lambda s, w=w, m=min_p: s.rolling(w, min_periods=m).max().shift(1))
        panel[f"near_high_{w}d"] = ((panel["close"] / roll_h.replace(0.0, np.nan)) > 0.95).astype(int)
        panel[f"new_high_{w}d_flag"] = (panel["close"] > roll_h).astype(int)

    return panel


# ── Section E: Sector Rotation ────────────────────────────────────────────────

def add_sector_rotation_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Sector-level aggregation: RS rank, breadth, rotation score."""
    if "sector_primary" not in panel.columns:
        panel["sector_rotation_score"] = 0.5
        return panel

    for d in [20, 60]:
        ret_col = f"ret_{d}d"
        if ret_col not in panel.columns:
            continue
        # Sector RS rank among all sectors on each date
        panel[f"sector_rs_rank_{d}d"] = panel.groupby("date")[f"sector_ret_{d}d"].rank(pct=True, na_option="bottom") \
            if f"sector_ret_{d}d" in panel.columns else np.nan

        vni_col = f"vni_ret_{d}d"
        if f"sector_ret_{d}d" in panel.columns and vni_col in panel.columns:
            panel[f"sector_rel_vnindex_{d}d"] = panel[f"sector_ret_{d}d"] - panel[vni_col]

    # Sector breadth
    if "above_ema50" in panel.columns:
        panel["sector_breadth_above_ma50"] = panel.groupby(["date", "sector_primary"])["above_ema50"].transform("mean")
    if "above_ema100" in panel.columns:
        panel["sector_breadth_above_ma100"] = panel.groupby(["date", "sector_primary"])["above_ema100"].transform("mean")

    # Leader and breakout counts
    if "rs_rank_market_20d" in panel.columns:
        panel["_is_leader"] = (panel["rs_rank_market_20d"] >= 0.8).astype(int)
        panel["sector_leader_count"] = panel.groupby(["date", "sector_primary"])["_is_leader"].transform("sum")
        panel.drop(columns=["_is_leader"], inplace=True)

    if "breakout_volume_flag" in panel.columns:
        panel["sector_breakout_count"] = panel.groupby(["date", "sector_primary"])["breakout_volume_flag"].transform("sum")

    # Sector rotation composite (0-1)
    rot_parts = []
    if "sector_rel_vnindex_20d" in panel.columns:
        rot_parts.append(
            panel.groupby("date")["sector_rel_vnindex_20d"].transform(
                lambda x: x.rank(pct=True, na_option="bottom")
            ) * 0.30
        )
    if "sector_breadth_above_ma50" in panel.columns:
        rot_parts.append(panel["sector_breadth_above_ma50"].fillna(0.5) * 0.25)
    if "sector_rs_rank_20d" in panel.columns:
        rot_parts.append(panel["sector_rs_rank_20d"].fillna(0.5) * 0.25)
    if "sector_breakout_count" in panel.columns:
        max_bc = panel.groupby("date")["sector_breakout_count"].transform("max").replace(0.0, 1.0)
        rot_parts.append((panel["sector_breakout_count"].fillna(0) / max_bc).clip(0, 1) * 0.20)

    if rot_parts:
        panel["sector_rotation_score"] = sum(rot_parts).clip(0, 1)
    else:
        panel["sector_rotation_score"] = 0.5

    return panel


# ── Section F: Market Regime ──────────────────────────────────────────────────

def _compute_breadth_from_panel(panel: pd.DataFrame) -> pd.Series:
    """Compute % stocks above MA50 per date from the OHLCV panel itself.

    Falls back to above_ema50 if already computed, otherwise computes a
    50-day rolling MA on close. Returns a Series indexed like panel with
    values in [0, 100].
    """
    if "above_ema50" in panel.columns:
        return panel.groupby("date")["above_ema50"].transform("mean") * 100.0
    # Compute MA50 per symbol and flag
    ma50 = _sym_transform(panel, "close",
                          lambda s: s.rolling(50, min_periods=25).mean().shift(1))
    above = (panel["close"] > ma50).astype(float)
    return above.groupby(panel["date"]).transform("mean") * 100.0


def add_regime_features(panel: pd.DataFrame, regime_log: pd.DataFrame) -> pd.DataFrame:
    """Join regime log features to the panel by date."""
    r = regime_log.copy()

    if "ma50" in r.columns and "close" in r.columns:
        r["close_num"] = pd.to_numeric(r["close"], errors="coerce")
        r["ma50_num"] = pd.to_numeric(r["ma50"], errors="coerce")
        r["ma200_num"] = pd.to_numeric(r.get("ma200", pd.Series(np.nan, index=r.index)), errors="coerce")
        r["vnindex_above_ema50"] = (r["close_num"] > r["ma50_num"]).astype(int)
        r["vnindex_above_ema200"] = (r["close_num"] > r["ma200_num"]).astype(int)

    if "ma50_above_ma200" in r.columns:
        r["vnindex_cloud_bull"] = pd.to_numeric(r["ma50_above_ma200"], errors="coerce").fillna(0).astype(int)
    elif "ma50_num" in r.columns and "ma200_num" in r.columns:
        r["vnindex_cloud_bull"] = (r["ma50_num"] > r["ma200_num"]).astype(int)

    if "breadth_pct" in r.columns:
        r["market_pct_above_ma50"] = pd.to_numeric(r["breadth_pct"], errors="coerce")

    keep = [
        "date", "market_status_combined", "allow_new_buys", "breadth_pct",
        "distribution_count_20d", "vnindex_above_ema50", "vnindex_above_ema200",
        "vnindex_cloud_bull", "market_pct_above_ma50",
    ]
    keep = [c for c in keep if c in r.columns]
    panel = panel.merge(r[keep].copy(), on="date", how="left")

    # Fix: breadth_pct from regime log is often all-NaN.
    # Compute from raw OHLCV panel using above_ema50.
    if "market_pct_above_ma50" not in panel.columns or panel["market_pct_above_ma50"].isna().all():
        panel["market_pct_above_ma50"] = _compute_breadth_from_panel(panel)
    else:
        # Fill any NaN gaps with panel-computed breadth
        nan_mask = panel["market_pct_above_ma50"].isna()
        if nan_mask.any():
            panel.loc[nan_mask, "market_pct_above_ma50"] = _compute_breadth_from_panel(panel)[nan_mask]

    # Recompute regime bucket using the fixed breadth.
    # NOTE: regime log only has 'correction'/'downtrend' status — no 'uptrend'.
    # Use breadth thresholds alone so BULL buckets appear when breadth is high.
    def _bucket_breadth(bp) -> str:
        try:
            bp = float(bp)
        except (TypeError, ValueError):
            bp = 50.0
        if bp >= 60:
            return "BULL_BROAD"
        elif bp >= 50:
            return "BULL_NARROW"
        elif bp >= 40:
            return "NEUTRAL"
        elif bp >= 30:
            return "BEAR"
        else:
            return "STRESS"

    panel["breadth_regime_bucket"] = [
        _bucket_breadth(bp) for bp in panel["market_pct_above_ma50"]
    ]

    return panel


# ── Section I: Fundamental Confirmation ──────────────────────────────────────

def add_fundamental_features(panel: pd.DataFrame, fa: pd.DataFrame) -> pd.DataFrame:
    """Add YoY growth and quality score with 45-day publication lag."""
    import calendar

    qend_month = {1: 3, 2: 6, 3: 9, 4: 12}
    rev_col = "financialValues_TotalRevenue"
    np_col = "financialValues_ProfitAfterTax"

    if rev_col not in fa.columns or np_col not in fa.columns:
        return panel

    fa = fa[["symbol", "year", "quarter", rev_col, np_col]].copy()
    fa[["year", "quarter"]] = fa[["year", "quarter"]].apply(pd.to_numeric, errors="coerce")
    fa[[rev_col, np_col]] = fa[[rev_col, np_col]].apply(pd.to_numeric, errors="coerce")
    fa = fa.dropna(subset=["year", "quarter"])

    def _avail_date(row) -> pd.Timestamp:
        try:
            yr, mo = int(row["year"]), qend_month.get(int(row["quarter"]), 12)
            day = calendar.monthrange(yr, mo)[1]
            return pd.Timestamp(yr, mo, day) + pd.Timedelta(days=FA_PUB_LAG_DAYS)
        except Exception:
            return pd.NaT

    fa["avail_date"] = fa.apply(_avail_date, axis=1)
    fa = fa.dropna(subset=["avail_date"])

    # YoY growth vs same quarter prior year
    fa = fa.sort_values(["symbol", "year", "quarter"])
    fa["rev_ly"] = fa.groupby(["symbol", "quarter"])[rev_col].shift(1)
    fa["np_ly"] = fa.groupby(["symbol", "quarter"])[np_col].shift(1)
    fa["revenue_growth_yoy"] = (fa[rev_col] / fa["rev_ly"].replace(0, np.nan) - 1).clip(-2, 10)
    fa["np_growth_yoy"] = (fa[np_col] / fa["np_ly"].replace(0, np.nan) - 1).clip(-2, 10)

    fa["np_growth_prev"] = fa.groupby("symbol")["np_growth_yoy"].shift(1)
    fa["earnings_acceleration_flag"] = (
        (fa["np_growth_yoy"] > 0.15) & (fa["np_growth_yoy"] > fa["np_growth_prev"])
    ).astype(int)

    rev_rank = fa.groupby(["year", "quarter"])["revenue_growth_yoy"].rank(pct=True, na_option="bottom")
    np_rank = fa.groupby(["year", "quarter"])["np_growth_yoy"].rank(pct=True, na_option="bottom")
    fa["fundamental_quality_score"] = (rev_rank * 0.4 + np_rank * 0.6).clip(0, 1)

    fa_sub = fa[["symbol", "avail_date", "revenue_growth_yoy", "np_growth_yoy",
                 "earnings_acceleration_flag", "fundamental_quality_score"]].copy()
    fa_sub = fa_sub.rename(columns={"avail_date": "date"}).sort_values("date")

    # merge_asof requires both DataFrames globally sorted by the 'on' key (date)
    panel_sorted = panel.sort_values("date")
    merged = pd.merge_asof(
        panel_sorted,
        fa_sub,
        on="date",
        by="symbol",
        direction="backward",
    )
    return merged.sort_values(["symbol", "date"]).reset_index(drop=True)


# ── Section G: Phase-Aware Features ──────────────────────────────────────────

def add_phase_features(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Phase-aware features for the 6-label classifier.

    Depends on: add_price_volume_features and add_trend_features outputs.
    All features are backward-looking (no lookahead).
    """
    # pullback_depth_from_high: how far close is below the 20d high (≤0)
    high20 = _sym_transform(panel, "high",
                            lambda s: s.rolling(20, min_periods=10).max().shift(1))
    panel["pullback_depth_from_high"] = (
        (panel["close"] - high20) / high20.replace(0.0, np.nan)
    ).fillna(0.0).clip(-0.5, 0.0)

    # distribution_cluster_flag: ≥3 distribution days in last 10 bars
    if "distribution_day" in panel.columns:
        dist_10d = _sym_transform(panel, "distribution_day",
                                  lambda s: s.rolling(10, min_periods=5).sum())
        panel["distribution_cluster_flag"] = (dist_10d >= 3).astype(int)
    else:
        panel["distribution_cluster_flag"] = 0

    # post_breakout_failure_flag: broke above 60d high in past 1-5 bars, now back below
    if "new_high_60d_flag" in panel.columns:
        was_breakout = _sym_transform(
            panel, "new_high_60d_flag",
            lambda s: s.rolling(5, min_periods=1).max().shift(1)
        )
        high60 = _sym_transform(panel, "high",
                                lambda s: s.rolling(60, min_periods=30).max().shift(1))
        panel["post_breakout_failure_flag"] = (
            (was_breakout >= 1) & (panel["close"] < high60 * 0.97)
        ).astype(int)
    else:
        panel["post_breakout_failure_flag"] = 0

    # dry_up_near_high_with_trend_support: composite confirmation signal
    dup = panel.get("dry_up_pullback_flag", pd.Series(0, index=panel.index)).fillna(0)
    nh = panel.get("near_high_60d", pd.Series(0, index=panel.index)).fillna(0)
    cb = panel.get("cloud_bull_20_100", pd.Series(0, index=panel.index)).fillna(0)
    panel["dry_up_near_high_with_trend_support"] = ((dup == 1) & (nh == 1) & (cb == 1)).astype(int)

    # prior_runup_20d/60d: explicit aliases for clarity
    if "ret_20d" in panel.columns:
        panel["prior_runup_20d"] = panel["ret_20d"]
    if "ret_60d" in panel.columns:
        panel["prior_runup_60d"] = panel["ret_60d"]

    return panel


# ── Forward Returns (labels — never use as features) ─────────────────────────

def add_forward_returns(panel: pd.DataFrame, vnindex: pd.DataFrame) -> pd.DataFrame:
    """Compute forward return labels. MUST NOT be used as predictor features."""
    for d in [5, 10, 20, 60, 120]:
        panel[f"fwd_ret_{d}d"] = _sym_transform(
            panel, "close", lambda s, d=d: s.shift(-d) / s - 1
        )

    for d in [20, 60]:
        fwd_h = _sym_transform(panel, "high",
                               lambda s, d=d: s[::-1].rolling(d, min_periods=1).max()[::-1].shift(-(d - 1)))
        fwd_l = _sym_transform(panel, "low",
                               lambda s, d=d: s[::-1].rolling(d, min_periods=1).min()[::-1].shift(-(d - 1)))
        panel[f"fwd_max_gain_{d}d"] = (fwd_h / panel["close"] - 1).clip(lower=0)
        panel[f"fwd_max_drawdown_{d}d"] = (fwd_l / panel["close"] - 1).clip(upper=0)

    panel["tp1_18pct_hit_120d"] = (panel["fwd_max_gain_60d"] >= 0.18).astype(int)

    # Alpha vs VNINDEX
    vni_c = vnindex.set_index("date")["close"]
    for d in [20, 60, 120]:
        vni_fwd = (vni_c.shift(-d) / vni_c - 1).rename(f"vni_fwd_{d}d")
        vni_fwd_df = vni_fwd.reset_index()
        panel = panel.merge(vni_fwd_df, on="date", how="left")
        panel[f"fwd_alpha_{d}d_vs_vnindex"] = panel[f"fwd_ret_{d}d"] - panel[f"vni_fwd_{d}d"]
        panel.drop(columns=[f"vni_fwd_{d}d"], inplace=True)

    return panel


# ── Main Builder ──────────────────────────────────────────────────────────────

def build_feature_panel(
    data_dir: Path = DATA_DIR,
    start_date: str = FEATURE_START_DATE,
    min_adv50_vnd: float = 1e9,
    include_fa: bool = True,
) -> pd.DataFrame:
    """
    Build the full Capital Footprint feature panel.

    Args:
        data_dir: Root data directory.
        start_date: Earliest date to include in output (warmup excluded).
        min_adv50_vnd: Minimum ADV50 filter (VND). 0 = no filter.
        include_fa: Whether to join FA fundamental features.

    Returns:
        DataFrame with all features + forward return labels.
        Forward return columns must NOT be used as predictor features.
    """
    print("Loading data sources...")
    ohlcv = load_ohlcv(data_dir)
    vnindex = load_vnindex(data_dir)
    regime = load_regime_log(data_dir)
    fa = load_fa_quarterly(data_dir) if include_fa else None

    sector_map = load_sector_map(data_dir, fa=fa)
    ohlcv["sector_primary"] = ohlcv["symbol"].map(sector_map).fillna("Unknown")

    print(f"  OHLCV: {ohlcv.shape[0]:,} rows, {ohlcv['symbol'].nunique():,} symbols")
    print(f"  Sector coverage: {ohlcv['sector_primary'].ne('Unknown').mean():.1%}")

    panel = ohlcv.copy()

    print("Computing liquidity features (A)...")
    panel = add_liquidity_features(panel)

    print("Computing relative strength features (B)...")
    panel = add_rs_features(panel, vnindex.copy())

    print("Computing price-volume accumulation features (C)...")
    panel = add_price_volume_features(panel)

    print("Computing trend features (D)...")
    panel = add_trend_features(panel)

    print("Computing sector rotation features (E)...")
    panel = add_sector_rotation_features(panel)

    print("Joining market regime features (F)...")
    panel = add_regime_features(panel, regime)

    print("Computing phase-aware features (G)...")
    panel = add_phase_features(panel)

    if include_fa and fa is not None:
        print("Computing fundamental features (I)...")
        panel = add_fundamental_features(panel, fa)

    print("Computing forward return labels...")
    panel = add_forward_returns(panel, vnindex)

    # Drop warmup period
    panel = panel[panel["date"] >= pd.Timestamp(start_date)].copy()

    if min_adv50_vnd > 0:
        pre = len(panel)
        panel = panel[panel["adv50_vnd"].fillna(0) >= min_adv50_vnd].copy()
        post = len(panel)
        print(f"  Liquidity filter (ADV50 >= {min_adv50_vnd/1e9:.0f}bn VND): {pre:,} -> {post:,} rows")

    print(f"Feature panel: {panel.shape[0]:,} rows, {panel.shape[1]} cols")
    print(f"  Date range: {panel['date'].min().date()} to {panel['date'].max().date()}")
    print(f"  Symbols: {panel['symbol'].nunique():,}")

    return panel.reset_index(drop=True)
