"""
Daily mode: refresh market signals, risk flag, allocation override, sell signals.
No full macro/policy narrative — use weekly for that.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

from src.intake.auto_inputs_fireant import build_auto_inputs
from src.intake.auto_inputs_global import build_auto_global
from src.regime.state_machine import LiquiditySignals, detect_regime
from src.alloc.engine import load_thresholds, allocation_from_regime
from src.exec.market_risk import market_risk_flags
from src.alloc.overrides import apply_risk_overrides
from src.alloc.core_gate import core_allowed
from src.alloc.bucket_allocation import split_buckets
from src.exec.sell_rules import evaluate as eval_sell

RAW_PATH = Path("data/raw/manual_inputs.json")
TECH_PATH = Path("data/raw/tech_status.json")
OUT_ALERTS = Path("data/alerts/market_flags.json")
OUT_ALLOC = Path("data/decision/allocation_plan.json")
LAST_STATE = Path("data/state/last_regime_state.json")
OUT_DAILY = Path("data/decision/daily_snapshot.md")

def load_manual_inputs() -> Dict[str, Any]:
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def infer_liquidity_signals(inputs: Dict[str, Any]) -> LiquiditySignals:
    overrides = inputs.get("overrides", {})
    gl = overrides.get("global_liquidity", "unknown")
    vl = overrides.get("vn_liquidity", "unknown")
    if gl not in ("easing", "tight", "unknown"):
        gl = "unknown"
    if vl not in ("easing", "tight", "unknown"):
        vl = "unknown"
    return LiquiditySignals(global_liquidity=gl, vn_liquidity=vl)

def load_last_state() -> Dict[str, Any]:
    if not LAST_STATE.exists():
        return {"asof_date": None, "regime": None}
    return json.loads(LAST_STATE.read_text(encoding="utf-8"))

def load_tech_status() -> Dict[str, Any]:
    if not TECH_PATH.exists():
        return {}
    return json.loads(TECH_PATH.read_text(encoding="utf-8"))

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def run_daily() -> None:
    inputs = load_manual_inputs()
    asof = inputs.get("asof_date")

    auto = build_auto_inputs(asof)
    inputs.setdefault("market", {})
    for k in ("vnindex_level", "vn30_level", "distribution_days_rolling_20", "dist_proxy_symbol", "distribution_days", "dist_risk_composite", "vn30_trend_ok"):
        if inputs["market"].get(k) is None:
            inputs["market"][k] = auto["market"].get(k)

    auto_g = build_auto_global(asof)
    inputs.setdefault("global", {})
    for k in ("ust_2y", "ust_10y", "dxy"):
        if inputs["global"].get(k) is None:
            inputs["global"][k] = auto_g.get("global", {}).get(k)

    signals = infer_liquidity_signals(inputs)
    regime = detect_regime(signals)
    thresholds = load_thresholds()
    alloc = allocation_from_regime(regime, thresholds)
    mkt_flags = market_risk_flags(inputs.get("market", {}))
    alloc2 = apply_risk_overrides(alloc if isinstance(alloc, dict) else {}, mkt_flags, regime)
    core_ok = core_allowed(regime, mkt_flags)
    bucket = split_buckets(alloc2, core_ok)

    tech = load_tech_status()
    sell_eval = eval_sell(tech) if tech else []

    write_json(OUT_ALERTS, mkt_flags)
    write_json(OUT_ALLOC, {
        "asof_date": asof,
        "regime": regime,
        "probabilities": {},
        "allocation": alloc2,
    })
    write_json(Path("data/alerts/sell_signals.json"), {"asof_date": asof, "signals": sell_eval})

    lines = [
        f"# Daily Snapshot — {asof}",
        "",
        f"- **Risk flag:** {mkt_flags.get('risk_flag')} | dist20={mkt_flags.get('distribution_days_rolling_20')} | proxy={mkt_flags.get('dist_proxy_symbol')}",
        f"- **Override:** gross={alloc2.get('gross_exposure_override')}, cash={alloc2.get('cash_weight_override')} | no_new_buys={alloc2.get('no_new_buys')}",
        f"- **Core allowed:** {core_ok} | Bucket: {bucket}",
        "",
        "## Sell/Trim signals",
    ]
    if not sell_eval:
        lines.append("- None")
    else:
        for s in sell_eval:
            lines.append(f"- {s['ticker']}: {s['action']} | {s['reason']}")
    OUT_DAILY.parent.mkdir(parents=True, exist_ok=True)
    OUT_DAILY.write_text("\n".join(lines), encoding="utf-8")

    print(f"Daily: risk_flag={mkt_flags.get('risk_flag')}, dist20={mkt_flags.get('distribution_days_rolling_20')}, proxy={mkt_flags.get('dist_proxy_symbol')}")
    print(f"Override: gross={alloc2.get('gross_exposure_override')}, cash={alloc2.get('cash_weight_override')}, no_new_buys={alloc2.get('no_new_buys')}")
    print(f"Core allowed: {core_ok}, bucket: {bucket}")
    print(f"Wrote: {OUT_ALERTS}, {OUT_ALLOC}, {OUT_DAILY}")

if __name__ == "__main__":
    run_daily()
