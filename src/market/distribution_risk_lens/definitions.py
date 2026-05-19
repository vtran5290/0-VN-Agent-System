"""Distribution day rule variants (no lookahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

DIST_DROP_BASE = 0.002
DIST_DROP_STRICT = 0.005
VOL_HEAVY_MULT = 1.1


def dist_day_flag(
    df: pd.DataFrame,
    *,
    variant: str = "base",
    close_col: str = "close",
    vol_col: str = "volume",
    high_col: str = "high",
    low_col: str = "low",
) -> pd.Series:
    """Boolean dist day at t using only data <= t."""
    c = df[close_col].astype(float)
    v = df[vol_col].astype(float)
    prev_c = c.shift(1)
    prev_v = v.shift(1)
    drop_thr = DIST_DROP_STRICT if variant == "strict_close_0_5pct" else DIST_DROP_BASE
    down = c <= prev_c * (1.0 - drop_thr)
    if variant == "heavy_volume_1_1x":
        vol_up = v >= prev_v * VOL_HEAVY_MULT
    elif variant == "adv20_volume":
        adv20 = v.rolling(20, min_periods=20).mean()
        vol_up = v >= adv20
    else:
        vol_up = v > prev_v
    valid = c.notna() & prev_c.notna() & v.notna() & prev_v.notna() & (prev_v > 0)
    mask = down & vol_up & valid
    if variant == "oneyl_refined_optional" and high_col in df.columns and low_col in df.columns:
        h = df[high_col].astype(float)
        lo = df[low_col].astype(float)
        span = (h - lo).replace(0, np.nan)
        close_pos = (c - lo) / span
        mask = mask & (close_pos <= 0.5)
    return mask.fillna(False)
