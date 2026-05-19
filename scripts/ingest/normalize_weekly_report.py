"""
Normalize current weekly_report.json (flat) into schema v1.0.
Preserves backward compatibility; maps legacy keys into new sections.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from scripts.ingest.config import (
    CONFIDENCE_HIGH_MIN,
    CONFIDENCE_MEDIUM_MIN,
    DECISION_WEEKLY_JSON,
    PENALTY_MISSING_REQUIRED,
    PENALTY_STALE_REPORT,
    REPO,
)
from scripts.ingest.legacy_adapter import (
    resolve_market_levels,
    resolve_suggested_regime,
    resolve_mismatch,
    resolve_watchlist_posture,
    resolve_sell_trim_signals,
    resolve_portfolio_health,
    resolve_dist_risk_composite,
)
from scripts.utils.date_utils import report_age_days
from scripts.utils.io import read_json
from scripts.utils.validation import validate_weekly_report_payload

# Paths
REGIME_STATE = REPO / "data" / "state" / "regime_state.json"
ALLOC = REPO / "data" / "decision" / "allocation_plan.json"
ALERTS = REPO / "data" / "alerts" / "market_flags.json"
COUNCIL = REPO / "data" / "decision" / "council_output.json"
GEO_HORMUZ = REPO / "data" / "state" / "geo_hormuz_energy_shock.json"
MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"
CORE_FEATURES = REPO / "data" / "features" / "core_features.json"
DOWNTREND_V2 = REPO / "data" / "decision" / "vnindex_downtrend_probability_v2.json"


def _confidence_score(legacy: Dict[str, Any], age_days: int | None) -> float:
    """Compute 0–1 confidence from missing data and staleness."""
    score = 1.0
    # Stale report
    if age_days is not None and age_days > 3:
        score -= PENALTY_STALE_REPORT
    # Required metrics: check manual_inputs for global/market
    manual = read_json(MANUAL_INPUTS)
    g = (manual.get("global") or {}) if manual else {}
    m = (manual.get("market") or {}) if manual else {}
    if g.get("ust_2y") is None:
        score -= PENALTY_MISSING_REQUIRED
    if g.get("ust_10y") is None:
        score -= PENALTY_MISSING_REQUIRED
    if m.get("vnindex_level") is None and m.get("vn30_level") is None:
        score -= PENALTY_MISSING_REQUIRED
    return max(0.0, min(1.0, score))


def _confidence_label(score: float) -> str:
    if score >= CONFIDENCE_HIGH_MIN:
        return "High"
    if score >= CONFIDENCE_MEDIUM_MIN:
        return "Medium"
    return "Low"


def _open_questions_with_gaps(
    base: List[str], global_deltas: List[Dict[str, Any]], vn_what: List[Dict[str, Any]]
) -> List[str]:
    out = list(base)
    bond_deltas = [d.get("delta") for d in global_deltas if isinstance(d, dict) and d.get("metric") in ("UST2Y", "UST10Y")]
    if not bond_deltas or all(x is None or x == 0 for x in bond_deltas):
        out.append("Bond WoW (UST 2Y/10Y): cần data/raw/manual_inputs_prev.json với số liệu tuần trước (khác tuần hiện tại).")
    if not vn_what:
        out.append("Vietnam liquidity WoW: cần manual_inputs_prev.vietnam (omo_net, interbank_on, credit_growth_yoy) tuần trước.")
    return out


def normalize_weekly_report(legacy_path: Path | None = None) -> Dict[str, Any]:
    """
    Read legacy weekly_report.json and return normalized payload (schema v1.0).
    """
    path = legacy_path or DECISION_WEEKLY_JSON
    legacy = read_json(path) if path and path.exists() else {}
    if not legacy:
        # Build minimal from current inputs
        manual = read_json(MANUAL_INPUTS)
        asof = (manual.get("asof_date") or "").strip() if manual else ""
        legacy = {"asof_date": asof or None, "data_confidence": "Low", "what_changed": [], "actions": [], "risks": [], "open_questions": []}

    from datetime import date
    asof = str(legacy.get("asof_date") or "").strip()
    if not asof:
        asof = str(date.today())
    age = report_age_days(asof)
    score = _confidence_score(legacy, age)
    conf_label = legacy.get("data_confidence") or _confidence_label(score)

    # Metadata
    from scripts.utils.date_utils import iso_now_utc
    metadata: Dict[str, Any] = {
        "asof_date": asof or None,
        "generated_at": iso_now_utc(),
        "report_age_days": age,
        "data_confidence": conf_label,
        "market_snapshot_date": legacy.get("market_snapshot_date"),
        "schema_version": "1.0.0",
        "build_id": "weekly-v1.0",
        "source_coverage_score": round(score, 2),
        "warnings": [],
    }
    if age is not None and age > 3:
        metadata["warnings"].append("Report is based on stale as-of date")

    # Global macro: what_changed from legacy; enrich from core_features if legacy deltas missing
    what = legacy.get("what_changed") or []
    global_deltas = [d for d in what if isinstance(d, dict) and d.get("metric") in ("UST2Y", "UST10Y", "DXY")]
    features = read_json(CORE_FEATURES) if CORE_FEATURES.exists() else {}
    fg = (features.get("global") or {}) if features else {}
    if fg and isinstance(fg, dict):
        def _dir(x: Any) -> str:
            if x is None: return "—"
            return "+" if x > 0 else ("-" if x < 0 else "0")
        def _bps(x: Any) -> Any:
            if x is None: return None
            try: return int(round(float(x) * 100))
            except Exception: return None
        for metric, chg_key in [("UST2Y", "ust_2y_chg_wow"), ("UST10Y", "ust_10y_chg_wow"), ("DXY", "dxy_chg_wow")]:
            val = fg.get(chg_key)
            if val is not None and not any(d.get("metric") == metric and d.get("delta") is not None for d in global_deltas):
                existing = next((d for d in global_deltas if d.get("metric") == metric), None)
                if existing is not None:
                    existing["delta"] = val
                    existing["delta_bps"] = _bps(val) if metric != "DXY" else None
                    existing["direction"] = _dir(val)
                else:
                    global_deltas.append({"metric": metric, "delta": val, "delta_bps": _bps(val) if metric != "DXY" else None, "direction": _dir(val), "source": "core_features"})
    manual = read_json(MANUAL_INPUTS)
    g = (manual.get("global") or {}) if manual else {}
    global_macro: Dict[str, Any] = {
        "facts": {
            "ust_2y": g.get("ust_2y"),
            "ust_10y": g.get("ust_10y"),
            "ust_2y_value_date": g.get("ust_2y_value_date"),
            "ust_10y_value_date": g.get("ust_10y_value_date"),
            "ust_yield_basis": g.get("ust_yield_basis") or "fred_dgs_daily_observation",
            "dxy": g.get("dxy"),
            "dxy_reconstructed": g.get("dxy_reconstructed"),
            "dxy_reconstructed_value_date": g.get("dxy_reconstructed_value_date"),
            "dxy_third_party_proxy": g.get("dxy_third_party_proxy"),
            "dxy_third_party_value_date": g.get("dxy_third_party_value_date"),
            "dxy_ice_official": g.get("dxy_ice_official"),
            "dxy_ice_official_value_date": g.get("dxy_ice_official_value_date"),
            "dxy_ice": g.get("dxy"),
            "dxy_ice_value_date": g.get("dxy_ice_value_date"),
            "usd_broad_index_fred": g.get("usd_broad_index_fred"),
            "usd_broad_index_fred_value_date": g.get("usd_broad_index_fred_value_date"),
            "cpi_yoy": g.get("cpi_yoy"),
            "cpi_reference_month": g.get("cpi_reference_month"),
            "cpi_source": g.get("cpi_source"),
            "nonfarm_payroll_change_persons": g.get("nonfarm_payroll_change_persons"),
            "nonfarm_payroll_level_thousands": g.get("nonfarm_payroll_level_thousands"),
            "nfp_legacy": g.get("nfp"),
        },
        "what_changed": global_deltas,
        "interpretation": [],
        "sources": [],
    }
    bond_deltas = [d.get("delta") for d in global_deltas if isinstance(d, dict) and d.get("metric") in ("UST2Y", "UST10Y")]
    if not any(bond_deltas) or all(x is None or x == 0 for x in bond_deltas):
        metadata["warnings"].append("Bond WoW = 0 or missing: update data/raw/manual_inputs_prev.json with prior week UST 2Y, UST 10Y, DXY then re-run full weekly.")

    # Vietnam liquidity: what_changed from core_features when available
    v = (manual.get("vietnam") or {}) if manual else {}
    vn_what: List[Dict[str, Any]] = []
    fv = (features.get("vietnam") or {}) if features else {}
    if isinstance(fv, dict):
        for label, key in [("OMO net", "omo_net_chg_wow"), ("Interbank ON", "interbank_on_chg_wow"), ("Credit growth YoY", "credit_growth_yoy_chg_wow")]:
            val = fv.get(key)
            if val is not None:
                vn_what.append({"metric": label, "delta": val, "direction": "+" if val > 0 else ("-" if val < 0 else "0"), "source": "core_features"})
    vn_prov = (manual.get("vietnam_provenance") or {}) if manual else {}
    vietnam_liquidity: Dict[str, Any] = {
        "facts": {
            "omo_net": v.get("omo_net"),
            "interbank_on": v.get("interbank_on"),
            "credit_growth_yoy": v.get("credit_growth_yoy"),
            "sbv_reference_usd_vnd": v.get("fx_usd_vnd"),
            "fx_usd_vnd": v.get("fx_usd_vnd"),
            "omo_net_verification": (vn_prov.get("omo_net") or {}).get("verification_status")
            if isinstance(vn_prov.get("omo_net"), dict)
            else None,
            "omo_net_source_detail": (vn_prov.get("omo_net") or {}).get("source_detail")
            if isinstance(vn_prov.get("omo_net"), dict)
            else None,
        },
        "what_changed": vn_what,
        "interpretation": [],
        "transmission": [],
        "sources": [],
    }

    # Market structure: report_snapshot (embedded in report), latest_market (freshest), levels (KPI = latest or report_snapshot)
    market_deltas = [d for d in what if isinstance(d, dict) and d.get("metric") in ("VNINDEX", "DIST_DAYS_20")]
    m = (manual.get("market") or {}) if manual else {}
    resolved = resolve_market_levels(legacy, asof, age)
    report_snapshot = resolved.get("report_snapshot") or {}
    latest_market = resolved.get("latest_market")
    levels_for_kpi = resolved.get("levels") or {}
    if levels_for_kpi.get("kpi_is_stale"):
        metadata["warnings"].append(
            "KPI uses report snapshot (stale); add data/decision/latest_market_snapshot.json for current level."
        )
    breadth_fields = {"vn30_trend_ok": m.get("vn30_trend_ok"), "hnx_trend_ok": m.get("hnx_trend_ok"), "upcom_trend_ok": m.get("upcom_trend_ok")}
    for bk, bv in breadth_fields.items():
        if bv is not None and bk not in levels_for_kpi:
            levels_for_kpi[bk] = bv
    market_structure: Dict[str, Any] = {
        "report_snapshot": report_snapshot,
        "latest_market": latest_market,
        "levels": levels_for_kpi,
        "breadth": breadth_fields,
        "distribution": {"dist_risk_composite": resolve_dist_risk_composite(legacy, asof)},
        "breakout_health": {},
        "what_changed": market_deltas,
    }

    # Regime: suggested_regime and mismatch from decision_log
    rs = read_json(REGIME_STATE)
    current_regime = rs.get("regime")
    suggested_regime = resolve_suggested_regime(legacy, asof)
    regime_engine: Dict[str, Any] = {
        "current_regime": current_regime,
        "suggested_regime": suggested_regime,
        "mismatch": resolve_mismatch(legacy, asof, current_regime),
        "inputs": {"global_liquidity": rs.get("global_liquidity"), "vn_liquidity": rs.get("vn_liquidity")},
        "reasoning": [],
    }

    # Probability + allocation
    al = read_json(ALLOC)
    prob_alloc = al.get("probabilities") or {}
    alloc_dict = al.get("allocation") or {}
    probability_allocation: Dict[str, Any] = {
        "probabilities": prob_alloc,
        "allocation": alloc_dict,
        "override": {"gross_exposure_override": alloc_dict.get("gross_exposure_override"), "cash_weight_override": alloc_dict.get("cash_weight_override")},
    }

    # Portfolio structure (from allocation + core gate)
    portfolio_structure: Dict[str, Any] = {"core_allowed": False, "bucket_allocation": {}}

    # Decision layer
    decision_layer: Dict[str, Any] = {
        "top_actions": legacy.get("actions") or [],
        "top_risks": legacy.get("risks") or [],
        "watchlist_updates": {},
        "decision_rules_fired": legacy.get("triggers_fired") or [],
    }

    # Watchlist: posture from adapter (risk_flag + regime)
    watchlist: Dict[str, Any] = {
        "posture": resolve_watchlist_posture(legacy, asof),
        "candidates": [],  # optional: from watchlist_scores if needed
        "scores": [],
        "notes": [],
    }

    # Execution: sell_trim_signals from adapter (data/alerts/sell_signals.json)
    flags = read_json(ALERTS)
    execution_monitoring: Dict[str, Any] = {
        "risk_flags": {
            "risk_flag": flags.get("risk_flag"),
            "distribution_days_rolling_20": levels_for_kpi.get("distribution_days_rolling_20"),
            "dist_proxy_symbol": levels_for_kpi.get("dist_proxy_symbol"),
            "distribution_days": flags.get("distribution_days"),
        },
        "sell_trim_signals": resolve_sell_trim_signals(legacy, asof),
        "execution_notes": [],
    }

    # Downtrend V2: map adjusted probabilities for HTML card.
    downtrend_v2_raw = read_json(DOWNTREND_V2) if DOWNTREND_V2.exists() else {}
    downtrend_current = (downtrend_v2_raw.get("current_probabilities") or {}) if isinstance(downtrend_v2_raw, dict) else {}
    k_candidates = [10, "10", 5, "5", 20, "20"]

    def _pick_adjusted(target: str) -> Any:
        t = downtrend_current.get(target) if isinstance(downtrend_current, dict) else None
        if not isinstance(t, dict):
            return None
        for kk in k_candidates:
            kv = t.get(kk)
            if isinstance(kv, dict) and kv.get("adjusted_p") is not None:
                return kv.get("adjusted_p")
        return None

    downtrend_v2: Dict[str, Any] = {
        "asof": downtrend_v2_raw.get("asof") if isinstance(downtrend_v2_raw, dict) else None,
        "regime": downtrend_v2_raw.get("regime") if isinstance(downtrend_v2_raw, dict) else None,
        "outcome_b_adjusted": _pick_adjusted("outcome_B"),
        "confirmed_downtrend_adjusted": _pick_adjusted("confirmed_downtrend_20d"),
    }

    # Portfolio health: from decision_log via adapter
    portfolio_health: Dict[str, Any] = resolve_portfolio_health(legacy, asof)

    # Council
    council = read_json(COUNCIL)
    council_status: Dict[str, Any] = {
        "status": council.get("status", "missing"),
        "mechanically_executable": council.get("mechanically_executable", False),
        "chair_decision_logged": bool(council.get("chair_decision")),
        "next_step": "Run council prompts and save data/decision/council_output.json",
    }

    # Geo
    geo_layers: Dict[str, Any] = {}
    if legacy.get("geo_hormuz_energy_shock"):
        geo_layers["geo_hormuz_energy_shock"] = legacy["geo_hormuz_energy_shock"]
    elif GEO_HORMUZ.exists():
        geo_layers["geo_hormuz_energy_shock"] = read_json(GEO_HORMUZ)

    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections

    payload: Dict[str, Any] = {
        "metadata": metadata,
        "global_macro": global_macro,
        "vietnam_liquidity": vietnam_liquidity,
        "vietnam_policy": {"events": [], "transmission_map": [], "sources": []},
        "research_intake": {"macro": [], "sector": [], "company": [], "policy": []},
        "sectors_companies": {"weekly_events": [], "broker_notes": [], "earnings": [], "valuation_changes": [], "catalysts": [], "risks": []},
        "market_structure": market_structure,
        "regime_engine": regime_engine,
        "probability_allocation": probability_allocation,
        "portfolio_structure": portfolio_structure,
        "decision_layer": decision_layer,
        "watchlist": watchlist,
        "execution_monitoring": execution_monitoring,
        "downtrend_v2": downtrend_v2,
        "portfolio_health": portfolio_health,
        "council_status": council_status,
        "geo_layers": geo_layers,
        "open_questions": _open_questions_with_gaps(legacy.get("open_questions") or [], global_deltas, vn_what),
        "monitoring_next_week": [
            "Update: UST 2Y/10Y (FRED obs dates), ICE DXY, USD broad DTWEXBGS, BLS CPI ref month, payroll MoM change",
            "VN: OMO net (provenance), interbank ON, credit growth trend, SBV reference USD/VND",
            "Market: distribution days rolling-20, breadth, failed breakouts",
        ],
        "playbook_if_x_then_y": [
            "If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.",
            "If distribution days cluster + failed breakout → cut laggards, only hold leaders.",
            "If policy tailwind + earnings confirm for a sector → overweight with risk limits.",
        ],
    }
    return enrich_portfolio_decision_sections(payload, fetch_prices=True)
