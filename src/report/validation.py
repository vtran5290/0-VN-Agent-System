from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional


CORE_FIELDS = [
    ("global", "ust_2y"),
    ("global", "ust_10y"),
    ("vietnam", "omo_net"),
    ("vietnam", "interbank_on"),
    ("vietnam", "credit_growth_yoy"),
    ("market", "distribution_days_rolling_20"),
]


def _audit_row(audit: Any, metric_key: str) -> Optional[Dict[str, Any]]:
    if not isinstance(audit, list):
        return None
    for row in audit:
        if isinstance(row, dict) and row.get("metric_key") == metric_key:
            return row
    return None


def _is_weekend(d: str) -> bool:
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").weekday() >= 5
    except Exception:
        return False


def validate_core(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Split missing vs not_due_yet; add warnings for semantic/fallback issues.
    Confidence: do not treat intentional fail-closed (ICE DXY unavailable) like random gaps;
    do not treat official series marked not_due_yet as missing.
    """
    missing: List[str] = []
    not_due_yet: List[str] = []
    warnings: List[str] = []

    g = inputs.get("global") or {}
    audit = inputs.get("global_metrics_audit") or []

    for sec, key in CORE_FIELDS:
        val = inputs.get(sec, {}).get(key)
        if val is None:
            missing.append(f"{sec}.{key}")

    # Heuristic: broad dollar ~120 vs DXY ~100 — if `dxy` looks like broad and broad field missing
    if g.get("dxy") is not None:
        try:
            if (
                float(g["dxy"]) > 110  # type: ignore[arg-type]
                and g.get("dxy_reconstructed") is None
                and g.get("usd_broad_index_fred") is None
            ):
                warnings.append(
                    "suspected_broad_dollar_mislabeled_as_dxy (large dxy without reconstructed/broad; check inputs)"
                )
        except (TypeError, ValueError):
            pass

    # Primary USD index display: reconstructed FRED basket and/or legacy `dxy`; never silent map from DTWEXBGS
    has_dxy_primary = g.get("dxy") is not None or g.get("dxy_reconstructed") is not None
    if not has_dxy_primary:
        if "global.dxy" in missing:
            missing.remove("global.dxy")
        rr = _audit_row(audit, "dxy_reconstructed")
        if rr and rr.get("fetch_status") in ("failed", "skipped"):
            warnings.append(
                "dxy_reconstructed_unavailable (FRED H.10 FX alignment failed or no FRED_API_KEY)"
            )
        tp = _audit_row(audit, "dxy_third_party")
        if tp and tp.get("fetch_status") == "failed":
            warnings.append("dxy_third_party_proxy_unavailable (Yahoo DX-Y.NYB)")

    mkt = inputs.get("market", {})
    vn = mkt.get("vnindex_level")
    vn30 = mkt.get("vn30_level") or mkt.get("vnindex_proxy_level")
    if vn is None and vn30 is None:
        missing.append("market.market_level(vnindex_or_vn30)")

    # CPI: FRED fallback is explicitly non-official
    if g.get("cpi_source") == "fred_cpiau_derived":
        warnings.append("cpi_yoy_from_fred_not_bls_official_release")

    cpi_row = _audit_row(audit, "cpi_yoy")
    if cpi_row and cpi_row.get("fetch_status") == "not_due_yet":
        not_due_yet.append("global.cpi_yoy")
        if "global.cpi_yoy" in missing:
            missing.remove("global.cpi_yoy")

    # Generic FX label: SBV reference should be explicit in provenance
    vnliq = inputs.get("vietnam") or {}
    vprov = (inputs.get("vietnam_provenance") or {}).get("fx_usd_vnd") or {}
    if vnliq.get("fx_usd_vnd") is not None and isinstance(vprov, dict) and vprov:
        sd = str(vprov.get("source_detail") or "").lower()
        if "reference" not in sd and "sbv" not in sd and "trung tâm" not in sd:
            warnings.append("fx_usd_vnd_should_be_labeled_sbv_reference_check_provenance")

    # OMO: flag unlabeled fallback / failed fallback
    omop = (inputs.get("vietnam_provenance") or {}).get("omo_net") or {}
    if isinstance(omop, dict):
        vs = str(omop.get("verification_status") or "")
        if vs == "fallback_used" and not (omop.get("source_detail") or "").strip():
            warnings.append("omo_net_fallback_missing_source_detail")
        if vnliq.get("omo_net") is None and vs == "fallback_failed":
            warnings.append(f"omo_net_null ({vs})")

    # Weekend as-of vs same-day market-close dates (heuristic)
    asof = str(inputs.get("asof_date") or "")[:10]
    if asof and _is_weekend(asof):
        dxy_vd = str(g.get("dxy_third_party_value_date") or g.get("dxy_reconstructed_value_date") or "")[:10]
        if dxy_vd == asof:
            warnings.append("report_asof_weekend_but_dxy_same_calendar_day_suspicious")

    # Penalize missing, but not not_due_yet; soft-penalize semantic warnings
    eff_missing = len(missing)
    penalty = 0
    for w in warnings:
        if "cpi_yoy_from_fred" in w or "fallback_missing" in w:
            penalty += 1
        if w.startswith("omo_net_null"):
            penalty += 0  # already in missing for omo if omo in CORE and null — omo_net is in missing

    score = eff_missing + penalty
    if score == 0:
        confidence = "High"
    elif score <= 4:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "confidence": confidence,
        "missing": missing,
        "not_due_yet": not_due_yet,
        "warnings": warnings,
    }
