"""Prior rally / overextension context from index views (v1.3 research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.index_views import load_index_views


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def build_prior_rally_context(
    *,
    start: str = "2012-01-01",
    primary_view: str = "ex_vin_proxy",
) -> pd.DataFrame:
    views, _, _ = load_index_views(start=start)
    if primary_view not in views:
        primary_view = "vnindex_raw" if "vnindex_raw" in views else next(iter(views))
    df = views[primary_view][["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    c = df["close"].astype(float)
    for n, col in ((10, "ret_10d"), (20, "ret_20d"), (60, "ret_60d")):
        df[col] = c / c.shift(n) - 1.0
    for span, name in ((20, "ma20"), (50, "ma50"), (100, "ma100")):
        ma = _ema(c, span)
        df[f"distance_from_{name}"] = c / ma - 1.0
    df["above_ma20_flag"] = (c > _ema(c, 20)).astype(int)
    ema50 = _ema(c, 50)
    df["above_ma50_flag"] = (c > ema50).astype(int)
    df["below_ma20_above_ma50_flag"] = ((c <= _ema(c, 20)) & (c > ema50)).astype(int)
    df["below_ma50_flag"] = (c <= ema50).astype(int)

    def _prior_bucket(r: float) -> str:
        if pd.isna(r):
            return "unknown"
        if r < 0:
            return "cold"
        if r <= 0.08:
            return "normal"
        return "hot"

    def _ma_zone(row: pd.Series) -> str:
        if row["above_ma20_flag"]:
            return "above_ma20"
        if row["below_ma20_above_ma50_flag"]:
            return "below_ma20_above_ma50"
        if row["below_ma50_flag"]:
            return "below_ma50"
        return "unknown"

    df["prior_20d_return_bucket"] = df["ret_20d"].apply(_prior_bucket)
    df["index_ma_zone"] = df.apply(_ma_zone, axis=1)
    df["view"] = primary_view
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df
