# src/theme/features.py — Compute/derive components Q,R,T,V,M; allow nulls
from __future__ import annotations

import numpy as np
import pandas as pd


def rank_pct(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Rank percentile 0..100. ascending=True: higher raw -> higher rank (better)."""
    if s.dropna().empty:
        return pd.Series(index=s.index, dtype=float)
    r = s.rank(method="average", ascending=ascending, na_option="keep")
    n = r.dropna().max()
    if n <= 0:
        return pd.Series(50.0, index=s.index)
    return (r - 1) / (n - 1) * 100.0 if n > 1 else pd.Series(50.0, index=s.index)


def safe_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """Get column as float; missing -> NaN."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def component_q(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Quality: ROE, ROIC, FCF margin, FCF positive years. Higher better. Cap at cap_quality when ROIC/FCF missing."""
    cap = cfg.get("cap_quality_at_when_missing_roic_fcf", 60)
    roe = safe_numeric(df, "roe_5y_median")
    roic = safe_numeric(df, "roic_5y_median")
    fcf_m = safe_numeric(df, "fcf_margin_5y_median")
    fcf_y = safe_numeric(df, "fcf_positive_years_5y")
    r_roe = rank_pct(roe, ascending=True)
    r_roic = rank_pct(roic, ascending=True)
    r_fcf_m = rank_pct(fcf_m, ascending=True)
    r_fcf_y = rank_pct(fcf_y, ascending=True)
    q = (r_roe + r_roic + r_fcf_m + r_fcf_y) / 4.0
    missing_roic_fcf = roic.isna() | fcf_m.isna()
    q = q.clip(upper=cap).where(~missing_roic_fcf, q.clip(upper=cap))
    return q.fillna(50.0)


def component_r(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Resilience: lower leverage better, higher interest coverage better. Mild penalty when leverage missing."""
    nd = safe_numeric(df, "net_debt_to_ebitda")
    ic = safe_numeric(df, "interest_coverage")
    r_nd = rank_pct(nd, ascending=False)
    r_ic = rank_pct(ic, ascending=True)
    r = (r_nd + r_ic) / 2.0
    if cfg.get("resilience_mild_penalty_when_leverage_missing", True):
        r = r.where(nd.notna(), r - 10).clip(0, 100)
    return r.fillna(50.0)


def component_t(df: pd.DataFrame, _cfg: dict) -> pd.Series:
    """T: e.g. capex/sales or stability; higher better."""
    capex = safe_numeric(df, "capex_to_sales_5y")
    if capex.isna().all():
        return pd.Series(50.0, index=df.index)
    return rank_pct(capex, ascending=True).fillna(50.0)


def component_v(df: pd.DataFrame, _cfg: dict) -> pd.Series:
    """Valuation: lower PE/PB/EV_EBITDA better -> rank ascending then 100-rank."""
    pe = safe_numeric(df, "pe_ttm")
    pb = safe_numeric(df, "pb_ttm")
    ev = safe_numeric(df, "ev_ebitda_ttm")
    r_pe = rank_pct(pe, ascending=True)
    r_pb = rank_pct(pb, ascending=True)
    r_ev = rank_pct(ev, ascending=True)
    v = (r_pe + r_pb + r_ev) / 3.0
    return v.fillna(50.0)


def component_m(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Macro/technical. If missing use neutral (50)."""
    neutral = float(cfg.get("technicals_neutral_when_missing", 50))
    gms = safe_numeric(df, "gross_margin_stability")
    if gms.isna().all():
        return pd.Series(neutral, index=df.index)
    return rank_pct(gms, ascending=True).fillna(neutral)


def build_component_df(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add columns Q, R, T, V, M to dataframe (symbol index or row-aligned)."""
    out = df.copy()
    out["Q"] = component_q(df, cfg)
    out["R"] = component_r(df, cfg)
    out["T"] = component_t(df, cfg)
    out["V"] = component_v(df, cfg)
    out["M"] = component_m(df, cfg)
    return out
