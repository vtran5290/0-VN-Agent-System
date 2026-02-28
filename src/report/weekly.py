from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

from src.regime.state_machine import LiquiditySignals, detect_regime, explain_regime
from src.regime.suggestion import suggest_regime_from_market
from src.alloc.engine import load_thresholds, probabilities_from_features, allocation_from_regime
from src.alloc.watchlist_score import score_watchlist
from src.features.core_features import build_core_features
from src.exec.market_risk import market_risk_flags
from src.interpret.templates import render_policy_section, render_earnings_section, render_research_intake_section, render_portfolio_health_section
from src.alloc.decision_rules import top_actions, top_risks
from src.alloc.watchlist_updates import watchlist_updates
from src.alloc.watchlist_scoring import rank_watchlist
from src.exec.sell_rules import evaluate as eval_sell
from src.report.validation import validate_core
from src.knowledge.resolver import get_backtest_edge, get_regime_break_status
from src.quality.validators import canonicalize_input_hash
from src.alloc.overrides import apply_risk_overrides
from src.alloc.core_gate import core_allowed
from src.alloc.bucket_allocation import split_buckets
from src.intake.auto_inputs_fireant import build_auto_inputs
from src.intake.auto_inputs_global import build_auto_global

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
COUNCIL_OUTPUT_PATH = Path("data/decision/council_output.json")
REPO = Path(__file__).resolve().parents[2]
DECISION_LOG_DIR = REPO / "decision_log"
DECISION_DIGEST_PATH = REPO / "data" / "decision" / "decision_digest.csv"
OUT_JSON = REPO / "data" / "decision" / "weekly_report.json"

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


def load_council_output() -> Dict[str, Any]:
    """
    Optional council snapshot written by the prompt workflow.
    If missing/invalid, weekly run must continue without failure.
    """
    if not COUNCIL_OUTPUT_PATH.exists():
        return {}
    try:
        data = json.loads(COUNCIL_OUTPUT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"status": "invalid_shape", "source": str(COUNCIL_OUTPUT_PATH)}
    except json.JSONDecodeError as e:
        return {"status": "invalid_json", "error": str(e), "source": str(COUNCIL_OUTPUT_PATH)}

def save_last_state(payload: Dict[str, Any]) -> None:
    write_json(LAST_STATE, payload)


def portfolio_health_metrics(tech_status: Dict[str, Any], sell_eval: list) -> Dict[str, Any]:
    """Build portfolio_health dict for decision audit log (same logic as render)."""
    tickers = tech_status.get("tickers") or []
    n = len(tickers)
    if not n:
        return {"n_positions": 0}
    below_ma = sum(1 for t in tickers if t.get("close_below_ma") is True)
    sell_active = sum(1 for s in sell_eval if (s.get("action") or "HOLD") != "HOLD")
    r_vals = [t.get("r_multiple") for t in tickers if t.get("r_multiple") is not None]
    avg_r: Optional[float] = None
    if r_vals:
        try:
            avg_r = round(sum(float(x) for x in r_vals) / len(r_vals), 2)
        except (TypeError, ValueError):
            pass
    sectors: Dict[str, int] = {}
    for t in tickers:
        sec = t.get("sector") or "Unknown"
        sectors[sec] = sectors.get(sec, 0) + 1
    sector_concentration = [
        {"sector": sec, "pct": round(100 * count / n, 1), "count": count}
        for sec, count in sorted(sectors.items(), key=lambda x: -x[1])
    ]
    return {
        "n_positions": n,
        "pct_below_ma20": round(100 * below_ma / n, 1),
        "pct_sell_trim_active": round(100 * sell_active / n, 1),
        "avg_r_multiple_open": avg_r,
        "sector_concentration": sector_concentration,
    }




def _append_decision_digest(
    run_date: str, asof_date: str, regime: Optional[str], risk_flag: Any, gross_cap: Any, new_buys_allowed: bool
) -> None:
    DECISION_DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not DECISION_DIGEST_PATH.exists()
    with open(DECISION_DIGEST_PATH, "a", encoding="utf-8") as f:
        if need_header:
            f.write("run_date,asof_date,regime,risk_flag,gross_cap,new_buys_allowed\n")
        f.write(f"{run_date},{asof_date},{regime or ''},{risk_flag},{gross_cap},{new_buys_allowed}\n")


def write_decision_log(
    asof_date: str,
    regime: Optional[str],
    suggested_regime: Optional[str],
    mkt_flags: Dict[str, Any],
    alloc: Dict[str, Any],
    market: Dict[str, Any],
    tech_status: Dict[str, Any],
    sell_eval: list,
    council_output: Dict[str, Any],
    inputs: Optional[Dict[str, Any]] = None,
    wl_scores: Optional[Dict[str, Any]] = None,
) -> None:
    """Write decision audit log + digest row. Optional input_hash when inputs/wl_scores provided."""
    council = council_output if isinstance(council_output, dict) else {}
    council_status = council.get("status") or ("provided" if council else "missing")
    payload = {
        "asof_date": asof_date,
        "regime": regime,
        "suggested_regime": suggested_regime,
        "risk_flag": mkt_flags.get("risk_flag"),
        "gross_cap": alloc.get("gross_exposure_override"),
        "new_buys_allowed": not alloc.get("no_new_buys", False),
        "composite_dist": market.get("dist_risk_composite"),
        "portfolio_health": portfolio_health_metrics(tech_status, sell_eval),
        "council": {
            "status": council_status,
            "source": str(COUNCIL_OUTPUT_PATH),
            "meeting_id": council.get("meeting_id"),
            "final_recommendation": council.get("final_recommendation"),
            "conflicts": council.get("conflicts", []),
            "guardrail_violations": council.get("guardrail_violations", []),
            "mechanically_executable": council.get("mechanically_executable"),
            "chair_decision": council.get("chair_decision"),
        },
    }
    if inputs is not None and wl_scores is not None:
        payload["input_hash"] = canonicalize_input_hash(inputs, tech_status, wl_scores)
    DECISION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = DECISION_LOG_DIR / f"{asof_date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    from datetime import date as _date
    run_date = _date.today().isoformat()
    _append_decision_digest(run_date, asof_date, regime, mkt_flags.get("risk_flag"), alloc.get("gross_exposure_override"), not alloc.get("no_new_buys", False))
    logger.info("Decision log: %s", path)

def generate_report(inputs: Dict[str, Any]) -> str:
    auto = build_auto_inputs(inputs.get("asof_date"))
    inputs.setdefault("market", {})
    if inputs["market"].get("vnindex_level") is None:
        inputs["market"]["vnindex_level"] = auto["market"]["vnindex_level"]
    if inputs["market"].get("distribution_days_rolling_20") is None:
        inputs["market"]["distribution_days_rolling_20"] = auto["market"].get("distribution_days_rolling_20")
    if inputs["market"].get("dist_proxy_symbol") is None:
        inputs["market"]["dist_proxy_symbol"] = auto["market"].get("dist_proxy_symbol")
    if inputs["market"].get("vn30_level") is None:
        inputs["market"]["vn30_level"] = auto["market"].get("vn30_level")
    for k in ("hnx_level", "hnx_trend_ok", "upcom_level", "upcom_trend_ok", "vn30_trend_ok", "distribution_days", "dist_risk_composite", "dist_hnx_reason", "dist_upcom_reason"):
        if inputs["market"].get(k) is None:
            inputs["market"][k] = auto["market"].get(k)

    auto_g = build_auto_global(inputs.get("asof_date"))
    inputs.setdefault("global", {})
    for k in ("ust_2y", "ust_10y", "dxy"):
        if inputs["global"].get(k) is None:
            inputs["global"][k] = auto_g.get("global", {}).get(k)
    if inputs.get("market", {}).get("vnindex_level") is None and inputs.get("market", {}).get("vn30_level") is None:
        logger.warning("Critical: vnindex_level and vn30_level missing (manual_inputs + auto fill)")
    if inputs.get("global", {}).get("ust_2y") is None or inputs.get("global", {}).get("ust_10y") is None:
        logger.warning("Critical: UST 2Y or 10Y missing (manual_inputs + FRED)")

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
    alloc2 = apply_risk_overrides(alloc if isinstance(alloc, dict) else {}, mkt_flags, regime)
    core_ok = core_allowed(regime, mkt_flags)
    bucket = split_buckets(alloc2, core_ok)
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
    council_output = load_council_output()
    asof_date = str(inputs.get("asof_date") or "")
    meeting_id = str(council_output.get("meeting_id") or "")
    if council_output and asof_date and meeting_id and not meeting_id.startswith(asof_date):
        council_output = {**council_output, "status": "stale_meeting_id"}
    council_status = council_output.get("status") or ("provided" if council_output else "missing")

    # Report (facts-first; currently Unknown where data missing)
    lines = []
    lines.append(f"# Weekly Macro/Policy/Decision Packet — {inputs.get('asof_date')}")
    lines.append("")
    validation = validate_core(inputs)
    lines.insert(2, f"**Data confidence:** {validation['confidence']} | missing: {', '.join(validation['missing']) if validation['missing'] else 'None'}")
    mkt = inputs.get("market", {})
    ml_src = "VNINDEX" if mkt.get("vnindex_level") is not None else ("VN30" if mkt.get("vn30_level") is not None else "N/A")
    lines.append(f"**Market level source:** {ml_src} | **DistDays proxy:** {mkt.get('dist_proxy_symbol') or 'N/A'}")
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
    lines.extend(render_research_intake_section(notes))
    lines.append("")
    lines.extend(render_earnings_section(notes))

    lines.append("")
    fm = features.get("market", {})
    mkt = inputs.get("market", {})
    lines.append(f"- MARKET (levels): vnindex_level={mkt.get('vnindex_level')}, vn30_level={mkt.get('vn30_level')}, distribution_days_rolling_20={mkt.get('distribution_days_rolling_20')} (proxy: {mkt.get('dist_proxy_symbol') or 'N/A'})")
    dd = mkt.get("distribution_days") or {}
    vn30_d, hnx_d, upcom_d = dd.get("vn30"), dd.get("hnx"), dd.get("upcom")
    hnx_r, upcom_r = mkt.get("dist_hnx_reason"), mkt.get("dist_upcom_reason")
    dd_parts = [f"VN30={vn30_d}", f"HNX={hnx_d}" if hnx_d is not None else f"HNX={hnx_r or 'N/A'}", f"UPCOM={upcom_d}" if upcom_d is not None else f"UPCOM={upcom_r or 'N/A'}"]
    lines.append(f"- **Distribution (LB=25, refined):** {', '.join(dd_parts)} → Composite={mkt.get('dist_risk_composite')} (leader={mkt.get('dist_proxy_symbol') or 'N/A'})")
    if mkt.get("dist_risk_composite") == "High":
        lines.append("- **Action bias:** No new buys; only manage risk/exits; raise cash into strength.")
    lines.append(f"- Breadth: VN30 trend_ok(>MA20)={mkt.get('vn30_trend_ok')} | HNX close={mkt.get('hnx_level')}, trend_ok(>MA20)={mkt.get('hnx_trend_ok')} | UPCOM close={mkt.get('upcom_level')}, trend_ok(>MA20)={mkt.get('upcom_trend_ok')}")
    if mkt.get("hnx_trend_ok") is False and mkt.get("upcom_trend_ok") is False and (mkt.get("hnx_level") is not None or mkt.get("upcom_level") is not None):
        lines.append("- **Broad market weak:** HNX and UPCOM both below MA20.")
    if mkt.get("vn30_trend_ok") is True and (mkt.get("hnx_trend_ok") is False or mkt.get("upcom_trend_ok") is False):
        lines.append("- **Index holding but breadth weak → breakout failure risk ↑**")
    lines.append("- WHAT CHANGED (WoW):")
    lines.append(f"  - VNIndex Δ: {fm.get('vnindex_chg_wow')}, Dist days Δ: {fm.get('dist_days_chg_wow')}")
    lines.append("")
    lines.append("## Regime Engine")
    lines.append(f"- {explain_regime(regime)}")
    lines.append(f"- Regime shift: {shift}")
    lines.append(f"- Inputs: global_liquidity={signals.global_liquidity}, vn_liquidity={signals.vn_liquidity}")
    suggested = suggest_regime_from_market(mkt, features.get("global") if isinstance(features, dict) else None)
    current_str = (regime if regime else "Unknown")
    suggested_str = (suggested if suggested else "Unknown")
    mismatch = (suggested is not None and regime is not None and suggested != regime)
    lines.append(f"- **Suggested Regime (advisory):** {suggested_str} (from dist composite, breadth, MA trend)")
    lines.append(f"- **Current Regime:** {current_str}")
    lines.append(f"- **Mismatch:** {'Yes' if mismatch else 'No'}")

    lines.append("")
    lines.append("## Probability + Allocation")
    lines.append(f"- P(Fed cut within 3m): {probs.fed_cut_3m}")
    lines.append(f"- P(VN tightening within 1m): {probs.vn_tightening_1m}")
    lines.append(f"- P(VNIndex breakout within 1m): {probs.vnindex_breakout_1m}")
    lines.append(f"- Allocation: {alloc2}")
    if isinstance(alloc2, dict):
        if alloc2.get("gross_exposure_override") is not None:
            lines.append(f"- Override: gross={alloc2.get('gross_exposure_override')}, cash={alloc2.get('cash_weight_override')} — {alloc2.get('override_reason', '')}")
        if alloc2.get("no_new_buys"):
            lines.append("- **no_new_buys: True** — only manage risk / exits / trims.")

    lines.append("")
    lines.append("## Portfolio Structure (Hybrid)")
    lines.append(f"- Core allowed: {core_ok}")
    lines.append(f"- Bucket allocation: {bucket}")

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

    # Backtest knowledge (resolver): tickers in Decision, max_tickers from resolver_rules
    try:
        import yaml
        _repo = Path(__file__).resolve().parent.parent.parent
        rules_path = _repo / "knowledge" / "resolver_rules.yml"
        rules = {}
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}
        max_tickers = (rules.get("injection_points", {}).get("decision", {}) or {}).get("max_tickers", 12)
    except Exception:
        max_tickers = 12
    knowledge_tickers = list(tickers)[:max_tickers]
    ctx = {
        "regime": regime,
        "regime_flag": regime,
        "mkt_flags": mkt_flags,
        "vn30_dd20": mkt.get("distribution_days_rolling_20") or (mkt_flags.get("distribution_days_rolling_20") if isinstance(mkt_flags, dict) else None),
        "stock_below_ma50": None,
    }
    records_queried = len(knowledge_tickers)
    loaded_records = 0
    stale_warnings = 0
    regime_status = get_regime_break_status()
    system_warnings = []
    if regime_status.get("expired_warning"):
        system_warnings.append(regime_status["expired_warning"])

    lines.append("")
    lines.append("### Backtest edge (knowledge)")
    for sym in knowledge_tickers:
        edge = get_backtest_edge(sym, strategy_id=None, context=ctx)
        if not edge["found"]:
            continue
        loaded_records += 1
        rec = edge.get("record", {})
        st = rec.get("stats", {})
        dr = rec.get("date_range", {})
        win_rate = st.get("win_rate")
        expectancy = st.get("avg_ret")
        sample_size = st.get("n_trades") or st.get("num_trades") or rec.get("n_trades")
        regime_filter = rec.get("regime_filter") or "—"
        wr = f"{win_rate:.0%}" if win_rate is not None else "—"
        ex = f"{expectancy:.2%}" if expectancy is not None else "—"
        n_val = sample_size if isinstance(sample_size, (int, float)) else None
        n = str(sample_size) if sample_size is not None else "—"
        low_sample = "" if (n_val is None or n_val >= 20) else " (low sample)"
        lines.append(f"- {sym}: win_rate={wr} | expectancy={ex} | n={n}{low_sample} | regime={regime_filter}")
        for w in edge.get("warnings", []):
            stale_warnings += 1
            lines.append(f"  ⚠️ {w}")
    if loaded_records == 0:
        lines.append("- No backtest records available.")
    for w in system_warnings:
        lines.append(f"- ⚠️ {w}")

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
    lines.extend(render_portfolio_health_section(tech, sell_eval))

    lines.append("")
    lines.append("## Council Process Status")
    lines.append(f"- council_output status: {council_status}")
    lines.append(f"- mechanically_executable: {council_output.get('mechanically_executable')}")
    lines.append(f"- chair_decision logged: {bool(str(council_output.get('chair_decision') or '').strip())}")
    if council_status != "provided":
        lines.append("- Next step: run council prompts and save `data/decision/council_output.json`, then re-run weekly.")

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

    # Decision audit layer: store snapshot for later behavior audit (institutional improvement)
    alloc_dict = alloc2 if isinstance(alloc2, dict) else {}
    write_decision_log(
        inputs.get("asof_date", "unknown_date"),
        regime,
        suggested,
        mkt_flags,
        alloc_dict,
        mkt,
        tech,
        sell_eval,
        council_output,
        inputs=inputs,
        wl_scores=wl_payload,
    )

    def _delta_direction(d: Optional[float]) -> str:
        if d is None:
            return "—"
        return "+" if d > 0 else ("-" if d < 0 else "0")
    def _to_bps(x: Optional[float]) -> Optional[int]:
        if x is None:
            return None
        return int(round(x * 100))
    what_changed_list: List[Dict[str, Any]] = []
    for name, val, unit in [
        ("UST2Y", fg.get("ust_2y_chg_wow"), "bps"),
        ("UST10Y", fg.get("ust_10y_chg_wow"), "bps"),
        ("DXY", fg.get("dxy_chg_wow"), "pts"),
        ("VNINDEX", fm.get("vnindex_chg_wow"), "pts"),
        ("DIST_DAYS_20", fm.get("dist_days_chg_wow"), "days"),
    ]:
        delta_bps = _to_bps(val) if unit == "bps" and val is not None else None
        delta = val if val is not None else None
        what_changed_list.append({
            "metric": name,
            "delta": delta,
            "delta_bps": delta_bps,
            "direction": _delta_direction(val),
            "source": "manual_inputs" if name in ("UST2Y", "UST10Y", "DXY") else ("computed" if name == "DIST_DAYS_20" else "manual_inputs"),
        })
    payload = {
        "asof_date": inputs.get("asof_date"),
        "data_confidence": validation.get("confidence"),
        "what_changed": what_changed_list,
        "triggers_fired": [x for x in [mkt_flags.get("risk_flag"), "no_new_buys" if (alloc2.get("no_new_buys") if isinstance(alloc2, dict) else False) else None] if x],
        "actions": actions[:3],
        "risks": risks[:3],
        "open_questions": ["WoW Vietnam liquidity", "Dist days trend", "Council execution"] if loaded_records == 0 else ["Dist days trend", "Council execution"][:3],
    }
    return "\n".join(lines), payload

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true", help="Also write weekly_report.md (readable report). Default: JSON only.")
    args = ap.parse_args()
    inputs = load_manual_inputs()
    report, payload = generate_report(inputs)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, payload)
    if getattr(args, "render", False):
        OUT_MD.write_text(report, encoding="utf-8")
    asof = inputs.get("asof_date", "unknown_date")
    d = HIST_DIR / asof
    d.mkdir(parents=True, exist_ok=True)
    to_archive = [OUT_JSON, OUT_STATE, OUT_ALLOC, Path("data/features/core_features.json"), Path("data/alerts/market_flags.json"), Path("data/alerts/sell_signals.json")]
    if OUT_MD.exists():
        to_archive.append(OUT_MD)
    for p in to_archive:
        if p.exists():
            (d / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    logger.info("Weekly: %s | %s | archive=%s", OUT_JSON, OUT_STATE, d)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
