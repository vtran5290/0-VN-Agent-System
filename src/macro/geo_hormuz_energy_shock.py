from __future__ import annotations

"""
geo_hormuz_energy_shock — deterministic Hormuz energy shock layer (v2).

Facts-first, no forecasting:
- Inputs: conflict intensity, transit status, oil/LNG/market signals, VN supply conditions.
- Outputs: risk_state (LOW/MED/HIGH), shock_mode (headline|risk_premium|transition|physical_disruption),
  inflation_risk_vn, supply_disruption_risk_vn, sbv_policy_constraint, signal_counts,
  real_cycle_checklist, next_fill_priority, regime-aware transmission_map_vn.

Thresholds and checklist from config/geo_hormuz_energy_shock_rules.yaml when present.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUTS = REPO_ROOT / "data" / "raw" / "geo_hormuz_energy_shock_inputs.json"
RULES_PATH = REPO_ROOT / "config" / "geo_hormuz_energy_shock_rules.yaml"

# Inline defaults if YAML missing
DEFAULT_THRESHOLDS = {
    "brent_change_5d_pct": {"med": 5, "high": 12},
    "tanker_rates_change_5d_pct": {"med": 20, "high": 35},
    "backwardation_1m_6m": {"market_signal": 2},
    "asia_diesel_crack_change_5d_pct": {"market_signal": 15},
    "jkm_change_5d_pct": {"market_signal": 10},
    "ais_transit_drop_7d_pct": {"physical_signal": -20},
    "vn_fuel_price_adjustment_pct": {"medium": 2, "high": 4},
}
REAL_CYCLE_CHECKLIST_ITEMS = [
    "hormuz_transit_status",
    "war_risk_insurance_status",
    "tanker_rates_change_5d_pct",
    "backwardation_1m_6m",
    "qatar_lng_status",
    "vn_lpg_supply_status",
]
GEO_EVENTS_TAGS = {"ship_attack", "mine", "port_hit", "insurance_pullback", "naval_escort"}


def _load_rules() -> Dict[str, Any]:
    if not RULES_PATH.exists():
        return {}
    try:
        import yaml
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_threshold(rules: Dict[str, Any], key: str, subkey: str, default: Any) -> Any:
    t = (rules.get("thresholds") or {}).get(key) or DEFAULT_THRESHOLDS.get(key) or {}
    return t.get(subkey, default)


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_status(v: Any, allowed: List[str], default: str) -> str:
    s = (str(v) if v is not None else "").strip().lower()
    return s if s in allowed else default


def _norm_usd_vnd_pressure(v: Any) -> str:
    s = (str(v) if v is not None else "").strip().lower()
    if s == "up":
        return "pressure"
    allowed = {"down", "stable", "mild", "pressure", "severe", "unknown"}
    return s if s in allowed else "unknown"


def _count_geo_signals(
    conflict_level: int,
    hormuz_transit_status: str,
    events_24h: List[str],
    geo_events_tags: List[str],
) -> int:
    count = 0
    if conflict_level >= 3:
        count += 1
    if hormuz_transit_status in {"slowed", "rerouting", "partial_stop", "closed"}:
        count += 1
    events_set = set(str(x).strip().lower() for x in events_24h)
    tags = set((geo_events_tags or []) if isinstance(geo_events_tags, list) else GEO_EVENTS_TAGS)
    if events_set & tags:
        count += 1
    return count


def _count_market_signals(
    brent_change_5d_pct: Optional[float],
    tanker_rates_change_5d_pct: Optional[float],
    backwardation_1m_6m: Optional[float],
    war_risk_insurance_status: str,
    asia_diesel_crack_change_5d_pct: Optional[float],
    jkm_change_5d_pct: Optional[float],
    rules: Dict[str, Any],
) -> int:
    count = 0
    brent_med = _get_threshold(rules, "brent_change_5d_pct", "med", 5)
    tanker_med = _get_threshold(rules, "tanker_rates_change_5d_pct", "med", 20)
    bwd = _get_threshold(rules, "backwardation_1m_6m", "market_signal", 2)
    diesel = _get_threshold(rules, "asia_diesel_crack_change_5d_pct", "market_signal", 15)
    jkm = _get_threshold(rules, "jkm_change_5d_pct", "market_signal", 10)
    if (brent_change_5d_pct or 0) >= brent_med:
        count += 1
    if (tanker_rates_change_5d_pct or 0) >= tanker_med:
        count += 1
    if (backwardation_1m_6m or 0) >= bwd:
        count += 1
    if war_risk_insurance_status in {"stressed", "withdrawal"}:
        count += 1
    if (asia_diesel_crack_change_5d_pct or 0) >= diesel:
        count += 1
    if (jkm_change_5d_pct or 0) >= jkm:
        count += 1
    return count


def _count_physical_signals(
    hormuz_transit_status: str,
    qatar_lng_status: str,
    vn_lpg_supply_status: str,
    vn_lng_supply_status: str,
    domestic_refinery_status: str,
    ais_transit_drop_7d_pct: Optional[float],
    rules: Dict[str, Any],
) -> int:
    count = 0
    if hormuz_transit_status in {"partial_stop", "closed"}:
        count += 1
    if qatar_lng_status in {"force_majeure", "halted"}:
        count += 1
    if vn_lpg_supply_status in {"delayed", "force_majeure"}:
        count += 1
    if vn_lng_supply_status == "delayed":
        count += 1
    if domestic_refinery_status in {"reduced_run", "disrupted"}:
        count += 1
    thr = _get_threshold(rules, "ais_transit_drop_7d_pct", "physical_signal", -20)
    if ais_transit_drop_7d_pct is not None and ais_transit_drop_7d_pct <= thr:
        count += 1
    return count


def _classify_shock_mode(
    geo_count: int,
    market_count: int,
    physical_count: int,
    hormuz_transit_status: str,
) -> str:
    if physical_count >= 2:
        return "physical_disruption"
    if hormuz_transit_status == "closed":
        return "physical_disruption"
    if hormuz_transit_status == "partial_stop" and market_count >= 2:
        return "physical_disruption"
    if physical_count == 1:
        return "transition"
    if geo_count >= 2 and market_count >= 2:
        return "transition"
    if physical_count == 0 and market_count >= 2:
        return "risk_premium"
    return "headline"


def _classify_risk_state(
    shock_mode: str,
    brent_change_5d_pct: Optional[float],
    tanker_rates_change_5d_pct: Optional[float],
    hormuz_transit_status: str,
    rules: Dict[str, Any],
) -> str:
    brent_high = _get_threshold(rules, "brent_change_5d_pct", "high", 12)
    tanker_high = _get_threshold(rules, "tanker_rates_change_5d_pct", "high", 35)
    brent_med = _get_threshold(rules, "brent_change_5d_pct", "med", 5)
    tanker_med = _get_threshold(rules, "tanker_rates_change_5d_pct", "med", 20)
    if shock_mode == "physical_disruption":
        return "ENERGY_SHOCK_HIGH"
    if (brent_change_5d_pct or 0) >= brent_high:
        return "ENERGY_SHOCK_HIGH"
    if (tanker_rates_change_5d_pct or 0) >= tanker_high:
        return "ENERGY_SHOCK_HIGH"
    if hormuz_transit_status == "closed":
        return "ENERGY_SHOCK_HIGH"
    if shock_mode in {"risk_premium", "transition"}:
        return "ENERGY_SHOCK_MED"
    if (brent_med <= (brent_change_5d_pct or 0) < brent_high):
        return "ENERGY_SHOCK_MED"
    if (tanker_med <= (tanker_rates_change_5d_pct or 0) < tanker_high):
        return "ENERGY_SHOCK_MED"
    return "ENERGY_SHOCK_LOW"


def _classify_supply_disruption_risk_vn(
    vn_lpg_supply_status: str,
    vn_lng_supply_status: str,
    domestic_refinery_status: str,
    shock_mode: str,
) -> str:
    if vn_lpg_supply_status == "force_majeure":
        return "high"
    if domestic_refinery_status == "disrupted":
        return "high"
    if shock_mode == "physical_disruption" and (
        vn_lpg_supply_status in {"tight", "delayed"}
        or vn_lng_supply_status == "delayed"
        or domestic_refinery_status in {"reduced_run", "maintenance"}
    ):
        return "high"
    if vn_lpg_supply_status in {"tight", "delayed"}:
        return "medium"
    if vn_lng_supply_status == "delayed":
        return "medium"
    if domestic_refinery_status in {"reduced_run", "maintenance"}:
        return "medium"
    if shock_mode == "transition":
        return "medium"
    return "low"


def _classify_inflation_risk_vn(
    risk_state: str,
    shock_mode: str,
    vn_fuel_pct: Optional[float],
    usd_vnd_pressure: str,
    asia_diesel_crack_change_5d_pct: Optional[float],
    jkm_change_5d_pct: Optional[float],
    rules: Dict[str, Any],
) -> str:
    fuel_high = _get_threshold(rules, "vn_fuel_price_adjustment_pct", "high", 4)
    fuel_med = _get_threshold(rules, "vn_fuel_price_adjustment_pct", "medium", 2)
    diesel_sig = _get_threshold(rules, "asia_diesel_crack_change_5d_pct", "market_signal", 15)
    jkm_sig = _get_threshold(rules, "jkm_change_5d_pct", "market_signal", 10)
    fuel = vn_fuel_pct or 0
    if risk_state == "ENERGY_SHOCK_HIGH":
        return "high"
    if fuel >= fuel_high or usd_vnd_pressure == "severe":
        return "high"
    if shock_mode == "physical_disruption" and (asia_diesel_crack_change_5d_pct or 0) >= diesel_sig:
        return "high"
    if risk_state == "ENERGY_SHOCK_MED":
        return "medium"
    if fuel >= fuel_med or usd_vnd_pressure in {"mild", "pressure"}:
        return "medium"
    if (jkm_change_5d_pct or 0) >= jkm_sig:
        return "medium"
    return "low"


def _classify_sbv_policy_constraint(
    inflation_risk_vn: str,
    usd_vnd_pressure: str,
    sbv_liquidity_direction: str,
) -> str:
    if inflation_risk_vn == "high":
        return "high"
    if usd_vnd_pressure == "severe" and sbv_liquidity_direction in {"tightening", "absorbing", "withdrawing"}:
        return "high"
    if inflation_risk_vn == "medium":
        return "medium"
    if usd_vnd_pressure in {"mild", "pressure"}:
        return "medium"
    return "low"


def _transmission_map_fallback() -> Dict[str, List[str]]:
    return {
        "beneficiaries": ["oil_gas_upstream", "oil_gas_services"],
        "neutral_mixed": ["rubber"],
        "headwinds": ["airlines", "transport_logistics", "rate_sensitive_real_estate"],
    }


def _transmission_map_risk_premium() -> Dict[str, List[str]]:
    return {
        "beneficiaries": ["oil_gas_upstream", "oil_gas_services", "refining", "energy_shipping"],
        "neutral_mixed": ["gas_midstream", "fuel_retail", "fertilizer"],
        "headwinds": ["airlines", "transport_logistics", "gas_power", "rate_sensitive_real_estate"],
    }


def _transmission_map_physical_disruption() -> Dict[str, List[str]]:
    return {
        "beneficiaries": ["energy_shipping", "refining_if_feedstock_secure", "selected_fertilizer"],
        "neutral_mixed": ["gas_midstream", "fuel_retail", "ports"],
        "headwinds": ["lpg_distribution", "gas_power", "airlines", "transport_logistics", "rate_sensitive_real_estate"],
    }


def _transmission_map_for_shock_mode(shock_mode: str) -> Dict[str, List[str]]:
    if shock_mode == "risk_premium":
        return _transmission_map_risk_premium()
    if shock_mode == "physical_disruption":
        return _transmission_map_physical_disruption()
    return _transmission_map_fallback()


def _real_cycle_checklist_hits(
    hormuz_transit_status: str,
    war_risk_insurance_status: str,
    tanker_rates_change_5d_pct: Optional[float],
    backwardation_1m_6m: Optional[float],
    qatar_lng_status: str,
    vn_lpg_supply_status: str,
    rules: Dict[str, Any],
) -> int:
    hits = 0
    if hormuz_transit_status in {"partial_stop", "closed"}:
        hits += 1
    if war_risk_insurance_status in {"stressed", "withdrawal"}:
        hits += 1
    tanker_thr = _get_threshold(rules, "tanker_rates_change_5d_pct", "med", 20)
    if (tanker_rates_change_5d_pct or 0) >= tanker_thr:
        hits += 1
    bwd_thr = _get_threshold(rules, "backwardation_1m_6m", "market_signal", 2)
    if (backwardation_1m_6m or 0) >= bwd_thr:
        hits += 1
    if qatar_lng_status in {"delayed", "force_majeure", "halted"}:
        hits += 1
    if vn_lpg_supply_status in {"tight", "delayed", "force_majeure"}:
        hits += 1
    return hits


def _real_cycle_classification(hits: int, total: int, missing_count: int) -> str:
    if total == 0 or missing_count > 3:
        return "unknown"
    if hits <= 2:
        return "risk_premium"
    if hits == 3:
        return "transition"
    return "real_cycle"


def _next_fill_priority(inputs_normalized: Dict[str, Any]) -> List[str]:
    priority_order = [
        "war_risk_insurance_status",
        "qatar_lng_status",
        "vn_lpg_supply_status",
        "vn_lng_supply_status",
        "domestic_refinery_status",
        "brent_change_5d_pct",
        "tanker_rates_change_5d_pct",
        "backwardation_1m_6m",
        "asia_diesel_crack_change_5d_pct",
        "jkm_change_5d_pct",
        "ais_transit_drop_7d_pct",
        "hormuz_transit_status",
        "conflict_level",
    ]
    missing_or_unknown: List[str] = []
    for key in priority_order:
        v = inputs_normalized.get(key)
        if v is None:
            missing_or_unknown.append(key)
        elif isinstance(v, str) and (v.strip().lower() in ("unknown", "")):
            missing_or_unknown.append(key)
    return missing_or_unknown[:10]


def _decision_rules() -> Dict[str, List[str]]:
    return {
        "to_MED": ["conflict_level>=3", "brent_change_5d_pct>=5"],
        "to_HIGH": [
            "conflict_level>=4",
            "brent_change_5d_pct>=10",
            "hormuz_transit_status in ['partial_stop','rerouting','closed']",
        ],
    }


def load_inputs(path: Path = DEFAULT_INPUTS) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import json
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    if "inputs" in data and isinstance(data["inputs"], dict):
        out = dict(data["inputs"])
        if "asof_date" in data:
            out.setdefault("asof_date", data["asof_date"])
        return out
    return data


def score(inputs: Dict[str, Any], asof: Optional[str] = None) -> Dict[str, Any]:
    rules = _load_rules()
    checklist_items = rules.get("real_cycle_checklist") or REAL_CYCLE_CHECKLIST_ITEMS
    geo_events_tags = rules.get("geo_events_tags") or list(GEO_EVENTS_TAGS)

    # Alias: vn_fuel_price_adjustment_pct
    vn_fuel_pct = _safe_float(inputs.get("vn_fuel_price_adjustment_pct"))
    if vn_fuel_pct is None:
        vn_fuel_pct = _safe_float(inputs.get("vn_fuel_price_adjustment"))

    conflict_level = _safe_int(inputs.get("conflict_level")) or 0
    conflict_level = max(0, min(5, conflict_level))

    hormuz_transit_status = _norm_status(
        inputs.get("hormuz_transit_status"),
        allowed=["normal", "slowed", "rerouting", "partial_stop", "closed"],
        default="normal",
    )
    raw_events = inputs.get("events_24h") or []
    events_24h = [str(x) for x in raw_events] if isinstance(raw_events, list) else []

    brent_usd_bbl = _safe_float(inputs.get("brent_usd_bbl"))
    brent_change_5d_pct = _safe_float(inputs.get("brent_change_5d_pct"))
    backwardation_1m_6m = _safe_float(inputs.get("backwardation_1m_6m"))
    tanker_rates_change_5d_pct = _safe_float(inputs.get("tanker_rates_change_5d_pct"))
    asia_diesel_crack_change_5d_pct = _safe_float(inputs.get("asia_diesel_crack_change_5d_pct"))
    jkm_change_5d_pct = _safe_float(inputs.get("jkm_change_5d_pct"))
    ais_transit_drop_7d_pct = _safe_float(inputs.get("ais_transit_drop_7d_pct"))

    war_risk_insurance_status = _norm_status(
        inputs.get("war_risk_insurance_status"),
        allowed=["normal", "elevated", "stressed", "withdrawal", "unknown"],
        default="unknown",
    )
    qatar_lng_status = _norm_status(
        inputs.get("qatar_lng_status"),
        allowed=["normal", "delayed", "force_majeure", "halted", "unknown"],
        default="unknown",
    )
    vn_lpg_supply_status = _norm_status(
        inputs.get("vn_lpg_supply_status"),
        allowed=["normal", "tight", "delayed", "force_majeure", "unknown"],
        default="unknown",
    )
    vn_lng_supply_status = _norm_status(
        inputs.get("vn_lng_supply_status"),
        allowed=["normal", "tight", "delayed", "unknown"],
        default="unknown",
    )
    domestic_refinery_status = _norm_status(
        inputs.get("domestic_refinery_status"),
        allowed=["normal", "reduced_run", "maintenance", "disrupted", "unknown"],
        default="unknown",
    )

    sbv_liquidity_direction = _norm_status(
        inputs.get("sbv_liquidity_direction"),
        allowed=["easing", "neutral", "tightening", "withdrawing", "absorbing", "unknown"],
        default="unknown",
    )
    usd_vnd_pressure = _norm_usd_vnd_pressure(inputs.get("usd_vnd_pressure"))

    geo_count = _count_geo_signals(
        conflict_level, hormuz_transit_status, events_24h, geo_events_tags
    )
    market_count = _count_market_signals(
        brent_change_5d_pct,
        tanker_rates_change_5d_pct,
        backwardation_1m_6m,
        war_risk_insurance_status,
        asia_diesel_crack_change_5d_pct,
        jkm_change_5d_pct,
        rules,
    )
    physical_count = _count_physical_signals(
        hormuz_transit_status,
        qatar_lng_status,
        vn_lpg_supply_status,
        vn_lng_supply_status,
        domestic_refinery_status,
        ais_transit_drop_7d_pct,
        rules,
    )

    shock_mode = _classify_shock_mode(
        geo_count, market_count, physical_count, hormuz_transit_status
    )
    risk_state = _classify_risk_state(
        shock_mode, brent_change_5d_pct, tanker_rates_change_5d_pct, hormuz_transit_status, rules
    )
    supply_disruption_risk_vn = _classify_supply_disruption_risk_vn(
        vn_lpg_supply_status, vn_lng_supply_status, domestic_refinery_status, shock_mode
    )
    inflation_risk_vn = _classify_inflation_risk_vn(
        risk_state,
        shock_mode,
        vn_fuel_pct,
        usd_vnd_pressure,
        asia_diesel_crack_change_5d_pct,
        jkm_change_5d_pct,
        rules,
    )
    sbv_policy_constraint = _classify_sbv_policy_constraint(
        inflation_risk_vn, usd_vnd_pressure, sbv_liquidity_direction
    )

    checklist_hits = _real_cycle_checklist_hits(
        hormuz_transit_status,
        war_risk_insurance_status,
        tanker_rates_change_5d_pct,
        backwardation_1m_6m,
        qatar_lng_status,
        vn_lpg_supply_status,
        rules,
    )
    total_checklist = len(checklist_items)
    missing_inputs = [
        k for k in checklist_items
        if inputs.get(k) is None or (isinstance(inputs.get(k), str) and (inputs.get(k) or "").strip().lower() == "unknown")
    ]
    real_cycle_class = _real_cycle_classification(
        checklist_hits, total_checklist, len(missing_inputs)
    )

    inputs_normalized = dict(inputs)
    inputs_normalized["vn_fuel_price_adjustment_pct"] = vn_fuel_pct
    inputs_normalized["usd_vnd_pressure"] = usd_vnd_pressure
    next_fill = _next_fill_priority(inputs_normalized)

    transmission_map_vn = _transmission_map_for_shock_mode(shock_mode)

    notes: List[str] = [
        "Hormuz is a major global oil transit chokepoint; escalation reprices the energy risk premium.",
        "Rubber impact is mixed: synthetic rubber cost channel vs. tire-demand / China industrial cycle.",
    ]
    if brent_usd_bbl is None or brent_change_5d_pct is None:
        notes.append("Brent level or 5d change missing — treat energy shock state as conservative.")
    if vn_fuel_pct is None:
        notes.append("vn_fuel_price_adjustment_pct missing — VN inflation transmission may be understated.")

    layer_asof = asof or str(inputs.get("asof_date") or "")
    state: Dict[str, Any] = {
        "risk_state": risk_state,
        "shock_mode": shock_mode,
        "inflation_risk_vn": inflation_risk_vn,
        "supply_disruption_risk_vn": supply_disruption_risk_vn,
        "sbv_policy_constraint": sbv_policy_constraint,
        "signal_counts": {"geo": geo_count, "market": market_count, "physical": physical_count},
        "real_cycle_checklist": {
            "hits": checklist_hits,
            "total": total_checklist,
            "classification": real_cycle_class,
            "missing_inputs": missing_inputs,
        },
        "next_fill_priority": next_fill,
        "transmission_map_vn": transmission_map_vn,
        "decision_rules": _decision_rules(),
    }

    payload = {
        "layer": "geo_hormuz_energy_shock",
        "version": "v2.0",
        "asof": layer_asof,
        "inputs": {
            "conflict_level": conflict_level,
            "hormuz_transit_status": hormuz_transit_status,
            "events_24h": events_24h,
            "brent_usd_bbl": brent_usd_bbl,
            "brent_change_5d_pct": brent_change_5d_pct,
            "backwardation_1m_6m": backwardation_1m_6m,
            "tanker_rates_change_5d_pct": tanker_rates_change_5d_pct,
            "oil_volatility_proxy": inputs.get("oil_volatility_proxy"),
            "vn_fuel_price_adjustment_pct": vn_fuel_pct,
            "sbv_liquidity_direction": sbv_liquidity_direction,
            "usd_vnd_pressure": usd_vnd_pressure,
            "war_risk_insurance_status": war_risk_insurance_status,
            "qatar_lng_status": qatar_lng_status,
            "asia_diesel_crack_change_5d_pct": asia_diesel_crack_change_5d_pct,
            "jkm_change_5d_pct": jkm_change_5d_pct,
            "ais_transit_drop_7d_pct": ais_transit_drop_7d_pct,
            "vn_lpg_supply_status": vn_lpg_supply_status,
            "vn_lng_supply_status": vn_lng_supply_status,
            "domestic_refinery_status": domestic_refinery_status,
        },
        "state": state,
        "transmission_map_vn": transmission_map_vn,
        "decision_rules": _decision_rules(),
        "notes": notes,
    }
    return payload
