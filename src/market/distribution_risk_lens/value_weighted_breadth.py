"""Volume-weighted breadth for liquid universe (v1.3 research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.liquid_universe import liquid_slice, load_normalized_panel, per_ticker_ma_flags


def build_value_weighted_breadth(
    *,
    start: str = "2012-01-01",
    panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    base = panel if panel is not None else load_normalized_panel()
    enriched = per_ticker_ma_flags(base)
    liq = liquid_slice(enriched, start=start)
    if liq.empty:
        return pd.DataFrame()

    rows = []
    for dt, g in liq.groupby("date", sort=True):
        tv = g["tv"].fillna(0).astype(float)
        total = float(tv.sum())
        adv_v = float(tv[g["is_advancer"]].sum())
        dec_v = float(tv[g["is_decliner"]].sum())
        unch_v = float(tv[g["is_unchanged"]].sum())
        if total <= 0:
            rows.append(
                {
                    "date": dt,
                    "total_value_traded_liquid": 0.0,
                    "advancing_value_traded": adv_v,
                    "declining_value_traded": dec_v,
                    "unchanged_value_traded": unch_v,
                    "advancing_value_pct": np.nan,
                    "declining_value_pct": np.nan,
                    "unchanged_value_pct": np.nan,
                    "value_net_breadth_pct": np.nan,
                }
            )
            continue
        rows.append(
            {
                "date": dt,
                "total_value_traded_liquid": total,
                "advancing_value_traded": adv_v,
                "declining_value_traded": dec_v,
                "unchanged_value_traded": unch_v,
                "advancing_value_pct": adv_v / total,
                "declining_value_pct": dec_v / total,
                "unchanged_value_pct": unch_v / total,
                "value_net_breadth_pct": (adv_v - dec_v) / total,
            }
        )
    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    daily["advancing_value_pct_5d_avg"] = daily["advancing_value_pct"].rolling(5, min_periods=1).mean()
    daily["declining_value_pct_5d_avg"] = daily["declining_value_pct"].rolling(5, min_periods=1).mean()
    daily["value_net_breadth_pct_5d_avg"] = daily["value_net_breadth_pct"].rolling(5, min_periods=1).mean()
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily
