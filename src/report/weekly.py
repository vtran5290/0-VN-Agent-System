from __future__ import annotations
import json
from typing import Any, Dict, Optional
from pathlib import Path

from src.regime.state_machine import LiquiditySignals, detect_regime, explain_regime
from src.alloc.engine import load_thresholds, probabilities_from_features, allocation_from_regime
from src.alloc.watchlist_score import score_watchlist
from src.features.core_features import build_core_features
from src.exec.market_risk import market_risk_flags
from src.interpret.templates import render_policy_section, render_earnings_section
from src.alloc.decision_rules import top_actions, top_risks
from src.alloc.watchlist_updates import watchlist_updates
from src.alloc.watchlist_scoring import rank_watchlist
from src.exec.sell_rules import evaluate as eval_sell
from src.report.validation import validate_core
from src.alloc.overrides import apply_risk_overrides

RAW_PATH = Path("data/raw/manual_inputs.json")
NOTES_PATH = Path("data/raw/weekly_notes.json")
RAW_PREV_PATH = Path("data/raw/manual_inputs_prev.json")
WATCHLIST_PATH = Path("data/raw/watchlist.json")
WL_SCORES = Path("data/raw/watchlist_scores.json")
TECH_PATH = Path("data/raw/tech_status.json")
OUT_MD = Path("data/decision/weekly_report.md")
OUT_STATE = Path("data/state/regime_state.json")
OUT_ALLOC = Path("data/decision/allocation_plan.json")
OUT_FEATURES = Path("data/features/core_features.json")
OUT_ALERTS = Path("data/alerts/market_flags.json")
LAST_STATE = Path("data/state/last_regime_state.json")
HIST_DIR = Path("data/history")

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

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def load_weekly_notes() -> Dict[str, Any]:
    if not NOTES_PATH.exists():
        return {}
    return json.loads(NOTES_PATH.read_text(encoding="utf-8"))

def load_prev_inputs() -> Dict[str, Any]:
    if not RAW_PREV_PATH.exists():
        return {}
    return json.loads(RAW_PREV_PATH.read_text(encoding="utf-8"))

def load_tech_status() -> Dict[str, Any]:
    if not TECH_PATH.exists():
        return {}
    return json.loads(TECH_PATH.read_text(encoding="utf-8"))

def load_watchlist_scores() -> Dict[str, Any]:
    if not WL_SCORES.exists():
        return {}
    return json.loads(WL_SCORES.read_text(encoding="utf-8"))

def load_watchlist() -> list:
    """Load tickers from data/raw/watchlist.json; return [] if missing."""
    if not WATCHLIST_PATH.exists():
        return []
    data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    return data.get("tickers", [])

def load_last_state() -> Dict[str, Any]:
    if not LAST_STATE.exists():
        return {"asof_date": None, "regime": None}
    return json.loads(LAST_STATE.read_text(encoding="utf-8"))

def save_last_state(payload: Dict[str, Any]) -> None:
    write_json(LAST_STATE, payload)

def generate_report(inputs: Dict[str, Any]) -> str:
    prev_inputs = load_prev_inputs()
    features = build_core_features(inputs, prev_inputs) if prev_inputs else {"note": "Prev inputs missing"}
    write_json(OUT_FEATURES, features)

    thresholds = load_thresholds()
    signals = infer_liquidity_signals(inputs)
    regime = detect_regime(signals)
    last = load_last_state()
    last_regime = last.get("regime")
    shift = None
    if last_regime != regime and last_regime is not None and regime is not None:
        shift = f"{last_regime} → {regime}"

    probs = probabilities_from_features(regime, features if isinstance(features, dict) else {})
    alloc = allocation_from_regime(regime, thresholds)
    mkt_flags = market_risk_flags(inputs.get("market", {}))
    alloc2 = apply_risk_overrides(alloc if isinstance(alloc, dict) else {}, mkt_flags)
    tickers = load_watchlist()
    watchlist_scores = score_watchlist(tickers, regime)
    wl_payload = load_watchlist_scores()
    wl_ranked = rank_watchlist(wl_payload) if wl_payload else []

    # Persist state + allocation
    state_payload = {
        "asof_date": inputs.get("asof_date"),
        "global_liquidity": signals.global_liquidity,
        "vn_liquidity": signals.vn_liquidity,
        "regime": regime,
        "regime_shift": shift
    }
    write_json(OUT_STATE, state_payload)
    save_last_state({"asof_date": inputs.get("asof_date"), "regime": regime})
    write_json(OUT_ALLOC, {
        "asof_date": inputs.get("asof_date"),
        "regime": regime,
        "probabilities": {
            "fed_cut_3m": probs.fed_cut_3m,
            "vn_tightening_1m": probs.vn_tightening_1m,
            "vnindex_breakout_1m": probs.vnindex_breakout_1m
        },
        "allocation": alloc2
    })
    write_json(OUT_ALERTS, mkt_flags)
    tech = load_tech_status()
    sell_eval = eval_sell(tech) if tech else []
    write_json(Path("data/alerts/sell_signals.json"), {"asof_date": inputs.get("asof_date"), "signals": sell_eval})
    notes = load_weekly_notes()

    # Report (facts-first; currently Unknown where data missing)
    lines = []
    lines.append(f"# Weekly Macro/Policy/Decision Packet — {inputs.get('asof_date')}")
    lines.append("")
    v = validate_core(inputs)
    lines.insert(2, f"**Data confidence:** {v['confidence']} | missing: {', '.join(v['missing']) if v['missing'] else 'None'}")
    lines.append("## Global Macro + Fed")
    g = inputs.get("global", {})
    v = inputs.get("vietnam", {})
    fg = features.get("global", {})
    lines.append("- FACTS (levels):")
    lines.append(f"  - UST 2Y: {g.get('ust_2y')}")
    lines.append(f"  - UST 10Y: {g.get('ust_10y')}")
    lines.append(f"  - DXY: {g.get('dxy')}")
    lines.append(f"  - CPI YoY: {g.get('cpi_yoy')}")
    lines.append(f"  - NFP: {g.get('nfp')}")
    lines.append("- WHAT CHANGED (WoW):")
    lines.append(f"  - UST 2Y Δ: {fg.get('ust_2y_chg_wow')}")
    lines.append(f"  - UST 10Y Δ: {fg.get('ust_10y_chg_wow')}")
    lines.append(f"  - DXY Δ: {fg.get('dxy_chg_wow')}")
    lines.append("- INTERPRETATION: TBD when data is filled.")

    lines.append("")
    lines.append("## Vietnam Policy + Liquidity")
    fv = features.get("vietnam", {})
    lines.append("- FACTS (levels):")
    lines.append(f"  - OMO net: {v.get('omo_net')}")
    lines.append(f"  - Interbank ON: {v.get('interbank_on')}")
    lines.append(f"  - Credit growth YoY: {v.get('credit_growth_yoy')}")
    lines.append(f"  - USD/VND: {v.get('fx_usd_vnd')}")
    lines.append("- WHAT CHANGED (WoW):")
    lines.append(f"  - OMO net Δ: {fv.get('omo_net_chg_wow')}")
    lines.append(f"  - Interbank ON Δ: {fv.get('interbank_on_chg_wow')}")
    lines.append(f"  - Credit growth YoY Δ: {fv.get('credit_growth_yoy_chg_wow')}")
    lines.append("- TRANSMISSION (template): rates → credit → FX → sentiment (fill next).")

    lines.append("")
    lines.extend(render_policy_section(notes))
    lines.append("")
    lines.extend(render_earnings_section(notes))

    lines.append("")
    fm = features.get("market", {})
    lines.append("- MARKET (levels): vnindex_level, distribution_days_rolling_20 — see raw inputs.")
    lines.append("- WHAT CHANGED (WoW):")
    lines.append(f"  - VNIndex Δ: {fm.get('vnindex_chg_wow')}, Dist days Δ: {fm.get('dist_days_chg_wow')}")
    lines.append("")
    lines.append("## Regime Engine")
    lines.append(f"- {explain_regime(regime)}")
    lines.append(f"- Regime shift: {shift}")
    lines.append(f"- Inputs: global_liquidity={signals.global_liquidity}, vn_liquidity={signals.vn_liquidity}")

    lines.append("")
    lines.append("## Probability + Allocation")
    lines.append(f"- P(Fed cut within 3m): {probs.fed_cut_3m}")
    lines.append(f"- P(VN tightening within 1m): {probs.vn_tightening_1m}")
    lines.append(f"- P(VNIndex breakout within 1m): {probs.vnindex_breakout_1m}")
    lines.append(f"- Allocation: {alloc2}")

    actions = top_actions(regime, mkt_flags, alloc2 if isinstance(alloc2, dict) else {})
    risks = top_risks(regime, mkt_flags)

    lines.append("")
    lines.append("## Decision Layer")
    lines.append("- Top 3 actions:")
    for i, a in enumerate(actions, 1):
        lines.append(f"  {i}) {a}")
    lines.append("- Top 3 risks:")
    for i, r in enumerate(risks, 1):
        lines.append(f"  {i}) {r}")
    wu = watchlist_updates(tickers, regime, mkt_flags)
    lines.append("- Watchlist updates (regime-fit + risk posture):")
    lines.append(f"  - Posture: {wu.get('posture', 'Neutral')}")
    lines.append(f"  - Tickers: {', '.join(wu.get('tickers', []))}")
    lines.append(f"  - {wu.get('notes', '')}")
    for row in watchlist_scores:
        lines.append(f"  - {row['ticker']}: regime_fit={row['regime_fit']}, total_score={row['total_score']}")

    lines.append("")
    lines.append("## Watchlist Updates")
    if not wl_ranked:
        lines.append("- No watchlist scores provided yet.")
    else:
        lines.append("- Top candidates (by total score):")
        for row in wl_ranked[:5]:
            lines.append(f"  - {row['ticker']}: total={row.get('total')} (F={row.get('fundamental')}, T={row.get('technical')}, R={row.get('regime_fit')}) | {row.get('notes')}")

    lines.append("")
    lines.append("## Execution & Monitoring")
    lines.append(f"- Market risk flag (dist days): {mkt_flags}")

    lines.append("")
    lines.append("## Execution — Sell/Trim Signals (MVP)")
    if not sell_eval:
        lines.append("- No tech_status provided yet.")
    else:
        for s in sell_eval:
            lines.append(f"- {s['ticker']}: {s['action']} | {s['reason']} (tier={s.get('tier')})")

    lines.append("")
    lines.append("## Signals to monitor next week")
    lines.append("- Update: UST 2Y/10Y, DXY, CPI/NFP surprises")
    lines.append("- VN: OMO net, interbank ON, credit growth trend, USD/VND")
    lines.append("- Market: distribution days rolling-20, breadth, failed breakouts")

    lines.append("")
    lines.append("## If X happens → do Y")
    lines.append("- If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.")
    lines.append("- If distribution days cluster + failed breakout → cut laggards, only hold leaders.")
    lines.append("- If policy tailwind + earnings confirm for a sector → overweight with risk limits.")

    return "\n".join(lines)

def main() -> None:
    inputs = load_manual_inputs()
    report = generate_report(inputs)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(report, encoding="utf-8")
    print(f"Wrote: {OUT_MD}")
    print(f"Wrote: {OUT_STATE}")
    print(f"Wrote: {OUT_ALLOC}")
    print(f"Wrote: {OUT_FEATURES}")
    print(f"Wrote: {OUT_ALERTS}")
    print(f"Wrote: {LAST_STATE}")

    asof = inputs.get("asof_date", "unknown_date")
    d = HIST_DIR / asof
    d.mkdir(parents=True, exist_ok=True)
    for p in [OUT_MD, OUT_STATE, OUT_ALLOC, Path("data/features/core_features.json"), Path("data/alerts/market_flags.json"), Path("data/alerts/sell_signals.json")]:
        if p.exists():
            (d / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Archived to: {d}")

if __name__ == "__main__":
    main()
