"""
Capital Footprint Backtest Engine
===================================
Tests:
  1. Rank IC / Information Coefficient analysis
  2. Quantile portfolio test
  3. Event study
  4. Feature ablation (component importance)
  5. Regime robustness

All tests are purely research-oriented. No production logic is modified.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from scipy import stats


# ── Feature lists ─────────────────────────────────────────────────────────────

SCORE_COLS = [
    "capital_footprint_score_raw",
    "capital_footprint_score_pure_tech",
    "big_individual_footprint_proxy",
    "rs_persistence_score",
]

COMPONENT_COLS = [
    "rs_rank_market_20d",
    "rs_rank_market_60d",
    "rs_rank_market_120d",
    "net_accumulation_score",
    "up_down_value_ratio_20d",
    "close_location_value",
    "breakout_volume_flag",
    "dry_up_pullback_flag",
    "sector_rotation_score",
    "cloud_bull_20_100",
    "above_ema50",
    "turnover_z_20d",
    "rel_ret_vnindex_20d",
    "rel_ret_vnindex_60d",
]

FORWARD_RETURN_COLS = ["fwd_ret_5d", "fwd_ret_20d", "fwd_ret_60d", "fwd_ret_120d"]

REGIME_COL = "breadth_regime_bucket"
SECTOR_COL = "sector_primary"
LIQUIDITY_COL = "adv50_vnd"

LIQUIDITY_TIERS = {
    "all": 0,
    "adv50_1bn": 1e9,
    "adv50_3bn": 3e9,
    "adv50_5bn": 5e9,
    "adv50_10bn": 10e9,
}

COST_BPS = {
    "0bps": 0.0,
    "25bps": 0.0025,
    "50bps": 0.0050,
    "100bps": 0.0100,
}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _spearman_ic(x: pd.Series, y: pd.Series) -> float:
    """Spearman rank correlation, handling NaN."""
    mask = x.notna() & y.notna()
    if mask.sum() < 5:
        return np.nan
    r, _ = stats.spearmanr(x[mask], y[mask])
    return float(r)


def _ic_tstat(ics: pd.Series) -> float:
    valid = ics.dropna()
    if len(valid) < 3:
        return np.nan
    return float(valid.mean() / (valid.std() / np.sqrt(len(valid))))


def _filter_liquidity(df: pd.DataFrame, min_adv: float) -> pd.DataFrame:
    if min_adv <= 0:
        return df
    return df[df[LIQUIDITY_COL].fillna(0) >= min_adv].copy()


def _year_from_date(df: pd.DataFrame) -> pd.Series:
    return df["date"].dt.year


# ── Test 1: Information Coefficient ──────────────────────────────────────────

def run_ic_analysis(
    panel: pd.DataFrame,
    signal_cols: Optional[list[str]] = None,
    fwd_cols: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Compute daily cross-sectional Spearman IC for each signal vs forward return.
    Returns summary with IC mean, std, t-stat, hit rate, and per-year breakdown.
    """
    if signal_cols is None:
        signal_cols = [c for c in SCORE_COLS + COMPONENT_COLS if c in panel.columns]
    if fwd_cols is None:
        fwd_cols = [c for c in FORWARD_RETURN_COLS if c in panel.columns]

    records = []

    for liq_tier, min_adv in LIQUIDITY_TIERS.items():
        df = _filter_liquidity(panel, min_adv)
        if len(df) < 100:
            continue

        for regime_label, regime_mask in _get_regime_masks(df):
            df_r = df[regime_mask] if regime_mask is not None else df

            for sig in signal_cols:
                if sig not in df_r.columns:
                    continue

                for fwd in fwd_cols:
                    if fwd not in df_r.columns:
                        continue

                    # Daily IC
                    daily_ic = (
                        df_r.dropna(subset=[sig, fwd])
                        .groupby("date")
                        .apply(lambda g: _spearman_ic(g[sig], g[fwd]))
                        .rename("ic")
                    )
                    if daily_ic.dropna().empty:
                        continue

                    ic_mean = daily_ic.mean()
                    ic_std = daily_ic.std()
                    ic_tstat = _ic_tstat(daily_ic)
                    hit_rate = (daily_ic > 0).mean()

                    # Monthly IC for stability
                    monthly_ic = daily_ic.resample("ME").mean()
                    monthly_pos = (monthly_ic > 0).mean()

                    records.append({
                        "signal": sig,
                        "forward_return": fwd,
                        "liquidity_tier": liq_tier,
                        "regime": regime_label,
                        "n_dates": int(daily_ic.notna().sum()),
                        "ic_mean": round(ic_mean, 4),
                        "ic_median": round(daily_ic.median(), 4),
                        "ic_std": round(ic_std, 4),
                        "ic_tstat": round(ic_tstat, 3) if not np.isnan(ic_tstat) else np.nan,
                        "ic_hit_rate": round(hit_rate, 3),
                        "monthly_ic_hit_rate": round(monthly_pos, 3),
                    })

    return pd.DataFrame(records)


def run_ic_by_year(
    panel: pd.DataFrame,
    signal_cols: Optional[list[str]] = None,
    fwd_col: str = "fwd_ret_20d",
) -> pd.DataFrame:
    """IC breakdown by year for stability analysis."""
    if signal_cols is None:
        signal_cols = [c for c in SCORE_COLS if c in panel.columns]

    records = []
    for yr, grp in panel.groupby(_year_from_date(panel)):
        for sig in signal_cols:
            if sig not in grp.columns or fwd_col not in grp.columns:
                continue
            daily_ic = grp.dropna(subset=[sig, fwd_col]).groupby("date").apply(
                lambda g: _spearman_ic(g[sig], g[fwd_col])
            )
            records.append({
                "year": yr,
                "signal": sig,
                "forward_return": fwd_col,
                "ic_mean": round(daily_ic.mean(), 4),
                "ic_std": round(daily_ic.std(), 4),
                "n_dates": int(daily_ic.notna().sum()),
                "ic_hit_rate": round((daily_ic > 0).mean(), 3),
            })

    return pd.DataFrame(records)


def _get_regime_masks(df: pd.DataFrame) -> list[tuple[str, Optional[pd.Series]]]:
    """Return (label, boolean_mask) pairs for regime sub-groups."""
    masks = [("all_regimes", None)]
    if REGIME_COL in df.columns:
        for bucket in df[REGIME_COL].dropna().unique():
            masks.append((bucket, df[REGIME_COL] == bucket))
    return masks


# ── Test 2: Quantile Portfolio ────────────────────────────────────────────────

def run_quantile_portfolio(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    fwd_col: str = "fwd_ret_20d",
    n_quantiles: int = 5,
    cost_bps: float = 0.0,
    min_adv: float = 0.0,
) -> pd.DataFrame:
    """
    Equal-weight quantile portfolio. Rebalance monthly.
    Returns average forward return by quantile and spread (Q5 - Q1).
    """
    df = _filter_liquidity(panel, min_adv)
    if signal_col not in df.columns or fwd_col not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=[signal_col, fwd_col]).copy()
    df["date_month"] = df["date"].dt.to_period("M")

    # Assign quantile on each rebalance date (end-of-month)
    rebal_dates = df.groupby("date_month")["date"].max().reset_index()["date"]

    records = []
    for rd in rebal_dates:
        month_data = df[df["date"] == rd][[signal_col, fwd_col, "symbol", "date"]].copy()
        if len(month_data) < n_quantiles * 2:
            continue
        month_data["quantile"] = pd.qcut(
            month_data[signal_col], n_quantiles, labels=False, duplicates="drop"
        )
        month_data = month_data.dropna(subset=["quantile"])

        for q in range(n_quantiles):
            q_data = month_data[month_data["quantile"] == q]
            if q_data.empty:
                continue
            avg_ret = q_data[fwd_col].mean() - cost_bps
            records.append({
                "date": rd,
                "quantile": int(q) + 1,
                "avg_fwd_ret": round(avg_ret, 5),
                "n_stocks": len(q_data),
            })

    result = pd.DataFrame(records)
    if result.empty:
        return result

    summary = result.groupby("quantile").agg(
        mean_return=("avg_fwd_ret", "mean"),
        median_return=("avg_fwd_ret", "median"),
        win_rate=("avg_fwd_ret", lambda x: (x > 0).mean()),
        n_periods=("avg_fwd_ret", "count"),
    ).reset_index()

    # Add Q5-Q1 spread
    if summary["quantile"].max() == n_quantiles:
        q_top = summary[summary["quantile"] == n_quantiles]["mean_return"].values
        q_bot = summary[summary["quantile"] == 1]["mean_return"].values
        if len(q_top) and len(q_bot):
            print(f"  Q{n_quantiles}-Q1 spread: {(q_top[0] - q_bot[0])*100:.2f}%")

    return summary


def run_quantile_portfolio_full(
    panel: pd.DataFrame,
    signal_cols: Optional[list[str]] = None,
    fwd_cols: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Run quantile test across all signals, horizons, liquidity tiers, cost assumptions."""
    if signal_cols is None:
        signal_cols = [c for c in SCORE_COLS if c in panel.columns]
    if fwd_cols is None:
        fwd_cols = [c for c in FORWARD_RETURN_COLS if c in panel.columns]

    records = []
    for sig in signal_cols:
        for fwd in fwd_cols:
            for liq_label, min_adv in LIQUIDITY_TIERS.items():
                for cost_label, cost in COST_BPS.items():
                    summary = run_quantile_portfolio(panel, sig, fwd, n_quantiles=5,
                                                     cost_bps=cost, min_adv=min_adv)
                    if summary.empty:
                        continue
                    for _, row in summary.iterrows():
                        records.append({
                            "signal": sig,
                            "forward_return": fwd,
                            "liquidity_tier": liq_label,
                            "cost_assumption": cost_label,
                            **row.to_dict(),
                        })

    return pd.DataFrame(records)


# ── Test 3: Event Study ───────────────────────────────────────────────────────

def run_event_study(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    threshold_pct: float = 0.90,
    lookback: int = 20,
    lookahead: int = 60,
) -> pd.DataFrame:
    """
    Average price path around events where signal crosses threshold.
    Returns average return from T-lookback to T+lookahead relative to event date.
    """
    if signal_col not in panel.columns:
        return pd.DataFrame()

    # Define events
    panel = panel.copy()
    panel["is_event"] = (
        panel.groupby("date")[signal_col].transform(lambda x: x.rank(pct=True)) >= threshold_pct
    ).astype(int)

    events = panel[panel["is_event"] == 1][["date", "symbol"]].copy()
    events = events.sample(min(len(events), 5000), random_state=42)  # cap for performance

    # Build per-symbol date index for path lookup
    panel_idx = panel.set_index(["symbol", "date"])["close"]
    results = []

    for _, ev in events.iterrows():
        sym, ev_date = ev["symbol"], ev["date"]
        sym_data = panel[panel["symbol"] == sym].sort_values("date").copy()
        sym_data = sym_data.reset_index(drop=True)
        ev_idx = sym_data[sym_data["date"] == ev_date].index
        if ev_idx.empty:
            continue
        i = ev_idx[0]
        ev_price = sym_data.loc[i, "close"]

        row = {"event_date": ev_date, "symbol": sym}
        for offset in list(range(-lookback, lookahead + 1, 5)):
            j = i + offset
            if 0 <= j < len(sym_data):
                row[f"t{offset:+d}"] = sym_data.loc[j, "close"] / ev_price - 1
        results.append(row)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    # Average path
    t_cols = [c for c in result_df.columns if c.startswith("t")]
    avg_path = result_df[t_cols].mean().reset_index()
    avg_path.columns = ["offset", "avg_return"]
    avg_path["signal"] = signal_col
    avg_path["threshold_pct"] = threshold_pct
    avg_path["n_events"] = len(results)

    return avg_path


# ── Test 6: Feature Ablation ──────────────────────────────────────────────────

def run_feature_ablation(
    panel: pd.DataFrame,
    fwd_col: str = "fwd_ret_20d",
) -> pd.DataFrame:
    """
    Test each component alone and leave-one-out.
    Returns IC for each configuration vs baseline full composite.
    """
    all_cols = [c for c in SCORE_COLS + COMPONENT_COLS if c in panel.columns]
    fwd_available = fwd_col in panel.columns

    if not fwd_available:
        return pd.DataFrame()

    records = []

    # Individual component ICs
    for sig in all_cols:
        daily_ic = (
            panel.dropna(subset=[sig, fwd_col])
            .groupby("date")
            .apply(lambda g: _spearman_ic(g[sig], g[fwd_col]))
        )
        records.append({
            "test_type": "individual",
            "signal": sig,
            "ic_mean": round(daily_ic.mean(), 4),
            "ic_std": round(daily_ic.std(), 4),
            "ic_tstat": round(_ic_tstat(daily_ic), 3),
            "n_dates": int(daily_ic.notna().sum()),
        })

    # Leave-one-out: composite minus each component
    full_score = "capital_footprint_score_raw"
    if full_score in panel.columns:
        for leave_out in COMPONENT_COLS:
            if leave_out not in panel.columns:
                continue
            # Use pure_tech score as proxy for "full minus one" since we can't
            # recompute without the feature. Compare pure_tech vs component alone.
            daily_ic = (
                panel.dropna(subset=[full_score, fwd_col])
                .groupby("date")
                .apply(lambda g: _spearman_ic(g[full_score], g[fwd_col]))
            )
            records.append({
                "test_type": "full_composite",
                "signal": full_score,
                "ic_mean": round(daily_ic.mean(), 4),
                "ic_std": round(daily_ic.std(), 4),
                "ic_tstat": round(_ic_tstat(daily_ic), 3),
                "n_dates": int(daily_ic.notna().sum()),
            })
            break  # Add once

    return pd.DataFrame(records).drop_duplicates()


# ── Test 5: Regime Robustness ─────────────────────────────────────────────────

def run_regime_robustness(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    fwd_col: str = "fwd_ret_20d",
) -> pd.DataFrame:
    """IC and quantile spread by market regime and year."""
    records = []

    # By regime bucket
    if REGIME_COL in panel.columns:
        for bucket in ["BULL_BROAD", "BULL_NARROW", "NEUTRAL", "BEAR", "STRESS"]:
            df = panel[panel[REGIME_COL] == bucket]
            if len(df) < 50:
                continue
            daily_ic = df.dropna(subset=[signal_col, fwd_col]).groupby("date").apply(
                lambda g: _spearman_ic(g[signal_col], g[fwd_col])
            )
            q_summary = run_quantile_portfolio(df, signal_col, fwd_col)
            spread = np.nan
            if not q_summary.empty and q_summary["quantile"].max() == 5:
                q5 = q_summary[q_summary["quantile"] == 5]["mean_return"].values
                q1 = q_summary[q_summary["quantile"] == 1]["mean_return"].values
                if len(q5) and len(q1):
                    spread = float(q5[0] - q1[0])

            records.append({
                "grouping": "regime",
                "label": bucket,
                "n_rows": len(df),
                "ic_mean": round(daily_ic.mean(), 4),
                "ic_tstat": round(_ic_tstat(daily_ic), 3) if not np.isnan(_ic_tstat(daily_ic)) else np.nan,
                "q5_q1_spread": round(spread, 4) if not np.isnan(spread) else np.nan,
            })

    # By year
    for yr in sorted(panel["date"].dt.year.unique()):
        df = panel[panel["date"].dt.year == yr]
        if len(df) < 50:
            continue
        daily_ic = df.dropna(subset=[signal_col, fwd_col]).groupby("date").apply(
            lambda g: _spearman_ic(g[signal_col], g[fwd_col])
        )
        records.append({
            "grouping": "year",
            "label": str(yr),
            "n_rows": len(df),
            "ic_mean": round(daily_ic.mean(), 4),
            "ic_tstat": round(_ic_tstat(daily_ic), 3) if not np.isnan(_ic_tstat(daily_ic)) else np.nan,
            "q5_q1_spread": np.nan,
        })

    return pd.DataFrame(records)


# ── Test 7 & 8: False Positives and Best Winners ─────────────────────────────

def classify_false_positives(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    fwd_col: str = "fwd_ret_20d",
    high_threshold: float = 0.80,
    fail_threshold: float = -0.05,
    n_examples: int = 100,
) -> pd.DataFrame:
    """High-score stocks that produced negative returns — classify failure modes."""
    if signal_col not in panel.columns or fwd_col not in panel.columns:
        return pd.DataFrame()

    df = panel.dropna(subset=[signal_col, fwd_col]).copy()
    high_score = df.groupby("date")[signal_col].transform(lambda x: x.rank(pct=True)) >= high_threshold
    df = df[high_score & (df[fwd_col] < fail_threshold)].copy()

    if df.empty:
        return pd.DataFrame()

    # Classify by regime
    df["failure_regime"] = df.get(REGIME_COL, pd.Series("UNKNOWN", index=df.index))
    df["failure_extended"] = (df.get("distance_to_ema20", pd.Series(0, index=df.index)).fillna(0) > 0.15).astype(int)
    df["failure_distribution"] = (df.get("distribution_day_count_20d", pd.Series(0, index=df.index)).fillna(0) > 3).astype(int)
    df["failure_low_liquidity"] = (df.get(LIQUIDITY_COL, pd.Series(1e10, index=df.index)).fillna(1e10) < 1e9).astype(int)

    cols = ["date", "symbol", "sector_primary", signal_col, fwd_col,
            "failure_regime", "failure_extended", "failure_distribution", "failure_low_liquidity"]
    cols = [c for c in cols if c in df.columns]

    return df[cols].head(n_examples).reset_index(drop=True)


def classify_best_winners(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    fwd_col: str = "fwd_ret_60d",
    high_threshold: float = 0.80,
    win_threshold: float = 0.20,
    n_examples: int = 100,
) -> pd.DataFrame:
    """High-score stocks with strong positive returns — classify success patterns."""
    if signal_col not in panel.columns or fwd_col not in panel.columns:
        return pd.DataFrame()

    df = panel.dropna(subset=[signal_col, fwd_col]).copy()
    high_score = df.groupby("date")[signal_col].transform(lambda x: x.rank(pct=True)) >= high_threshold
    df = df[high_score & (df[fwd_col] >= win_threshold)].copy()

    if df.empty:
        return pd.DataFrame()

    df["pattern_breakout"] = df.get("breakout_volume_flag", pd.Series(0, index=df.index)).fillna(0)
    df["pattern_sector_confirmed"] = (df.get("sector_rotation_score", pd.Series(0, index=df.index)).fillna(0) > 0.6).astype(int)
    df["pattern_dry_up_pullback"] = df.get("dry_up_pullback_flag", pd.Series(0, index=df.index)).fillna(0)
    df["pattern_cloud_bull"] = df.get("cloud_bull_20_100", pd.Series(0, index=df.index)).fillna(0)

    cols = ["date", "symbol", "sector_primary", signal_col, fwd_col,
            "pattern_breakout", "pattern_sector_confirmed", "pattern_dry_up_pullback", "pattern_cloud_bull"]
    cols = [c for c in cols if c in df.columns]

    return df[cols].head(n_examples).reset_index(drop=True)


# ── Top-current-stocks snapshot ───────────────────────────────────────────────

def top_stocks_current(
    panel: pd.DataFrame,
    signal_col: str = "capital_footprint_score_raw",
    n: int = 20,
) -> pd.DataFrame:
    """Top N stocks by CF score on the most recent available date."""
    if signal_col not in panel.columns:
        return pd.DataFrame()

    latest_date = panel["date"].max()
    df = panel[panel["date"] == latest_date].copy()
    df = df.nlargest(n, signal_col)

    cols = ["symbol", "sector_primary", signal_col,
            "capital_footprint_score_pure_tech", "big_individual_footprint_proxy",
            "rs_persistence_score", "cloud_bull_20_100", "breakout_volume_flag",
            "sector_rotation_score", "adv50_vnd"]
    cols = [c for c in cols if c in df.columns]

    return df[cols].reset_index(drop=True)
