from __future__ import annotations
import json
from typing import Any, Dict, Optional
from pathlib import Path

from src.regime.state_machine import LiquiditySignals, detect_regime, explain_regime
from src.alloc.engine import load_thresholds, probabilities_from_features, allocation_from_regime
from src.alloc.watchlist_score import score_watchlist
from src.features.core_features import build_core_features
from src.exec.market_risk import market_risk_flags

RAW_PATH = Path("data/raw/manual_inputs.json")
RAW_PREV_PATH = Path("data/raw/manual_inputs_prev.json")
WATCHLIST_PATH = Path("data/raw/watchlist.json")
OUT_MD = Path("data/decision/weekly_report.md")
OUT_STATE = Path("data/state/regime_state.json")
OUT_ALLOC = Path("data/decision/allocation_plan.json")
OUT_FEATURES = Path("data/features/core_features.json")
OUT_ALERTS = Path("data/alerts/market_flags.json")
LAST_STATE = Path("data/state/last_regime_state.json")

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

def load_prev_inputs() -> Dict[str, Any]:
    if not RAW_PREV_PATH.exists():
        return {}
    return json.loads(RAW_PREV_PATH.read_text(encoding="utf-8"))

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
    tickers = load_watchlist()
    watchlist_scores = score_watchlist(tickers, regime)

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
        "allocation": alloc
    })

    mkt_flags = market_risk_flags(inputs.get("market", {}))
    write_json(OUT_ALERTS, mkt_flags)

    # Report (facts-first; currently Unknown where data missing)
    lines = []
    lines.append(f"# Weekly Macro/Policy/Decision Packet — {inputs.get('asof_date')}")
    lines.append("")
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
    lines.append(f"- Allocation: {alloc}")

    lines.append("")
    lines.append("## Decision Layer")
    lines.append("- Top 3 actions:")
    risk_flag = mkt_flags.get("risk_flag", "Unknown")
    if regime == "B":
        lines.append("  1) Keep exposure mid (theo allocation band B); không vượt gross/cash band.")
        lines.append("  2) Chỉ tăng tỷ trọng khi market risk flag Normal hoặc Elevated nhẹ; nếu High → giữ hoặc giảm.")
        lines.append("  3) Ưu tiên leaders + earnings clarity; tránh high-beta, rủi ro bị đập bởi global.")
    else:
        lines.append("  1) If regime unknown → keep exposure conservative; fill missing data first.")
        lines.append("  2) Prepare watchlist scoring once regime is identified.")
        lines.append("  3) Set alerts for distribution-day cluster / key MA violations.")
    lines.append("- Top 3 risks:")
    lines.append("  1) Narrative bias due to missing data")
    lines.append("  2) Liquidity shock (global or VN) without early detection")
    lines.append("  3) Earnings revisions risk in high-beta names")
    lines.append("- Watchlist updates (MVP placeholder):")
    for row in watchlist_scores:
        lines.append(f"  - {row['ticker']}: regime_fit={row['regime_fit']}, total_score={row['total_score']}")

    lines.append("")
    lines.append("## Execution & Monitoring")
    lines.append(f"- Market risk flag (dist days): {mkt_flags}")

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

if __name__ == "__main__":
    main()
