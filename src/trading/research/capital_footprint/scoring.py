"""
Capital Footprint Composite Scoring
=====================================
Builds three composite scores from the feature panel:
  1. capital_footprint_score_raw       - full composite (OHLCV + sector + regime + FA)
  2. capital_footprint_score_pure_tech - OHLCV + sector + regime only
  3. big_individual_footprint_proxy    - domestic large-money footprint proxy

All scores are 0-1 cross-sectional percentile ranks on each date.
Dynamic reweighting: if a component is all-NaN on a date, its weight is redistributed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Normalization ─────────────────────────────────────────────────────────────

def _pct_rank(s: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank within a date group (0-1)."""
    return s.rank(pct=True, na_option="bottom")


def _clip_winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    """Winsorize to [lo, hi] quantile."""
    q_lo = s.quantile(lo)
    q_hi = s.quantile(hi)
    return s.clip(lower=q_lo, upper=q_hi)


def _norm_to_01(s: pd.Series) -> pd.Series:
    """Min-max normalize to [0, 1]. Returns 0.5 if all values equal."""
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


# ── Component scorers (return 0-1 series on same index) ──────────────────────

def _rs_component(df: pd.DataFrame) -> pd.Series:
    """Relative strength component. Rewards multi-horizon RS persistence."""
    cols = ["rs_rank_market_20d", "rs_rank_market_60d", "rs_rank_market_120d"]
    avail = [c for c in cols if c in df.columns]
    if not avail:
        return pd.Series(np.nan, index=df.index)
    base = df[avail].mean(axis=1)
    # Bonus: add persistence score if available
    if "rs_persistence_score" in df.columns:
        base = base * 0.7 + df["rs_persistence_score"] * 0.3
    return base.clip(0, 1)


def _pv_component(df: pd.DataFrame) -> pd.Series:
    """Price-volume accumulation component."""
    parts = []

    if "net_accumulation_score" in df.columns:
        # Rank net accumulation (higher = more accumulation days than distribution)
        parts.append(df.groupby("date")["net_accumulation_score"].transform(_pct_rank) * 0.25)

    if "up_down_value_ratio_20d" in df.columns:
        ratio = _clip_winsorize(df["up_down_value_ratio_20d"].fillna(1.0))
        parts.append(df.groupby("date")["up_down_value_ratio_20d"].transform(
            lambda x: _norm_to_01(_clip_winsorize(x.fillna(1.0)))
        ) * 0.20)

    if "close_location_value" in df.columns:
        parts.append(df["close_location_value"].fillna(0.5) * 0.15)

    if "breakout_volume_flag" in df.columns:
        parts.append(df["breakout_volume_flag"].fillna(0).astype(float) * 0.15)

    if "dry_up_pullback_flag" in df.columns:
        parts.append(df["dry_up_pullback_flag"].fillna(0).astype(float) * 0.10)

    if "turnover_z_20d" in df.columns:
        parts.append(df.groupby("date")["turnover_z_20d"].transform(
            lambda x: _norm_to_01(_clip_winsorize(x.fillna(0.0)))
        ) * 0.15)

    if not parts:
        return pd.Series(np.nan, index=df.index)

    score = sum(parts)
    # Normalize sum to [0,1]
    total_w = sum([0.25, 0.20, 0.15, 0.15, 0.10, 0.15][:len(parts)])
    return (score / total_w).clip(0, 1) if total_w > 0 else score.clip(0, 1)


def _sector_rotation_component(df: pd.DataFrame) -> pd.Series:
    if "sector_rotation_score" in df.columns:
        return df["sector_rotation_score"].fillna(0.5).clip(0, 1)
    return pd.Series(np.nan, index=df.index)


def _regime_component(df: pd.DataFrame) -> pd.Series:
    """Market regime and breadth component."""
    parts = []

    if "market_pct_above_ma50" in df.columns:
        bpct = pd.to_numeric(df["market_pct_above_ma50"], errors="coerce").fillna(50.0) / 100.0
        parts.append(bpct.clip(0, 1) * 0.5)

    if "vnindex_cloud_bull" in df.columns:
        parts.append(pd.to_numeric(df["vnindex_cloud_bull"], errors="coerce").fillna(0).astype(float) * 0.3)

    if "allow_new_buys" in df.columns:
        parts.append(pd.to_numeric(df["allow_new_buys"], errors="coerce").fillna(0).astype(float) * 0.2)

    if not parts:
        return pd.Series(0.5, index=df.index)
    return sum(parts).clip(0, 1)


def _liquidity_component(df: pd.DataFrame) -> pd.Series:
    if "liquidity_rank_market" in df.columns:
        return df["liquidity_rank_market"].fillna(0.5).clip(0, 1)
    return pd.Series(np.nan, index=df.index)


def _fundamental_component(df: pd.DataFrame) -> pd.Series:
    if "fundamental_quality_score" in df.columns:
        return df["fundamental_quality_score"].fillna(0.5).clip(0, 1)
    return pd.Series(np.nan, index=df.index)


def _compute_weighted_score(
    component_values: dict[str, pd.Series],
    weights: dict[str, float],
) -> pd.Series:
    """
    Weighted average of component scores with dynamic reweighting for missing data.
    Components that are all-NaN on a given row get their weight redistributed.
    """
    index = next(iter(component_values.values())).index
    result = pd.Series(0.0, index=index)
    total_w = pd.Series(0.0, index=index)

    for name, w in weights.items():
        if name not in component_values:
            continue
        s = component_values[name]
        valid = s.notna()
        result += s.fillna(0.0) * w * valid.astype(float)
        total_w += w * valid.astype(float)

    return (result / total_w.replace(0.0, np.nan)).fillna(0.5).clip(0, 1)


# ── Main score builders ───────────────────────────────────────────────────────

def add_scores(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute all three Capital Footprint composite scores and add to panel."""

    print("Computing RS component...")
    rs_comp = _rs_component(panel)

    print("Computing price-volume component...")
    pv_comp = _pv_component(panel)

    print("Computing sector rotation component...")
    sr_comp = _sector_rotation_component(panel)

    print("Computing regime/breadth component...")
    reg_comp = _regime_component(panel)

    print("Computing liquidity component...")
    liq_comp = _liquidity_component(panel)

    print("Computing fundamental component...")
    fund_comp = _fundamental_component(panel)

    components = {
        "rs": rs_comp,
        "pv": pv_comp,
        "sector": sr_comp,
        "regime": reg_comp,
        "liquidity": liq_comp,
        "fundamental": fund_comp,
    }

    # ── Score 1: Full composite (spec weights) ────────────────────────────
    # RS 20% | PV 25% | Sector 15% | Regime 15% | Liquidity 10% | FA 5%
    # Foreign/Index flow (15% combined) redistributed to RS and PV since unavailable
    weights_raw = {
        "rs": 0.275,        # 20% base + 7.5% redistributed from foreign/index
        "pv": 0.325,        # 25% base + 7.5% redistributed
        "sector": 0.15,
        "regime": 0.15,
        "liquidity": 0.10,
        "fundamental": 0.00,  # 0% — FA is optional enhancement, not primary signal
    }
    panel["capital_footprint_score_raw"] = _compute_weighted_score(components, weights_raw)

    # Cross-sectional percentile rank on each date
    panel["capital_footprint_score_raw"] = panel.groupby("date")["capital_footprint_score_raw"].transform(_pct_rank)

    # ── Score 2: Pure technical (no FA) ──────────────────────────────────
    weights_tech = {"rs": 0.30, "pv": 0.30, "sector": 0.20, "regime": 0.15, "liquidity": 0.05}
    panel["capital_footprint_score_pure_tech"] = _compute_weighted_score(
        {k: v for k, v in components.items() if k != "fundamental"}, weights_tech
    )
    panel["capital_footprint_score_pure_tech"] = panel.groupby("date")["capital_footprint_score_pure_tech"].transform(_pct_rank)

    # ── Score 3: Big individual footprint proxy ───────────────────────────
    # Captures domestic large-money signal via footprint, not account identity.
    # IMPORTANT: This is a proxy. Cannot confirm account type. Label accordingly.
    bif = pd.Series(0.0, index=panel.index)

    # Abnormal value with strong close = possible large domestic accumulation
    if "value_z_20d" in panel.columns and "close_location_value" in panel.columns:
        high_val = (pd.to_numeric(panel["value_z_20d"], errors="coerce").fillna(0) > 1.0).astype(float)
        strong_close = (panel["close_location_value"].fillna(0.5) > 0.65).astype(float)
        bif += high_val * strong_close * 0.30

    # Repeated accumulation with limited pullback = patient buying
    if "net_accumulation_score" in panel.columns and "dry_up_pullback_flag" in panel.columns:
        net_acc = panel.groupby("date")["net_accumulation_score"].transform(_pct_rank).fillna(0.5)
        bif += net_acc * panel["dry_up_pullback_flag"].fillna(0).astype(float) * 0.25

    # Sector peers moving (thematic coordination)
    if "sector_rotation_score" in panel.columns:
        bif += panel["sector_rotation_score"].fillna(0.5) * 0.20

    # Tight closes (stealthy accumulation)
    if "tight_close_flag" in panel.columns:
        bif += panel["tight_close_flag"].fillna(0).astype(float) * 0.15

    # Up/down value ratio dominance
    if "up_down_value_ratio_20d" in panel.columns:
        udv = panel.groupby("date")["up_down_value_ratio_20d"].transform(
            lambda x: _norm_to_01(_clip_winsorize(x.fillna(1.0)))
        ).fillna(0.5)
        bif += udv * 0.10

    panel["big_individual_footprint_proxy"] = panel.groupby("date")[bif.name if hasattr(bif, 'name') else 0].transform(_pct_rank) if False else \
        panel.groupby("date").apply(lambda g: bif.loc[g.index].rank(pct=True, na_option="bottom")).reset_index(level=0, drop=True)

    # Fallback if above fails
    if "big_individual_footprint_proxy" not in panel.columns or panel["big_individual_footprint_proxy"].isna().all():
        panel["big_individual_footprint_proxy"] = bif.clip(0, 1)

    print("Scores computed.")
    return panel
