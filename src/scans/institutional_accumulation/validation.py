from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import MF_CORR_WARN_THRESHOLD

CONSENSUS_CHECK = ["MBB", "CTG", "MWG", "HPG", "GMD"]
VIN_DISTORTED_CHECK = ["VIC", "VHM"]

MONEY_FLOW_FEATURE_COLS = [
    "cmf20_daily",
    "cmf20_weekly",
    "obv_slope_20",
    "obv_slope_50",
    "adl_slope_20",
    "pvt_slope_20",
    "up_down_volume_ratio_20",
    "turnover_accel_ratio_5d50d",
]


def run_spot_checks(df: pd.DataFrame, scan_date: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if df.empty:
        return {"error": "empty_scan"}

    sub = df.set_index("ticker", drop=False)
    for sym in CONSENSUS_CHECK:
        if sym not in sub.index:
            out[f"consensus_{sym}"] = "not_in_universe_or_filtered"
            continue
        r = sub.loc[sym]
        out[f"consensus_{sym}"] = (
            f"tier={r['tier']} score={r['institutional_accumulation_score']:.1f} "
            f"money={r.get('score_money_flow', 0):.0f} vin_flag={r.get('vingroup_distortion_flag')}"
        )

    for sym in VIN_DISTORTED_CHECK:
        if sym not in sub.index:
            out[f"vin_{sym}"] = "not_in_universe"
            continue
        r = sub.loc[sym]
        out[f"vin_{sym}"] = (
            f"tier={r['tier']} score={r['institutional_accumulation_score']:.1f} "
            f"vin_distortion={r.get('vingroup_distortion_flag')} "
            f"cmf_d={r.get('cmf20_daily')} cmf_w={r.get('cmf20_weekly')}"
        )

    t1 = df[df["tier"] == "Tier 1"]
    if not t1.empty:
        dom = t1["score_money_flow"].mean() - t1["score_context"].mean()
        out["tier1_money_vs_context_spread"] = f"{dom:.1f} (positive => flow-driven)"
    return out


def money_flow_correlation_check(df: pd.DataFrame) -> Dict[str, Any]:
    """Intra-block redundancy: warn if any pairwise |corr| > threshold."""
    cols = [c for c in MONEY_FLOW_FEATURE_COLS if c in df.columns]
    if len(cols) < 2:
        return {"status": "insufficient_columns", "high_corr_pairs": []}

    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    if sub.dropna(how="all").shape[0] < 5:
        return {"status": "insufficient_rows", "high_corr_pairs": []}

    corr = sub.corr(numeric_only=True)
    high_pairs: List[Dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            v = corr.loc[a, b] if a in corr.index and b in corr.columns else np.nan
            if pd.notna(v) and abs(float(v)) > MF_CORR_WARN_THRESHOLD:
                high_pairs.append({"a": a, "b": b, "corr": round(float(v), 4)})

    return {
        "status": "warn" if high_pairs else "ok",
        "threshold": MF_CORR_WARN_THRESHOLD,
        "n_features": len(cols),
        "high_corr_pairs": high_pairs,
        "correlation_matrix": {
            a: {b: round(float(corr.loc[a, b]), 4) for b in cols if pd.notna(corr.loc[a, b])}
            for a in cols
            if a in corr.index
        },
    }


def unit_handling_check(df: pd.DataFrame) -> Dict[str, Any]:
    if "price_unit_mode" not in df.columns:
        return {"status": "missing_column", "warnings": []}
    modes = df["price_unit_mode"].value_counts().to_dict()
    warnings = []
    if "unit_warning" in df.columns:
        uw = df[df["unit_warning"].notna() & (df["unit_warning"] != "")]
        for _, r in uw.iterrows():
            warnings.append(f"{r['ticker']}: {r['unit_warning']}")
    unknown = int((df["price_unit_mode"] == "unknown").sum())
    if unknown > 0:
        warnings.append(f"{unknown} symbols with unknown price_unit_mode")
    return {
        "status": "warn" if warnings else "ok",
        "modes": modes,
        "warnings": warnings,
    }


def score_component_balance(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    corr = df[
        [
            "institutional_accumulation_score",
            "score_money_flow",
            "score_price_structure",
            "score_context",
            "score_risk_penalty",
        ]
    ].corr(numeric_only=True)
    top_decile = df.nlargest(max(10, len(df) // 10), "institutional_accumulation_score")
    mf_dom = float(top_decile["score_money_flow"].mean()) > float(top_decile["score_context"].mean()) * 1.2
    one_indicator_dominated = bool(
        corr.get("institutional_accumulation_score", {}).get("score_money_flow", 0) > 0.95
    )
    sectors = top_decile["sector"].value_counts()
    theme_concentrated = False
    if not sectors.empty and sectors.iloc[0] >= max(3, len(top_decile) * 0.6):
        theme_concentrated = True
    return {
        "top_decile_money_flow_dominant": mf_dom,
        "single_indicator_correlation_warning": one_indicator_dominated,
        "top_decile_sector_concentrated": theme_concentrated,
        "dominant_top_decile_sector": sectors.index[0] if not sectors.empty else None,
        "money_flow_groups_present": "score_mf_cmf" in df.columns,
    }


def confirm_no_lookahead(symbol: str, stocks_dir, scan_date: str) -> bool:
    from .filters import load_symbol_ohlcv
    from .indicators import slice_through

    raw = load_symbol_ohlcv(stocks_dir, symbol)
    if raw is None:
        return True
    sliced = slice_through(raw, scan_date)
    if sliced.empty:
        return True
    last = pd.Timestamp(sliced["date"].max())
    return last <= pd.Timestamp(scan_date)


def confirm_no_execution_fields(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Scan outputs must not contain trading execution keys."""
    forbidden = ("final_action", "order_", "dnse", "oms", "buy_order", "sell_order")
    issues: List[str] = []

    def _walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if any(f in kl for f in forbidden):
                    issues.append(f"{path}.{k}")
                _walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:50]):
                _walk(v, f"{path}[{i}]")

    _walk(payload, "root")
    return len(issues) == 0, issues
