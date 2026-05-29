from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .p1_diagnostics import _extension_threshold_value

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

ALLOWED_VARIANT_LABELS = {
    "PROMISING_RESEARCH_VARIANT",
    "RISK_REDUCTION_ONLY",
    "REJECTED_VARIANT",
    "INCONCLUSIVE",
    "BLOCKED_BY_SAMPLE",
}

SPLITS = [
    "full_sample",
    "sample_2022_2026",
    "ex_vin",
    "high_liquidity_subset",
    "normal_regime",
    "correction_or_bear",
    "fragile_uptrend_narrow_leadership",
    "bull_breadth_expansion",
]


@dataclass
class P2Outputs:
    variant_results: pd.DataFrame
    top_decile_exhaustion: pd.DataFrame
    extension_cap_sweep: pd.DataFrame
    distribution_gate_sweep: pd.DataFrame
    diagnostic_summary: pd.DataFrame


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


def _safe_median(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.median())


def enrich_outcomes(outcomes: pd.DataFrame) -> pd.DataFrame:
    x = outcomes.copy()
    x["scan_date"] = pd.to_datetime(x["scan_date"], errors="coerce").dt.normalize()
    if "score_decile" not in x.columns:
        x["score_decile"] = pd.qcut(
            pd.to_numeric(x["institutional_accumulation_score"], errors="coerce"),
            10,
            labels=False,
            duplicates="drop",
        )
    if "bull_breadth_expansion" not in x.columns:
        x["bull_breadth_expansion"] = x.get("normal_regime", False) == True  # noqa: E712
    return x


def _split_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "full_sample": pd.Series(True, index=df.index),
        "sample_2022_2026": (df["scan_date"] >= pd.Timestamp("2022-01-01")) & (df["scan_date"] <= pd.Timestamp("2026-12-31")),
        "ex_vin": df.get("is_vin", False) == False,  # noqa: E712
        "high_liquidity_subset": pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= 20_000_000_000,
        "normal_regime": df.get("normal_regime", False) == True,  # noqa: E712
        "correction_or_bear": df.get("correction_or_bear", False) == True,  # noqa: E712
        "fragile_uptrend_narrow_leadership": df.get("fragile_uptrend_narrow_leadership_proxy", False) == True,  # noqa: E712
        "bull_breadth_expansion": df.get("bull_breadth_expansion", False) == True,  # noqa: E712
    }


def _ext_le(series: pd.Series, pct: float) -> pd.Series:
    thr = _extension_threshold_value(series, pct)
    return pd.to_numeric(series, errors="coerce") <= thr


def _no_dist(df: pd.DataFrame) -> pd.Series:
    return df.get("distribution_risk_flag", False) == False  # noqa: E712


def _decile_6_8(df: pd.DataFrame) -> pd.Series:
    d = pd.to_numeric(df["score_decile"], errors="coerce")
    return d.isin([6, 7, 8])


def _decile_5_8(df: pd.DataFrame) -> pd.Series:
    d = pd.to_numeric(df["score_decile"], errors="coerce")
    return d.isin([5, 6, 7, 8])


def _no_turnover_climax(df: pd.DataFrame, p90: float) -> pd.Series:
    t = pd.to_numeric(df.get("turnover_accel_ratio_5d50d"), errors="coerce")
    return t < p90


def _regime_gated(mask: pd.Series, df: pd.DataFrame) -> pd.Series:
    regime_ok = (df.get("normal_regime", False) == True) | (df.get("bull_breadth_expansion", False) == True)  # noqa: E712
    return mask & regime_ok


def build_variant_masks(df: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    ext = pd.to_numeric(df.get("extension_pct_above_ma20"), errors="coerce")
    turnover = pd.to_numeric(df.get("turnover_accel_ratio_5d50d"), errors="coerce")
    p90 = float(turnover.quantile(0.90)) if turnover.notna().any() else float("inf")

    v2 = _decile_6_8(df)
    v4 = _no_dist(df)
    v5 = _no_turnover_climax(df, p90)

    masks: dict[str, tuple[str, pd.Series]] = {
        "V0_RAW_SCORE": ("Raw current score deciles (baseline)", pd.Series(True, index=df.index)),
        "V1_EXCLUDE_DECILE_9": ("Exclude score decile 9 (top-decile exhaustion test)", pd.to_numeric(df["score_decile"], errors="coerce") != 9),
        "V2_SCORE_DECILE_6_8": ("Sweet-spot decile band 6-8 only", v2),
        "V3_EXTENSION_CAP_8": ("Extension cap <= 8% (unit-normalized)", _ext_le(ext, 8.0)),
        "V3_EXTENSION_CAP_12": ("Extension cap <= 12% (unit-normalized)", _ext_le(ext, 12.0)),
        "V3_EXTENSION_CAP_15": ("Extension cap <= 15% (unit-normalized)", _ext_le(ext, 15.0)),
        "V4_NO_DISTRIBUTION_RISK": ("Exclude distribution_risk_flag == True", v4),
        "V4B_DECILE_6_8_NO_DISTRIBUTION_RISK": ("Decile 6-8 with no distribution risk flag", v2 & v4),
        "V5_NO_TURNOVER_CLIMAX": ("Exclude turnover_accel >= 90th percentile", v5),
        "V5B_DECILE_6_8_NO_TURNOVER_CLIMAX": ("Decile 6-8 excluding turnover climax", v2 & v5),
    }

    v6 = (
        _decile_5_8(df)
        & _ext_le(ext, 12.0)
        & v4
        & (pd.to_numeric(df.get("distribution_days_25"), errors="coerce") < 5)
    )
    masks["V6_CONTROLLED_ACCUMULATION"] = (
        "Decile 5-8, extension<=12%, no dist flag, dist_days<5",
        v6,
    )

    v7 = (
        (pd.to_numeric(df.get("score_price_structure"), errors="coerce") >= 50)
        & _ext_le(ext, 8.0)
        & v4
        & (pd.to_numeric(df.get("score_risk_penalty"), errors="coerce") <= 35)
    )
    masks["V7_BASE_BUILDING_V2"] = (
        "price_structure>=50, extension<=8%, no dist, risk<=35",
        v7,
    )
    masks["V7B_BASE_BUILDING_WITH_FLOW_CONFIRM"] = (
        "V7 plus score_money_flow>=40",
        v7 & (pd.to_numeric(df.get("score_money_flow"), errors="coerce") >= 40),
    )

    masks["V8_FLOW_CONTROLLED_EXTENSION"] = (
        "money_flow>=55, extension<=12%, no distribution flag",
        (pd.to_numeric(df.get("score_money_flow"), errors="coerce") >= 55) & _ext_le(ext, 12.0) & v4,
    )

    masks["V9_V2_REGIME_GATED"] = ("V2 only in normal/bull breadth regimes", _regime_gated(v2, df))
    masks["V9_V6_REGIME_GATED"] = ("V6 only in normal/bull breadth regimes", _regime_gated(v6, df))
    masks["V9_V7_REGIME_GATED"] = ("V7 only in normal/bull breadth regimes", _regime_gated(v7, df))

    return masks


def compute_metrics_block(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {
            "n": 0,
            "ticker_n": 0,
            "scan_count": 0,
            "avg_names_per_scan": None,
            "ret_5d_mean": None,
            "ret_10d_mean": None,
            "ret_20d_mean": None,
            "ret_60d_mean": None,
            "ret_120d_mean": None,
            "excess_ret_20d_mean": None,
            "excess_ret_60d_mean": None,
            "hit_rate_20d": None,
            "hit_rate_60d": None,
            "max_dd_60d_mean": None,
            "p_ret20_negative": None,
            "p_ret60_negative": None,
            "p_dd5_60d": None,
            "p_dd10_60d": None,
            "turnover_accel_mean": None,
            "extension_mean": None,
            "distribution_days_mean": None,
            "risk_penalty_mean": None,
            "adv50_vnd_median": None,
            "vin_share": None,
        }
    scan_n = int(sub["scan_date"].nunique()) if "scan_date" in sub.columns else 0
    return {
        "n": int(len(sub)),
        "ticker_n": int(sub["ticker"].nunique()) if "ticker" in sub.columns else 0,
        "scan_count": scan_n,
        "avg_names_per_scan": float(len(sub) / scan_n) if scan_n > 0 else None,
        "ret_5d_mean": _safe_mean(sub.get("ret_5d", pd.Series(dtype=float))),
        "ret_10d_mean": _safe_mean(sub.get("ret_10d", pd.Series(dtype=float))),
        "ret_20d_mean": _safe_mean(sub.get("ret_20d", pd.Series(dtype=float))),
        "ret_60d_mean": _safe_mean(sub.get("ret_60d", pd.Series(dtype=float))),
        "ret_120d_mean": _safe_mean(sub.get("ret_120d", pd.Series(dtype=float))),
        "excess_ret_20d_mean": _safe_mean(sub.get("excess_ret_20d_vs_vnindex", pd.Series(dtype=float))),
        "excess_ret_60d_mean": _safe_mean(sub.get("excess_ret_60d_vs_vnindex", pd.Series(dtype=float))),
        "hit_rate_20d": _safe_rate(sub.get("ret_20d", pd.Series(dtype=float)) > 0),
        "hit_rate_60d": _safe_rate(sub.get("ret_60d", pd.Series(dtype=float)) > 0),
        "max_dd_60d_mean": _safe_mean(sub.get("max_dd_60d", pd.Series(dtype=float))),
        "p_ret20_negative": _safe_rate(sub.get("ret_20d", pd.Series(dtype=float)) < 0),
        "p_ret60_negative": _safe_rate(sub.get("ret_60d", pd.Series(dtype=float)) < 0),
        "p_dd5_60d": _safe_rate(sub.get("max_dd_60d", pd.Series(dtype=float)) <= -0.05),
        "p_dd10_60d": _safe_rate(sub.get("max_dd_60d", pd.Series(dtype=float)) <= -0.10),
        "turnover_accel_mean": _safe_mean(sub.get("turnover_accel_ratio_5d50d", pd.Series(dtype=float))),
        "extension_mean": _safe_mean(sub.get("extension_pct_above_ma20", pd.Series(dtype=float))),
        "distribution_days_mean": _safe_mean(sub.get("distribution_days_25", pd.Series(dtype=float))),
        "risk_penalty_mean": _safe_mean(sub.get("score_risk_penalty", pd.Series(dtype=float))),
        "adv50_vnd_median": _safe_median(sub.get("adv50_vnd", pd.Series(dtype=float))),
        "vin_share": _safe_rate(sub.get("is_vin", pd.Series(dtype=float))),
    }


def _attach_lifts(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    b60 = baseline.get("ret_60d_mean")
    v60 = row.get("ret_60d_mean")
    be60 = baseline.get("excess_ret_60d_mean")
    ve60 = row.get("excess_ret_60d_mean")
    bp10 = baseline.get("p_dd10_60d")
    vp10 = row.get("p_dd10_60d")
    row["ret_60d_lift_vs_v0"] = None if b60 is None or v60 is None else float(v60 - b60)
    row["excess_ret_60d_lift_vs_v0"] = None if be60 is None or ve60 is None else float(ve60 - be60)
    row["dd10_lift_vs_v0"] = None if bp10 is None or vp10 is None else float(bp10 - vp10)
    return row


def compute_variant_results(df: pd.DataFrame) -> pd.DataFrame:
    masks = build_variant_masks(df)
    splits = _split_masks(df)
    rows: list[dict[str, Any]] = []
    baseline_by_split: dict[str, dict[str, Any]] = {}

    for split_name, split_mask in splits.items():
        sub_split = df[split_mask.fillna(False)]
        bmask = masks["V0_RAW_SCORE"][1]
        baseline_by_split[split_name] = compute_metrics_block(sub_split[bmask.reindex(sub_split.index, fill_value=False)])

    for variant_id, (desc, mask) in masks.items():
        for split_name, split_mask in splits.items():
            use = df[mask.fillna(False) & split_mask.fillna(False)]
            metrics = compute_metrics_block(use)
            row = {
                "variant_id": variant_id,
                "variant_description": desc,
                "research_only_flag": RESEARCH_ONLY_FLAG,
                "split": split_name,
                **metrics,
            }
            if variant_id != "V0_RAW_SCORE":
                row = _attach_lifts(row, baseline_by_split[split_name])
            else:
                row["ret_60d_lift_vs_v0"] = 0.0
                row["excess_ret_60d_lift_vs_v0"] = 0.0
                row["dd10_lift_vs_v0"] = 0.0
            rows.append(row)

    return pd.DataFrame(rows)


def label_variant(
    results: pd.DataFrame,
    variant_id: str,
) -> tuple[str, str, str]:
    full = results[(results["variant_id"] == variant_id) & (results["split"] == "full_sample")]
    ex = results[(results["variant_id"] == variant_id) & (results["split"] == "ex_vin")]
    v0_full = results[(results["variant_id"] == "V0_RAW_SCORE") & (results["split"] == "full_sample")]
    v0_ex = results[(results["variant_id"] == "V0_RAW_SCORE") & (results["split"] == "ex_vin")]

    if full.empty:
        return "INCONCLUSIVE", "no full_sample row", "inspect data pipeline"

    n = int(full["n"].iloc[0])
    if n < 500:
        return "BLOCKED_BY_SAMPLE", f"n={n} below minimum", "increase sample or relax filter"

    ret_lift = full["ret_60d_lift_vs_v0"].iloc[0]
    dd_lift = full["dd10_lift_vs_v0"].iloc[0]
    p_dd10 = full["p_dd10_60d"].iloc[0]
    v0_p_dd10 = v0_full["p_dd10_60d"].iloc[0] if not v0_full.empty else None

    ret_lift = 0.0 if pd.isna(ret_lift) else float(ret_lift)
    dd_lift = 0.0 if pd.isna(dd_lift) else float(dd_lift)
    p_dd10_v = None if pd.isna(p_dd10) else float(p_dd10)
    v0_p = None if v0_p_dd10 is None or pd.isna(v0_p_dd10) else float(v0_p_dd10)

    dd_improve = dd_lift is not None and dd_lift >= 0.03
    dd_strong = dd_lift is not None and dd_lift >= 0.05

    ex_ok = True
    if not ex.empty and not v0_ex.empty and variant_id != "V0_RAW_SCORE":
        ex_ret = ex["ret_60d_lift_vs_v0"].iloc[0]
        ex_dd = ex["dd10_lift_vs_v0"].iloc[0]
        ex_ret = 0.0 if pd.isna(ex_ret) else float(ex_ret)
        ex_dd = 0.0 if pd.isna(ex_dd) else float(ex_dd)
        ex_ok = ex_ret >= 0.005 and ex_dd >= 0.03

    if n >= 1000 and ret_lift >= 0.005 and dd_improve and ex_ok:
        return (
            "PROMISING_RESEARCH_VARIANT",
            f"ret_60d_lift={ret_lift:.4f}, dd10_lift={dd_lift:.4f}, ex_vin_ok={ex_ok}",
            "candidate for P3 controlled research only — not production",
        )

    if dd_strong and ret_lift < 0.005:
        return (
            "RISK_REDUCTION_ONLY",
            f"dd10_lift={dd_lift:.4f} with weak return lift={ret_lift:.4f}",
            "use as risk filter research path, not alpha promotion",
        )

    if ret_lift < 0 and (dd_lift is None or dd_lift < 0.03):
        return (
            "REJECTED_VARIANT",
            f"ret_60d_lift={ret_lift:.4f}, dd10_lift={dd_lift}",
            "do not promote",
        )

    return "INCONCLUSIVE", f"ret_60d_lift={ret_lift:.4f}, dd10_lift={dd_lift}", "needs more evidence"


def build_diagnostic_summary(results: pd.DataFrame) -> pd.DataFrame:
    variant_ids = [v for v in results["variant_id"].unique() if v != "V0_RAW_SCORE"]
    rows = []
    for vid in sorted(variant_ids):
        label, evidence, step = label_variant(results, vid)
        rows.append(
            {
                "variant_id": vid,
                "label": label if label in ALLOWED_VARIANT_LABELS else "INCONCLUSIVE",
                "evidence": evidence,
                "recommended_next_step": step,
            }
        )
    return pd.DataFrame(rows)


def top_decile_exhaustion_table(df: pd.DataFrame) -> pd.DataFrame:
    ext = pd.to_numeric(df.get("extension_pct_above_ma20"), errors="coerce")
    d68 = _decile_6_8(df)
    buckets: list[tuple[str, pd.Series]] = [
        ("decile_9", pd.to_numeric(df["score_decile"], errors="coerce") == 9),
        ("decile_6_8", d68),
        ("decile_6_8_no_distribution", d68 & _no_dist(df)),
        ("decile_6_8_extension_cap_12", d68 & _ext_le(ext, 12.0)),
    ]
    rows = []
    for name, mask in buckets:
        sub = df[mask.fillna(False)]
        m = compute_metrics_block(sub)
        rows.append({"bucket": name, **m})
    return pd.DataFrame(rows)


def extension_cap_sweep(df: pd.DataFrame) -> pd.DataFrame:
    ext = pd.to_numeric(df.get("extension_pct_above_ma20"), errors="coerce")
    rows = []
    for cap in [5, 8, 10, 12, 15, 20]:
        sub = df[_ext_le(ext, float(cap)).reindex(df.index, fill_value=False)]
        m = compute_metrics_block(sub)
        rows.append({"cap_pct": cap, "cap_rule": f"extension<={cap}%", **m})
    rows.append({"cap_pct": None, "cap_rule": "no_cap", **compute_metrics_block(df)})
    return pd.DataFrame(rows)


def distribution_gate_sweep(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    gates: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = [
        ("dist_flag_false", lambda d: _no_dist(d)),
        ("dist_days_lt_6", lambda d: pd.to_numeric(d.get("distribution_days_25"), errors="coerce") < 6),
        ("dist_days_lt_5", lambda d: pd.to_numeric(d.get("distribution_days_25"), errors="coerce") < 5),
        ("dist_days_lt_4", lambda d: pd.to_numeric(d.get("distribution_days_25"), errors="coerce") < 4),
        ("dist_days_lt_3", lambda d: pd.to_numeric(d.get("distribution_days_25"), errors="coerce") < 3),
    ]
    for name, fn in gates:
        mask = fn(df)
        sub = df[mask.fillna(False)]
        m = compute_metrics_block(sub)
        rows.append({"gate": name, **m})
    return pd.DataFrame(rows)


P3_VARIANT_MAP: dict[str, str] = {
    "P3_V0_LIQUID_UNIVERSE_BASELINE": "liquid_universe",
    "P3_V4_NO_DISTRIBUTION_RISK": "V4_NO_DISTRIBUTION_RISK",
    "P3_V6_CONTROLLED_ACCUMULATION": "V6_CONTROLLED_ACCUMULATION",
    "P3_V9_V6_REGIME_GATED": "V9_V6_REGIME_GATED",
    "P3_V4B_DECILE_6_8_NO_DISTRIBUTION_RISK": "V4B_DECILE_6_8_NO_DISTRIBUTION_RISK",
}


def _liquid_universe_mask(df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= 20_000_000_000


def get_p3_variant_mask(df: pd.DataFrame, p3_variant_id: str) -> pd.Series:
    if p3_variant_id not in P3_VARIANT_MAP:
        raise KeyError(f"Unknown P3 variant: {p3_variant_id}")
    key = P3_VARIANT_MAP[p3_variant_id]
    if key == "liquid_universe":
        return _liquid_universe_mask(df)
    p2_masks = build_variant_masks(df)
    if key not in p2_masks:
        raise KeyError(f"Unknown P2 mask key: {key}")
    return p2_masks[key][1]


def run_p2_variants(outcomes: pd.DataFrame, out_dir: Path) -> P2Outputs:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = enrich_outcomes(outcomes)
    variant_results = compute_variant_results(df)
    top_ex = top_decile_exhaustion_table(df)
    ext_sweep = extension_cap_sweep(df)
    dist_sweep = distribution_gate_sweep(df)
    summary = build_diagnostic_summary(variant_results)

    variant_results.to_csv(out_dir / "p2_variant_results.csv", index=False)
    top_ex.to_csv(out_dir / "p2_top_decile_exhaustion.csv", index=False)
    ext_sweep.to_csv(out_dir / "p2_extension_cap_sweep.csv", index=False)
    dist_sweep.to_csv(out_dir / "p2_distribution_gate_sweep.csv", index=False)
    summary.to_csv(out_dir / "p2_diagnostic_summary.csv", index=False)

    return P2Outputs(variant_results, top_ex, ext_sweep, dist_sweep, summary)
