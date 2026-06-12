"""Load VNINDEX raw, ex-VIN proxy, and VIN group basket series."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
VNINDEX_CSV = REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv"
EX_VIN_SERIES_CSV = REPO / "data" / "research" / "vnindex_ex_vin_daily_series.csv"
VIN_SYMBOLS = ("VIC", "VHM", "VRE")
VPL_SYMBOL = "VPL"
STOCK_LEGACY = REPO / "minervini_backtest" / "data" / "raw"
STOCK_NEW = REPO / "data" / "stocks"
DATA_START = pd.Timestamp("2012-01-01")


@dataclass
class IndexViewMeta:
    index_view: str
    label: str
    is_proxy: bool
    notes: str
    distribution_volume_available: bool = True
    ohlc_synthetic_from_close: bool = False


def _load_vnindex_csv() -> pd.DataFrame:
    df = pd.read_csv(VNINDEX_CSV)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df.rename(columns={"close": "close", "volume": "volume"})


def _load_stock(symbol: str) -> pd.DataFrame:
    leg = STOCK_LEGACY / f"{symbol}.csv"
    neu = STOCK_NEW / f"{symbol}.csv"
    if leg.exists():
        df = pd.read_csv(leg)
        df["close"] = df["close"].astype(float) / 1000.0
    elif neu.exists():
        df = pd.read_csv(neu)
    else:
        return pd.DataFrame(columns=["date", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    cols = ["date", "close"]
    if "volume" in df.columns:
        cols.append("volume")
    if "high" in df.columns:
        cols.append("high")
    if "low" in df.columns:
        cols.append("low")
    return df[cols].sort_values("date").reset_index(drop=True)


def load_index_views(
    *,
    start: Optional[str] = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, IndexViewMeta], list[str]]:
    """Return {view_id: ohlcv_df}, metadata, warnings."""
    warnings: list[str] = []
    start_ts = pd.Timestamp(start) if start else DATA_START
    views: dict[str, pd.DataFrame] = {}
    meta: dict[str, IndexViewMeta] = {}

    raw = _load_vnindex_csv()
    raw = raw[raw["date"] >= start_ts].copy()
    if raw.empty:
        warnings.append("VNINDEX CSV empty after start filter")
    else:
        views["vnindex_raw"] = raw[["date", "open", "high", "low", "close", "volume"]].copy()
        meta["vnindex_raw"] = IndexViewMeta(
            index_view="vnindex_raw",
            label="VNINDEX native (CSV)",
            is_proxy=False,
            notes="FireAnt/minervini VNINDEX.csv",
        )

    if EX_VIN_SERIES_CSV.exists():
        ex = pd.read_csv(EX_VIN_SERIES_CSV)
        ex["date"] = pd.to_datetime(ex["date"])
        ex = ex[ex["date"] >= start_ts].sort_values("date")
        if "close_ex_vin" in ex.columns:
            ohlcv = pd.DataFrame(
                {
                    "date": ex["date"],
                    "close": ex["close_ex_vin"].astype(float),
                    "volume": ex.get("volume_ex_vin", pd.Series(np.nan, index=ex.index)).astype(float),
                    "open": ex["close_ex_vin"].astype(float),
                    "high": ex["close_ex_vin"].astype(float),
                    "low": ex["close_ex_vin"].astype(float),
                }
            )
            views["ex_vin_proxy"] = ohlcv.reset_index(drop=True)
            meta["ex_vin_proxy"] = IndexViewMeta(
                index_view="ex_vin_proxy",
                label="ex-VIN proxy (cap-weight decomposition)",
                is_proxy=True,
                notes="NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology",
                ohlc_synthetic_from_close=True,
            )
    else:
        warnings.append("ex_vin_proxy unavailable: vnindex_ex_vin_daily_series.csv missing")

    vin_price_frames: list[pd.DataFrame] = []
    vin_vol_frames: list[pd.DataFrame] = []
    vpl_bars = 0
    for sym in list(VIN_SYMBOLS) + [VPL_SYMBOL]:
        s = _load_stock(sym)
        if s.empty:
            if sym in VIN_SYMBOLS:
                warnings.append(f"VIN symbol {sym} OHLCV missing")
            continue
        if sym == VPL_SYMBOL:
            vpl_bars = len(s)
            if vpl_bars < 252:
                warnings.append(f"VPL excluded from VIN group index ({vpl_bars} bars < 252)")
            continue
        idx = s.set_index("date")
        vin_price_frames.append(idx[["close"]].rename(columns={"close": sym}))
        if "volume" in s.columns:
            vin_vol_frames.append(idx[["volume"]].rename(columns={"volume": f"vol_{sym}"}))
        else:
            warnings.append(f"VIN symbol {sym} missing volume column")

    if vin_price_frames:
        vin = pd.concat(vin_price_frames, axis=1)
        if vin_vol_frames:
            vin = vin.join(pd.concat(vin_vol_frames, axis=1), how="left")
        vin = vin.reset_index()
        vin = vin[vin["date"] >= start_ts].sort_values("date")
        price_cols = [c for c in vin.columns if c in VIN_SYMBOLS]
        if price_cols:
            rets = vin[price_cols].pct_change()
            ew = (1.0 + rets.mean(axis=1, skipna=True)).cumprod()
            ew.iloc[0] = 1.0
            base = 1000.0
            close_vin = base * ew
            vol_cols = [c for c in vin.columns if c.startswith("vol_")]
            aggregate_volume = pd.Series(np.nan, index=vin.index)
            aggregate_turnover = pd.Series(np.nan, index=vin.index)
            if vol_cols:
                aggregate_volume = vin[vol_cols].sum(axis=1, min_count=1)
                turnover_parts = []
                for sym in VIN_SYMBOLS:
                    vc = f"vol_{sym}"
                    if sym in vin.columns and vc in vin.columns:
                        turnover_parts.append(vin[sym].astype(float) * vin[vc].astype(float))
                if turnover_parts:
                    aggregate_turnover = pd.concat(turnover_parts, axis=1).sum(axis=1, min_count=1)
            vol_ok = (
                aggregate_volume.notna().any()
                and (aggregate_volume.fillna(0) > 0).sum() > 0
            )
            vin_note = "Research basket only; VPL excluded if <252 bars"
            dist_vol_ok = vol_ok
            if not dist_vol_ok:
                vin_note = (
                    "VIN group distribution day unavailable due to missing basket volume. "
                    + vin_note
                )
                warnings.append(
                    "vin_group: distribution_volume unavailable — dist counts set to null"
                )
            views["vin_group"] = pd.DataFrame(
                {
                    "date": vin["date"],
                    "close": close_vin,
                    "volume": aggregate_volume if dist_vol_ok else np.nan,
                    "aggregate_turnover": aggregate_turnover if dist_vol_ok else np.nan,
                    "open": close_vin,
                    "high": close_vin,
                    "low": close_vin,
                }
            )
            meta["vin_group"] = IndexViewMeta(
                index_view="vin_group",
                label="VIN basket equal-weight return index (VIC,VHM,VRE)",
                is_proxy=True,
                notes=vin_note,
                distribution_volume_available=dist_vol_ok,
            )

    if not raw.empty and raw["date"].min() > DATA_START:
        warnings.append(
            f"Data starts {raw['date'].min().date()}; shorter history flagged"
        )

    return views, meta, warnings
