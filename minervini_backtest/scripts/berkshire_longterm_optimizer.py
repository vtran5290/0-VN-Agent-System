from __future__ import annotations

"""
berkshire_longterm_optimizer.py

Long-term optimizer for Berkshire-style FA cohort presets on VN equities.

Focus horizons (weeks): 78, 104, 156, 208, 260 (+ 52w as auxiliary).

Design goals:
- Reuse existing FA cohort machinery (fa_cohort.cohort_backtest, FaFilterConfig).
- Define a robustness-first long-term objective (plateau > spike).
- Enforce conservative hard gates for durability.
- Use anchor-based local search + adaptive pruning (self-correcting).
- Implement plateau and era validation to avoid narrow, fragile pockets.

CLI (from repo root):
  cd minervini_backtest
  python scripts/berkshire_longterm_optimizer.py --fa-csv ../data/fa_minervini.csv
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # minervini_backtest
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.cohort_backtest import (  # type: ignore
    _cohort_for_quarter,
    _horizon_exit,
    _load_price_data,
    _next_trading_day_close,
    load_fa_csv,
)
from fa_cohort.fa_filters import FaFilterConfig  # type: ignore


# Core long-term horizons
HORIZONS_LT: Tuple[int, ...] = (78, 104, 156, 208, 260)
# We also look at 52w as a supporting signal (not primary objective).
SUPPORT_HORIZONS: Tuple[int, ...] = (52,)


@dataclass
class LongTermObjectiveWeights:
    """
    Weights and penalties for the long-term robustness objective.

    long_score =
        3.0 * alpha_156w
      + 2.0 * alpha_104w
      + 1.5 * alpha_208w
      + 1.25 * alpha_260w
      + 1.0 * alpha_78w
      + 0.5 * alpha_52w
      - 6.0 * negative_penalty
      - 1.25 * horizon_instability
      + 1.0 * min_alpha_bonus
      + 1.0 * coverage_score
      + 1.0 * subperiod_consistency
    """

    w_78: float = 1.0
    w_104: float = 2.0
    w_156: float = 3.0
    w_208: float = 1.5
    w_260: float = 1.25
    w_52: float = 0.5

    w_negative: float = 6.0
    w_instability: float = 1.25
    w_min_alpha: float = 1.0
    w_coverage: float = 1.0
    w_subperiod: float = 1.0


@dataclass
class LongTermRiskGates:
    """
    Hard gates / reject rules for long-term presets.

    These are intentionally conservative; tweak via CLI if needed.
    """

    # Any relevant long horizon below this absolute floor → reject immediately.
    min_horizon_alpha_floor: float = -0.01

    # Minimum absolute alphas at key long horizons.
    min_alpha_104: float = 0.04
    min_alpha_156: float = 0.10

    # Cohort breadth and era robustness.
    min_avg_annual_n: float = 5.0  # avoid ultra-thin cohorts
    min_years_positive: int = 3  # number of years with positive median alpha
    min_fraction_positive_eras: float = 0.6  # share of eras (years) with positive alpha

    # Ensure winner is not dominated by one subperiod.
    max_era_alpha_ratio: float = 3.0  # max(best_era / worst_positive_era)


def _compute_longterm_metrics(
    fa_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    cfg: FaFilterConfig,
    horizons: Iterable[int],
    bench_symbol: str,
) -> Dict[str, Any] | None:
    """
    Run FA cohort for given config and compute long-term metrics.

    Returns a dict with:
      - median_alpha_by_horizon: {h: alpha}
      - yearly_alpha: DataFrame with columns [year, horizon_weeks, alpha]
      - avg_annual_n: float
      - years_positive: int
      - negative_penalty: float
      - horizon_instability: float
      - min_alpha: float
      - coverage_score: float
      - subperiod_consistency: float
      - fraction_positive_eras: float
      - worst_era_alpha: float
      - in_sample_score, out_of_sample_score, worst_era_score, percent_positive_eras
    """
    cohort_df = _cohort_for_quarter(fa_df, cfg)
    if cohort_df.empty:
        return None

    bench_df = price_data.get(bench_symbol.upper())
    if bench_df is None or bench_df.empty:
        raise ValueError(f"Benchmark symbol {bench_symbol} not found.")

    horizons = list(horizons)
    all_horizons = sorted({*horizons, *SUPPORT_HORIZONS})

    records: List[Dict[str, Any]] = []
    for _, row in cohort_df.iterrows():
        sym = row["symbol"]
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        entry = _next_trading_day_close(px, row["report_date"])
        if entry is None:
            continue
        entry_dt, entry_px = entry
        bench_entry = _next_trading_day_close(bench_df, entry_dt)
        if bench_entry is None:
            continue
        bench_entry_dt, bench_entry_px = bench_entry

        for weeks in all_horizons:
            exit_pair = _horizon_exit(px, entry_dt, weeks)
            bench_exit_pair = _horizon_exit(bench_df, bench_entry_dt, weeks)
            if exit_pair is None or bench_exit_pair is None:
                continue
            _, exit_px = exit_pair
            _, bench_exit_px = bench_exit_pair
            ret = (exit_px / entry_px) - 1.0
            bench_ret = (bench_exit_px / bench_entry_px) - 1.0
            records.append(
                {
                    "year": entry_dt.year,
                    "horizon_weeks": weeks,
                    "alpha": ret - bench_ret,
                }
            )

    if not records:
        return None

    yearly_alpha = (
        pd.DataFrame(records)
        .groupby(["year", "horizon_weeks"])["alpha"]
        .median()
        .reset_index()
    )
    median_alpha_by_h = (
        yearly_alpha.groupby("horizon_weeks")["alpha"].median().to_dict()
    )

    # Require all core long horizons to have data.
    if any(h not in median_alpha_by_h for h in horizons):
        return None

    # Coverage metrics
    annual_counts = cohort_df.groupby("year")["symbol"].nunique()
    avg_annual_n = float(annual_counts.mean()) if not annual_counts.empty else 0.0
    years_pos = int(
        (yearly_alpha.groupby("year")["alpha"].median() > 0).sum()
    )

    # Negative penalty and instability across core long horizons.
    long_alphas_vec = np.array(
        [median_alpha_by_h[h] for h in HORIZONS_LT if h in median_alpha_by_h],
        dtype=float,
    )
    negative_penalty = float(np.abs(long_alphas_vec[long_alphas_vec < 0.0]).sum())
    horizon_instability = float(np.std(long_alphas_vec))  # higher = noisier
    min_alpha = float(long_alphas_vec.min()) if long_alphas_vec.size else 0.0

    # Subperiod consistency: per-year pooled alpha across long horizons.
    long_mask = yearly_alpha["horizon_weeks"].isin(HORIZONS_LT)
    per_year_long = (
        yearly_alpha[long_mask]
        .groupby("year")["alpha"]
        .median()
    )
    if per_year_long.empty:
        fraction_positive_eras = 0.0
        worst_era_alpha = 0.0
        best_era_alpha = 0.0
    else:
        fraction_positive_eras = float((per_year_long > 0.0).mean())
        worst_era_alpha = float(per_year_long.min())
        best_era_alpha = float(per_year_long.max())

    percent_positive_eras = fraction_positive_eras * 100.0

    # Coverage score: soft cap at 20 names/year, plus years_pos bonus.
    coverage_score = min(avg_annual_n / 20.0, 1.0) + min(years_pos / 5.0, 1.0)
    # Subperiod consistency score: combine fraction of eras and worst-era alpha.
    subperiod_consistency = fraction_positive_eras + max(worst_era_alpha, 0.0)

    # Simple in/out-of-sample split by calendar years.
    all_years = sorted(per_year_long.index.tolist())
    if len(all_years) >= 4:
        split_idx = max(2, int(len(all_years) * 0.6))
    elif len(all_years) >= 3:
        split_idx = 2
    else:
        split_idx = len(all_years)
    in_years = all_years[:split_idx]
    out_years = all_years[split_idx:]

    def _era_score(years: List[int]) -> float:
        if not years:
            return 0.0
        sub = per_year_long[per_year_long.index.isin(years)]
        return float(sub.mean()) if not sub.empty else 0.0

    in_sample_score = _era_score(in_years)
    out_of_sample_score = _era_score(out_years)
    worst_era_score = worst_era_alpha

    return {
        "median_alpha_by_horizon": median_alpha_by_h,
        "yearly_alpha": yearly_alpha,
        "avg_annual_n": avg_annual_n,
        "years_positive": years_pos,
        "negative_penalty": negative_penalty,
        "horizon_instability": horizon_instability,
        "min_alpha": min_alpha,
        "coverage_score": coverage_score,
        "subperiod_consistency": subperiod_consistency,
        "fraction_positive_eras": fraction_positive_eras,
        "percent_positive_eras": percent_positive_eras,
        "worst_era_alpha": worst_era_alpha,
        "best_era_alpha": best_era_alpha,
        "in_sample_score": in_sample_score,
        "out_of_sample_score": out_of_sample_score,
        "worst_era_score": worst_era_score,
    }


def _compute_long_score(
    metrics: Dict[str, Any],
    weights: LongTermObjectiveWeights,
) -> float:
    ma = metrics["median_alpha_by_horizon"]
    a78 = float(ma.get(78, 0.0))
    a104 = float(ma.get(104, 0.0))
    a156 = float(ma.get(156, 0.0))
    a208 = float(ma.get(208, 0.0))
    a260 = float(ma.get(260, 0.0))
    a52 = float(ma.get(52, 0.0))

    neg = float(metrics["negative_penalty"])
    instab = float(metrics["horizon_instability"])
    min_alpha = float(metrics["min_alpha"])
    cov = float(metrics["coverage_score"])
    sub = float(metrics["subperiod_consistency"])

    min_alpha_bonus = max(min_alpha, 0.0)

    score = (
        weights.w_156 * a156
        + weights.w_104 * a104
        + weights.w_208 * a208
        + weights.w_260 * a260
        + weights.w_78 * a78
        + weights.w_52 * a52
        - weights.w_negative * neg
        - weights.w_instability * instab
        + weights.w_min_alpha * min_alpha_bonus
        + weights.w_coverage * cov
        + weights.w_subperiod * sub
    )
    return float(score)


def _passes_longterm_risk_gates(
    metrics: Dict[str, Any],
    gates: LongTermRiskGates,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    ma = metrics["median_alpha_by_horizon"]
    avg_annual_n = float(metrics["avg_annual_n"])
    years_pos = int(metrics["years_positive"])
    fraction_pos = float(metrics["fraction_positive_eras"])
    worst_era_alpha = float(metrics["worst_era_alpha"])
    best_era_alpha = float(metrics["best_era_alpha"])

    # Any long horizon below absolute floor?
    for h in HORIZONS_LT:
        if ma.get(h, 0.0) < gates.min_horizon_alpha_floor:
            reasons.append(f"horizon_{h}w_alpha < {gates.min_horizon_alpha_floor}")

    # Key horizon floors.
    if ma.get(104, 0.0) < gates.min_alpha_104:
        reasons.append(f"alpha_104w < {gates.min_alpha_104}")
    if ma.get(156, 0.0) < gates.min_alpha_156:
        reasons.append(f"alpha_156w < {gates.min_alpha_156}")

    if avg_annual_n < gates.min_avg_annual_n:
        reasons.append(f"avg_annual_n < {gates.min_avg_annual_n}")
    if years_pos < gates.min_years_positive:
        reasons.append(f"years_positive < {gates.min_years_positive}")
    if fraction_pos < gates.min_fraction_positive_eras:
        reasons.append(
            f"fraction_positive_eras < {gates.min_fraction_positive_eras}"
        )

    # Avoid eras dominated by a single pocket.
    if best_era_alpha > 0.0 and worst_era_alpha > 0.0:
        ratio = best_era_alpha / max(worst_era_alpha, 1e-6)
        if ratio > gates.max_era_alpha_ratio:
            reasons.append(f"era_concentration_ratio>{gates.max_era_alpha_ratio}")

    return (len(reasons) == 0), reasons


def _config_to_key(cfg: FaFilterConfig) -> Tuple[Any, ...]:
    """Stable tuple key for a FaFilterConfig (used to dedupe trials)."""
    d = asdict(cfg)
    return (
        d.get("roe_min"),
        d.get("debt_to_equity_max"),
        d.get("gross_margin_min"),
        d.get("sales_yoy_min"),
        d.get("earnings_yoy_min"),
        d.get("eps_yoy_min"),
        d.get("margin_yoy_min"),
        bool(d.get("require_earnings_accel")),
        bool(d.get("require_eps_accel")),
    )


def _neighbors_for_anchor(
    cfg: FaFilterConfig,
    search_space: Dict[str, List[Any]],
) -> List[FaFilterConfig]:
    """
    One-step coordinate neighbors for a given anchor config within the discrete search_space.
    Acceleration flags are kept OFF in the core long-term optimizer.
    """
    base = asdict(cfg)
    neighbors: List[FaFilterConfig] = []

    def _adjacent_values(values: List[Any], current: Any) -> List[Any]:
        if current not in values:
            return []
        idx = values.index(current)
        out: List[Any] = []
        if idx - 1 >= 0:
            out.append(values[idx - 1])
        if idx + 1 < len(values):
            out.append(values[idx + 1])
        return out

    for field in [
        "debt_to_equity_max",
        "gross_margin_min",
        "roe_min",
        "sales_yoy_min",
        "earnings_yoy_min",
        "eps_yoy_min",
        "margin_yoy_min",
    ]:
        values = search_space.get(field)
        if not values:
            continue
        for v in _adjacent_values(values, base.get(field)):
            new = dict(base)
            new[field] = v
            # Force accel flags off per design.
            new["require_earnings_accel"] = False
            new["require_eps_accel"] = False
            neighbors.append(FaFilterConfig(**new))

    return neighbors


def _build_anchor_configs() -> Dict[str, FaFilterConfig]:
    """
    Initial long-term hypotheses / anchors.

    These follow the user's Candidate A/B/C plus key existing Berkshire presets.
    """
    anchors: Dict[str, FaFilterConfig] = {}

    # Candidate A: low-debt compounder
    anchors["A_low_debt_compounder"] = FaFilterConfig(
        debt_to_equity_max=0.85,
        gross_margin_min=0.18,
        roe_min=14,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=False,
        require_eps_accel=False,
    )

    # Candidate B: balanced quality
    anchors["B_balanced_quality"] = FaFilterConfig(
        debt_to_equity_max=0.90,
        gross_margin_min=0.20,
        roe_min=15,
        sales_yoy_min=8,
        earnings_yoy_min=3,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=False,
        require_eps_accel=False,
    )

    # Candidate C: quality plus moat bias
    anchors["C_quality_moat"] = FaFilterConfig(
        debt_to_equity_max=0.85,
        gross_margin_min=0.24,
        roe_min=15,
        sales_yoy_min=10,
        earnings_yoy_min=3,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=False,
        require_eps_accel=False,
    )

    # Existing Berkshire low-leverage winner
    anchors["B_low_leverage"] = FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=0.85,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    )

    # Existing Berkshire sweet spot / quality presets as anchors.
    anchors["B1_tuned"] = FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    )
    anchors["B_sweet_spot"] = FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=0.95,
        gross_margin_min=0.19,
        sales_yoy_min=8,
        earnings_yoy_min=3,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    )

    return anchors


def _plateau_neighbors(
    candidate_key: Tuple[Any, ...],
    all_trials: Dict[Tuple[Any, ...], Dict[str, Any]],
    search_space: Dict[str, List[Any]],
) -> List[Dict[str, Any]]:
    """
    Collect direct coordinate neighbors (already evaluated) for plateau validation.
    """
    (
        roe_min,
        debt_to_equity_max,
        gross_margin_min,
        sales_yoy_min,
        earnings_yoy_min,
        eps_yoy_min,
        margin_yoy_min,
        req_ea,
        req_eps,
    ) = candidate_key
    base_cfg = FaFilterConfig(
        roe_min=roe_min,
        debt_to_equity_max=debt_to_equity_max,
        gross_margin_min=gross_margin_min,
        sales_yoy_min=sales_yoy_min,
        earnings_yoy_min=earnings_yoy_min,
        eps_yoy_min=eps_yoy_min,
        margin_yoy_min=margin_yoy_min,
        require_earnings_accel=bool(req_ea),
        require_eps_accel=bool(req_eps),
    )
    neighbor_cfgs = _neighbors_for_anchor(base_cfg, search_space)
    out: List[Dict[str, Any]] = []
    for cfg in neighbor_cfgs:
        k = _config_to_key(cfg)
        trial = all_trials.get(k)
        if trial is not None:
            out.append(trial)
    return out


def _passes_plateau(
    trial: Dict[str, Any],
    all_trials: Dict[Tuple[Any, ...], Dict[str, Any]],
    search_space: Dict[str, List[Any]],
    min_competitive_neighbors: int = 3,
    competitive_delta: float = 0.15,
) -> Tuple[bool, str]:
    """
    Plateau validation:
      - at least min_competitive_neighbors neighbors with long_score within
        competitive_delta fraction of the candidate's long_score.
    """
    key = tuple(trial["config_key"])
    neighbors = _plateau_neighbors(key, all_trials, search_space)
    if not neighbors:
        return False, "no_neighbors_evaluated"

    s = float(trial["long_score"])

    def _competitive(n: Dict[str, Any]) -> bool:
        return float(n["long_score"]) >= (1.0 - competitive_delta) * s

    n_comp = sum(1 for n in neighbors if _competitive(n))
    if n_comp < min_competitive_neighbors:
        return False, f"fragile_plateau_neighbors={n_comp}"
    return True, "plateau_ok"


def _run_longterm_optimizer(
    fa_csv: Path,
    bench: str,
    max_trials_per_anchor: int,
    weights: LongTermObjectiveWeights,
    gates: LongTermRiskGates,
    out_dir: Path,
) -> Dict[str, Any]:
    fa_df = load_fa_csv(fa_csv)
    price_data = _load_price_data()

    out_dir.mkdir(parents=True, exist_ok=True)

    # Long-term parameter search space (discrete, around low-debt / quality anchors).
    search_space: Dict[str, List[Any]] = {
        "debt_to_equity_max": [0.80, 0.85, 0.90, 0.95, 1.00],
        "gross_margin_min": [0.18, 0.20, 0.22, 0.24, 0.26],
        "roe_min": [14, 15, 16, 18],
        "sales_yoy_min": [5, 8, 10],
        "earnings_yoy_min": [None, 0, 3, 5],
        "eps_yoy_min": [None],
        "margin_yoy_min": [0],
        # Acceleration flags intentionally excluded / held at False.
    }

    anchors = _build_anchor_configs()

    # Trial storage: config_key -> trial dict
    all_trials: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    trial_log: List[Dict[str, Any]] = []

    # Failure/success statistics for "self-correcting" search.
    param_fail_counts: Dict[Tuple[str, Any], int] = {}
    param_success_counts: Dict[Tuple[str, Any], int] = {}

    def _record_param_outcome(cfg: FaFilterConfig, success: bool) -> None:
        d = asdict(cfg)
        for name, values in search_space.items():
            if name not in d:
                continue
            val = d[name]
            key = (name, val)
            if success:
                param_success_counts[key] = param_success_counts.get(key, 0) + 1
            else:
                param_fail_counts[key] = param_fail_counts.get(key, 0) + 1

    trial_id = 0

    for anchor_name, anchor_cfg in anchors.items():
        queue: List[FaFilterConfig] = [anchor_cfg]
        tested = 0
        while queue and tested < max_trials_per_anchor:
            cfg = queue.pop(0)
            # Force acceleration flags off in all configs.
            cfg = FaFilterConfig(
                **{
                    **asdict(cfg),
                    "require_earnings_accel": False,
                    "require_eps_accel": False,
                }
            )
            key = _config_to_key(cfg)
            if key in all_trials:
                continue

            # Basic pruning: avoid configs dominated by param values with repeated failures.
            d_cfg = asdict(cfg)
            skip = False
            for pname, values in search_space.items():
                if pname not in d_cfg:
                    continue
                val = d_cfg[pname]
                f = param_fail_counts.get((pname, val), 0)
                s = param_success_counts.get((pname, val), 0)
                if f >= 4 and s == 0:
                    skip = True
                    break
            if skip:
                continue

            tested += 1
            trial_id += 1

            metrics = _compute_longterm_metrics(
                fa_df=fa_df,
                price_data=price_data,
                cfg=cfg,
                horizons=list(HORIZONS_LT),
                bench_symbol=bench,
            )
            if metrics is None:
                # treat as hard failure
                _record_param_outcome(cfg, success=False)
                continue

            long_score = _compute_long_score(metrics, weights)
            passes_gates, gate_reasons = _passes_longterm_risk_gates(metrics, gates)

            _record_param_outcome(cfg, success=passes_gates)

            # Approximate PASS behavior from run_cohort_backtest: positive medians on all long horizons and >=3 positive years.
            pass_flag = (
                all(metrics["median_alpha_by_horizon"].get(h, 0.0) > 0.0 for h in HORIZONS_LT)
                and metrics["years_positive"] >= 3
            )

            trial = {
                "trial_id": trial_id,
                "anchor": anchor_name,
                "config": asdict(cfg),
                "config_key": list(key),
                "median_alpha_by_horizon": metrics["median_alpha_by_horizon"],
                "avg_annual_n": metrics["avg_annual_n"],
                "years_positive": metrics["years_positive"],
                "negative_penalty": metrics["negative_penalty"],
                "horizon_instability": metrics["horizon_instability"],
                "min_alpha": metrics["min_alpha"],
                "coverage_score": metrics["coverage_score"],
                "subperiod_consistency": metrics["subperiod_consistency"],
                "fraction_positive_eras": metrics["fraction_positive_eras"],
                "percent_positive_eras": metrics["percent_positive_eras"],
                "worst_era_alpha": metrics["worst_era_alpha"],
                "best_era_alpha": metrics["best_era_alpha"],
                "in_sample_score": metrics["in_sample_score"],
                "out_of_sample_score": metrics["out_of_sample_score"],
                "worst_era_score": metrics["worst_era_score"],
                "long_score": long_score,
                "passes_gates": passes_gates,
                "gate_reasons": gate_reasons,
                "pass_flag": pass_flag,
            }
            all_trials[key] = trial
            trial_log.append(trial)

            # If this config passes gates, add its neighbors to queue (coordinate descent / local expansion).
            if passes_gates:
                neighbors = _neighbors_for_anchor(cfg, search_space)
                for n_cfg in neighbors:
                    n_key = _config_to_key(n_cfg)
                    if n_key not in all_trials:
                        queue.append(n_cfg)

    # Plateau validation and leaderboard.
    promotable: List[Dict[str, Any]] = []
    for trial in trial_log:
        if not trial["passes_gates"]:
            trial["plateau_ok"] = False
            trial["plateau_reason"] = "failed_risk_gates"
            continue
        ok, reason = _passes_plateau(trial, all_trials, search_space)
        trial["plateau_ok"] = ok
        trial["plateau_reason"] = reason
        if ok:
            promotable.append(trial)

    def _top_by(field: str, n: int = 50) -> List[Dict[str, Any]]:
        return sorted(promotable, key=lambda t: float(t[field]), reverse=True)[:n]

    leaderboard = {
        "top_long_score": _top_by("long_score", n=50),
        "top_156w": sorted(
            promotable,
            key=lambda t: float(t["median_alpha_by_horizon"].get(156, 0.0)),
            reverse=True,
        )[:50],
        "top_104w": sorted(
            promotable,
            key=lambda t: float(t["median_alpha_by_horizon"].get(104, 0.0)),
            reverse=True,
        )[:50],
    }

    # Simple Pareto frontier on (long_score, subperiod_consistency, coverage_score).
    pareto: List[Dict[str, Any]] = []
    for t in promotable:
        dominated = False
        for u in promotable:
            if u is t:
                continue
            if (
                float(u["long_score"]) >= float(t["long_score"])
                and float(u["subperiod_consistency"]) >= float(t["subperiod_consistency"])
                and float(u["coverage_score"]) >= float(t["coverage_score"])
                and (
                    float(u["long_score"]) > float(t["long_score"])
                    or float(u["subperiod_consistency"]) > float(t["subperiod_consistency"])
                    or float(u["coverage_score"]) > float(t["coverage_score"])
                )
            ):
                dominated = True
                break
        if not dominated:
            pareto.append(t)

    # Parameter importance diagnostics.
    param_importance: Dict[str, Dict[str, Any]] = {}
    for (pname, val), fails in param_fail_counts.items():
        succ = param_success_counts.get((pname, val), 0)
        total = succ + fails
        if total == 0:
            continue
        param_importance.setdefault(pname, {})
        param_importance[pname][str(val)] = {
            "success": succ,
            "fail": fails,
            "success_rate": succ / total,
        }

    # Serialize trials and leaderboard.
    trials_path = out_dir / "longterm_trials.json"
    leaderboard_path = out_dir / "longterm_leaderboard.json"
    pareto_path = out_dir / "longterm_pareto.json"
    param_importance_path = out_dir / "longterm_param_importance.json"

    trials_path.write_text(json.dumps(trial_log, indent=2), encoding="utf-8")
    leaderboard_path.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    pareto_path.write_text(json.dumps(pareto, indent=2), encoding="utf-8")
    param_importance_path.write_text(
        json.dumps(param_importance, indent=2), encoding="utf-8"
    )

    return {
        "trials_path": str(trials_path),
        "leaderboard_path": str(leaderboard_path),
        "pareto_path": str(pareto_path),
        "param_importance_path": str(param_importance_path),
        "n_trials": len(trial_log),
        "n_promotable": len(promotable),
        "n_pareto": len(pareto),
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Long-term Berkshire FA cohort preset optimizer (VN)"
    )
    p.add_argument(
        "--fa-csv",
        required=True,
        help="Path to FA CSV (e.g. ../data/fa_minervini.csv)",
    )
    p.add_argument(
        "--bench",
        default="VNINDEX",
        help="Benchmark symbol",
    )
    p.add_argument(
        "--max-trials-per-anchor",
        type=int,
        default=80,
        help=(
            "Maximum number of configs to test per anchor "
            "(upper bound; actual may be lower due to pruning)."
        ),
    )
    p.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs" / "berkshire_longterm"),
        help="Output directory for optimizer artifacts.",
    )
    args = p.parse_args()

    fa_csv = Path(args.fa_csv)
    out_dir = Path(args.out_dir)

    weights = LongTermObjectiveWeights()
    gates = LongTermRiskGates()

    summary = _run_longterm_optimizer(
        fa_csv=fa_csv,
        bench=args.bench,
        max_trials_per_anchor=args.max_trials_per_anchor,
        weights=weights,
        gates=gates,
        out_dir=out_dir,
    )

    print(
        "Long-term optimizer completed: "
        f"{summary['n_trials']} trials, "
        f"{summary['n_promotable']} promotable, "
        f"{summary['n_pareto']} Pareto-front presets.",
        flush=True,
    )
    print(f"Trials log: {summary['trials_path']}")
    print(f"Leaderboard: {summary['leaderboard_path']}")
    print(f"Pareto frontier: {summary['pareto_path']}")
    print(f"Param importance: {summary['param_importance_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

