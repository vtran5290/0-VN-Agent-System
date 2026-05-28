from __future__ import annotations

import pandas as pd


def component_ablation(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["score_without_context"] = 0.38 * x["score_money_flow"] + 0.28 * x["score_price_structure"] - 0.16 * x["score_risk_penalty"]
    x["score_without_money_flow"] = 0.18 * x["score_context"] + 0.28 * x["score_price_structure"] - 0.16 * x["score_risk_penalty"]
    x["score_without_price_structure"] = 0.18 * x["score_context"] + 0.38 * x["score_money_flow"] - 0.16 * x["score_risk_penalty"]
    x["score_without_risk_penalty"] = 0.18 * x["score_context"] + 0.38 * x["score_money_flow"] + 0.28 * x["score_price_structure"]
    rows = []
    for col in [
        "institutional_accumulation_score",
        "score_without_context",
        "score_without_money_flow",
        "score_without_price_structure",
        "score_without_risk_penalty",
        "score_mf_cmf",
        "score_mf_obv_pvt",
        "score_mf_adl",
        "score_mf_participation",
    ]:
        q = x.copy()
        q["q"] = pd.qcut(q[col], 5, labels=False, duplicates="drop")
        q5 = q[q["q"] == q["q"].max()]["ret_60d"].mean()
        q1 = q[q["q"] == q["q"].min()]["ret_60d"].mean()
        rows.append({"component": col, "q5_ret60": q5, "q1_ret60": q1, "spread_q5_q1": q5 - q1})
    return pd.DataFrame(rows)


def risk_penalty_calibration(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["risk_bucket"] = pd.cut(x["score_risk_penalty"], bins=[-1, 15, 30, 45, 60, 100], labels=["0-15", "16-30", "31-45", "46-60", "61-100"])
    return (
        x.groupby("risk_bucket")
        .agg(
            n=("ticker", "count"),
            ret_60d_mean=("ret_60d", "mean"),
            max_dd_60d_mean=("max_dd_60d", "mean"),
            p_dd_5=("hit_dd_minus_5pct_60d", "mean"),
            p_dd_10=("hit_dd_minus_10pct_60d", "mean"),
        )
        .reset_index()
    )


def distribution_flag_validation(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    return (
        x.groupby("distribution_risk_flag")
        .agg(
            n=("ticker", "count"),
            ret_60d_mean=("ret_60d", "mean"),
            max_dd_60d_mean=("max_dd_60d", "mean"),
            p_dd_5=("hit_dd_minus_5pct_60d", "mean"),
            p_dd_10=("hit_dd_minus_10pct_60d", "mean"),
        )
        .reset_index()
    )
