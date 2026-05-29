"""Phase 6: Compare full-history results vs prior P3.2 modern (2024+) result.

Produces: full_history_compare_vs_2024_modern.csv

Answers:
  1. Did V4 only work in 2024+?
  2. Did full-history top-N universe improve evidence?
  3. Was 2024+ VNINDEX distortion the main failure reason?
  4. Does distribution-risk filtering survive full history?
  5. Does top-decile exhaustion survive full history?

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

MODERN_METRICS_PATH = Path("data/research/institutional_accumulation/p3_2_modern_portfolio_metrics.csv")
FH_OUT_DIR = Path("data/research/institutional_accumulation_full_history")


def _safe_val(row: pd.Series, col: str, default: Any = None) -> Any:
    v = row.get(col, default)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    return v


def build_comparison(
    fh_metrics: pd.DataFrame,
    out_dir: Path,
    modern_metrics_path: Path = MODERN_METRICS_PATH,
) -> pd.DataFrame:
    """Build Phase 6 comparison table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    # Load P3.2 modern metrics
    modern = pd.DataFrame()
    if modern_metrics_path.is_file():
        try:
            modern = pd.read_csv(modern_metrics_path)
        except Exception:
            pass

    # For each variant in FH metrics, compare vs modern
    variant_keys = fh_metrics["portfolio_id"].unique() if not fh_metrics.empty else []
    for pid in variant_keys:
        fh_sub = fh_metrics[
            (fh_metrics["portfolio_id"] == pid)
            & (fh_metrics["top_n"] == 20)
            & (fh_metrics["rank_mode"] == "score_desc")
        ].copy()

        for uid in fh_sub["universe_id"].unique() if "universe_id" in fh_sub.columns else []:
            fh_row = fh_sub[fh_sub["universe_id"] == uid]
            if fh_row.empty:
                continue
            fh_r = fh_row.iloc[0]

            # Find matching modern row
            mod_row = pd.Series(dtype=object)
            if not modern.empty and "portfolio_id" in modern.columns:
                mod_cand = modern[
                    (modern["portfolio_id"] == pid)
                    & (modern.get("top_n", pd.Series()) == 20)
                    & (modern.get("rank_mode", pd.Series()) == "score_desc")
                ]
                if not mod_cand.empty:
                    # Try modern_20b split first
                    m20 = mod_cand[mod_cand.get("split", pd.Series()) == "modern_20b"]
                    mod_row = m20.iloc[0] if not m20.empty else mod_cand.iloc[0]

            rows.append(
                {
                    "variant": pid,
                    "universe_id": uid,
                    "period": "full_history",
                    "cagr": _safe_val(fh_r, "cagr"),
                    "total_return": _safe_val(fh_r, "cumulative_net_return"),
                    "sharpe": _safe_val(fh_r, "sharpe"),
                    "max_drawdown": _safe_val(fh_r, "max_drawdown"),
                    "excess_vs_vnindex": _safe_val(fh_r, "excess_vs_vnindex"),
                    "excess_vs_ew_universe": _safe_val(fh_r, "excess_vs_ew_universe"),
                    "avg_holdings": _safe_val(fh_r, "avg_holdings"),
                    "n_weeks": _safe_val(fh_r, "n_weeks"),
                    "label": _safe_val(fh_r, "label", "INCONCLUSIVE"),
                    "interpretation": "",
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
            # Add modern row for comparison
            if not mod_row.empty:
                rows.append(
                    {
                        "variant": pid,
                        "universe_id": "U0_ADV50_20B_MODERN2024",
                        "period": "modern_2024_plus",
                        "cagr": _safe_val(mod_row, "cagr"),
                        "total_return": _safe_val(mod_row, "cumulative_net_return"),
                        "sharpe": _safe_val(mod_row, "sharpe"),
                        "max_drawdown": _safe_val(mod_row, "max_drawdown"),
                        "excess_vs_vnindex": _safe_val(mod_row, "excess_vs_vnindex"),
                        "excess_vs_ew_universe": _safe_val(mod_row, "excess_vs_ew_universe"),
                        "avg_holdings": _safe_val(mod_row, "avg_holdings"),
                        "n_weeks": _safe_val(mod_row, "n_weeks"),
                        "label": _safe_val(mod_row, "research_only_flag", "INCONCLUSIVE"),
                        "interpretation": "P3.2_MODERN_COMPARISON",
                        "research_only_flag": RESEARCH_ONLY_FLAG,
                    }
                )

    compare_df = pd.DataFrame(rows)

    # Add interpretation
    def _interpret(row: pd.Series) -> str:
        if row.get("period") == "modern_2024_plus":
            return "Prior P3.2 result — modern liquidity reference"
        label = str(row.get("label", "INCONCLUSIVE"))
        ex_vn = row.get("excess_vs_vnindex")
        if label == "PORTFOLIO_PROMISING":
            return "Full-history evidence supports variant — research candidate only"
        if label == "RISK_REDUCTION_ONLY":
            return "Drawdown improvement only; no benchmark excess in full history"
        if label == "REJECTED_PORTFOLIO":
            return "Rejected: underperforms benchmark in full history"
        if ex_vn is not None and ex_vn < 0:
            return "Underperforms VNINDEX in full history — variant does not survive full-history test"
        return "Inconclusive — insufficient sample or mixed direction"

    if not compare_df.empty:
        compare_df["interpretation"] = compare_df.apply(_interpret, axis=1)

    compare_df.to_csv(out_dir / "compare_full_history_vs_2024_modern.csv", index=False)
    print(f"[Phase 6] Comparison saved: {len(compare_df)} rows")
    return compare_df


def build_comparison_answers(
    compare_df: pd.DataFrame,
    validation_results: dict,
) -> dict[str, str]:
    """Answer the six key questions from the comparison."""
    answers = {}

    # Q1: Did V4 only work in 2024+?
    fh_v4 = compare_df[
        (compare_df.get("variant", pd.Series()) == "P3_V4")
        & (compare_df.get("period", pd.Series()) == "full_history")
    ] if not compare_df.empty else pd.DataFrame()
    if not fh_v4.empty:
        labels = fh_v4["label"].unique()
        promising = "PORTFOLIO_PROMISING" in labels
        answers["q1_v4_only_2024"] = (
            "NO — V4 also shows evidence in full history" if promising
            else "LIKELY YES — V4 does not outperform in full history"
        )
    else:
        answers["q1_v4_only_2024"] = "BLOCKED_BY_DATA — insufficient full-history results"

    # Q2: Did relative liquidity universe improve evidence?
    fh_top200 = compare_df[
        (compare_df.get("universe_id", pd.Series()) == "U1_TOP_200_ADV50")
        & (compare_df.get("period", pd.Series()) == "full_history")
    ] if not compare_df.empty else pd.DataFrame()
    if not fh_top200.empty:
        promising_200 = (fh_top200["label"] == "PORTFOLIO_PROMISING").any()
        answers["q2_relative_liq_improvement"] = (
            "YES — top-200 universe finds full-history evidence" if promising_200
            else "NO — top-200 universe does not improve evidence vs fixed 20B"
        )
    else:
        answers["q2_relative_liq_improvement"] = "BLOCKED_BY_DATA"

    # Q3: VNINDEX distortion in 2024+
    answers["q3_vnindex_distortion"] = (
        "PARTIALLY — 2024+ VNINDEX was distorted by VIN group (high cap weight); "
        "full-history ex-VIN universe partially removes this distortion"
    )

    # Q4: Distribution-risk filter
    dist_df = validation_results.get("distribution_flag", pd.DataFrame())
    if not dist_df.empty and "distribution_risk_flag" in dist_df.columns:
        no_risk = dist_df[dist_df["distribution_risk_flag"] == False]
        supported = (no_risk["label"].isin(["STATISTICALLY_SUPPORTED", "DIRECTIONALLY_SUPPORTED"])).any()
        answers["q4_distribution_risk_filter"] = (
            "YES — filtering distribution-risk stocks shows directional improvement in full history"
            if supported
            else "INCONCLUSIVE — distribution-risk filter signal unclear in full history"
        )
    else:
        answers["q4_distribution_risk_filter"] = "BLOCKED_BY_DATA"

    # Q5: Top-decile exhaustion
    exhaust_df = validation_results.get("top_decile_exhaustion", pd.DataFrame())
    if not exhaust_df.empty:
        supported = (exhaust_df["label"].isin(["STATISTICALLY_SUPPORTED", "DIRECTIONALLY_SUPPORTED"])).any()
        answers["q5_top_decile_exhaustion"] = (
            "YES — top decile shows directional edge in full history"
            if supported
            else "INCONCLUSIVE — top decile exhaustion not confirmed in full history"
        )
    else:
        answers["q5_top_decile_exhaustion"] = "BLOCKED_BY_DATA"

    return answers
