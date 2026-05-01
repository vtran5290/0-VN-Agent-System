from __future__ import annotations

"""
berkshire_shortterm_optimizer.py

Short-term / mid-term optimizer for Berkshire-style FA cohort presets on VN equities.

Focus horizons (weeks): 13, 25, 52

Design goals:
- Reuse existing FA cohort machinery (fa_cohort.cohort_backtest, FaFilterConfig).
- Provide configurable short-term objective functions (score_13, score_25, score_52).
- Enforce conservative hard gates to avoid fragile / overfit presets.
- Use local neighborhood search around anchor presets + adaptive pruning rather than brute-force grid.
- Log all trials with rich diagnostics for later analysis / learning.
"""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # minervini_backtest
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from fa_cohort.cohort_backtest import (  # type: ignore  # noqa: E402
    _cohort_for_quarter,
    _horizon_exit,
    _load_price_data,
    _next_trading_day_close,
    load_fa_csv,
)
from fa_cohort.fa_filters import FaFilterConfig  # type: ignore  # noqa: E402


HORIZONS_ST: Tuple[int, int, int] = (13, 25, 52)


@dataclass
class ObjectiveWeights:
    """Weights and penalties for short-term objectives."""

    # negative_penalty = sum abs(negative alphas)
    # horizon_instability = variability across horizons
    # coverage_score = reward for breadth / years
    # subperiod_consistency = reward for per-era robustness

    # score_13
    w13_alpha_13: float = 3.0
    w13_alpha_25: float = 2.0
    w13_alpha_52: float = 1.0
    w13_negative: float = 4.0
    w13_instability: float = 1.5
    w13_coverage: float = 1.0
    w13_subperiod: float = 0.5

    # score_25
    w25_alpha_13: float = 1.0
    w25_alpha_25: float = 2.5
    w25_alpha_52: float = 2.0
    w25_negative: float = 4.0
    w25_instability: float = 1.25
    w25_coverage: float = 1.0
    w25_subperiod: float = 1.0

    # score_52
    w52_alpha_13: float = 1.0
    w52_alpha_25: float = 1.5
    w52_alpha_52: float = 3.0
    w52_negative: float = 5.0
    w52_instability: float = 1.0
    w52_coverage: float = 1.0
    w52_subperiod: float = 1.0


@dataclass
class RiskGates:
    """Hard gates / reject rules for short-term presets."""

    min_alpha_25: float = 0.0
    min_alpha_52: float = 0.0
    min_horizon_alpha: float = -0.02  # any horizon below this → reject
    min_avg_annual_n: float = 5.0  # avoid tiny cohorts
    min_years_positive: int = 3  # number of years with positive median alpha (all horizons pooled)
    min_fraction_positive_eras: float = 0.6  # share of eras with positive alpha


def _compute_shortterm_metrics(
    fa_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    cfg: FaFilterConfig,
    horizons: Iterable[int],
    bench_symbol: str,
) -> Dict[str, Any] | None:
    """
    Run FA cohort for given config and compute short-term metrics on 13/25/52w.

    Returns a dict with:
      - median_alpha_by_horizon: {h: alpha}
      - yearly_alpha: DataFrame with columns [year, horizon_weeks, alpha]
      - avg_annual_n: float
      - years_positive: int
      - negative_penalty: float
      - horizon_instability: float
      - coverage_score: float
      - subperiod_consistency: float
    """
    cohort_df = _cohort_for_quarter(fa_df, cfg)
    if cohort_df.empty:
        return None

    bench_df = price_data.get(bench_symbol.upper())
    if bench_df is None or bench_df.empty:
        raise ValueError(f"Benchmark symbol {bench_symbol} not found.")

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

        for weeks in horizons:
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

    yearly_alpha = pd.DataFrame(records).groupby(["year", "horizon_weeks"])["alpha"].median().reset_index()
    median_alpha_by_h = yearly_alpha.groupby("horizon_weeks")["alpha"].median().to_dict()

    # Require all requested horizons to have data
    horizons = list(horizons)
    if any(h not in median_alpha_by_h for h in horizons):
        return None

    # Coverage metrics
    annual_counts = cohort_df.groupby("year")["symbol"].nunique()
    avg_annual_n = float(annual_counts.mean()) if not annual_counts.empty else 0.0
    years_pos = int((yearly_alpha.groupby("year")["alpha"].median() > 0).sum())

    # Negative penalty and instability across horizons
    alphas_vec = np.array([median_alpha_by_h[h] for h in horizons], dtype=float)
    negative_penalty = float(np.abs(alphas_vec[alphas_vec < 0.0]).sum())
    horizon_instability = float(np.std(alphas_vec))  # higher = noisier

    # Subperiod consistency: share of years with positive pooled alpha, and worst-year alpha
    per_year_alpha = yearly_alpha.groupby("year")["alpha"].median()
    if per_year_alpha.empty:
        fraction_positive_eras = 0.0
        worst_era_alpha = 0.0
    else:
        fraction_positive_eras = float((per_year_alpha > 0.0).mean())
        worst_era_alpha = float(per_year_alpha.min())

    # Coverage score: soft cap at 20 names/year, plus years_pos bonus
    coverage_score = min(avg_annual_n / 20.0, 1.0) + min(years_pos / 5.0, 1.0)
    # Subperiod consistency score: combine fraction of eras and worst-era alpha
    subperiod_consistency = fraction_positive_eras + max(worst_era_alpha, 0.0)

    return {
        "median_alpha_by_horizon": median_alpha_by_h,
        "yearly_alpha": yearly_alpha,
        "avg_annual_n": avg_annual_n,
        "years_positive": years_pos,
        "negative_penalty": negative_penalty,
        "horizon_instability": horizon_instability,
        "coverage_score": coverage_score,
        "subperiod_consistency": subperiod_consistency,
        "fraction_positive_eras": fraction_positive_eras,
        "worst_era_alpha": worst_era_alpha,
    }


def _compute_objective_scores(
    metrics: Dict[str, Any],
    weights: ObjectiveWeights,
) -> Dict[str, float]:
    ma = metrics["median_alpha_by_horizon"]
    a13 = float(ma.get(13, 0.0))
    a25 = float(ma.get(25, 0.0))
    a52 = float(ma.get(52, 0.0))
    neg = float(metrics["negative_penalty"])
    instab = float(metrics["horizon_instability"])
    cov = float(metrics["coverage_score"])
    sub = float(metrics["subperiod_consistency"])

    score_13 = (
        weights.w13_alpha_13 * a13
        + weights.w13_alpha_25 * a25
        + weights.w13_alpha_52 * a52
        - weights.w13_negative * neg
        - weights.w13_instability * instab
        + weights.w13_coverage * cov
        + weights.w13_subperiod * sub
    )
    score_25 = (
        weights.w25_alpha_13 * a13
        + weights.w25_alpha_25 * a25
        + weights.w25_alpha_52 * a52
        - weights.w25_negative * neg
        - weights.w25_instability * instab
        + weights.w25_coverage * cov
        + weights.w25_subperiod * sub
    )
    score_52 = (
        weights.w52_alpha_13 * a13
        + weights.w52_alpha_25 * a25
        + weights.w52_alpha_52 * a52
        - weights.w52_negative * neg
        - weights.w52_instability * instab
        + weights.w52_coverage * cov
        + weights.w52_subperiod * sub
    )

    return {"score_13": float(score_13), "score_25": float(score_25), "score_52": float(score_52)}


def _passes_risk_gates(
    metrics: Dict[str, Any],
    gates: RiskGates,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    ma = metrics["median_alpha_by_horizon"]
    a13 = float(ma.get(13, 0.0))
    a25 = float(ma.get(25, 0.0))
    a52 = float(ma.get(52, 0.0))
    avg_annual_n = float(metrics["avg_annual_n"])
    years_pos = int(metrics["years_positive"])
    fraction_pos = float(metrics["fraction_positive_eras"])

    if a25 < gates.min_alpha_25:
        reasons.append(f"alpha_25w < {gates.min_alpha_25}")
    if a52 < gates.min_alpha_52:
        reasons.append(f"alpha_52w < {gates.min_alpha_52}")
    for h in (13, 25, 52):
        if ma.get(h, 0.0) < gates.min_horizon_alpha:
            reasons.append(f"horizon_{h}w_alpha < {gates.min_horizon_alpha}")
    if avg_annual_n < gates.min_avg_annual_n:
        reasons.append(f"avg_annual_n < {gates.min_avg_annual_n}")
    if years_pos < gates.min_years_positive:
        reasons.append(f"years_positive < {gates.min_years_positive}")
    if fraction_pos < gates.min_fraction_positive_eras:
        reasons.append(f"fraction_positive_eras < {gates.min_fraction_positive_eras}")

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
    ]:
        values = search_space.get(field)
        if not values:
            continue
        for v in _adjacent_values(values, base.get(field)):
            new = dict(base)
            new[field] = v
            neighbors.append(FaFilterConfig(**new))

    # Boolean accel flags: flip individually; both-on only as branch
    for field in ["require_earnings_accel", "require_eps_accel"]:
        if field in search_space:
            new = dict(base)
            new[field] = not bool(base.get(field))
            neighbors.append(FaFilterConfig(**new))

    # Explicit both-accel neighbor if both dimensions exist in space
    if "require_earnings_accel" in search_space and "require_eps_accel" in search_space:
        new = dict(base)
        new["require_earnings_accel"] = True
        new["require_eps_accel"] = True
        neighbors.append(FaFilterConfig(**new))

    return neighbors


def _build_anchor_configs() -> Dict[str, FaFilterConfig]:
    """Initial short-term hypotheses / anchors."""
    anchors: Dict[str, FaFilterConfig] = {}

    # Candidate A: short-term balanced improver
    anchors["A_balanced_improver"] = FaFilterConfig(
        debt_to_equity_max=0.90,
        gross_margin_min=0.18,
        roe_min=14,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=True,
        require_eps_accel=False,
    )

    # Candidate B: short-term burst
    anchors["B_short_burst"] = FaFilterConfig(
        debt_to_equity_max=1.00,
        gross_margin_min=0.15,
        roe_min=13,
        sales_yoy_min=12,
        earnings_yoy_min=7,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=False,
        require_eps_accel=True,
    )

    # Candidate C: short-term quality carry
    anchors["C_quality_carry"] = FaFilterConfig(
        debt_to_equity_max=0.85,
        gross_margin_min=0.20,
        roe_min=15,
        sales_yoy_min=8,
        earnings_yoy_min=3,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=False,
        require_eps_accel=False,
    )

    # Include two existing Berkshire winners as additional anchors
    anchors["B2_pro"] = FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=0.8,
        gross_margin_min=0.30,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    )
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

    return anchors


def _plateau_neighbors(
    candidate_key: Tuple[Any, ...],
    all_trials: Dict[Tuple[Any, ...], Dict[str, Any]],
    search_space: Dict[str, List[Any]],
) -> List[Dict[str, Any]]:
    """
    Collect direct coordinate neighbors (already evaluated) for plateau validation.
    """
    # Reconstruct cfg from key
    roe_min, debt_to_equity_max, gross_margin_min, sales_yoy_min, earnings_yoy_min, eps_yoy_min, margin_yoy_min, req_ea, req_eps = (
        candidate_key
    )
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
      - at least min_competitive_neighbors neighbors with objective scores within competitive_delta fraction
        of the candidate's scores.
    """
    key = tuple(trial["config_key"])
    neighbors = _plateau_neighbors(key, all_trials, search_space)
    if not neighbors:
        return False, "no_neighbors_evaluated"

    s13 = float(trial["score_13"])
    s25 = float(trial["score_25"])
    s52 = float(trial["score_52"])

    def _competitive(n: Dict[str, Any]) -> bool:
        return (
            float(n["score_13"]) >= (1.0 - competitive_delta) * s13
            and float(n["score_25"]) >= (1.0 - competitive_delta) * s25
            and float(n["score_52"]) >= (1.0 - competitive_delta) * s52
        )

    n_comp = sum(1 for n in neighbors if _competitive(n))
    if n_comp < min_competitive_neighbors:
        return False, f"fragile_plateau_neighbors={n_comp}"
    return True, "plateau_ok"


def _run_shortterm_optimizer(
    fa_csv: Path,
    bench: str,
    max_trials_per_anchor: int,
    weights: ObjectiveWeights,
    gates: RiskGates,
    out_dir: Path,
) -> Dict[str, Any]:
    fa_df = load_fa_csv(fa_csv)
    price_data = _load_price_data()

    out_dir.mkdir(parents=True, exist_ok=True)

    # Short-term parameter search space
    search_space: Dict[str, List[Any]] = {
        "debt_to_equity_max": [0.85, 0.90, 0.95, 1.00],
        "gross_margin_min": [0.15, 0.18, 0.20, 0.22],
        "roe_min": [13, 14, 15, 16],
        "sales_yoy_min": [8, 10, 12, 15],
        "earnings_yoy_min": [0, 3, 5, 7, 10],
        "eps_yoy_min": [None, 0, 3],
        "margin_yoy_min": [0],
        "require_earnings_accel": [False, True],
        "require_eps_accel": [False, True],
    }

    anchors = _build_anchor_configs()

    # Trial storage: config_key -> trial dict
    all_trials: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    trial_log: List[Dict[str, Any]] = []

    # Simple failure statistics for "self-correcting" search
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
            key = _config_to_key(cfg)
            if key in all_trials:
                continue

            # Basic pruning: avoid configs dominated by param values with repeated failures
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

            metrics = _compute_shortterm_metrics(
                fa_df=fa_df,
                price_data=price_data,
                cfg=cfg,
                horizons=HORIZONS_ST,
                bench_symbol=bench,
            )
            if metrics is None:
                # treat as hard failure
                _record_param_outcome(cfg, success=False)
                continue

            scores = _compute_objective_scores(metrics, weights)
            passes_gates, gate_reasons = _passes_risk_gates(metrics, gates)
            _record_param_outcome(cfg, success=passes_gates)

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
                "coverage_score": metrics["coverage_score"],
                "subperiod_consistency": metrics["subperiod_consistency"],
                "fraction_positive_eras": metrics["fraction_positive_eras"],
                "worst_era_alpha": metrics["worst_era_alpha"],
                "score_13": scores["score_13"],
                "score_25": scores["score_25"],
                "score_52": scores["score_52"],
                "passes_gates": passes_gates,
                "gate_reasons": gate_reasons,
            }
            all_trials[key] = trial
            trial_log.append(trial)

            # If this config passes gates, add its neighbors to queue
            if passes_gates:
                neighbors = _neighbors_for_anchor(cfg, search_space)
                for n_cfg in neighbors:
                    n_key = _config_to_key(n_cfg)
                    if n_key not in all_trials:
                        queue.append(n_cfg)

    # Plateau validation and leaderboard
    promotable: List[Dict[str, Any]] = []
    for trial in trial_log:
        if not trial["passes_gates"]:
            continue
        ok, reason = _passes_plateau(trial, all_trials, search_space)
        trial["plateau_ok"] = ok
        trial["plateau_reason"] = reason
        if ok:
            promotable.append(trial)

    def _top_by(field: str, n: int = 20) -> List[Dict[str, Any]]:
        return sorted(promotable, key=lambda t: float(t[field]), reverse=True)[:n]

    leaderboard = {
        "top_13": _top_by("score_13", n=20),
        "top_25": _top_by("score_25", n=20),
        "top_52": _top_by("score_52", n=20),
    }

    # Very simple Pareto frontier on (score_13, score_25, score_52, subperiod_consistency)
    pareto: List[Dict[str, Any]] = []
    for t in promotable:
        dominated = False
        for u in promotable:
            if u is t:
                continue
            if (
                float(u["score_13"]) >= float(t["score_13"])
                and float(u["score_25"]) >= float(t["score_25"])
                and float(u["score_52"]) >= float(t["score_52"])
                and float(u["subperiod_consistency"]) >= float(t["subperiod_consistency"])
                and (
                    float(u["score_13"]) > float(t["score_13"])
                    or float(u["score_25"]) > float(t["score_25"])
                    or float(u["score_52"]) > float(t["score_52"])
                    or float(u["subperiod_consistency"]) > float(t["subperiod_consistency"])
                )
            ):
                dominated = True
                break
        if not dominated:
            pareto.append(t)

    # Serialize trials and leaderboard
    trials_path = out_dir / "shortterm_trials.json"
    leaderboard_path = out_dir / "shortterm_leaderboard.json"
    pareto_path = out_dir / "shortterm_pareto.json"

    trials_path.write_text(json.dumps(trial_log, indent=2), encoding="utf-8")
    leaderboard_path.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    pareto_path.write_text(json.dumps(pareto, indent=2), encoding="utf-8")

    return {
        "trials_path": str(trials_path),
        "leaderboard_path": str(leaderboard_path),
        "pareto_path": str(pareto_path),
        "n_trials": len(trial_log),
        "n_promotable": len(promotable),
        "n_pareto": len(pareto),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Short-term Berkshire FA cohort preset optimizer (VN)")
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
        help="Maximum number of configs to test per anchor (upper bound; actual may be lower due to pruning).",
    )
    p.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs" / "berkshire_shortterm"),
        help="Output directory for optimizer artifacts.",
    )
    args = p.parse_args()

    fa_csv = Path(args.fa_csv)
    out_dir = Path(args.out_dir)

    weights = ObjectiveWeights()
    gates = RiskGates()

    summary = _run_shortterm_optimizer(
        fa_csv=fa_csv,
        bench=args.bench,
        max_trials_per_anchor=args.max_trials_per_anchor,
        weights=weights,
        gates=gates,
        out_dir=out_dir,
    )

    print(
        "Short-term optimizer completed: "
        f"{summary['n_trials']} trials, "
        f"{summary['n_promotable']} promotable, "
        f"{summary['n_pareto']} Pareto-front presets.",
        flush=True,
    )
    print(f"Trials log: {summary['trials_path']}")
    print(f"Leaderboard: {summary['leaderboard_path']}")
    print(f"Pareto frontier: {summary['pareto_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

