"""Simple O'Neil-style distribution day (must match vnindex_low_dist_forward_returns)."""
from __future__ import annotations

import numpy as np
import pandas as pd

DIST_DROP = 0.002


def add_dist_day(df: pd.DataFrame, close_col: str, vol_col: str) -> pd.DataFrame:
    out = df.copy()
    c = out[close_col].astype(float)
    v = out[vol_col].astype(float)
    prev_c = c.shift(1)
    prev_v = v.shift(1)
    down = c <= prev_c * (1.0 - DIST_DROP)
    vol_up = v > prev_v
    valid = c.notna() & prev_c.notna() & v.notna() & prev_v.notna() & (v > 0) & (prev_v > 0)
    dist = pd.Series(np.nan, index=out.index, dtype=float)
    dist[valid] = (down[valid] & vol_up[valid]).astype(float)
    out["dist_day"] = dist
    out["pct_change"] = c / prev_c - 1.0
    return out
