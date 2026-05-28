from __future__ import annotations

import math

import pandas as pd


def _cost_rate(adv50: float | None, base: float) -> float:
    if adv50 is None or not math.isfinite(adv50):
        return base + 0.003
    if adv50 < 5_000_000_000:
        return base + 0.003
    if adv50 < 20_000_000_000:
        return base + 0.0015
    return base + 0.0005


def build_strategy_curves(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["scan_date"] = pd.to_datetime(x["scan_date"])
    records: list[dict] = []
    for dt, g in x.groupby("scan_date"):
        s1a = g[g["is_tier1"] == True]  # noqa: E712
        s1b = g[g["is_tier12"] == True]  # noqa: E712
        s1c = g[g["is_tier12"] == True].sort_values("institutional_accumulation_score", ascending=False).head(10)  # noqa: E712
        s1d = g[g["is_tier123"] == True].sort_values("institutional_accumulation_score", ascending=False).head(20)  # noqa: E712
        q = g.copy()
        q["quintile"] = pd.qcut(q["institutional_accumulation_score"], 5, labels=False, duplicates="drop")
        s2_q5 = q[q["quintile"] == q["quintile"].max()]
        s2_q1 = q[q["quintile"] == q["quintile"].min()]
        s4_safe = g[(g["is_tier123"] == True) & (g["caution_proxy"] == False)]  # noqa: E712
        s4_all = g[g["is_tier123"] == True]  # noqa: E712
        s5 = g[g["is_reject"] == False]  # noqa: E712
        s3_fund = g[(g["is_tier123"] == True) & (g["has_fund_disclosure_tag"] == True)]  # noqa: E712
        s3_non = g[(g["is_tier123"] == True) & (g["has_fund_disclosure_tag"] == False)]  # noqa: E712
        s3_em = g[g["emerging_accumulation_candidate"] == True]  # noqa: E712
        baskets = {
            "S1A_tier1_only": s1a,
            "S1B_tier12_equal": s1b,
            "S1C_top10_tier12": s1c,
            "S1D_top20_tier123": s1d,
            "S2_q5": s2_q5,
            "S2_q1": s2_q1,
            "S3_fund_tagged_tier123": s3_fund,
            "S3_non_fund_tier123": s3_non,
            "S3_emerging_only": s3_em,
            "S4_exclude_caution": s4_safe,
            "S4_include_caution": s4_all,
            "S5_exclude_rejects": s5,
        }
        for name, sub in baskets.items():
            if sub.empty:
                records.append({"scan_date": dt, "strategy": name, "ret_20d_gross": 0.0, "ret_60d_gross": 0.0, "positions": 0})
                continue
            r20 = float(sub["ret_20d"].mean())
            r60 = float(sub["ret_60d"].mean())
            avg_adv = float(sub["adv50_vnd"].mean()) if "adv50_vnd" in sub.columns else None
            low = _cost_rate(avg_adv, 0.0015)
            base = _cost_rate(avg_adv, 0.0030)
            high = _cost_rate(avg_adv, 0.0050)
            records.append(
                {
                    "scan_date": dt,
                    "strategy": name,
                    "ret_20d_gross": r20,
                    "ret_60d_gross": r60,
                    "ret_20d_net_low_cost": r20 - low,
                    "ret_20d_net_base_cost": r20 - base,
                    "ret_20d_net_high_cost": r20 - high,
                    "ret_60d_net_low_cost": r60 - low,
                    "ret_60d_net_base_cost": r60 - base,
                    "ret_60d_net_high_cost": r60 - high,
                    "excess_ret_20d_vs_vnindex": float(sub["excess_ret_20d_vs_vnindex"].mean())
                    if "excess_ret_20d_vs_vnindex" in sub.columns
                    else None,
                    "excess_ret_60d_vs_vnindex": float(sub["excess_ret_60d_vs_vnindex"].mean())
                    if "excess_ret_60d_vs_vnindex" in sub.columns
                    else None,
                    "positions": int(len(sub)),
                }
            )
    return pd.DataFrame(records)


def summarize_metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, g in curves.groupby("strategy"):
        g = g.sort_values("scan_date")
        r = g["ret_20d_gross"].fillna(0.0)
        avg = float(r.mean())
        vol = float(r.std(ddof=0))
        sharpe = (avg / vol) if vol > 0 else 0.0
        cum = float((1.0 + r).prod() - 1.0)
        dd = float((1.0 + r).cumprod().div((1.0 + r).cumprod().cummax()).sub(1.0).min())
        rows.append(
            {
                "strategy": name,
                "CAGR": avg * 12.0,
                "annualized_vol": vol * (12.0**0.5),
                "Sharpe": sharpe,
                "Sortino": sharpe,
                "max_drawdown": dd,
                "hit_rate": float((r > 0).mean()),
                "avg_excess_vs_vnindex": float(g.get("excess_ret_20d_vs_vnindex", pd.Series(dtype=float)).mean()),
                "turnover": 1.0,
                "avg_positions": float(g["positions"].mean()),
                "capacity_adv_participation": float(g["positions"].mean()),
                "gross_return": cum,
                "net_low_cost_return": float((1.0 + g["ret_20d_net_low_cost"].fillna(0)).prod() - 1.0),
                "net_base_cost_return": float((1.0 + g["ret_20d_net_base_cost"].fillna(0)).prod() - 1.0),
                "net_high_cost_return": float((1.0 + g["ret_20d_net_high_cost"].fillna(0)).prod() - 1.0),
            }
        )
    return pd.DataFrame(rows)
