"""
Market regime overlays — computed from stock panel and VNINDEX series.
M0: ex-VIN eligible universe EMA20/100 cloud_bull breadth (PRIMARY).
   Do NOT use regime_decomposition_breadth.csv as M0.
M1: VNINDEX EMA20/100 cloud_bull flag.
M2: ex-VIN index EMA20/100 cloud_bull flag.
M3: VIN group cloud breadth.
M4: VIN distortion flag (2025-01-01 onward, adjustable).
"""
from __future__ import annotations
import logging

import pandas as pd
import numpy as np

from pp_backtest.ema_levels.indicators import ema_cloud
from .config import (
    OUTPUT_DIR,
    VNINDEX_PARQUET,
    EX_VIN_SERIES_PATH,
    VIN_GROUP_SYMBOLS,
    EMA_FAST,
    EMA_SLOW,
    M0_NORMAL_THRESHOLD,
    M0_DEFENSIVE_THRESHOLD,
)

log = logging.getLogger(__name__)

VIN_DISTORTION_START = pd.Timestamp("2025-01-01")


def compute_m0_breadth(
    panel: pd.DataFrame,
    ex_vin: bool = True,
) -> pd.DataFrame:
    """
    Compute daily market cloud breadth (fraction of eligible universe with cloud_bull=1).
    Returns date-indexed DataFrame with columns:
      market_cloud_breadth, m0_label (normal/defensive/bear)
    """
    df = panel.copy()
    if ex_vin:
        df = df[~df["symbol"].isin(VIN_GROUP_SYMBOLS)]

    breadth = (
        df.groupby("date")["cloud_bull_20_100"]
        .mean()
        .reset_index()
        .rename(columns={"cloud_bull_20_100": "market_cloud_breadth"})
    )
    breadth["m0_label"] = pd.cut(
        breadth["market_cloud_breadth"],
        bins=[-np.inf, M0_DEFENSIVE_THRESHOLD, M0_NORMAL_THRESHOLD, np.inf],
        labels=["bear", "defensive", "normal"],
    ).astype(str)
    suffix = "ex_vin" if ex_vin else "full"
    breadth = breadth.rename(columns={
        "market_cloud_breadth": f"M0_{suffix}_breadth",
        "m0_label":             f"M0_{suffix}_label",
    })
    return breadth


def compute_m1_vnindex(vnindex_close: pd.Series, dates: pd.Index) -> pd.DataFrame:
    """VNINDEX EMA20/100 cloud_bull flag."""
    cloud = ema_cloud(vnindex_close, EMA_FAST, EMA_SLOW)
    df = pd.DataFrame({
        "date":    vnindex_close.index if hasattr(vnindex_close.index, "freq") else dates,
        "M1_vnindex_cloud_bull": cloud["cloud_bull"].astype(int).values,
    })
    return df


def compute_m2_ex_vin_index(ex_vin_df: pd.DataFrame) -> pd.DataFrame:
    """
    ex-VIN index EMA20/100 cloud_bull flag.
    ex_vin_df must have date + a close/index column.
    """
    close_col = [c for c in ex_vin_df.columns if c not in ("date",)][0]
    close = ex_vin_df.set_index("date")[close_col].sort_index()
    cloud = ema_cloud(close, EMA_FAST, EMA_SLOW)
    df = pd.DataFrame({
        "date":                ex_vin_df["date"].values,
        "M2_ex_vin_index_cloud_bull": cloud["cloud_bull"].astype(int).values,
    })
    return df


def compute_m3_vin_breadth(panel: pd.DataFrame) -> pd.DataFrame:
    """VIN group cloud breadth (fraction of VIN group symbols that are cloud_bull)."""
    vin = panel[panel["symbol"].isin(VIN_GROUP_SYMBOLS)]
    if vin.empty:
        return pd.DataFrame(columns=["date", "M3_vin_group_breadth"])
    breadth = (
        vin.groupby("date")["cloud_bull_20_100"]
        .mean()
        .reset_index()
        .rename(columns={"cloud_bull_20_100": "M3_vin_group_breadth"})
    )
    return breadth


def compute_m4_vin_distortion_flag(dates: pd.Series) -> pd.DataFrame:
    """Flag dates where VIN-group return distortion is likely (2025+)."""
    df = pd.DataFrame({"date": dates})
    df["M4_vin_distortion_flag"] = (
        pd.to_datetime(df["date"]) >= VIN_DISTORTION_START
    ).astype(int)
    return df


def build_all_regimes(
    panel: pd.DataFrame,
    vnindex_df: pd.DataFrame,
    ex_vin_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a date-level regime overlay table with M0–M4.
    Returns DataFrame indexed by date.
    """
    dates = panel["date"].drop_duplicates().sort_values()

    m0_ex = compute_m0_breadth(panel, ex_vin=True)
    m0_full = compute_m0_breadth(panel, ex_vin=False)

    vnix_close = vnindex_df.set_index("date")["close"].sort_index()
    m1 = compute_m1_vnindex(vnix_close, dates)

    m2 = compute_m2_ex_vin_index(ex_vin_df)
    m3 = compute_m3_vin_breadth(panel)
    m4 = compute_m4_vin_distortion_flag(dates)

    regimes = (
        m0_ex
        .merge(m0_full,  on="date", how="outer")
        .merge(m1,       on="date", how="outer")
        .merge(m2,       on="date", how="outer")
        .merge(m3,       on="date", how="outer")
        .merge(m4,       on="date", how="outer")
        .sort_values("date")
        .reset_index(drop=True)
    )

    out_path = OUTPUT_DIR / "regime_overlays.csv"
    regimes.to_csv(out_path, index=False)
    log.info("Regime overlays saved to %s  shape=%s", out_path, regimes.shape)
    return regimes
