from __future__ import annotations

import pandas as pd


def yearly_validation(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["year"] = pd.to_datetime(x["scan_date"]).dt.year
    x["q"] = pd.qcut(x["institutional_accumulation_score"], 5, labels=False, duplicates="drop")
    out = (
        x.groupby("year")
        .agg(
            n=("ticker", "count"),
            tier12_ret60=("ret_60d", lambda s: float(pd.Series(s).mean())),
            q5_ret60=("ret_60d", lambda s: float(x.loc[s.index][x.loc[s.index, "q"] == x["q"].max()]["ret_60d"].mean()) if len(s) else None),
            q1_ret60=("ret_60d", lambda s: float(x.loc[s.index][x.loc[s.index, "q"] == x["q"].min()]["ret_60d"].mean()) if len(s) else None),
        )
        .reset_index()
    )
    if not out.empty:
        out["q5_minus_q1_ret60"] = out["q5_ret60"] - out["q1_ret60"]
    return out


def score_decile_calibration(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["score_decile"] = pd.qcut(x["institutional_accumulation_score"], 10, labels=False, duplicates="drop")
    return (
        x.groupby("score_decile")
        .agg(
            n=("ticker", "count"),
            p_ret_20d_neg=("ret_20d", lambda s: float((pd.Series(s) < 0).mean())),
            p_ret_60d_neg=("ret_60d", lambda s: float((pd.Series(s) < 0).mean())),
            p_maxdd_60d_gt5=("max_dd_60d", lambda s: float((pd.Series(s) <= -0.05).mean())),
            p_maxdd_60d_gt10=("max_dd_60d", lambda s: float((pd.Series(s) <= -0.10).mean())),
        )
        .reset_index()
    )


def regime_validation(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["fragile_uptrend_narrow_leadership_proxy", "correction_or_bear", "normal_regime"] if c in df.columns]
    if not cols:
        return pd.DataFrame(columns=["regime", "n", "ret_60d_mean", "max_dd_60d_mean"])
    rows = []
    for c in cols:
        sub = df[df[c] == True]  # noqa: E712
        rows.append(
            {
                "regime": c,
                "n": len(sub),
                "ret_60d_mean": float(sub["ret_60d"].mean()) if not sub.empty else None,
                "max_dd_60d_mean": float(sub["max_dd_60d"].mean()) if not sub.empty else None,
            }
        )
    return pd.DataFrame(rows)


def vin_sensitivity_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, sub in [("full", df), ("ex_vin", df[df["is_vin"] == False]), ("vin_only", df[df["is_vin"] == True])]:  # noqa: E712
        rows.append(
            {
                "universe": label,
                "n": len(sub),
                "ret_60d_mean": float(sub["ret_60d"].mean()) if not sub.empty else None,
                "max_dd_60d_mean": float(sub["max_dd_60d"].mean()) if not sub.empty else None,
            }
        )
    return pd.DataFrame(rows)
