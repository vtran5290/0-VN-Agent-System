"""Liquid-universe breadth features (v1.3 research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.liquid_universe import (
    liquid_slice,
    load_normalized_panel,
    per_ticker_ma_flags,
)


def _streak(series: pd.Series, positive: bool) -> pd.Series:
    out: list[int] = []
    run = 0
    for v in series:
        hit = bool(v) if not (isinstance(v, float) and np.isnan(v)) else False
        if hit == positive:
            run += 1
        else:
            run = 0
        out.append(run)
    return pd.Series(out, index=series.index)


def build_breadth_features(
    *,
    start: str = "2012-01-01",
    panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    base = panel if panel is not None else load_normalized_panel()
    enriched = per_ticker_ma_flags(base)
    liq = liquid_slice(enriched, start=start)
    if liq.empty:
        return pd.DataFrame()

    def _agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        adv = int(g["is_advancer"].sum())
        dec = int(g["is_decliner"].sum())
        unch = int(g["is_unchanged"].sum())
        adv_pct = adv / n if n else np.nan
        dec_pct = dec / n if n else np.nan
        unch_pct = unch / n if n else np.nan
        net = adv - dec
        net_pct = net / n if n else np.nan
        udr = adv / dec if dec > 0 else (np.inf if adv > 0 else np.nan)
        return pd.Series(
            {
                "liquid_universe_n": n,
                "advancers_n": adv,
                "decliners_n": dec,
                "unchanged_n": unch,
                "advancers_pct": adv_pct,
                "decliners_pct": dec_pct,
                "unchanged_pct": unch_pct,
                "net_adv_dec": net,
                "net_adv_dec_pct": net_pct,
                "up_down_ratio": udr,
            }
        )

    daily = liq.groupby("date", sort=True).apply(_agg).reset_index()
    daily["advancers_pct_3d_avg"] = daily["advancers_pct"].rolling(3, min_periods=1).mean()
    daily["advancers_pct_5d_avg"] = daily["advancers_pct"].rolling(5, min_periods=1).mean()
    daily["decliners_pct_3d_avg"] = daily["decliners_pct"].rolling(3, min_periods=1).mean()
    daily["decliners_pct_5d_avg"] = daily["decliners_pct"].rolling(5, min_periods=1).mean()
    daily["net_adv_dec_pct_5d_avg"] = daily["net_adv_dec_pct"].rolling(5, min_periods=1).mean()
    daily["positive_breadth_streak"] = _streak(daily["net_adv_dec"] > 0, positive=True)
    daily["negative_breadth_streak"] = _streak(daily["net_adv_dec"] < 0, positive=True)
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily
