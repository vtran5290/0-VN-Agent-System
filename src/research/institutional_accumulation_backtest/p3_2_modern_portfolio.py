"""P3.2 Modern-Liquidity Portfolio Simulation.

Primary evaluation window: 2024-01-01 onward (the period where the VN market
has sufficient liquid names at ADV50 >= 20B VND to fill portfolios).

RESEARCH_ONLY_NOT_PRODUCTION — no A3/S3/OMS/final_action/DNSE/live orders touched.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data_loader import load_benchmark_df, resolve_sources
from .p2_variants import P3_VARIANT_MAP, build_variant_masks, enrich_outcomes, get_p3_variant_mask
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
    _p3_split_masks,
    simulate_portfolio,
)

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

MODERN_WINDOW_START = "2024-01-01"

LIQUIDITY_CONFIGS: dict[str, float] = {
    "20b": 20_000_000_000.0,
    "10b": 10_000_000_000.0,
    "5b": 5_000_000_000.0,
}
PRIMARY_LIQUIDITY = "20b"

ALLOWED_PORTFOLIO_LABELS = {
    "PORTFOLIO_PROMISING",
    "RISK_REDUCTION_ONLY",
    "REJECTED_PORTFOLIO",
    "INCONCLUSIVE",
    "BLOCKED_BY_DATA",
}


# ---------------------------------------------------------------------------
# Split masks for modern window
# ---------------------------------------------------------------------------


def _modern_splits(df: pd.DataFrame, liq_threshold: float) -> dict[str, pd.Series]:
    modern = df["scan_date"] >= pd.Timestamp(MODERN_WINDOW_START)
    vin_ok = df.get("is_vin", pd.Series(False, index=df.index)) == False  # noqa: E712
    return {
        f"modern_{_liq_label(liq_threshold)}": modern,
        f"modern_{_liq_label(liq_threshold)}_ex_vin": modern & vin_ok,
    }


def _liq_label(threshold: float) -> str:
    for label, val in LIQUIDITY_CONFIGS.items():
        if abs(val - threshold) < 1:
            return label
    return f"{int(threshold // 1_000_000_000)}b"


def _liquid_mask(df: pd.DataFrame, threshold: float) -> pd.Series:
    return pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= threshold


# ---------------------------------------------------------------------------
# Metrics + labeling
# ---------------------------------------------------------------------------


def _metrics_from_equity(eq: pd.DataFrame) -> dict[str, Any]:
    if eq.empty:
        return {}
    w = pd.to_numeric(eq["net_return_base"], errors="coerce")
    ann = _annualize_from_weekly(w)
    eq_s = pd.to_numeric(eq["equity_base"], errors="coerce")
    mdd = _max_drawdown(eq_s)
    bench = pd.to_numeric(eq.get("vnindex_return"), errors="coerce")
    ew = pd.to_numeric(eq.get("ew_universe_return"), errors="coerce")
    cum_net = float((1.0 + w.fillna(0)).prod() - 1.0)
    cum_bench = float((1.0 + bench.fillna(0)).prod() - 1.0) if bench.notna().any() else None
    cum_ew = float((1.0 + ew.fillna(0)).prod() - 1.0) if ew.notna().any() else None
    weeks_lt10 = int((pd.to_numeric(eq.get("holdings"), errors="coerce") < 10).sum())
    worst = w.nsmallest(10).tolist()
    best = w.nlargest(10).tolist()
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
        "excess_vs_vnindex": None if cum_bench is None else cum_net - cum_bench,
        "excess_vs_ew_universe": None if cum_ew is None else cum_net - cum_ew,
        "avg_turnover": float(pd.to_numeric(eq.get("turnover"), errors="coerce").mean()),
        "avg_holdings": float(pd.to_numeric(eq.get("holdings"), errors="coerce").mean()),
        "weeks_lt10_holdings": weeks_lt10,
        "worst_10_weeks": json.dumps(worst),
        "best_10_weeks": json.dumps(best),
    }


def label_portfolio_modern(
    metrics: pd.DataFrame,
    portfolio_id: str,
    primary_split: str,
    ex_vin_split: str,
    baseline_id: str = "P3_V0_LIQUID_UNIVERSE_BASELINE",
) -> tuple[str, str, str]:
    full = metrics[
        (metrics["portfolio_id"] == portfolio_id)
        & (metrics["split"] == primary_split)
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    ex = metrics[
        (metrics["portfolio_id"] == portfolio_id)
        & (metrics["split"] == ex_vin_split)
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    base = metrics[
        (metrics["portfolio_id"] == baseline_id)
        & (metrics["split"] == primary_split)
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    if full.empty:
        return "BLOCKED_BY_DATA", "no metrics for primary split", "check simulation"

    row = full.iloc[0]
    n_weeks = int(row.get("n_weeks", 0))
    if n_weeks < 20:
        return "BLOCKED_BY_DATA", f"only {n_weeks} weeks", "insufficient history"

    avg_hold = float(row.get("avg_holdings", 0) or 0)
    if avg_hold < 10:
        return "BLOCKED_BY_DATA", f"avg_holdings={avg_hold:.1f}", "too few holdings"

    ex_vs_vn = row.get("excess_vs_vnindex")
    ex_vs_ew = row.get("excess_vs_ew_universe")
    mdd = float(row.get("max_drawdown", 0) or 0)
    turn = float(row.get("avg_turnover", 1) or 1)

    base_mdd = float(base.iloc[0]["max_drawdown"]) if not base.empty else mdd
    dd_improve_pp = (mdd - base_mdd) * 100.0

    ex_ok = True
    if not ex.empty:
        ex_row = ex.iloc[0]
        ex_ok = (
            (ex_row.get("excess_vs_vnindex") or -1) > 0
            and (ex_row.get("excess_vs_ew_universe") or -1) > 0
        )

    beats_vn = ex_vs_vn is not None and ex_vs_vn > 0
    beats_ew = ex_vs_ew is not None and ex_vs_ew > 0
    dd_ok = dd_improve_pp >= -2.0
    turn_ok = turn < TURNOVER_EXCESSIVE_THRESHOLD

    if beats_vn and beats_ew and dd_ok and turn_ok and ex_ok:
        return (
            "PORTFOLIO_PROMISING",
            f"ex_vnindex={ex_vs_vn:.4f}, ex_ew={ex_vs_ew:.4f}, dd_vs_v0_pp={dd_improve_pp:.2f}",
            "research candidate only — not production",
        )
    if dd_improve_pp <= -3.0 and not beats_vn and not beats_ew:
        return (
            "RISK_REDUCTION_ONLY",
            f"dd_vs_v0_pp={dd_improve_pp:.2f}, ex_vnindex={ex_vs_vn}",
            "risk filter research path only",
        )
    if (ex_vs_vn is not None and ex_vs_vn < 0) and (ex_vs_ew is not None and ex_vs_ew < 0) and dd_improve_pp < 0:
        return "REJECTED_PORTFOLIO", f"ex_vn={ex_vs_vn:.4f}, ex_ew={ex_vs_ew:.4f}", "do not promote"

    return (
        "INCONCLUSIVE",
        f"ex_vn={ex_vs_vn}, ex_ew={ex_vs_ew}, dd_pp={dd_improve_pp:.2f}",
        "needs more evidence",
    )


# ---------------------------------------------------------------------------
# Liquidity sensitivity table (pre-computed forward returns, no price cache)
# ---------------------------------------------------------------------------


def _sensitivity_run(
    df: pd.DataFrame,
    liq_threshold: float,
    variant_key: str,
    top_n: int = 20,
) -> dict[str, Any]:
    """Simple sensitivity using pre-computed ret_20d — no simulation needed."""
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    modern = enriched[enriched["scan_date"] >= pd.Timestamp(MODERN_WINDOW_START)].copy()
    liq = _liquid_mask(modern, liq_threshold)

    p2_masks = build_variant_masks(modern)
    if variant_key == "liquid_universe":
        var_mask = liq
    elif variant_key in p2_masks:
        var_mask = p2_masks[variant_key][1]
    else:
        var_mask = pd.Series(True, index=modern.index)

    candidates = modern[
        liq.reindex(modern.index, fill_value=False) & var_mask.reindex(modern.index, fill_value=False)
    ].copy()

    if candidates.empty:
        return {
            "liq_label": _liq_label(liq_threshold),
            "variant_key": variant_key,
            "top_n": top_n,
            "n_scans": 0,
            "avg_candidates": 0.0,
            "avg_holdings_at_top_n": 0.0,
            "ret_20d_mean": None,
            "ret_20d_hit_rate": None,
            "excess_20d_mean": None,
            "ret_60d_mean": None,
            "ret_60d_hit_rate": None,
        }

    rows: list[dict[str, Any]] = []
    for dt, g in candidates.groupby("scan_date"):
        ranked = g.sort_values("institutional_accumulation_score", ascending=False).head(top_n)
        r20 = pd.to_numeric(ranked.get("ret_20d", pd.Series(dtype=float)), errors="coerce").dropna()
        r60 = pd.to_numeric(ranked.get("ret_60d", pd.Series(dtype=float)), errors="coerce").dropna()
        ex20 = pd.to_numeric(ranked.get("excess_ret_20d_vs_vnindex", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "scan_date": dt,
                "n_candidates": len(g),
                "n_held": len(ranked),
                "ret_20d": float(r20.mean()) if len(r20) else None,
                "excess_20d": float(ex20.mean()) if len(ex20) else None,
                "ret_60d": float(r60.mean()) if len(r60) else None,
                "hit_20d": float((r20 > 0).mean()) if len(r20) else None,
                "hit_60d": float((r60 > 0).mean()) if len(r60) else None,
            }
        )
    sens = pd.DataFrame(rows)
    return {
        "liq_label": _liq_label(liq_threshold),
        "variant_key": variant_key,
        "top_n": top_n,
        "n_scans": len(sens),
        "avg_candidates": float(sens["n_candidates"].mean()),
        "avg_holdings_at_top_n": float(sens["n_held"].mean()),
        "ret_20d_mean": float(pd.to_numeric(sens["ret_20d"], errors="coerce").mean()),
        "ret_20d_hit_rate": float(pd.to_numeric(sens["hit_20d"], errors="coerce").mean()),
        "excess_20d_mean": float(pd.to_numeric(sens["excess_20d"], errors="coerce").mean()),
        "ret_60d_mean": float(pd.to_numeric(sens["ret_60d"], errors="coerce").mean()),
        "ret_60d_hit_rate": float(pd.to_numeric(sens["hit_60d"], errors="coerce").mean()),
    }


def build_sensitivity_table(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for p3_id, v_key in P3_VARIANT_MAP.items():
        for liq_label, threshold in LIQUIDITY_CONFIGS.items():
            r = _sensitivity_run(df, threshold, v_key, top_n=top_n)
            r["portfolio_id"] = p3_id
            rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4-week holding sensitivity (uses ret_20d proxy, no price cache needed)
# ---------------------------------------------------------------------------


def holding_period_sensitivity(
    df: pd.DataFrame,
    liq_threshold: float = LIQUIDITY_CONFIGS[PRIMARY_LIQUIDITY],
    top_n: int = 20,
) -> pd.DataFrame:
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    modern = enriched[enriched["scan_date"] >= pd.Timestamp(MODERN_WINDOW_START)].copy()
    liq = _liquid_mask(modern, liq_threshold)
    liq_cands = modern[liq.reindex(modern.index, fill_value=False)].copy()

    horizon_map = {
        "weekly_5d": "ret_5d",
        "2week_10d": "ret_10d",
        "4week_20d": "ret_20d",
        "12week_60d": "ret_60d",
    }

    rows: list[dict[str, Any]] = []
    for dt, g in liq_cands.groupby("scan_date"):
        ranked = g.sort_values("institutional_accumulation_score", ascending=False).head(top_n)
        for label, col in horizon_map.items():
            r = pd.to_numeric(ranked.get(col, pd.Series(dtype=float)), errors="coerce").dropna()
            bn_col = f"vnindex_ret_{col.split('_')[1]}"
            b = pd.to_numeric(ranked.get(bn_col, pd.Series(dtype=float)), errors="coerce").dropna()
            rows.append(
                {
                    "scan_date": dt,
                    "holding_label": label,
                    "return_column": col,
                    "n_held": len(ranked),
                    "n_with_return": len(r),
                    "mean_return": float(r.mean()) if len(r) else None,
                    "hit_rate": float((r > 0).mean()) if len(r) else None,
                    "mean_bench": float(b.mean()) if len(b) else None,
                    "mean_excess": float((r - b.reindex(r.index)).mean()) if len(r) and len(b) else None,
                    "liq_threshold": liq_threshold,
                    "top_n": top_n,
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main simulation runner
# ---------------------------------------------------------------------------


@dataclass
class P32Outputs:
    portfolio_metrics: pd.DataFrame
    equity_curves: pd.DataFrame
    turnover_capacity: pd.DataFrame
    yearly_returns: pd.DataFrame
    sensitivity: pd.DataFrame
    diagnostic_summary: pd.DataFrame


def run_p3_2_modern(outcomes: pd.DataFrame, out_dir: Path) -> P32Outputs:
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = resolve_sources()
    bench = load_benchmark_df(sources.benchmark_path)

    df = enrich_outcomes(outcomes)
    df["scan_date"] = pd.to_datetime(df["scan_date"])

    tickers = set(df["ticker"].astype(str).str.upper().unique())
    price_cache = _build_price_cache(tickers, sources.stocks_dir)

    all_scan = sorted(df["scan_date"].dropna().unique())
    bench_returns = _bench_weekly_returns(bench, all_scan)

    equity_parts: list[pd.DataFrame] = []
    turnover_parts: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []

    for liq_label, liq_threshold in LIQUIDITY_CONFIGS.items():
        liq_mask_series = _liquid_mask(df, liq_threshold)
        splits = _modern_splits(df, liq_threshold)
        primary_split = f"modern_{liq_label}"
        ex_vin_split = f"modern_{liq_label}_ex_vin"

        for p3_id in P3_VARIANT_MAP:
            variant_mask = get_p3_variant_mask(df, p3_id)
            for split_name, split_mask in splits.items():
                for top_n in TOP_N_OPTIONS:
                    for rank_mode in RANK_MODES:
                        eq, turn = simulate_portfolio(
                            df,
                            portfolio_id=p3_id,
                            split_name=split_name,
                            split_mask=split_mask,
                            variant_mask=variant_mask,
                            top_n=top_n,
                            rank_mode=rank_mode,
                            stocks_dir=sources.stocks_dir,
                            bench_returns=bench_returns,
                            liquid_mask=liq_mask_series,
                            price_cache=price_cache,
                        )
                        if eq.empty:
                            continue
                        equity_parts.append(eq)
                        turnover_parts.append(turn)
                        m = _metrics_from_equity(eq)
                        m["avg_adv_participation"] = (
                            float(pd.to_numeric(turn["adv50_vnd_median"], errors="coerce").median())
                            if not turn.empty
                            else None
                        )
                        metric_rows.append(
                            {
                                "portfolio_id": p3_id,
                                "split": split_name,
                                "top_n": top_n,
                                "rank_mode": rank_mode,
                                "liq_threshold_label": liq_label,
                                "liq_threshold_vnd": liq_threshold,
                                "research_only_flag": RESEARCH_ONLY_FLAG,
                                "n_weeks": len(eq),
                                **m,
                            }
                        )

    equity_wide = pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
    equity_curves = _expand_equity_cost_rows(equity_wide)
    turnover_capacity = pd.concat(turnover_parts, ignore_index=True) if turnover_parts else pd.DataFrame()
    portfolio_metrics = pd.DataFrame(metric_rows)

    # Yearly returns
    yearly_rows: list[dict[str, Any]] = []
    if not equity_wide.empty:
        ew = equity_wide.copy()
        ew["year"] = pd.to_datetime(ew["scan_date"]).dt.year
        for keys, g in ew.groupby(["portfolio_id", "split", "top_n", "rank_mode", "year"]):
            pid, split, tn, rm, year = keys
            w = pd.to_numeric(g["net_return_base"], errors="coerce").fillna(0)
            yearly_rows.append(
                {
                    "portfolio_id": pid,
                    "split": split,
                    "top_n": int(tn),
                    "rank_mode": rm,
                    "year": int(year),
                    "year_return": float((1.0 + w).prod() - 1.0),
                }
            )
    yearly_returns = pd.DataFrame(yearly_rows)

    # Sensitivity table
    sensitivity = build_sensitivity_table(df, top_n=20)

    # Diagnostic summary
    summary_rows: list[dict[str, Any]] = []
    for p3_id in P3_VARIANT_MAP:
        for liq_label in LIQUIDITY_CONFIGS:
            primary_split = f"modern_{liq_label}"
            ex_vin_split = f"modern_{liq_label}_ex_vin"
            label, evidence, step = label_portfolio_modern(
                portfolio_metrics,
                p3_id,
                primary_split=primary_split,
                ex_vin_split=ex_vin_split,
            )
            summary_rows.append(
                {
                    "portfolio_id": p3_id,
                    "liq_threshold_label": liq_label,
                    "primary_split": primary_split,
                    "label": label if label in ALLOWED_PORTFOLIO_LABELS else "INCONCLUSIVE",
                    "evidence": evidence,
                    "recommended_next_step": step,
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    diagnostic_summary = pd.DataFrame(summary_rows)

    portfolio_metrics.to_csv(out_dir / "p3_2_modern_portfolio_metrics.csv", index=False)
    equity_curves.to_csv(out_dir / "p3_2_modern_equity_curves.csv", index=False)
    turnover_capacity.to_csv(out_dir / "p3_2_modern_turnover_capacity.csv", index=False)
    yearly_returns.to_csv(out_dir / "p3_2_modern_yearly_returns.csv", index=False)
    sensitivity.to_csv(out_dir / "p3_2_modern_sensitivity.csv", index=False)
    diagnostic_summary.to_csv(out_dir / "p3_2_diagnostic_summary.csv", index=False)

    return P32Outputs(portfolio_metrics, equity_curves, turnover_capacity, yearly_returns, sensitivity, diagnostic_summary)
