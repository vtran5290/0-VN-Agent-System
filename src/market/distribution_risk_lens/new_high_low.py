"""New 20d/50d high-low participation for liquid universe (v1.3 research)."""
from __future__ import annotations

import pandas as pd

from src.market.distribution_risk_lens.liquid_universe import liquid_slice, load_normalized_panel, per_ticker_ma_flags


def build_new_high_low_features(
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
        n = len(g)
        rows.append(
            {
                "date": dt,
                "new_20d_high_pct": float(g["new_20d_high"].mean()),
                "new_50d_high_pct": float(g["new_50d_high"].mean()),
                "new_20d_low_pct": float(g["new_20d_low"].mean()),
                "new_50d_low_pct": float(g["new_50d_low"].mean()),
                "new_high_minus_new_low_20d_pct": float(g["new_20d_high"].mean() - g["new_20d_low"].mean()),
                "new_high_minus_new_low_50d_pct": float(g["new_50d_high"].mean() - g["new_50d_low"].mean()),
                "liquid_universe_n": n,
            }
        )
    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily
