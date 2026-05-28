from __future__ import annotations

from typing import Any

import pandas as pd


def _tiny_spread(spread: float | None, *, threshold: float = 0.005) -> bool:
    if spread is None or pd.isna(spread):
        return True
    return abs(float(spread)) < threshold


def _label_generic_spread(spread: float | None) -> tuple[str, str]:
    if spread is None or pd.isna(spread):
        return "INCONCLUSIVE", "spread unavailable"
    if _tiny_spread(spread):
        return "INCONCLUSIVE", "spread too small for robust evidence"
    if float(spread) > 0:
        return "SUPPORTED", "positive spread above minimum effect threshold"
    return "REJECTED", "negative spread"


def label_composite(
    spread: float | None,
    yearly_q5_minus_q1: pd.Series,
) -> tuple[str, str]:
    non_null = yearly_q5_minus_q1.dropna()
    positive_years = int((non_null > 0).sum())
    if _tiny_spread(spread) or positive_years < 5:
        return "INCONCLUSIVE", "weak spread and insufficient yearly consistency"
    return _label_generic_spread(spread)


def label_tier1(coverage_summary: dict[str, Any]) -> tuple[str, str]:
    tier1_rows = int(float(coverage_summary.get("tier1_rows", 0) or 0))
    if tier1_rows == 0:
        return "INCONCLUSIVE", "no Tier 1 rows in sample"
    return "INCONCLUSIVE", "Tier 1 evidence requires stricter statistical test"


def label_tier12(metrics: pd.DataFrame) -> tuple[str, str]:
    s1b = metrics[metrics["strategy"] == "S1B_tier12_equal"] if not metrics.empty else pd.DataFrame()
    if s1b.empty:
        return "INCONCLUSIVE", "Tier 1/2 strategy row missing"
    gross = float(s1b.iloc[0].get("gross_return", 0.0) or 0.0)
    if gross < 0:
        return "REJECTED", "negative gross return in Tier 1/2 simulation"
    return "INCONCLUSIVE", "Tier 1/2 needs stronger statistical validation"


def label_fund_backed(context_mode: str) -> tuple[str, str]:
    if str(context_mode).upper() == "OHLCV_ONLY":
        return "BLOCKED_BY_DATA", "fund context unavailable under OHLCV_ONLY"
    if "SYNTHETIC" in str(context_mode).upper():
        return "SYNTHETIC_ONLY", "fund evidence is synthetic sensitivity only"
    return "INCONCLUSIVE", "fund-backed evidence requires PIT context validation"


def label_distribution_risk(dist_flag: pd.DataFrame) -> tuple[str, str]:
    if dist_flag.empty:
        return "INCONCLUSIVE", "distribution validation unavailable"
    flagged = dist_flag[dist_flag["distribution_risk_flag"] == True]  # noqa: E712
    normal = dist_flag[dist_flag["distribution_risk_flag"] == False]  # noqa: E712
    if flagged.empty or normal.empty:
        return "INCONCLUSIVE", "missing flagged/unflagged comparison buckets"
    f_dd = float(flagged["max_dd_60d_mean"].iloc[0])
    n_dd = float(normal["max_dd_60d_mean"].iloc[0])
    if f_dd < n_dd:
        return "SUPPORTED_AS_RISK_WARNING", "supports drawdown warning use, not standalone alpha"
    return "INCONCLUSIVE", "risk warning direction is not stable"


def label_warning_system(warning_validation: pd.DataFrame) -> tuple[str, str]:
    if warning_validation.empty or "ret_60d_mean" not in warning_validation.columns:
        return "INCONCLUSIVE", "warning validation unavailable"
    mean_ret = float(pd.to_numeric(warning_validation["ret_60d_mean"], errors="coerce").dropna().mean())
    if mean_ret > 0:
        return "INCONCLUSIVE_POSITIVE_DIRECTION", "positive direction without strict test confirmation"
    return "INCONCLUSIVE", "no robust warning-edge confirmation"


def label_changes_event(changes_event: pd.DataFrame) -> tuple[str, str]:
    if changes_event.empty or "ret_60d_mean" not in changes_event.columns:
        return "REJECTED", "changes event study unavailable for positive-edge support"
    vals = pd.to_numeric(changes_event["ret_60d_mean"], errors="coerce").dropna()
    if vals.empty:
        return "REJECTED", "changes event returns unavailable for positive-edge support"
    if float(vals.mean()) <= 0:
        return "REJECTED", "changes/upgrades event study does not support positive edge"
    return "REJECTED", "changes/upgrades not robust under strict testing"


def label_risk_penalty() -> tuple[str, str]:
    return "INCONCLUSIVE", "mixed utility: drawdown warning value, not clean alpha"


def label_emerging() -> tuple[str, str]:
    return "INCONCLUSIVE", "emerging list not supported as alpha basket yet"


def build_evidence_summary(
    *,
    ablation: pd.DataFrame,
    yearly: pd.DataFrame,
    coverage_summary: dict[str, Any],
    metrics: pd.DataFrame,
    dist_flag: pd.DataFrame,
    warning_validation: pd.DataFrame,
    changes_event: pd.DataFrame,
    context_mode: str,
) -> tuple[dict[str, tuple[str, str]], pd.DataFrame]:
    yearly_spread = yearly["q5_minus_q1_ret60"] if "q5_minus_q1_ret60" in yearly.columns else pd.Series(dtype=float)
    composite_row = ablation[ablation["component"] == "institutional_accumulation_score"] if not ablation.empty else pd.DataFrame()
    composite_spread = composite_row["spread_q5_q1"].iloc[0] if not composite_row.empty else None

    evidence: dict[str, tuple[str, str]] = {
        "composite_score": label_composite(composite_spread, yearly_spread),
        "tier1": label_tier1(coverage_summary),
        "tier12": label_tier12(metrics),
        "distribution_risk_flag": label_distribution_risk(dist_flag),
        "risk_penalty": label_risk_penalty(),
        "emerging_list": label_emerging(),
        "fund_backed": label_fund_backed(context_mode),
        "warning_system": label_warning_system(warning_validation),
        "changes_upgrades": label_changes_event(changes_event),
    }

    ab = ablation.copy()
    if ab.empty:
        ab["evidence_status"] = []
        ab["note"] = []
        return evidence, ab

    statuses: list[str] = []
    notes: list[str] = []
    for _, row in ab.iterrows():
        component = str(row.get("component", ""))
        spread = row.get("spread_q5_q1")
        if component == "institutional_accumulation_score":
            status, note = evidence["composite_score"]
        else:
            status, note = _label_generic_spread(spread)
        statuses.append(status)
        notes.append(note)
    ab["evidence_status"] = statuses
    ab["note"] = notes
    return evidence, ab
