"""Build in-memory provisional panel (never writes EOD parquet)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.trading.intraday.volume_projection import project_full_day_volume

EOD_PANEL_DEFAULT = Path("data/research/ema_cloud/ohlcv_panel_ext2012.parquet")


def load_eod_panel(panel_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(panel_path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def build_provisional_panel(
    eod_panel: pd.DataFrame,
    intraday_quotes: pd.DataFrame,
    *,
    target_date: Optional[pd.Timestamp] = None,
    run_timestamp: Optional[datetime] = None,
    volume_projection_method: str = "session_time",
    exchange_calendar: Optional[Dict[str, Any]] = None,
    min_elapsed_fraction: float = 0.15,
) -> pd.DataFrame:
    """
    Return a copy of eod_panel with today's bar replaced/append as PARTIAL intraday bar.
    Does not mutate or write the source parquet.
    """
    run_timestamp = run_timestamp or datetime.now()
    target_date = pd.Timestamp(target_date or run_timestamp.date()).normalize()
    panel = eod_panel.copy()
    if intraday_quotes is None or intraday_quotes.empty:
        return panel

    quotes = intraday_quotes.set_index("symbol", drop=False)
    out_parts = []
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if sym not in quotes.index:
            out_parts.append(sdf)
            continue
        q = quotes.loc[sym]
        if isinstance(q, pd.DataFrame):
            q = q.iloc[0]
        last_px = float(q.get("last_price_kvnd") or 0)
        if last_px <= 0:
            out_parts.append(sdf)
            continue

        mask_today = sdf["date"] == target_date
        vol = q.get("cumulative_volume")
        vol_f = float(vol) if vol is not None and not pd.isna(vol) else np.nan
        proj = project_full_day_volume(
            vol_f if not np.isnan(vol_f) else 0,
            run_timestamp,
            exchange_calendar=exchange_calendar,
            method=volume_projection_method,
            min_elapsed_fraction=min_elapsed_fraction,
        )
        use_vol = vol_f
        if proj.get("volume_is_projected") and proj.get("projected_volume"):
            use_vol = float(proj["projected_volume"])

        o = q.get("open_price_kvnd")
        h = q.get("high_price_kvnd")
        l = q.get("low_price_kvnd")
        open_p = float(o) if o is not None and not pd.isna(o) else last_px
        high_p = float(h) if h is not None and not pd.isna(h) else last_px
        low_p = float(l) if l is not None and not pd.isna(l) else last_px
        if mask_today.any():
            idx = sdf.index[mask_today][0]
            prev_high = float(sdf.at[idx, "high"]) if "high" in sdf.columns else high_p
            prev_low = float(sdf.at[idx, "low"]) if "low" in sdf.columns else low_p
            sdf.at[idx, "close"] = last_px
            sdf.at[idx, "high"] = max(prev_high, high_p, last_px)
            sdf.at[idx, "low"] = min(prev_low, low_p, last_px)
            sdf.at[idx, "open"] = open_p if not np.isnan(open_p) else sdf.at[idx, "open"]
            if not np.isnan(use_vol):
                sdf.at[idx, "volume"] = use_vol
            if "value" in sdf.columns and not np.isnan(use_vol):
                sdf.at[idx, "value"] = last_px * use_vol * 1000
        else:
            new_row = {
                "symbol": sym,
                "date": target_date,
                "open": open_p,
                "high": max(high_p, last_px),
                "low": min(low_p, last_px),
                "close": last_px,
                "volume": use_vol if not np.isnan(use_vol) else 0.0,
            }
            if "value" in sdf.columns:
                new_row["value"] = last_px * (use_vol if not np.isnan(use_vol) else 0) * 1000
            sdf = pd.concat([sdf, pd.DataFrame([new_row])], ignore_index=True)

        sdf["is_intraday"] = False
        sdf.loc[sdf["date"] == target_date, "is_intraday"] = True
        sdf["provisional"] = False
        sdf.loc[sdf["date"] == target_date, "provisional"] = True
        sdf["bar_status"] = "EOD"
        sdf.loc[sdf["date"] == target_date, "bar_status"] = "PARTIAL"
        sdf["volume_is_projected"] = False
        sdf.loc[sdf["date"] == target_date, "volume_is_projected"] = bool(proj.get("volume_is_projected"))
        out_parts.append(sdf)

    return pd.concat(out_parts, ignore_index=True)
