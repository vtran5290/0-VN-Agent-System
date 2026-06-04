"""Large-cap vs broad-market breadth divergence (v1.3 research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.liquid_universe import liquid_slice, load_normalized_panel, per_ticker_ma_flags


def _group_metrics(g: pd.DataFrame) -> dict[str, float]:
    n = len(g)
    if n == 0:
        return {}
    adv_pct = float(g["is_advancer"].mean())
    dec_pct = float(g["is_decliner"].mean())
    net_pct = float((g["is_advancer"].sum() - g["is_decliner"].sum()) / n)
    return {
        "advancers_pct": adv_pct,
        "decliners_pct": dec_pct,
        "net_adv_dec_pct": net_pct,
        "pct_above_ma20": float(g["above_ma20"].mean()),
        "pct_above_ma50": float(g["above_ma50"].mean()),
        "pct_above_ma100": float(g["above_ma100"].mean()),
        "pct_above_ma200": float(g["above_ma200"].mean()),
    }


def build_largecap_divergence(
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
        g = g.sort_values("adv50_value", ascending=False)
        top30 = g.head(30)
        top100 = g.head(100)
        all_m = _group_metrics(g)
        t30 = _group_metrics(top30)
        t100 = _group_metrics(top100)
        rec: dict = {"date": dt}
        for prefix, m in (("top30_adv50", t30), ("top100_adv50", t100), ("all_liquid_adv50_gt_2b", all_m)):
            for k, v in m.items():
                rec[f"{prefix}_{k}"] = v
        rec["top30_advancers_minus_all_advancers"] = t30.get("advancers_pct", np.nan) - all_m.get(
            "advancers_pct", np.nan
        )
        rec["top100_advancers_minus_all_advancers"] = t100.get("advancers_pct", np.nan) - all_m.get(
            "advancers_pct", np.nan
        )
        rec["top30_ma50_minus_all_ma50"] = t30.get("pct_above_ma50", np.nan) - all_m.get("pct_above_ma50", np.nan)
        rec["top100_ma50_minus_all_ma50"] = t100.get("pct_above_ma50", np.nan) - all_m.get("pct_above_ma50", np.nan)
        rec["largecap_breadth_leadership_flag"] = int(
            t30.get("advancers_pct", 0) > all_m.get("advancers_pct", 0) + 0.10
        )
        rec["largecap_breadth_divergence_flag"] = int(
            t30.get("advancers_pct", 0) > 0.50 and all_m.get("advancers_pct", 0) < 0.45
        )
        rows.append(rec)
    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily
