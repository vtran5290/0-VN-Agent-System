"""Phase 5: Full-history portfolio simulation.

Runs portfolio simulation across multiple universe definitions and variants.
Does NOT use fixed 20B ADV as the only full-history universe.

Portfolio rules:
  - Weekly rebalance, T+1 entry, equal weight
  - top_n = 10, 20, 30
  - costs = 0.15%, 0.30%, 0.50% round-trip
  - Non-overlapping weekly equity curve

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .fh_data_loader import ParquetSymbolLoader, load_fh_benchmark
from .fh_universe import ALL_UNIVERSE_IDS, EX_VIN_TICKERS
from .p2_variants import P3_VARIANT_MAP, build_variant_masks, enrich_outcomes
from .p3_portfolio import (
    COST_SCENARIOS,
    RANK_MODES,
    TOP_N_OPTIONS,
    TURNOVER_EXCESSIVE_THRESHOLD,
    _annualize_from_weekly,
    _bench_weekly_returns,
    _build_price_cache,
    _expand_equity_cost_rows,
    _max_drawdown,
    simulate_portfolio,
)

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

# Primary full-history universe IDs to test (excluding the sparse U0 pre-2024)
FH_PRIMARY_UNIVERSES = [
    "U1_TOP_200_ADV50",
    "U1_TOP_300_ADV50",
    "U2_TOP_30PCT_ADV50",
    "U3_ADV50_5B",
]

# Modern-capacity comparison universe
MODERN_UNIVERSES = ["U0_ADV50_20B"]

# Variants to test
FH_VARIANTS = ["P3_V0", "P3_V4", "P3_V6", "P3_V9", "P3_V4B"]

ALLOWED_LABELS = {
    "PORTFOLIO_PROMISING",
    "RISK_REDUCTION_ONLY",
    "REJECTED_PORTFOLIO",
    "INCONCLUSIVE",
    "BLOCKED_BY_DATA",
}

PORTFOLIO_PROMISING_REQUIREMENTS = """
PORTFOLIO_PROMISING requires ALL of:
  1. beats VNINDEX net of base cost
  2. beats equal-weight universe net of base cost
  3. max drawdown not worse by more than 2pp vs V0
  4. holds ex-VIN separately
  5. avg_holdings >= 10
  6. not driven by one year (no single year > 50% of total return)
  7. turnover < 80% per week
"""


def _adv50_at_scan(outcomes: pd.DataFrame, universe_id: str, universe_weekly: pd.DataFrame) -> pd.Series:
    """Return boolean mask for outcomes rows where the universe is active."""
    u_weekly = universe_weekly[universe_weekly["universe_id"] == universe_id].copy()
    u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
    # Build a set of (date, ticker) pairs that are in the universe at each date
    # Approximate: mark dates with candidate_count > 0 as active
    active_dates = set(u_weekly[u_weekly["candidate_count"] > 0]["date"].dt.normalize())
    scan_dates = pd.to_datetime(outcomes["scan_date"]).dt.normalize()
    return scan_dates.isin(active_dates)


def _metrics_from_equity(eq: pd.DataFrame) -> dict[str, Any]:
    if eq.empty:
        return {}
    w = pd.to_numeric(eq.get("net_return_base"), errors="coerce")
    ann = _annualize_from_weekly(w)
    eq_s = pd.to_numeric(eq.get("equity_base"), errors="coerce")
    mdd = _max_drawdown(eq_s)
    bench = pd.to_numeric(eq.get("vnindex_return"), errors="coerce")
    ew = pd.to_numeric(eq.get("ew_universe_return"), errors="coerce")
    cum_net = float((1.0 + w.fillna(0)).prod() - 1.0)
    cum_bench = float((1.0 + bench.fillna(0)).prod() - 1.0) if bench.notna().any() else None
    cum_ew = float((1.0 + ew.fillna(0)).prod() - 1.0) if ew.notna().any() else None
    weeks_lt10 = int((pd.to_numeric(eq.get("holdings"), errors="coerce") < 10).sum())
    return {
        "cagr": ann["cagr"],
        "annualized_vol": ann["vol"],
        "sharpe": ann["sharpe"],
        "sortino": ann["sortino"],
        "max_drawdown": mdd,
        "hit_rate": float((w > 0).mean()) if w.notna().any() else None,
        "avg_weekly_return": float(w.mean()) if w.notna().any() else None,
        "cumulative_net_return": cum_net,
        "cumulative_vnindex_return": cum_bench,
        "cumulative_ew_universe_return": cum_ew,
        "excess_vs_vnindex": (cum_net - cum_bench) if cum_bench is not None else None,
        "excess_vs_ew_universe": (cum_net - cum_ew) if cum_ew is not None else None,
        "avg_turnover": float(pd.to_numeric(eq.get("turnover"), errors="coerce").mean()),
        "avg_holdings": float(pd.to_numeric(eq.get("holdings"), errors="coerce").mean()),
        "weeks_lt10_holdings": weeks_lt10,
    }


def _label_portfolio(
    metrics: dict[str, Any],
    baseline_mdd: float | None,
    yearly_returns: pd.DataFrame | None,
) -> tuple[str, str]:
    n_weeks = int(metrics.get("n_weeks", 0))
    if n_weeks < 20:
        return "BLOCKED_BY_DATA", f"only {n_weeks} weeks"

    avg_hold = float(metrics.get("avg_holdings", 0) or 0)
    if avg_hold < 10:
        return "BLOCKED_BY_DATA", f"avg_holdings={avg_hold:.1f}"

    ex_vn = metrics.get("excess_vs_vnindex")
    ex_ew = metrics.get("excess_vs_ew_universe")
    mdd = float(metrics.get("max_drawdown", 0) or 0)
    turn = float(metrics.get("avg_turnover", 1) or 1)

    beats_vn = ex_vn is not None and ex_vn > 0
    beats_ew = ex_ew is not None and ex_ew > 0
    dd_ok = (baseline_mdd is None) or ((mdd - baseline_mdd) * 100 >= -2.0)
    turn_ok = turn < TURNOVER_EXCESSIVE_THRESHOLD

    # Check single-year dominance
    single_year_ok = True
    if yearly_returns is not None and not yearly_returns.empty and metrics.get("cumulative_net_return"):
        total_ret = metrics["cumulative_net_return"]
        if abs(total_ret) > 0.01:
            max_year = yearly_returns["year_return"].abs().max()
            single_year_ok = max_year / abs(total_ret) < 0.50

    if beats_vn and beats_ew and dd_ok and turn_ok and single_year_ok:
        return "PORTFOLIO_PROMISING", f"ex_vn={ex_vn:.4f}, ex_ew={ex_ew:.4f}"
    if mdd < (baseline_mdd or 0) and not beats_vn and not beats_ew:
        return "RISK_REDUCTION_ONLY", f"dd_improvement, no benchmark excess"
    if ex_vn is not None and ex_vn < 0 and ex_ew is not None and ex_ew < 0:
        return "REJECTED_PORTFOLIO", f"ex_vn={ex_vn:.4f}, ex_ew={ex_ew:.4f}"
    return "INCONCLUSIVE", f"ex_vn={ex_vn}, ex_ew={ex_ew}"


def run_fh_portfolio(
    outcomes: pd.DataFrame,
    universe_weekly: pd.DataFrame,
    loader: ParquetSymbolLoader,
    out_dir: Path,
    universe_ids: list[str] | None = None,
    membership_wide: pd.DataFrame | None = None,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    """Run Phase 5: full-history portfolio simulation.

    Args:
        membership_wide: ticker-level universe membership from Phase 11.
            When provided, filters by (scan_date, ticker) pairs instead of
            date-only — fixes the v0.1 bug where all universes were identical.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if universe_ids is None:
        universe_ids = FH_PRIMARY_UNIVERSES + MODERN_UNIVERSES

    # Load membership_wide from disk if not passed
    if membership_wide is None:
        membership_path = out_dir / "universe_membership_wide.parquet"
        if membership_path.is_file():
            membership_wide = pd.read_parquet(membership_path)
            membership_wide["scan_date"] = pd.to_datetime(
                membership_wide["scan_date"]
            ).dt.normalize()
            if verbose:
                print("[Phase 5] Loaded ticker-level membership for universe filtering")
        else:
            if verbose:
                print(
                    "[Phase 5] WARNING: universe_membership_wide.parquet not found — "
                    "falling back to date-only filter (run Phase 11 first)"
                )

    df = enrich_outcomes(outcomes)
    df["scan_date"] = pd.to_datetime(df["scan_date"]).dt.normalize()

    bench = load_fh_benchmark()
    all_scan = sorted(df["scan_date"].dropna().unique())
    bench_returns = _bench_weekly_returns(bench, all_scan)

    # Build price cache from parquet loader
    tickers = set(df["ticker"].astype(str).str.upper().unique())
    price_cache: dict[str, pd.DataFrame] = {}
    for t in tickers:
        px = loader(t)
        if px is not None and not px.empty:
            price_cache[t] = px

    equity_parts: list[pd.DataFrame] = []
    turnover_parts: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []

    baseline_mdd_by_uid: dict[str, float | None] = {}

    for uid in universe_ids:
        # Ticker-level filter: (scan_date, ticker) pair from membership_wide
        if membership_wide is not None and uid in membership_wide.columns:
            uid_members = membership_wide[membership_wide[uid] == True][
                ["scan_date", "ticker"]
            ].copy()
            uid_members["_in_universe"] = True
            df_tagged = df.merge(uid_members, on=["scan_date", "ticker"], how="left")
            universe_mask = df_tagged["_in_universe"].fillna(False)
            universe_mask.index = df.index
        else:
            # Legacy fallback: date-only (v0.1 behaviour)
            universe_mask = _adv50_at_scan(df, uid, universe_weekly)
        if verbose:
            print(f"[Phase 5] Universe {uid}: {int(universe_mask.sum())} eligible rows")

        # ADV50 mask from the outcomes (use adv50_vnd column if available, else universe_mask only)
        if "adv50_vnd" in df.columns:
            liquid_mask = pd.to_numeric(df["adv50_vnd"], errors="coerce") > 0
        else:
            liquid_mask = universe_mask

        # Combine universe (active date) mask with variant mask
        for p3_id in P3_VARIANT_MAP:
            try:
                variant_mask = (
                    pd.Series(True, index=df.index)
                    if p3_id == "P3_V0"
                    else build_variant_masks(df).get(P3_VARIANT_MAP[p3_id], (None, pd.Series(True, index=df.index)))[1]
                )
            except Exception:
                variant_mask = pd.Series(True, index=df.index)

            # Combined: universe active dates + variant filter
            split_mask = universe_mask & variant_mask.reindex(df.index, fill_value=False)
            split_name = f"fh_{uid}_{p3_id}"

            for top_n in TOP_N_OPTIONS:
                for rank_mode in RANK_MODES:
                    try:
                        eq, turn = simulate_portfolio(
                            df,
                            portfolio_id=p3_id,
                            split_name=split_name,
                            split_mask=split_mask,
                            variant_mask=variant_mask.reindex(df.index, fill_value=False),
                            top_n=top_n,
                            rank_mode=rank_mode,
                            stocks_dir=None,  # unused — price_cache is used
                            bench_returns=bench_returns,
                            liquid_mask=liquid_mask,
                            price_cache=price_cache,
                        )
                    except Exception as e:
                        if verbose:
                            print(f"[Phase 5] Sim error {p3_id} {uid} {top_n} {rank_mode}: {e}")
                        continue

                    if eq.empty:
                        continue

                    equity_parts.append(eq)
                    turnover_parts.append(turn)

                    m = _metrics_from_equity(eq)
                    m["n_weeks"] = len(eq)

                    # Track baseline MDD
                    if p3_id == "P3_V0" and top_n == 20 and rank_mode == "score_desc":
                        baseline_mdd_by_uid[uid] = m.get("max_drawdown")

                    # Yearly returns for this portfolio
                    if not eq.empty:
                        eq2 = eq.copy()
                        eq2["year"] = pd.to_datetime(eq2["scan_date"]).dt.year
                        yr_df = (
                            eq2.groupby("year")
                            .apply(
                                lambda g: float(
                                    (1.0 + pd.to_numeric(g["net_return_base"], errors="coerce").fillna(0)).prod() - 1.0
                                )
                            )
                            .reset_index()
                        )
                        yr_df.columns = ["year", "year_return"]
                        yr_df["portfolio_id"] = p3_id
                        yr_df["universe_id"] = uid
                        yr_df["split"] = split_name
                        yr_df["top_n"] = top_n
                        yr_df["rank_mode"] = rank_mode
                        yr_df["research_only_flag"] = RESEARCH_ONLY_FLAG
                        yearly_rows.append(yr_df)

                    baseline_mdd = baseline_mdd_by_uid.get(uid)
                    label, evidence = _label_portfolio(m, baseline_mdd, None)

                    metric_rows.append(
                        {
                            "portfolio_id": p3_id,
                            "universe_id": uid,
                            "split": split_name,
                            "top_n": top_n,
                            "rank_mode": rank_mode,
                            "research_only_flag": RESEARCH_ONLY_FLAG,
                            "n_weeks": m.get("n_weeks", 0),
                            "label": label if label in ALLOWED_LABELS else "INCONCLUSIVE",
                            "evidence": evidence,
                            **{k: v for k, v in m.items() if k != "n_weeks"},
                        }
                    )

    equity_wide = pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
    equity_curves = _expand_equity_cost_rows(equity_wide) if not equity_wide.empty else pd.DataFrame()
    turnover_capacity = pd.concat(turnover_parts, ignore_index=True) if turnover_parts else pd.DataFrame()
    portfolio_metrics = pd.DataFrame(metric_rows)
    yearly_returns = pd.concat(yearly_rows, ignore_index=True) if yearly_rows else pd.DataFrame()

    # Regime returns — split by regime column if available
    regime_rows = []
    if not equity_wide.empty and "regime_label" in df.columns:
        for (pid, uid_r, top_n), g in equity_wide.groupby(["portfolio_id", "universe_id", "top_n"]) if "universe_id" in equity_wide.columns else []:
            for regime in df["regime_label"].dropna().unique():
                regime_dates = set(df[df["regime_label"] == regime]["scan_date"])
                rg = g[pd.to_datetime(g["scan_date"]).dt.normalize().isin(regime_dates)]
                w = pd.to_numeric(rg.get("net_return_base"), errors="coerce").fillna(0)
                if len(w) < 5:
                    continue
                regime_rows.append(
                    {
                        "portfolio_id": pid,
                        "universe_id": uid_r,
                        "top_n": top_n,
                        "regime": regime,
                        "n_weeks": len(w),
                        "year_return": float((1 + w).prod() - 1),
                        "research_only_flag": RESEARCH_ONLY_FLAG,
                    }
                )
    regime_returns = pd.DataFrame(regime_rows)

    # Save all outputs
    portfolio_metrics.to_csv(out_dir / "full_history_portfolio_metrics.csv", index=False)
    if not equity_curves.empty:
        equity_curves.to_csv(out_dir / "full_history_equity_curves.csv", index=False)
    if not turnover_capacity.empty:
        turnover_capacity.to_csv(out_dir / "full_history_turnover_capacity.csv", index=False)
    if not yearly_returns.empty:
        yearly_returns.to_csv(out_dir / "full_history_yearly_returns.csv", index=False)
    if not regime_returns.empty:
        regime_returns.to_csv(out_dir / "full_history_regime_returns.csv", index=False)

    if verbose:
        promising = portfolio_metrics[portfolio_metrics.get("label", pd.Series()) == "PORTFOLIO_PROMISING"] if not portfolio_metrics.empty else pd.DataFrame()
        print(f"[Phase 5] Portfolio simulation done. {len(metric_rows)} combinations, {len(promising)} PORTFOLIO_PROMISING")

    return {
        "portfolio_metrics": portfolio_metrics,
        "equity_curves": equity_curves,
        "turnover_capacity": turnover_capacity,
        "yearly_returns": yearly_returns,
        "regime_returns": regime_returns,
    }
