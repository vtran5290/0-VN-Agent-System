# src/macro/us_fiscal_stress.py — US Fiscal Stress Regime Pack scoring (deterministic)
"""
Engine-facing: us_fiscal_stress_score (0–100), us_fiscal_stress_regime, drivers_top3, flags.
Feeds Fed Dashboard / rotation framework. Missing inputs → neutral (50) per missing_policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PACK = REPO_ROOT / "config" / "macro_packs" / "us_fiscal_stress_pack_v1.json"
DEFAULT_INPUTS = REPO_ROOT / "data" / "raw" / "us_fiscal_stress_inputs.json"


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> str:
    if v is None:
        return "unknown"
    s = str(v).strip().lower()
    return s if s in ("yes", "no", "unknown", "up", "flat", "down") else "unknown"


def subscore_term_premium(inputs: dict, th: dict) -> tuple[float, list[str]]:
    """0–100. High term premium = high stress. Missing → 50."""
    tp = _safe_float(inputs.get("term_premium", {}).get("ust_10y_term_premium_bps"))
    if tp is None:
        return 50.0, []
    flags = []
    high = th.get("term_premium_high_bps", 120)
    elev = th.get("term_premium_elevated_bps", 80)
    if tp >= high:
        flags.append("term_premium_high")
        return 100.0, flags
    if tp >= elev:
        flags.append("term_premium_elevated")
        return 60.0, flags
    return 20.0, flags


def subscore_long_end_yields(inputs: dict, th: dict) -> tuple[float, list[str]]:
    """0–100. Elevated/high 10Y/30Y = stress. Missing → 50."""
    y = inputs.get("yields", {})
    u10 = _safe_float(y.get("ust_10y_yield_pct"))
    u30 = _safe_float(y.get("ust_30y_yield_pct"))
    flags = []
    u10_high = th.get("ust10_high_pct", 5.0)
    u10_elev = th.get("ust10_elevated_pct", 4.5)
    u30_high = th.get("ust30_high_pct", 5.5)
    u30_elev = th.get("ust30_elevated_pct", 5.0)
    s10 = 0.0
    s30 = 0.0
    if u10 is not None:
        if u10 >= u10_high:
            s10 = 100.0
            flags.append("ust10_high")
        elif u10 >= u10_elev:
            s10 = 60.0
            flags.append("ust10_elevated")
    if u30 is not None:
        if u30 >= u30_high:
            s30 = 100.0
            flags.append("ust30_high")
        elif u30 >= u30_elev:
            s30 = 60.0
            flags.append("ust30_elevated")
    if u10 is None and u30 is None:
        return 50.0, []
    combined = min(100.0, (s10 + s30) / 2.0 + (20.0 if s10 and s30 else 0.0))
    return combined, flags


def subscore_auction_demand(inputs: dict, th: dict) -> tuple[float, list[str]]:
    """0–100. Low BTC / low indirect = stress. Missing → 50."""
    a = inputs.get("auctions", {})
    btc10 = _safe_float(a.get("ust_10y_bid_to_cover"))
    btc30 = _safe_float(a.get("ust_30y_bid_to_cover"))
    ind10 = _safe_float(a.get("ust_10y_indirect_pct"))
    ind30 = _safe_float(a.get("ust_30y_indirect_pct"))
    flags = []
    b10_low = th.get("btc_10y_low", 2.30)
    b10_warn = th.get("btc_10y_warn", 2.45)
    b30_low = th.get("btc_30y_low", 2.20)
    b30_warn = th.get("btc_30y_warn", 2.35)
    i10_low = th.get("indirect_10y_low_pct", 55)
    i30_low = th.get("indirect_30y_low_pct", 55)
    s10 = 0.0
    s30 = 0.0
    if btc10 is not None:
        if btc10 < b10_low:
            s10 = 100.0
            flags.append("weak_auction_10y")
        elif btc10 < b10_warn:
            s10 = 60.0
    if btc30 is not None:
        if btc30 < b30_low:
            s30 = 100.0
            flags.append("weak_auction_30y")
        elif btc30 < b30_warn:
            s30 = 60.0
    score = max(s10, s30)
    if ind10 is not None and ind10 < i10_low:
        score = min(100.0, score + 20.0)
        flags.append("indirect_10y_low")
    if ind30 is not None and ind30 < i30_low:
        score = min(100.0, score + 20.0)
        flags.append("indirect_30y_low")
    if btc10 is None and btc30 is None:
        return 50.0, []
    if score == 0.0:
        score = 20.0
    return min(100.0, score), flags


def subscore_funding_stress(inputs: dict, th: dict) -> tuple[float, list[str]]:
    """0–100. Repo spike / wide SOFR spread / basis stress. Missing → 50."""
    f = inputs.get("funding_stress", {})
    repo = _safe_str(f.get("repo_spike_flag"))
    sofr = _safe_float(f.get("sofr_spread_bps"))
    basis_eur = _safe_float(f.get("cross_currency_basis_eur_bps"))
    basis_jpy = _safe_float(f.get("cross_currency_basis_jpy_bps"))
    flags = []
    score = 0.0
    if repo == "yes":
        score = 100.0
        flags.append("repo_spike")
    sofr_high = th.get("sofr_spread_high_bps", 25)
    sofr_warn = th.get("sofr_spread_warn_bps", 15)
    if sofr is not None:
        if sofr >= sofr_high:
            score = max(score, 100.0)
            flags.append("sofr_spread_high")
        elif sofr >= sofr_warn:
            score = max(score, 60.0)
            flags.append("sofr_spread_warn")
    be = th.get("basis_eur_stress_bps", -30)
    bj = th.get("basis_jpy_stress_bps", -50)
    if basis_eur is not None and basis_eur <= be:
        score = min(100.0, score + 20.0)
        flags.append("basis_eur_stress")
    if basis_jpy is not None and basis_jpy <= bj:
        score = min(100.0, score + 20.0)
        flags.append("basis_jpy_stress")
    if repo != "yes" and sofr is None and basis_eur is None and basis_jpy is None:
        return 50.0, []
    return min(100.0, score) if score > 0 else 50.0, flags


def subscore_fiscal_path(inputs: dict, th: dict) -> tuple[float, list[str]]:
    """0–100. Primary deficit / interest cost / debt ceiling. Missing → 50."""
    fp = inputs.get("fiscal_path", {})
    prim = _safe_float(fp.get("primary_deficit_pct_gdp"))
    interest = _safe_float(fp.get("interest_cost_pct_gdp"))
    ceiling = _safe_str(fp.get("debt_ceiling_risk_flag"))
    flags = []
    score = 0.0
    p_high = th.get("primary_deficit_high_pct_gdp", 4.0)
    p_warn = th.get("primary_deficit_warn_pct_gdp", 3.0)
    i_high = th.get("interest_cost_high_pct_gdp", 4.0)
    i_warn = th.get("interest_cost_warn_pct_gdp", 3.5)
    if prim is not None:
        if prim >= p_high:
            score += 100.0
            flags.append("primary_deficit_high")
        elif prim >= p_warn:
            score += 60.0
            flags.append("primary_deficit_warn")
    if interest is not None:
        if interest >= i_high:
            score += 40.0
            flags.append("interest_cost_high")
        elif interest >= i_warn:
            score += 20.0
            flags.append("interest_cost_warn")
    if ceiling == "yes":
        score = min(100.0, score + 20.0)
        flags.append("debt_ceiling_risk")
    if prim is None and interest is None and ceiling in ("unknown", ""):
        return 50.0, []
    return min(100.0, score) if score > 0 else 50.0, flags


def compute_regime(total: float, bands: dict) -> str:
    """NORMAL | ELEVATED | HIGH."""
    normal_max = bands.get("NORMAL_max", 35)
    elev_max = bands.get("ELEVATED_max", 65)
    if total <= normal_max:
        return "NORMAL"
    if total <= elev_max:
        return "ELEVATED"
    return "HIGH"


def _is_missing_input(component: str, inputs: dict) -> bool:
    """True if this component has no meaningful input (neutral-by-missing)."""
    if component == "term_premium":
        tp = inputs.get("term_premium", {}).get("ust_10y_term_premium_bps")
        return _safe_float(tp) is None
    if component == "long_end_yields":
        y = inputs.get("yields", {})
        return _safe_float(y.get("ust_10y_yield_pct")) is None and _safe_float(y.get("ust_30y_yield_pct")) is None
    if component == "auction_demand":
        a = inputs.get("auctions", {})
        return _safe_float(a.get("ust_10y_bid_to_cover")) is None and _safe_float(a.get("ust_30y_bid_to_cover")) is None
    if component == "funding_stress":
        f = inputs.get("funding_stress", {})
        repo = _safe_str(f.get("repo_spike_flag"))
        if repo == "yes":
            return False
        return (
            _safe_float(f.get("sofr_spread_bps")) is None
            and _safe_float(f.get("sofr_value")) is None
            and _safe_float(f.get("cross_currency_basis_eur_bps")) is None
            and _safe_float(f.get("cross_currency_basis_jpy_bps")) is None
        )
    if component == "fiscal_path":
        fp = inputs.get("fiscal_path", {})
        prim = _safe_float(fp.get("primary_deficit_pct_gdp"))
        interest = _safe_float(fp.get("interest_cost_pct_gdp"))
        ceiling = _safe_str(fp.get("debt_ceiling_risk_flag"))
        return prim is None and interest is None and ceiling != "yes"
    return True


def _missing_fields_list(inputs: dict) -> list[str]:
    """List of input field names that are missing (for reporting)."""
    out: list[str] = []
    tp = inputs.get("term_premium", {})
    if _safe_float(tp.get("ust_10y_term_premium_bps")) is None:
        out.append("term_premium.ust_10y_term_premium_bps")
    y = inputs.get("yields", {})
    if _safe_float(y.get("ust_2y_yield_pct")) is None:
        out.append("yields.ust_2y_yield_pct")
    if _safe_float(y.get("ust_10y_yield_pct")) is None:
        out.append("yields.ust_10y_yield_pct")
    if _safe_float(y.get("ust_30y_yield_pct")) is None:
        out.append("yields.ust_30y_yield_pct")
    a = inputs.get("auctions", {})
    if _safe_float(a.get("ust_10y_bid_to_cover")) is None:
        out.append("auctions.ust_10y_bid_to_cover")
    if _safe_float(a.get("ust_10y_indirect_pct")) is None:
        out.append("auctions.ust_10y_indirect_pct")
    if _safe_float(a.get("ust_30y_bid_to_cover")) is None:
        out.append("auctions.ust_30y_bid_to_cover")
    if _safe_float(a.get("ust_30y_indirect_pct")) is None:
        out.append("auctions.ust_30y_indirect_pct")
    f = inputs.get("funding_stress", {})
    if _safe_float(f.get("sofr_spread_bps")) is None and _safe_float(f.get("sofr_value")) is None:
        out.append("funding_stress.sofr_value_or_spread")
    fp = inputs.get("fiscal_path", {})
    if _safe_float(fp.get("primary_deficit_pct_gdp")) is None:
        out.append("fiscal_path.primary_deficit_pct_gdp")
    if _safe_float(fp.get("interest_cost_pct_gdp")) is None:
        out.append("fiscal_path.interest_cost_pct_gdp")
    return out


def drivers_top3_with_meta(
    subscores: dict[str, float],
    weights: dict[str, float],
    is_missing: dict[str, bool],
) -> tuple[list[str], list[dict], list[str]]:
    """
    Drivers: only include where contribution > 0 AND not missing.
    contribution = weight * abs(subscore - 50).
    Returns (drivers_top3, subscores_breakdown, missing_driver_flags).
    """
    breakdown: list[dict] = []
    missing_flags: list[str] = []
    for k in subscores:
        w = weights.get(k, 0.0)
        s = subscores[k]
        contrib = w * abs(s - 50.0)
        missing = is_missing.get(k, True)
        if missing:
            missing_flags.append(f"missing_{k}")
        breakdown.append({
            "name": k,
            "subscore": round(s, 2),
            "weight": w,
            "contribution": round(contrib, 4),
            "is_missing_input": missing,
            "neutral_reason": "missing" if missing else "measured",
        })
    # Sort by contribution desc; only include where contribution > 0 and not missing
    candidates = [
        b["name"] for b in breakdown
        if b["contribution"] > 0 and b["neutral_reason"] != "missing"
    ]
    by_contrib = {b["name"]: b["contribution"] for b in breakdown}
    candidates.sort(key=lambda x: by_contrib[x], reverse=True)
    drivers = candidates[:3]
    if not drivers:
        drivers = ["insufficient_signal"]
    return drivers, breakdown, missing_flags


def signal_quality_from_weights(weights: dict[str, float], is_missing: dict[str, bool]) -> str:
    """low if >30% of weight is neutral due to missing; else medium if >10%; else high."""
    weight_missing = sum(weights.get(k, 0.0) for k in is_missing if is_missing[k])
    if weight_missing > 0.30:
        return "low"
    if weight_missing > 0.10:
        return "medium"
    return "high"


def duration_risk_mode_and_style(
    regime: str,
    inputs: dict,
    th: dict,
) -> tuple[str, str]:
    """
    Buffett overlay: duration_risk_mode (high/medium/low), preferred_equity_style.
    Uses real_10y_proxy and term_premium when available; else inferred from regime.
    """
    tp = _safe_float(inputs.get("term_premium", {}).get("ust_10y_term_premium_bps"))
    real_10y = _safe_float(inputs.get("real_rates", {}).get("real_10y_proxy_pct"))
    tp_high = th.get("term_premium_high_bps", 120)
    tp_elev = th.get("term_premium_elevated_bps", 80)
    real_high = th.get("real_10y_high_pct", 2.5)
    real_elev = th.get("real_10y_elevated_pct", 2.0)
    stress_from_data = False
    if tp is not None and tp >= tp_elev:
        stress_from_data = True
    if real_10y is not None and real_10y >= real_elev:
        stress_from_data = True
    if regime == "HIGH":
        duration_risk_mode = "high"
        preferred_equity_style = "quality_cashflow"
    elif regime == "ELEVATED" or stress_from_data:
        duration_risk_mode = "medium"
        preferred_equity_style = "balanced"
    else:
        duration_risk_mode = "low"
        preferred_equity_style = "risk_on_growth"
    return duration_risk_mode, preferred_equity_style


def drivers_top3(subscores: dict[str, float]) -> list[str]:
    """Legacy: names of 3 components with highest subscore. Prefer drivers_top3_with_meta."""
    order = sorted(subscores.keys(), key=lambda k: subscores[k], reverse=True)
    return order[:3]


def implications(
    regime: str,
    policy_stance: str | None = None,
    signal_quality: str | None = None,
    coverage_weight: float | None = None,
    funding_stress_subscore: float | None = None,
) -> dict[str, str]:
    """Deterministic rule-of-thumb. v1.2.1: liquidity_put only when easing AND coverage_weight>=0.60 AND funding_stress_subscore<60."""
    if regime == "HIGH":
        risk_bias = "risk_off_tilt"
        if policy_stance == "tightening":
            risk_bias = "risk_off_strong"
        elif policy_stance == "easing" and (coverage_weight is not None and coverage_weight >= 0.60) and (funding_stress_subscore is not None and funding_stress_subscore < 60):
            risk_bias = "risk_off_liquidity_put"
        return {
            "usd_bias": "up_or_volatile",
            "rates_bias": "higher_term_premium_risk",
            "risk_assets_bias": risk_bias,
        }
    if regime == "ELEVATED":
        return {
            "usd_bias": "neutral_or_volatile",
            "rates_bias": "barbell_quality",
            "risk_assets_bias": "barbell_cash_quality_avoid_crowded",
        }
    return {
        "usd_bias": "neutral",
        "rates_bias": "allow_rotation",
        "risk_assets_bias": "em_beta_ok",
    }


def equity_factor_tilt_and_vn_hint(
    duration_risk_mode: str,
    policy_stance: str,
    usd_bias: str = "neutral",
) -> tuple[str, dict[str, list[str]]]:
    """Buffett v1.2.1: vn_sector_tilt_hint conditioned on usd_bias (Exporters USD revenue: overweight only when usd_bias down)."""
    if duration_risk_mode == "high":
        tilt = "quality_cashflow"
        ow = ["Bank quality", "Utilities/Power", "Consumer staples"]
        if usd_bias == "down":
            ow.append("Exporters USD revenue")
        elif usd_bias != "up_or_volatile":
            ow.append("Exporters USD revenue (selective)")
        hint = {
            "overweight": ow,
            "underweight": ["Real estate residential", "Mid/small high beta", "Brokers/Leveraged", "Rate-sensitive (conditional_on_liquidity)"],
        }
    elif duration_risk_mode == "low" and policy_stance == "easing":
        tilt = "growth_ok"
        hint = {
            "overweight": ["Tech/IT services", "Brokers", "Industrial growth"],
            "underweight": [],
        }
    else:
        tilt = "balanced"
        hint = {
            "overweight": ["Cash", "Quality"],
            "underweight": ["Crowded"],
        }
    return tilt, hint


def score(inputs: dict, pack: dict) -> dict[str, Any]:
    """
    Returns engine-facing result: score, regime, drivers_top3, flags, subscores, implications.
    inputs: dict with keys yields, term_premium, auctions, funding_stress, fiscal_path, usd (mirror pack inputs).
    pack: full pack JSON (uses scoring_config).
    """
    cfg = pack.get("scoring_config", {})
    weights = cfg.get("weights", {})
    th = cfg.get("thresholds", {})
    bands = cfg.get("regime_bands", {})

    subscores: dict[str, float] = {}
    all_flags: list[str] = []

    tp_score, tp_flags = subscore_term_premium(inputs, th)
    subscores["term_premium"] = tp_score
    all_flags.extend(tp_flags)

    le_score, le_flags = subscore_long_end_yields(inputs, th)
    subscores["long_end_yields"] = le_score
    all_flags.extend(le_flags)

    auct_score, auct_flags = subscore_auction_demand(inputs, th)
    subscores["auction_demand"] = auct_score
    all_flags.extend(auct_flags)

    fund_score, fund_flags = subscore_funding_stress(inputs, th)
    subscores["funding_stress"] = fund_score
    all_flags.extend(fund_flags)

    fisc_score, fisc_flags = subscore_fiscal_path(inputs, th)
    subscores["fiscal_path"] = fisc_score
    all_flags.extend(fisc_flags)

    total = 0.0
    for k, w in weights.items():
        if k in subscores:
            total += w * subscores[k]
    total = round(total)

    regime = compute_regime(total, bands)
    is_missing = {k: _is_missing_input(k, inputs) for k in subscores}
    drivers, subscores_breakdown, missing_driver_flags = drivers_top3_with_meta(subscores, weights, is_missing)
    all_flags.extend(missing_driver_flags)

    # v1.2.2: coverage_weight_final computed from pack weights + is_missing (avoid stale input)
    coverage_weight_final = round(sum(weights.get(k, 0.0) for k in weights if not is_missing.get(k, True)), 2)
    measured_components_count = sum(1 for k in subscores if not is_missing.get(k, True))

    policy = inputs.get("policy") or {}
    policy_stance = (policy.get("policy_stance") or "neutral").lower()
    if policy_stance not in ("tightening", "easing", "neutral"):
        policy_stance = "neutral"
    input_flags = inputs.get("flags") or []
    policy_3m_suspect = "policy_3m_window_suspect" in input_flags
    policy_stance_confidence = "low" if policy_3m_suspect else "high"
    policy_stance_effective = "neutral" if policy_3m_suspect else policy_stance

    signal_qual = signal_quality_from_weights(weights, is_missing)
    impl = implications(
        regime,
        policy_stance_effective,
        signal_qual,
        coverage_weight=coverage_weight_final,
        funding_stress_subscore=subscores.get("funding_stress"),
    )
    duration_risk_mode, preferred_equity_style = duration_risk_mode_and_style(regime, inputs, th)
    equity_factor_tilt, vn_sector_tilt_hint = equity_factor_tilt_and_vn_hint(duration_risk_mode, policy_stance_effective, impl["usd_bias"])
    missing_fields = _missing_fields_list(inputs)
    policy_delta_3m_bps = policy.get("policy_delta_3m_bps")
    policy_stance_source = policy.get("policy_stance_source")
    days_gap_actual = policy.get("days_gap_actual")

    # v1.2.2: override to NORMAL only when truly zero measured components (not just zero contribution)
    if drivers == ["insufficient_signal"] and measured_components_count == 0 and regime != "NORMAL":
        regime = "NORMAL"
        all_flags.append("monitor_only_due_to_insufficient_signal")
    flags_dedup = list(dict.fromkeys(all_flags))
    risk_flag = regime

    return {
        "us_fiscal_stress_score": int(total),
        "us_fiscal_stress_regime": regime,
        "risk_flag": risk_flag,
        "drivers_top3": drivers,
        "flags": flags_dedup,
        "subscores": subscores,
        "subscores_breakdown": subscores_breakdown,
        "missing_fields": missing_fields,
        "signal_quality": signal_qual,
        "coverage_weight_final": coverage_weight_final,
        "measured_components_count": measured_components_count,
        "duration_risk_mode": duration_risk_mode,
        "preferred_equity_style": preferred_equity_style,
        "policy_stance": policy_stance,
        "policy_stance_effective": policy_stance_effective,
        "policy_stance_confidence": policy_stance_confidence,
        "policy_delta_3m_bps": policy_delta_3m_bps,
        "policy_stance_source": policy_stance_source,
        "days_gap_actual": days_gap_actual,
        "equity_factor_tilt": equity_factor_tilt,
        "vn_sector_tilt_hint": vn_sector_tilt_hint,
        "us_fiscal_stress": {
            "score": int(total),
            "regime": regime,
            "drivers_top3": drivers,
            "flags": flags_dedup,
            "subscores_breakdown": subscores_breakdown,
            "missing_fields": missing_fields,
            "signal_quality": signal_qual,
            "coverage_weight_final": coverage_weight_final,
            "measured_components_count": measured_components_count,
            "duration_risk_mode": duration_risk_mode,
            "preferred_equity_style": preferred_equity_style,
            "policy_stance": policy_stance,
            "policy_stance_effective": policy_stance_effective,
            "policy_stance_confidence": policy_stance_confidence,
            "policy_delta_3m_bps": policy_delta_3m_bps,
            "policy_stance_source": policy_stance_source,
            "days_gap_actual": days_gap_actual,
            "equity_factor_tilt": equity_factor_tilt,
            "vn_sector_tilt_hint": vn_sector_tilt_hint,
        },
        "implications": impl,
    }


def load_pack(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_inputs(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("inputs", data)
