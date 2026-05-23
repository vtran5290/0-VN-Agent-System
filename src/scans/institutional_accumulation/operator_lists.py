"""Shared operator display list selectors (no score/tier changes)."""
from __future__ import annotations

import pandas as pd

from .operator_explain import FUND_BUCKETS

MAX_PER_BUCKET = 8
IMPORTANT_REJECT_MAX = 8
CAUTION_RISK_THRESHOLD = 45


def top_tier_df(df: pd.DataFrame) -> pd.DataFrame:
    """Universe for bucket-mix percentages: all Tier 1–3 names."""
    return df[df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])]


def caution_mask(df: pd.DataFrame) -> pd.Series:
    """Same criteria as distortion/caution display list (section 4)."""
    return (
        (df["vingroup_distortion_flag"] == True)  # noqa: E712
        | (df["distribution_risk_flag"] == True)  # noqa: E712
        | (df["score_risk_penalty"] >= CAUTION_RISK_THRESHOLD)
    )


def _pick(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.head(n) if not df.empty else df


def fund_backed_top(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[
        (df["has_fund_disclosure_tag"] == True)  # noqa: E712
        & df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])
    ].sort_values("institutional_accumulation_score", ascending=False)
    return _pick(sub, MAX_PER_BUCKET)


def emerging_top(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["emerging_accumulation_candidate"] == True].sort_values(  # noqa: E712
        "institutional_accumulation_score", ascending=False
    )
    return _pick(sub, MAX_PER_BUCKET)


def caution_top(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[caution_mask(df) & df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])].sort_values(
        "score_risk_penalty", ascending=False
    )
    return _pick(sub, MAX_PER_BUCKET)


def important_rejects(df: pd.DataFrame) -> pd.DataFrame:
    in_core = df["in_consensus_core"] == True if "in_consensus_core" in df.columns else False  # noqa: E712
    in_comm = (
        df["in_commentary_mention"] == True if "in_commentary_mention" in df.columns else False  # noqa: E712
    )
    sub = df[
        (df["tier"] == "Reject")
        & ((df["fund_context_bucket"].isin(FUND_BUCKETS)) | in_core | in_comm)
    ].copy()
    sort_cols = ["institutional_accumulation_score"]
    if "in_consensus_core" in sub.columns:
        sub["_core_sort"] = sub["in_consensus_core"].astype(int)
        sort_cols = ["_core_sort"] + sort_cols
    sub = sub.sort_values(sort_cols, ascending=False)
    return _pick(sub, IMPORTANT_REJECT_MAX)
