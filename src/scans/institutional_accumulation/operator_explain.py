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
