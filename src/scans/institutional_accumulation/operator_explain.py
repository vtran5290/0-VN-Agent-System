"""Rule-based operator explanations derived from existing scan columns (no score changes)."""
from __future__ import annotations

from typing import Any

import pandas as pd

FUND_BUCKETS = {
    "consensus_core",
    "consensus_second_ring",
    "fund_commentary_mention",
    "selective_fund_bet",
}


def _f(val: Any, default: float = 0.0) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _cmf_weak_phrase(row: pd.Series) -> str | None:
    cd = row.get("cmf20_daily")
    cw = row.get("cmf20_weekly")
    if pd.isna(cd):
        return "daily CMF missing"
    if pd.notna(cw) and float(cw) <= 0.03:
        return "weekly CMF still weak"
    if row.get("cmf_flow_conflict"):
        return "daily/weekly CMF conflict"
    if pd.notna(cd) and float(cd) <= 0.05 and (pd.isna(cw) or float(cw) <= 0.03):
        return "CMF not constructive"
    return None


def explain_row(row: pd.Series) -> dict[str, str]:
    """Deterministic short explanations from existing fields."""
    tier = str(row.get("tier", ""))
    bucket = str(row.get("fund_context_bucket", "outside_fund_disclosure"))
    emerging = bool(row.get("emerging_accumulation_candidate"))
    vin = bool(row.get("vingroup_distortion_flag"))
    dist = bool(row.get("distribution_risk_flag"))
    mf = _f(row.get("score_money_flow"))
    ctx = _f(row.get("score_context"))
    risk_pen = _f(row.get("score_risk_penalty"))
    sym = str(row.get("ticker", "")).upper()

    primary = _primary_driver(row, tier, bucket, emerging, vin, mf, ctx, risk_pen, sym)
    secondary = _secondary_driver(row, bucket, mf, ctx)
    risks = _main_risks(row, vin, dist, risk_pen, sym)
    note = _operator_note(row, tier, bucket, emerging, vin, mf, ctx, risk_pen, primary)

    return {
        "primary_driver": primary[:220],
        "secondary_driver": secondary[:220] if secondary else "",
        "main_risk": risks[:220],
        "operator_note": note[:220],
    }


def _primary_driver(
    row: pd.Series,
    tier: str,
    bucket: str,
    emerging: bool,
    vin: bool,
    mf: float,
    ctx: float,
    risk_pen: float,
    sym: str,
) -> str:
    cmf_note = _cmf_weak_phrase(row)

    if tier == "Reject" and bucket == "consensus_core":
        if mf < 42:
            return "Consensus-core, but grouped money flow still weak"
        return "Consensus-core name below accumulation tier thresholds"

    if emerging and tier in ("Tier 1", "Tier 2", "Tier 3") and mf >= 55 and risk_pen <= 25:
        return "Emerging name with strong grouped flow and low risk"

    if vin and tier in ("Tier 2", "Tier 3"):
        return "VIN distortion: strong RS without robust multi-horizon flow"

    if sym in {"VIC", "VHM", "VRE", "VPL"} and risk_pen >= 45 and not vin:
        return "VIN-linked name: elevated risk penalty; distortion flag not active at this as-of"

    if tier in ("Tier 2", "Tier 3") and risk_pen >= 45 and mf >= 50:
        return "Flow acceptable, but risk penalty too high for clean accumulation"

    if tier == "Tier 3" and bucket in FUND_BUCKETS and ctx >= 50 and mf < 48:
        base = "Tier held up mainly by context, not flow confirmation"
        if cmf_note:
            return f"{base}; {cmf_note}"
        return base

    if tier == "Tier 3" and bucket == "consensus_core" and mf < 48:
        return "Consensus-core, but weekly CMF / grouped flow still weak"

    if tier in ("Tier 2", "Tier 3") and mf >= 55 and ctx < 45:
        return "Flow-led candidate with limited fund-context support"

    if bucket in FUND_BUCKETS and mf < 42:
        return "Fund-linked, but grouped money flow not confirming"

    if emerging:
        return "Emerging (no fund tag); flow/risk pass emerging gate"

    if mf >= 55:
        return "Grouped money flow supportive"
    if mf < 40:
        return "Grouped money flow weak"

    return "Scan tier driven by mixed flow/context/risk profile"


def _secondary_driver(row: pd.Series, bucket: str, mf: float, ctx: float) -> str:
    parts: list[str] = []
    if bucket in FUND_BUCKETS:
        parts.append(f"bucket={bucket}")
    if _f(row.get("score_mf_cmf")) >= 60:
        parts.append("CMF block strong")
    if _f(row.get("score_mf_obv_pvt")) >= 60:
        parts.append("OBV/PVT supportive")
    if ctx >= 55:
        parts.append("context score elevated")
    elif ctx < 40 and bucket in FUND_BUCKETS:
        parts.append("context score thin")
    cmf = _cmf_weak_phrase(row)
    if cmf and cmf not in parts:
        parts.append(cmf)
    return "; ".join(parts[:3])


def _main_risks(row: pd.Series, vin: bool, dist: bool, risk_pen: float, sym: str) -> str:
    risks: list[str] = []
    if vin:
        risks.append("Vingroup distortion flag active")
    if dist:
        risks.append("Distribution-day count elevated")
    if risk_pen >= 50:
        risks.append(f"High risk penalty ({risk_pen:.0f})")
    elif risk_pen >= 30:
        risks.append(f"Moderate risk penalty ({risk_pen:.0f})")
    if sym in {"VIC", "VHM"} and not vin and risk_pen >= 45:
        risks.append("VIN name in caution via risk, not distortion flag")
    if not risks:
        return "No major structural risk flag"
    return "; ".join(risks[:3])


def _operator_note(
    row: pd.Series,
    tier: str,
    bucket: str,
    emerging: bool,
    vin: bool,
    mf: float,
    ctx: float,
    risk_pen: float,
    primary: str,
) -> str:
    if vin:
        return "Do not treat as clean accumulation until multi-horizon flow confirms."
    if tier == "Reject" and bucket == "consensus_core":
        return "Monitor as fund-core reject — check if flow repair is underway."
    if emerging and tier in ("Tier 1", "Tier 2"):
        return "Validate catalyst and liquidity; no fund disclosure tag."
    if tier == "Tier 2" and bucket == "outside_fund_disclosure" and mf >= 55:
        return "High-priority forensic review: strong flow without fund tag."
    if tier == "Tier 3" and bucket in FUND_BUCKETS and ctx >= 50 and mf < 48:
        return "Investigate whether context is masking weak CMF/participation."
    if risk_pen >= 45:
        return "Size as research only until risk penalty improves."
    if "weak" in primary.lower():
        return "Deprioritize until money-flow block strengthens."
    return f"{tier} — use full scan row for CMF/OBV detail."


def reject_failure_reason(row: pd.Series) -> str:
    """Why an important name is Reject (for monitoring list)."""
    reasons: list[str] = []
    if _f(row.get("score_money_flow")) < 40:
        reasons.append("weak grouped money flow")
    cmf = _cmf_weak_phrase(row)
    if cmf:
        reasons.append(cmf)
    if _f(row.get("score_risk_penalty")) >= 35:
        reasons.append("risk penalty elevated")
    if bool(row.get("distribution_risk_flag")):
        reasons.append("distribution risk flag")
    if bool(row.get("vingroup_distortion_flag")):
        reasons.append("Vingroup distortion")
    if not bool(row.get("liquidity_ok")):
        reasons.append("liquidity gate fail")
    if str(row.get("tier", "")) != "Reject":
        return ""
    if not reasons:
        reasons.append("below tier score/flow thresholds")
    return "; ".join(reasons[:4])


def attach_operator_explain(df: pd.DataFrame) -> pd.DataFrame:
    """Add explain columns to scan dataframe (derived only)."""
    if df.empty:
        return df
    out = df.copy()
    explains = [explain_row(out.loc[i]) for i in out.index]
    for key in ("primary_driver", "secondary_driver", "main_risk", "operator_note"):
        out[key] = [e[key] for e in explains]
    out["reject_failure_reason"] = [reject_failure_reason(out.loc[i]) for i in out.index]
    return out


# ─── Full-history backtest evidence (display-only annotations) ─────────────
# SSOT: data/research/institutional_accumulation_full_history/ia_dashboard_evidence_config.json
# Does NOT change scores, tiers, final_action, OMS, DNSE, or sizing.

from .config import REPO

EVIDENCE_CONFIG_PATH = (
    REPO / "data" / "research" / "institutional_accumulation_full_history" / "ia_dashboard_evidence_config.json"
)
EVIDENCE_METRICS_PATH = (
    REPO / "data" / "research" / "institutional_accumulation_full_history" / "full_history_portfolio_metrics.csv"
)

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

ALLOWED_EVIDENCE_LABELS = frozenset(
    {
        "INCONCLUSIVE_NOT_BUY_SIGNAL",
        "HEAT_RISK_MANUAL_REVIEW",
        "RISK_CONTROL_SUPPORTED",
        "RISK_CLEAN_RESEARCH_ONLY",
        "AVOID_OR_MANUAL_REVIEW",
        "DISPLAY_ONLY",
    }
)

EVIDENCE_LABEL_INCONCLUSIVE = "INCONCLUSIVE_NOT_BUY_SIGNAL"
EVIDENCE_LABEL_HEAT = "HEAT_RISK_MANUAL_REVIEW"
EVIDENCE_LABEL_RISK_CONTROL = "RISK_CONTROL_SUPPORTED"
EVIDENCE_LABEL_RISK_CLEAN = "RISK_CLEAN_RESEARCH_ONLY"
EVIDENCE_LABEL_AVOID = "AVOID_OR_MANUAL_REVIEW"
EVIDENCE_LABEL_DISPLAY = "DISPLAY_ONLY"

# Backward-compatible aliases for tests importing old names
EVIDENCE_LABEL_DIST_RISK = EVIDENCE_LABEL_AVOID
EVIDENCE_LABEL_NONE = EVIDENCE_LABEL_INCONCLUSIVE

EVIDENCE_RESEARCH_NOTE = (
    "Raw IA score is not validated as a standalone buy-ranking signal. "
    "Top-decile / extreme high-score names can be heat-risk or exhaustion-risk."
)

EVIDENCE_SAFETY_NOTE = (
    "This dashboard does not set final_action, OMS orders, DNSE routing, sizing, or live execution."
)

_FALLBACK_EVIDENCE_CONFIG: dict[str, object] = {
    "version": "full_history_v0.2",
    "research_only_flag": RESEARCH_ONLY_FLAG,
    "portfolio_promotion": "NO-GO",
    "portfolio_promising_count": 0,
    "banner_title": "Full-History Evidence Status",
    "raw_score_assessment": "INCONCLUSIVE / not a buy signal",
    "top_decile_assessment": "HEAT_RISK / manual review",
    "distribution_filter_assessment": "RISK_CONTROL_SUPPORTED",
    "best_use": "risk avoidance + research prioritization",
    "safety_note": EVIDENCE_SAFETY_NOTE,
    "how_to_read": (
        "Use this dashboard to avoid weak/risky setups first, then prioritize manual research. "
        "Do not treat high score as a buy signal."
    ),
    "validation_report_path": (
        "reports/research/institutional_accumulation_full_history/full_history_accumulation_validation.html"
    ),
}


def load_dashboard_evidence_config(*, validate_metrics: bool = True) -> dict[str, object]:
    """Load full-history dashboard evidence SSOT; optional CSV sanity check."""
    import json

    if EVIDENCE_CONFIG_PATH.is_file():
        cfg = json.loads(EVIDENCE_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        cfg = dict(_FALLBACK_EVIDENCE_CONFIG)

    if validate_metrics and EVIDENCE_METRICS_PATH.is_file():
        try:
            metrics = pd.read_csv(EVIDENCE_METRICS_PATH, usecols=["label"])
            if "label" in metrics.columns:
                n_promising = int((metrics["label"] == "PORTFOLIO_PROMISING").sum())
                cfg["portfolio_promising_count"] = n_promising
        except Exception:
            pass
    return cfg


def _turnover_p90(df: pd.DataFrame) -> float:
    col = "turnover_accel_ratio_5d50d"
    if col not in df.columns:
        return 2.0
    vals = df[col].dropna()
    return float(vals.quantile(0.90)) if len(vals) >= 10 else 2.0


def _operator_note_for_label(label: str) -> str:
    if label == EVIDENCE_LABEL_HEAT:
        return "High score may reflect late-stage heat. Manual review only. Not a buy signal."
    if label == EVIDENCE_LABEL_AVOID:
        return (
            "Full-history evidence supports distribution-risk filtering as risk control. "
            "Avoid new research unless there is a separate catalyst."
        )
    if label == EVIDENCE_LABEL_RISK_CLEAN:
        return "Risk-clean research queue only — not validated alpha or production entry."
    if label == EVIDENCE_LABEL_RISK_CONTROL:
        return "Distribution-risk profile clean; useful for risk screening, not automatic buying."
    if label == EVIDENCE_LABEL_DISPLAY:
        return "Display context only — no validated backtest promotion signal."
    return "Raw score not validated as buy signal — research prioritization only."


def attach_backtest_evidence_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add full-history v0.2 evidence fields to scan df. No score/tier/OMS changes."""
    if df.empty:
        return df
    out = df.copy()

    if "score_decile" not in out.columns:
        ranks = out["institutional_accumulation_score"].rank(method="first", na_option="bottom")
        out["score_decile"] = (
            pd.cut(ranks, bins=10, labels=range(10), include_lowest=True)
            .astype(float)
            .fillna(0)
            .astype(int)
        )

    dist_flag = out.get("distribution_risk_flag", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    ext = out.get("extension_pct_above_ma20", pd.Series(0.0, index=out.index)).fillna(0.0).astype(float)
    dd25 = out.get("distribution_days_25", pd.Series(0.0, index=out.index)).fillna(0.0).astype(float)
    turn = out.get("turnover_accel_ratio_5d50d", pd.Series(0.0, index=out.index)).fillna(0.0).astype(float)

    try:
        decile = out["score_decile"].fillna(0).astype(int)
    except (ValueError, TypeError):
        decile = out["score_decile"].fillna(0).astype(float).astype(int)

    p90_turn = _turnover_p90(out)
    heat_indicator = (ext > 15) | (dd25 >= 4) | (turn >= p90_turn)

    out["distribution_risk_clean"] = (~dist_flag).astype(bool)
    out["risk_clean_flag"] = out["distribution_risk_clean"]
    out["top_decile_heat_risk"] = ((decile >= 9) | heat_indicator).astype(bool)

    out["controlled_accumulation_flag"] = (
        decile.isin([5, 6, 7, 8]) & (ext <= 12) & (~dist_flag) & (dd25 < 5)
    ).astype(bool)

    risk_clean_candidate = (~dist_flag) & (~out["top_decile_heat_risk"]) & decile.isin([5, 6, 7, 8])
    out["risk_clean_research_candidate"] = risk_clean_candidate.astype(bool)

    labels = pd.Series(EVIDENCE_LABEL_INCONCLUSIVE, index=out.index)
    labels[(~dist_flag) & (~out["top_decile_heat_risk"])] = EVIDENCE_LABEL_RISK_CONTROL
    labels[risk_clean_candidate] = EVIDENCE_LABEL_RISK_CLEAN
    labels[out["top_decile_heat_risk"] | (decile >= 9)] = EVIDENCE_LABEL_HEAT
    labels[dist_flag] = EVIDENCE_LABEL_AVOID
    out["evidence_label"] = labels

    bucket = pd.Series("standard", index=out.index)
    bucket[(~dist_flag) & (~out["top_decile_heat_risk"])] = "risk_control_supported"
    bucket[risk_clean_candidate] = "risk_clean_research"
    bucket[out["top_decile_heat_risk"] | (decile >= 9)] = "heat_warning"
    bucket[dist_flag] = "dist_risk_avoid"
    out["dashboard_priority_bucket"] = bucket

    out["research_only_flag"] = RESEARCH_ONLY_FLAG
    out["dashboard_operator_note"] = [_operator_note_for_label(str(lbl)) for lbl in out["evidence_label"]]

    return out
