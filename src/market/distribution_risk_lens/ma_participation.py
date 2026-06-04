"""MA participation features for liquid ADV50 universe (v1.3 research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.liquid_universe import (
    liquid_slice,
    load_normalized_panel,
    per_ticker_ma_flags,
)


def build_ma_participation(
    *,
    start: str = "2012-01-01",
    panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    base = panel if panel is not None else load_normalized_panel()
    enriched = per_ticker_ma_flags(base)
    liq = liquid_slice(enriched, start=start)
    if liq.empty:
        return pd.DataFrame()

    ma_cols = ["above_ma20", "above_ma50", "above_ma100", "above_ma150", "above_ma200"]
    rows = []
    for dt, g in liq.groupby("date", sort=True):
        n = len(g)
        rec: dict = {"date": dt}
        for mc, prefix in zip(
            ma_cols,
            ("ma20", "ma50", "ma100", "ma150", "ma200"),
        ):
            cnt = int(g[mc].sum())
            rec[f"n_above_{prefix}"] = cnt
            rec[f"pct_above_{prefix}"] = cnt / n if n else np.nan
        rows.append(rec)
    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    daily["pct_above_ma20_change_5d"] = daily["pct_above_ma20"].diff(5)
    daily["pct_above_ma50_change_10d"] = daily["pct_above_ma50"].diff(10)
    daily["pct_above_ma100_change_20d"] = daily["pct_above_ma100"].diff(20)
    daily["pct_above_ma200_change_20d"] = daily["pct_above_ma200"].diff(20)
    daily["ma20_minus_ma50_participation"] = daily["pct_above_ma20"] - daily["pct_above_ma50"]
    daily["ma50_minus_ma200_participation"] = daily["pct_above_ma50"] - daily["pct_above_ma200"]
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily
