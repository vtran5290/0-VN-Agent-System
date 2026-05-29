from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data_loader import load_symbol_df, resolve_sources


ALLOWED_SUMMARY_LABELS = {
    "CONFIRMED_INVERSION",
    "CONFIRMED_FULL_INVERSION",
    "TOP_DECILE_EXHAUSTION",
    "NON_MONOTONIC_HUMP_SHAPE",
    "MEASUREMENT_ARTIFACT",
    "INCONCLUSIVE_SMALL_SPREAD",
    "HORIZON_MISMATCH",
    "REGIME_DEPENDENT",
    "EXHAUSTION_CONTAMINATED",
    "RISK_FILTER_USEFUL",
    "PROMISING_RESEARCH_DIRECTION",
    "COMPONENT_FAILURE",
    "THRESHOLD_FAILURE",
    "INCONCLUSIVE",
}


@dataclass
class P1Outputs:
    measurement_integrity: pd.DataFrame
    score_decile_autopsy: pd.DataFrame
    component_diagnostics: pd.DataFrame
    feature_lead_lag: pd.DataFrame
    accumulation_vs_exhaustion: pd.DataFrame
    unit_audit: pd.DataFrame
    distribution_flag_diagnostic: pd.DataFrame
    regime_dependency: pd.DataFrame
    horizon_dependency: pd.DataFrame
    tier_threshold_diagnostics: pd.DataFrame
    diagnostic_summary: pd.DataFrame


def _q_bucket_spread(df: pd.DataFrame, score_col: str, ret_col: str, q: int = 5) -> float | None:
    x = df[[score_col, ret_col]].dropna()
    if x.empty or x[score_col].nunique() < 2:
        return None
    try:
        x = x.copy()
        x["bucket"] = pd.qcut(x[score_col], q, labels=False, duplicates="drop")
    except Exception:
        return None
    if x["bucket"].nunique() < 2:
        return None
    top = x[x["bucket"] == x["bucket"].max()][ret_col].mean()
    bot = x[x["bucket"] == x["bucket"].min()][ret_col].mean()
    if pd.isna(top) or pd.isna(bot):
        return None
    return float(top - bot)


def _safe_mean(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce")
    if s.dropna().empty:
        return None
    return float(s.mean())


def _safe_rate(mask: pd.Series) -> float | None:
    s = pd.to_numeric(mask, errors="coerce")
    if s.dropna().empty:
        return None
    return float(s.mean())


def _extension_unit_and_scale(series: pd.Series) -> tuple[str, float, float]:
    s = pd.to_numeric(series, errors="coerce").dropna().abs()
    if s.empty:
        return "unknown", float("nan"), float("nan")
    med = float(s.median())
    p90 = float(s.quantile(0.90))
    if p90 > 2:
        return "percent_points", med, p90
    return "decimal", med, p90


def _extension_threshold_value(series: pd.Series, threshold_pct: float) -> float:
    unit, _, _ = _extension_unit_and_scale(series)
    return float(threshold_pct) if unit == "percent_points" else float(threshold_pct) / 100.0


def extension_unit_audit(outcomes: pd.DataFrame) -> pd.DataFrame:
    ext = pd.to_numeric(outcomes.get("extension_pct_above_ma20"), errors="coerce")
    unit, med, p90 = _extension_unit_and_scale(ext)
    rows = []
    for metric, pct in [
        ("healthy_accumulation_candidate", 12.0),
        ("late_stage_exhaustion_candidate", 15.0),
        ("base_building_candidate", 8.0),
    ]:
        thr = _extension_threshold_value(ext, pct)
        rows.append(
            {
                "metric": metric,
                "observed_median": med,
                "observed_p90": p90,
                "interpreted_unit": unit,
                "threshold_used": thr,
                "status": "OK" if unit in {"percent_points", "decimal"} else "INCONCLUSIVE",
            }
        )
    return pd.DataFrame(rows, columns=["metric", "observed_median", "observed_p90", "interpreted_unit", "threshold_used", "status"])


def _enrich_past_returns(outcomes: pd.DataFrame) -> pd.DataFrame:
    if outcomes.empty:
        return outcomes
    sources = resolve_sources()
    x = outcomes.copy()
    x["scan_date"] = pd.to_datetime(x["scan_date"], errors="coerce").dt.normalize()
    merged_chunks: list[pd.DataFrame] = []
    for ticker, g in x.groupby("ticker"):
        px = load_symbol_df(sources.stocks_dir, str(ticker))
        if px is None or px.empty:
            gg = g.copy()
            gg["past_ret_20d"] = np.nan
            gg["past_ret_60d"] = np.nan
            merged_chunks.append(gg)
            continue
        p = px.copy().sort_values("date")
        p["date"] = pd.to_datetime(p["date"], errors="coerce").dt.normalize()
        p = p.dropna(subset=["date"])
        p["past_ret_20d"] = p["close"].astype(float) / p["close"].astype(float).shift(20) - 1.0
        p["past_ret_60d"] = p["close"].astype(float) / p["close"].astype(float).shift(60) - 1.0
        gg = g.merge(p[["date", "past_ret_20d", "past_ret_60d"]], left_on="scan_date", right_on="date", how="left")
        gg = gg.drop(columns=["date"], errors="ignore")
        gg = gg.drop(columns=["date_x", "date_y"], errors="ignore")
        merged_chunks.append(gg)
    return pd.concat(merged_chunks, ignore_index=True)


def measurement_integrity(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["scan_date"] = pd.to_datetime(x["scan_date"], errors="coerce")
    subsets: list[tuple[str, pd.DataFrame]] = [
        ("full_sample", x),
        ("sample_2022_2026", x[(x["scan_date"] >= pd.Timestamp("2022-01-01")) & (x["scan_date"] <= pd.Timestamp("2026-12-31"))]),
        ("non_null_forward_rows", x[x["ret_20d"].notna() & x["ret_60d"].notna()]),
        ("ex_vin", x[x.get("is_vin", False) == False]),  # noqa: E712
        ("high_liquidity_subset", x[pd.to_numeric(x.get("adv50_vnd"), errors="coerce") >= 20_000_000_000]),
        ("benchmark_aligned_subset", x[x["vnindex_ret_20d"].notna() & x["vnindex_ret_60d"].notna()]),
    ]
    # non-overlapping approximation: 20-day spacing per ticker
    no_overlap = []
    for _, g in x.sort_values(["ticker", "scan_date"]).groupby("ticker"):
        keep_idx = []
        last_dt: pd.Timestamp | None = None
        for idx, dt in zip(g.index, g["scan_date"]):
            if pd.isna(dt):
                continue
            if last_dt is None or (dt - last_dt).days >= 20:
                keep_idx.append(idx)
                last_dt = dt
        if keep_idx:
            no_overlap.extend(keep_idx)
    subsets.append(("non_overlapping_20d_proxy", x.loc[sorted(set(no_overlap))].copy()))

    base_spread = _q_bucket_spread(x, "institutional_accumulation_score", "ret_60d", q=5)
    rows = []
    for name, sub in subsets:
        spread = _q_bucket_spread(sub, "institutional_accumulation_score", "ret_60d", q=5)
        label = "INCONCLUSIVE"
        note = ""
        if base_spread is not None and spread is not None and np.sign(base_spread) != np.sign(spread):
            delta = abs(float(base_spread - spread))
            if delta >= 0.005:
                label = "MEASUREMENT_ARTIFACT"
                note = "Q5-Q1 sign flips vs full sample with meaningful spread delta"
            else:
                label = "INCONCLUSIVE_SMALL_SPREAD"
                note = "Q5-Q1 sign flips but spread delta is economically small"
        rows.append(
            {
                "subset": name,
                "n": int(len(sub)),
                "ticker_n": int(sub["ticker"].nunique()) if "ticker" in sub.columns else 0,
                "q5_minus_q1_ret60": spread,
                "mean_ret_60d": _safe_mean(sub["ret_60d"]) if "ret_60d" in sub.columns else None,
                "mean_excess_ret_60d": _safe_mean(sub["excess_ret_60d_vs_vnindex"]) if "excess_ret_60d_vs_vnindex" in sub.columns else None,
                "diagnostic_label": label,
                "note": note,
            }
        )
    return pd.DataFrame(rows)


def score_decile_autopsy(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["score_decile"] = pd.qcut(x["institutional_accumulation_score"], 10, labels=False, duplicates="drop")
    rows = []
    for decile, g in x.groupby("score_decile"):
        rows.append(
            {
                "score_decile": int(decile),
                "n": int(len(g)),
                "ret_5d_mean": _safe_mean(g["ret_5d"]),
                "ret_10d_mean": _safe_mean(g["ret_10d"]),
                "ret_20d_mean": _safe_mean(g["ret_20d"]),
                "ret_60d_mean": _safe_mean(g["ret_60d"]),
                "ret_120d_mean": _safe_mean(g["ret_120d"]),
                "excess_ret_20d_mean": _safe_mean(g["excess_ret_20d_vs_vnindex"]),
                "excess_ret_60d_mean": _safe_mean(g["excess_ret_60d_vs_vnindex"]),
                "hit_rate_20d": _safe_rate(g["ret_20d"] > 0),
                "hit_rate_60d": _safe_rate(g["ret_60d"] > 0),
                "max_dd_60d_mean": _safe_mean(g["max_dd_60d"]),
                "p_ret20_negative": _safe_rate(g["ret_20d"] < 0),
                "p_ret60_negative": _safe_rate(g["ret_60d"] < 0),
                "p_dd5_60d": _safe_rate(g["max_dd_60d"] <= -0.05),
                "p_dd10_60d": _safe_rate(g["max_dd_60d"] <= -0.10),
                "past_ret_20d_mean": _safe_mean(g.get("past_ret_20d", pd.Series(dtype=float))),
                "past_ret_60d_mean": _safe_mean(g.get("past_ret_60d", pd.Series(dtype=float))),
                "extension_pct_above_ma20_mean": _safe_mean(g.get("extension_pct_above_ma20", pd.Series(dtype=float))),
                "distribution_days_25_mean": _safe_mean(g.get("distribution_days_25", pd.Series(dtype=float))),
                "turnover_accel_ratio_5d50d_mean": _safe_mean(g.get("turnover_accel_ratio_5d50d", pd.Series(dtype=float))),
                "cmf20_daily_mean": _safe_mean(g.get("cmf20_daily", pd.Series(dtype=float))),
                "obv_slope_20_mean": _safe_mean(g.get("obv_slope_20", pd.Series(dtype=float))),
                "adl_slope_20_mean": _safe_mean(g.get("adl_slope_20", pd.Series(dtype=float))),
                "pvt_slope_20_mean": _safe_mean(g.get("pvt_slope_20", pd.Series(dtype=float))),
                "adv50_vnd_mean": _safe_mean(g.get("adv50_vnd", pd.Series(dtype=float))),
                "vin_share": _safe_rate(g.get("is_vin", pd.Series(dtype=float))),
            }
        )
    return pd.DataFrame(rows).sort_values("score_decile")


def component_diagnostics(outcomes: pd.DataFrame) -> pd.DataFrame:
    components = [
        "institutional_accumulation_score",
        "score_money_flow",
        "score_price_structure",
        "score_risk_penalty",
        "score_context",
        "score_mf_cmf",
        "score_mf_obv_pvt",
        "score_mf_adl",
        "score_mf_participation",
    ]
    rows = []
    x = outcomes.copy()
    for comp in components:
        if comp not in x.columns:
            continue
        for bucket_type, q in [("quintile", 5), ("decile", 10)]:
            try:
                b = pd.qcut(x[comp], q, labels=False, duplicates="drop")
            except Exception:
                continue
            xx = x.copy()
            xx["bucket"] = b
            for bucket, g in xx.groupby("bucket"):
                pneg = _safe_rate(g["ret_60d"] < 0)
                ret60 = _safe_mean(g["ret_60d"])
                excess60 = _safe_mean(g.get("excess_ret_60d_vs_vnindex", pd.Series(dtype=float)))
                label = "INCONCLUSIVE"
                if len(g) < 30:
                    label = "INCONCLUSIVE"
                elif bucket == xx["bucket"].max() and (pneg or 0) > 0.55:
                    label = "EXHAUSTION_CONTAMINATED"
                elif (ret60 or 0) > 0 and (excess60 or 0) > 0 and (pneg or 1) < 0.5:
                    label = "COMPONENT_SUPPORTIVE"
                elif (ret60 or 0) < 0 and (pneg or 0) >= 0.55:
                    label = "COMPONENT_FAILURE"
                rows.append(
                    {
                        "component": comp,
                        "bucket_type": bucket_type,
                        "bucket": int(bucket),
                        "n": int(len(g)),
                        "ret_20d_mean": _safe_mean(g["ret_20d"]),
                        "ret_60d_mean": ret60,
                        "excess_ret_60d_mean": excess60,
                        "hit_rate_60d": _safe_rate(g["ret_60d"] > 0),
                        "max_dd_60d_mean": _safe_mean(g["max_dd_60d"]),
                        "p_ret60_negative": pneg,
                        "p_dd10_60d": _safe_rate(g["max_dd_60d"] <= -0.10),
                        "diagnostic_label": label,
                    }
                )
    return pd.DataFrame(rows)


def feature_lead_lag(outcomes: pd.DataFrame) -> pd.DataFrame:
    features = [
        "cmf20_daily",
        "cmf20_weekly",
        "obv_slope_20",
        "obv_slope_50",
        "adl_slope_20",
        "pvt_slope_20",
        "turnover_accel_ratio_5d50d",
        "up_down_volume_ratio_20",
        "distribution_days_25",
        "extension_pct_above_ma20",
    ]
    targets = {
        "past_ret_20d": "past",
        "past_ret_60d": "past",
        "ret_5d": "future",
        "ret_10d": "future",
        "ret_20d": "future",
        "ret_60d": "future",
        "ret_120d": "future",
    }
    rows = []
    for feat in features:
        if feat not in outcomes.columns:
            continue
        feat_s = pd.to_numeric(outcomes[feat], errors="coerce")
        corr_vals: dict[str, float | None] = {}
        for tgt, _kind in targets.items():
            if tgt not in outcomes.columns:
                corr_vals[f"spearman_{tgt}"] = None
                corr_vals[f"pearson_{tgt}"] = None
                continue
            tgt_s = pd.to_numeric(outcomes[tgt], errors="coerce")
            use = pd.DataFrame({"f": feat_s, "t": tgt_s}).dropna()
            if len(use) < 20:
                corr_vals[f"spearman_{tgt}"] = None
                corr_vals[f"pearson_{tgt}"] = None
            else:
                corr_vals[f"spearman_{tgt}"] = float(use["f"].corr(use["t"], method="spearman"))
                corr_vals[f"pearson_{tgt}"] = float(use["f"].corr(use["t"], method="pearson"))
        past_abs = []
        future_abs = []
        for tgt, kind in targets.items():
            val = corr_vals.get(f"spearman_{tgt}")
            if val is None or pd.isna(val):
                continue
            if kind == "past":
                past_abs.append(abs(val))
            else:
                future_abs.append(abs(val))
        label = "INCONCLUSIVE"
        if past_abs and future_abs and max(past_abs) > max(future_abs):
            label = "DESCRIPTIVE_NOT_PREDICTIVE"
        rows.append({"feature": feat, **corr_vals, "diagnostic_label": label})
    return pd.DataFrame(rows)


def accumulation_vs_exhaustion(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    ext = pd.to_numeric(x.get("extension_pct_above_ma20"), errors="coerce")
    thr_healthy = _extension_threshold_value(ext, 12.0)
    thr_exhaust = _extension_threshold_value(ext, 15.0)
    thr_base = _extension_threshold_value(ext, 8.0)
    x["healthy_accumulation_candidate"] = (
        (pd.to_numeric(x.get("score_money_flow"), errors="coerce") >= 55)
        & (pd.to_numeric(x.get("score_risk_penalty"), errors="coerce") <= 25)
        & (ext <= thr_healthy)
        & (pd.to_numeric(x.get("distribution_days_25"), errors="coerce") <= 3)
    )
    x["late_stage_exhaustion_candidate"] = (
        (pd.to_numeric(x.get("institutional_accumulation_score"), errors="coerce") >= 60)
        & (
            (ext > thr_exhaust)
            | (pd.to_numeric(x.get("distribution_days_25"), errors="coerce") >= 5)
        )
    )
    x["base_building_candidate"] = (
        (pd.to_numeric(x.get("score_price_structure"), errors="coerce") >= 50)
        & (ext <= thr_base)
    )
    x["flow_without_structure"] = (
        (pd.to_numeric(x.get("score_money_flow"), errors="coerce") >= 55)
        & (pd.to_numeric(x.get("score_price_structure"), errors="coerce") < 45)
    )
    x["structure_without_flow"] = (
        (pd.to_numeric(x.get("score_price_structure"), errors="coerce") >= 55)
        & (pd.to_numeric(x.get("score_money_flow"), errors="coerce") < 45)
    )
    x["high_score_high_risk"] = (
        (pd.to_numeric(x.get("institutional_accumulation_score"), errors="coerce") >= 60)
        & (pd.to_numeric(x.get("score_risk_penalty"), errors="coerce") >= 40)
    )
    x["high_score_low_risk"] = (
        (pd.to_numeric(x.get("institutional_accumulation_score"), errors="coerce") >= 60)
        & (pd.to_numeric(x.get("score_risk_penalty"), errors="coerce") <= 25)
    )
    defs = {
        "healthy_accumulation_candidate": f"money_flow>=55 & risk_penalty<=25 & extension<={thr_healthy:.6g} & dist_days<=3",
        "late_stage_exhaustion_candidate": f"score>=60 & (extension>{thr_exhaust:.6g} or dist_days>=5)",
        "base_building_candidate": f"price_structure>=50 & extension<={thr_base:.6g}",
        "flow_without_structure": "money_flow>=55 & price_structure<45",
        "structure_without_flow": "price_structure>=55 & money_flow<45",
        "high_score_high_risk": "score>=60 & risk_penalty>=40",
        "high_score_low_risk": "score>=60 & risk_penalty<=25",
    }
    rows = []
    for col, rule in defs.items():
        sub = x[x[col] == True]  # noqa: E712
        rows.append(
            {
                "bucket": col,
                "rule_definition": rule,
                "n": int(len(sub)),
                "ret_20d_mean": _safe_mean(sub["ret_20d"]),
                "ret_60d_mean": _safe_mean(sub["ret_60d"]),
                "max_dd_60d_mean": _safe_mean(sub["max_dd_60d"]),
                "hit_rate_60d": _safe_rate(sub["ret_60d"] > 0),
                "p_ret60_negative": _safe_rate(sub["ret_60d"] < 0),
                "p_dd10_60d": _safe_rate(sub["max_dd_60d"] <= -0.10),
            }
        )
    return pd.DataFrame(rows)


def distribution_flag_diagnostic(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    if "distribution_risk_flag" not in x.columns:
        return pd.DataFrame(columns=["flag_value", "n", "ret_60d_mean", "max_dd_60d_mean", "p_dd10_60d"])
    rows = []
    for flag in [False, True]:
        sub = x[x["distribution_risk_flag"] == flag]
        rows.append(
            {
                "flag_value": bool(flag),
                "n": int(len(sub)),
                "ret_60d_mean": _safe_mean(sub.get("ret_60d", pd.Series(dtype=float))),
                "max_dd_60d_mean": _safe_mean(sub.get("max_dd_60d", pd.Series(dtype=float))),
                "p_dd10_60d": _safe_rate(sub.get("max_dd_60d", pd.Series(dtype=float)) <= -0.10),
            }
        )
    return pd.DataFrame(rows)


def regime_dependency(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["bull_breadth_expansion"] = x.get("normal_regime", False) == True  # noqa: E712
    x["fragile_uptrend_narrow_leadership"] = x.get("fragile_uptrend_narrow_leadership_proxy", False) == True  # noqa: E712
    x["narrow_vin_led"] = (x.get("fragile_uptrend_narrow_leadership_proxy", False) == True) & (x.get("is_vin", False) == True)  # noqa: E712
    regimes = [
        "normal_regime",
        "correction_or_bear",
        "bull_breadth_expansion",
        "fragile_uptrend_narrow_leadership",
        "narrow_vin_led",
    ]
    rows = []
    for rg in regimes:
        if rg not in x.columns:
            continue
        sub = x[x[rg] == True]  # noqa: E712
        q5_20 = _q_bucket_spread(sub, "institutional_accumulation_score", "ret_20d", q=5)
        q5_60 = _q_bucket_spread(sub, "institutional_accumulation_score", "ret_60d", q=5)
        dec = sub.copy()
        try:
            dec["d"] = pd.qcut(dec["institutional_accumulation_score"], 10, labels=False, duplicates="drop")
            top_ret = _safe_mean(dec[dec["d"] >= dec["d"].max() - 1]["ret_60d"])
        except Exception:
            top_ret = None
        flagged = _safe_mean(sub[sub.get("distribution_risk_flag", False) == True]["ret_60d"])  # noqa: E712
        clean = _safe_mean(sub[sub.get("distribution_risk_flag", False) == False]["ret_60d"])  # noqa: E712
        dist_gap = None if flagged is None or clean is None else float(clean - flagged)
        rp = pd.to_numeric(sub.get("score_risk_penalty"), errors="coerce")
        lo = sub[rp <= rp.quantile(0.33)] if not rp.dropna().empty else pd.DataFrame()
        hi = sub[rp >= rp.quantile(0.67)] if not rp.dropna().empty else pd.DataFrame()
        risk_gap = None if lo.empty or hi.empty else float(_safe_mean(lo["ret_60d"]) - _safe_mean(hi["ret_60d"]))
        warn_gap = None
        if "caution_proxy" in sub.columns:
            t = _safe_mean(sub[sub["caution_proxy"] == True]["ret_60d"])  # noqa: E712
            f = _safe_mean(sub[sub["caution_proxy"] == False]["ret_60d"])  # noqa: E712
            if t is not None and f is not None:
                warn_gap = float(f - t)
        label = "INCONCLUSIVE"
        if len(sub) >= 200 and q5_60 is not None and abs(q5_60) >= 0.005:
            label = "REGIME_DEPENDENT" if q5_60 > 0 else "REGIME_INDEPENDENT_FAILURE"
        rows.append(
            {
                "regime": rg,
                "Q5_minus_Q1_20d": q5_20,
                "Q5_minus_Q1_60d": q5_60,
                "score_decile_9_ret60": top_ret,
                "distribution_flag_gap": dist_gap,
                "risk_penalty_gap": risk_gap,
                "warning_true_vs_false_gap": warn_gap,
                "n": int(len(sub)),
                "label": label,
            }
        )
    return pd.DataFrame(rows)


def horizon_dependency(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    rows = []
    for h in [5, 10, 20, 60, 120]:
        ret_col = f"ret_{h}d"
        if ret_col not in x.columns:
            continue
        spread = _q_bucket_spread(x, "institutional_accumulation_score", ret_col, q=5)
        try:
            dec = x.copy()
            dec["d"] = pd.qcut(dec["institutional_accumulation_score"], 10, labels=False, duplicates="drop")
            top = _safe_mean(dec[dec["d"] >= dec["d"].max() - 1][ret_col])
            mid = _safe_mean(dec[(dec["d"] >= 4) & (dec["d"] <= 5)][ret_col])
            q9_mid = None if top is None or mid is None else float(top - mid)
            top_hit = _safe_rate(dec[dec["d"] >= dec["d"].max() - 1][ret_col] > 0)
            mid_hit = _safe_rate(dec[(dec["d"] >= 4) & (dec["d"] <= 5)][ret_col] > 0)
            hit_gap = None if top_hit is None or mid_hit is None else float(top_hit - mid_hit)
            top_dd = _safe_mean(dec[dec["d"] >= dec["d"].max() - 1]["max_dd_60d"])
            mid_dd = _safe_mean(dec[(dec["d"] >= 4) & (dec["d"] <= 5)]["max_dd_60d"])
            dd_gap = None if top_dd is None or mid_dd is None else float(top_dd - mid_dd)
        except Exception:
            q9_mid = None
            hit_gap = None
            dd_gap = None
        label = "INCONCLUSIVE"
        if spread is not None and spread < -0.005:
            label = "FAILS_ALL_HORIZONS"
        elif h <= 20 and spread is not None and spread > 0.005:
            label = "SHORT_TERM_ONLY"
        elif h >= 60 and spread is not None and spread > 0.005:
            label = "LONG_TERM_ONLY"
        rows.append(
            {
                "horizon": f"{h}d",
                "Q5_minus_Q1": spread,
                "Q9_or_Q10_minus_mid": q9_mid,
                "hit_rate_gap": hit_gap,
                "dd_gap": dd_gap,
                "label": label,
            }
        )
    return pd.DataFrame(rows)


def tier_threshold_diagnostics(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    score = pd.to_numeric(x.get("institutional_accumulation_score"), errors="coerce")
    mf = pd.to_numeric(x.get("score_money_flow"), errors="coerce")
    risk = pd.to_numeric(x.get("score_risk_penalty"), errors="coerce")
    ps = pd.to_numeric(x.get("score_price_structure"), errors="coerce")
    buckets: dict[str, pd.Series] = {
        "score_65_72": (score >= 65) & (score < 72),
        "score_58_65": (score >= 58) & (score < 65),
        "score_52_58": (score >= 52) & (score < 58),
        "score_42_52": (score >= 42) & (score < 52),
        "high_score_mf_below_threshold": (score >= 60) & (mf < 50),
        "high_score_risk_above_threshold": (score >= 60) & (risk > 35),
        "mf_high_score_below_threshold": (mf >= 60) & (score < 55),
        "price_structure_high_money_flow_weak": (ps >= 60) & (mf < 45),
    }
    rows = []
    for name, mask in buckets.items():
        sub = x[mask.fillna(False)]
        label = "INCONCLUSIVE"
        if "risk_above" in name and _safe_mean(sub["ret_60d"]) is not None and _safe_mean(sub["ret_60d"]) < 0:
            label = "GATE_FAILURE"
        elif name.startswith("score_") and len(sub) >= 200:
            label = "THRESHOLD_TOO_STRICT" if _safe_mean(sub["ret_60d"]) and _safe_mean(sub["ret_60d"]) > 0 else "THRESHOLD_TOO_LOOSE"
        rows.append(
            {
                "bucket": name,
                "n": int(len(sub)),
                "ret_20d_mean": _safe_mean(sub["ret_20d"]),
                "ret_60d_mean": _safe_mean(sub["ret_60d"]),
                "max_dd_60d_mean": _safe_mean(sub["max_dd_60d"]),
                "hit_rate_60d": _safe_rate(sub["ret_60d"] > 0),
                "label": label,
            }
        )
    return pd.DataFrame(rows)


def diagnostic_summary(
    measurement: pd.DataFrame,
    autopsy: pd.DataFrame,
    components: pd.DataFrame,
    lead_lag: pd.DataFrame,
    buckets: pd.DataFrame,
    unit_audit: pd.DataFrame,
    dist_diag: pd.DataFrame,
    regimes: pd.DataFrame,
    horizons: pd.DataFrame,
    thresholds: pd.DataFrame,
) -> pd.DataFrame:
    comp_cols_ok = {"component", "diagnostic_label"}.issubset(components.columns)
    reg_cols_ok = "label" in regimes.columns
    hor_cols_ok = "label" in horizons.columns
    thr_cols_ok = "label" in thresholds.columns
    bucket_cols_ok = {"bucket", "ret_60d_mean"}.issubset(buckets.columns)
    composite_label = "INCONCLUSIVE"
    if not autopsy.empty and "score_decile" in autopsy.columns:
        a = autopsy.sort_values("score_decile").copy()
        ret_cols = [c for c in ["ret_20d_mean", "ret_60d_mean", "ret_120d_mean"] if c in a.columns]
        inversion_votes = 0
        valid_votes = 0
        for c in ret_cols:
            hi = _safe_mean(a[a["score_decile"] >= a["score_decile"].max() - 1][c])
            lo = _safe_mean(a[a["score_decile"] <= a["score_decile"].min() + 1][c])
            if hi is None or lo is None:
                continue
            valid_votes += 1
            if hi < lo:
                inversion_votes += 1
        dtop = _safe_mean(a[a["score_decile"] == a["score_decile"].max()]["ret_60d_mean"]) if "ret_60d_mean" in a.columns else None
        dbot = _safe_mean(a[a["score_decile"] == a["score_decile"].min()]["ret_60d_mean"]) if "ret_60d_mean" in a.columns else None
        dmid = _safe_mean(a[a["score_decile"].isin([6, 7, 8])]["ret_60d_mean"]) if "ret_60d_mean" in a.columns else None
        if valid_votes > 0 and inversion_votes >= max(2, valid_votes):
            composite_label = "CONFIRMED_FULL_INVERSION"
        elif dtop is not None and dmid is not None and dtop < dmid and (dbot is None or dtop >= (dbot - 0.002)):
            composite_label = "TOP_DECILE_EXHAUSTION"
        elif dtop is not None and dmid is not None and dmid > dtop:
            composite_label = "NON_MONOTONIC_HUMP_SHAPE"

    m_labels = set(measurement["diagnostic_label"].dropna().astype(str).tolist())
    if "MEASUREMENT_ARTIFACT" in m_labels:
        measurement_label = "MEASUREMENT_ARTIFACT"
    elif "INCONCLUSIVE_SMALL_SPREAD" in m_labels:
        measurement_label = "INCONCLUSIVE_SMALL_SPREAD"
    else:
        measurement_label = "INCONCLUSIVE"
    money_flow_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_money_flow") & (components["diagnostic_label"] == "COMPONENT_FAILURE")).any() else "INCONCLUSIVE"
    price_struct_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_price_structure") & (components["diagnostic_label"] == "COMPONENT_FAILURE")).any() else "INCONCLUSIVE"
    risk_label = "RISK_FILTER_USEFUL" if bucket_cols_ok and ((buckets["bucket"] == "high_score_high_risk") & (buckets["ret_60d_mean"] < 0)).any() else "INCONCLUSIVE"
    cmf_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_mf_cmf") & (components["diagnostic_label"] != "COMPONENT_SUPPORTIVE")).all() else "INCONCLUSIVE"
    obv_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_mf_obv_pvt") & (components["diagnostic_label"] != "COMPONENT_SUPPORTIVE")).all() else "INCONCLUSIVE"
    adl_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_mf_adl") & (components["diagnostic_label"] != "COMPONENT_SUPPORTIVE")).all() else "INCONCLUSIVE"
    part_label = "COMPONENT_FAILURE" if comp_cols_ok and ((components["component"] == "score_mf_participation") & (components["diagnostic_label"] != "COMPONENT_SUPPORTIVE")).all() else "INCONCLUSIVE"
    dist_label = "INCONCLUSIVE"
    if not dist_diag.empty and {"flag_value", "ret_60d_mean", "max_dd_60d_mean", "p_dd10_60d"}.issubset(dist_diag.columns):
        f = dist_diag[dist_diag["flag_value"] == True]  # noqa: E712
        nf = dist_diag[dist_diag["flag_value"] == False]  # noqa: E712
        if not f.empty and not nf.empty:
            f_ret = _safe_mean(f["ret_60d_mean"])
            nf_ret = _safe_mean(nf["ret_60d_mean"])
            f_dd = _safe_mean(f["max_dd_60d_mean"])
            nf_dd = _safe_mean(nf["max_dd_60d_mean"])
            f_pdd = _safe_mean(f["p_dd10_60d"])
            nf_pdd = _safe_mean(nf["p_dd10_60d"])
            useful = (
                (f_ret is not None and nf_ret is not None and f_ret < nf_ret)
                or (f_dd is not None and nf_dd is not None and f_dd < nf_dd)
                or (f_pdd is not None and nf_pdd is not None and f_pdd > nf_pdd)
            )
            dist_label = "RISK_FILTER_USEFUL" if useful else "INCONCLUSIVE"
    regime_label = "REGIME_DEPENDENT" if reg_cols_ok and (regimes["label"] == "REGIME_DEPENDENT").any() else "INCONCLUSIVE"
    horizon_label = "HORIZON_MISMATCH" if hor_cols_ok and ((horizons["label"] == "SHORT_TERM_ONLY") | (horizons["label"] == "LONG_TERM_ONLY")).any() else "INCONCLUSIVE"
    threshold_label = "THRESHOLD_FAILURE" if thr_cols_ok and (thresholds["label"] == "GATE_FAILURE").any() else "INCONCLUSIVE"
    exhaustion_label = "EXHAUSTION_CONTAMINATED" if bucket_cols_ok and ((buckets["bucket"] == "late_stage_exhaustion_candidate") & (buckets["ret_60d_mean"] < 0)).any() else "INCONCLUSIVE"
    base_building_label = "INCONCLUSIVE"
    bb = buckets[buckets["bucket"] == "base_building_candidate"] if not buckets.empty else pd.DataFrame()
    if not bb.empty:
        bb_ret = _safe_mean(bb["ret_60d_mean"])
        bb_pdd = _safe_mean(bb["p_dd10_60d"])
        bb_n = int(pd.to_numeric(bb["n"], errors="coerce").fillna(0).sum()) if "n" in bb.columns else 0
        if bb_ret is not None and bb_pdd is not None and bb_n >= 1000 and bb_ret > 0 and bb_pdd <= 0.40:
            base_building_label = "PROMISING_RESEARCH_DIRECTION"
    rows = [
        ("measurement_integrity", measurement_label, "subset spread sign consistency checks", "verify sample/coverage pipeline"),
        ("composite_score", composite_label, "decile autopsy top-vs-mid return gap", "diagnose inversion source before redesign"),
        ("money_flow", money_flow_label, "component bucket outcomes", "audit flow features for exhaustion contamination"),
        ("price_structure", price_struct_label, "component bucket outcomes", "review structure scoring behavior"),
        ("risk_penalty", risk_label, "high_score_high_risk underperformance", "keep as risk-warning candidate"),
        ("cmf", cmf_label, "CMF component diagnostics", "rescale or gate in P2 if persists"),
        ("obv_pvt", obv_label, "OBV/PVT component diagnostics", "check for trend-chasing leakage"),
        ("adl", adl_label, "ADL component diagnostics", "check stability by regime"),
        ("participation", part_label, "participation component diagnostics", "audit liquidity interaction"),
        ("distribution_flag", dist_label, "distribution warning gap", "retain as risk filter"),
        ("regime_dependency", regime_label, "regime-specific spreads", "consider regime gates in P2"),
        ("horizon_dependency", horizon_label, "horizon spread profile", "separate short vs long horizon logic"),
        ("tier_thresholds", threshold_label, "threshold bucket diagnostics", "revisit gates after inversion diagnosis"),
        ("accumulation_vs_exhaustion", exhaustion_label, "bucket return/drawdown split", "prioritize healthy accumulation bucket"),
        ("base_building_bucket", base_building_label, "base_building candidate risk-return profile", "investigate first in P2 as research direction only"),
    ]
    out = pd.DataFrame(rows, columns=["area", "diagnostic_label", "evidence", "recommended_next_step"])
    out["diagnostic_label"] = out["diagnostic_label"].apply(lambda x: x if x in ALLOWED_SUMMARY_LABELS else "INCONCLUSIVE")
    return out


def run_p1_diagnostics(outcomes: pd.DataFrame, out_dir: Path) -> P1Outputs:
    out_dir.mkdir(parents=True, exist_ok=True)
    x = _enrich_past_returns(outcomes)
    m = measurement_integrity(x)
    s = score_decile_autopsy(x)
    c = component_diagnostics(x)
    l = feature_lead_lag(x)
    b = accumulation_vs_exhaustion(x)
    u = extension_unit_audit(x)
    d = distribution_flag_diagnostic(x)
    r = regime_dependency(x)
    h = horizon_dependency(x)
    t = tier_threshold_diagnostics(x)
    summ = diagnostic_summary(m, s, c, l, b, u, d, r, h, t)
    m.to_csv(out_dir / "p1_measurement_integrity.csv", index=False)
    s.to_csv(out_dir / "p1_score_decile_autopsy.csv", index=False)
    c.to_csv(out_dir / "p1_component_diagnostics.csv", index=False)
    l.to_csv(out_dir / "p1_feature_lead_lag.csv", index=False)
    b.to_csv(out_dir / "p1_accumulation_vs_exhaustion.csv", index=False)
    u.to_csv(out_dir / "p1_unit_audit.csv", index=False)
    d.to_csv(out_dir / "p1_distribution_flag_diagnostic.csv", index=False)
    r.to_csv(out_dir / "p1_regime_dependency.csv", index=False)
    h.to_csv(out_dir / "p1_horizon_dependency.csv", index=False)
    t.to_csv(out_dir / "p1_tier_threshold_diagnostics.csv", index=False)
    summ.to_csv(out_dir / "p1_diagnostic_summary.csv", index=False)
    return P1Outputs(m, s, c, l, b, u, d, r, h, t, summ)

