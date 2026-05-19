"""Feature engineering at date t (no lookahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.definitions import dist_day_flag


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def build_features(
    df: pd.DataFrame,
    *,
    index_view: str,
    variant: str = "base",
    distribution_volume_available: bool = True,
) -> pd.DataFrame:
    out = df[["date", "close", "volume"]].copy()
    if "high" in df.columns:
        out["high"] = df["high"]
    if "low" in df.columns:
        out["low"] = df["low"]
    out["index_view"] = index_view
    if not distribution_volume_available:
        out["dist_day_flag"] = np.nan
        for w in (5, 10, 20, 25, 50):
            out[f"dist_count_{w}d"] = np.nan
    else:
        dist = dist_day_flag(
            out,
            variant=variant,
            close_col="close",
            vol_col="volume",
            high_col="high" if "high" in out.columns else "close",
            low_col="low" if "low" in out.columns else "close",
        )
        out["dist_day_flag"] = dist.astype(int)
        for w in (5, 10, 20, 25, 50):
            out[f"dist_count_{w}d"] = out["dist_day_flag"].rolling(w, min_periods=1).sum()
    if not distribution_volume_available:
        out["days_since_last_dist"] = np.nan
        out["consecutive_no_dist_days"] = np.nan
        out["dist_cluster_score"] = np.nan
    else:
        dsld = []
        last = -1
        for i, flag in enumerate(out["dist_day_flag"].tolist()):
            if flag:
                dsld.append(0 if last < 0 else i - last)
                last = i
            else:
                dsld.append(i - last if last >= 0 else np.nan)
        out["days_since_last_dist"] = dsld
        out["consecutive_no_dist_days"] = _consecutive_no_dist(out["dist_day_flag"])
        weights = np.array([0.4, 0.3, 0.2, 0.1])
        wsum = out[["dist_count_5d", "dist_count_10d", "dist_count_20d", "dist_count_25d"]].values @ weights[:4]
        out["dist_cluster_score"] = wsum
    c = out["close"].astype(float)
    for span, col in ((20, "ema20"), (50, "ema50"), (100, "ema100"), (200, "ema200")):
        e = _ema(c, span)
        out[f"close_above_{col}"] = (c > e).astype(float)
    for w in (20, 50, 100):
        roll_max = c.rolling(w, min_periods=1).max()
        out[f"drawdown_from_{w}d_high"] = c / roll_max - 1.0
    return out


def _consecutive_no_dist(flags: pd.Series) -> pd.Series:
    out = []
    run = 0
    for f in flags.astype(int).tolist():
        if f:
            run = 0
        else:
            run += 1
        out.append(run)
    return pd.Series(out, index=flags.index)
