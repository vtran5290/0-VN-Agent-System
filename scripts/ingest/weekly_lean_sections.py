"""
Lean weekly report sections: market pulse, smart KPIs, portfolio summary,
scan-aligned execution, compact data quality, narratives, visualizations.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from scripts.ingest.scan_ssot import (
    load_scan_lookup_all,
    load_scan_rows,
    map_operator_action,
    portfolio_scan_gap_kind,
    portfolio_scan_gap_reason,
    scan_by_symbol,
    watchlist_bucket,
    watchlist_trigger_label,
)
from scripts.reporting import report_format as rf
from scripts.reporting.metric_registry import build_metric_registry

REPO = Path(__file__).resolve().parents[2]
MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"
MANUAL_INPUTS_PREV = REPO / "data" / "raw" / "manual_inputs_prev.json"
CURRENT_POSITIONS_PATH = REPO / "data" / "raw" / "current_positions_derived.json"
TECH_STATUS_PATH = REPO / "data" / "raw" / "tech_status.json"

FORCED_EXIT_ACTIONS = frozenset({"TRAIL_EXIT", "MAX_HOLD_EXIT", "STOP_BREACH"})
FORCED_TRIM_ACTIONS = frozenset({"TP1_PARTIAL"})
ACTION_PRIORITY = {
    "STOP_BREACH": 0,
    "TRAIL_EXIT": 1,
    "MAX_HOLD_EXIT": 2,
    "TP1_PARTIAL": 3,
}


def execution_not_ready_message(scan_missing: int, n_positions: int) -> Optional[str]:
    """When no holdings have a production scan match, execution table is not decision-ready."""
    if n_positions > 0 and scan_missing == n_positions:
        return (
            f"Position execution not decision-ready: {scan_missing}/{n_positions} "
            "holdings have no production scan match."
        )
    return None


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _load_positions_by_ticker() -> Dict[str, Dict[str, Any]]:
    if not CURRENT_POSITIONS_PATH.exists():
        return {}
    try:
        raw = json.loads(CURRENT_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(raw, list):
        return {(p.get("ticker") or "").upper(): p for p in raw if isinstance(p, dict) and p.get("ticker")}
    return {}


def _strategy_book_for_holding(ticker: str, scan: Dict[str, str], pos: Dict[str, Any]) -> str:
    if pos.get("strategy_book"):
        return str(pos["strategy_book"])
    if pos.get("discretionary") or pos.get("manual_hold"):
        return "DISCRETIONARY"
    if scan:
        return (scan.get("strategy_tag") or "B_cloud20_100").strip() or "B_cloud20_100"
    return "UNKNOWN"


def _scan_panel_summary(scan_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    if not scan_rows:
        return {}
    r0 = scan_rows[0]
    forced = sum(
        1 for r in scan_rows if (r.get("final_action") or "").upper() in FORCED_EXIT_ACTIONS
    )
    new_t1 = sum(1 for r in scan_rows if "NEW_T1" in (r.get("final_action") or "").upper())
    try:
        pct = float(r0.get("pct_cloud_bull_a3") or r0.get("pct_cloud_bull_a3_universe") or 0)
    except (TypeError, ValueError):
        pct = None
    return {
        "pct_cloud_bull_a3": pct,
        "breadth_zone": r0.get("breadth_zone"),
        "regime_bull": r0.get("regime_bull"),
        "a3_forced_exits_count": forced,
        "a3_new_t1_count": new_t1,
        "scan_asof": r0.get("as_of_date"),
    }


def _macro_sanity_warnings(manual: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    v = manual.get("vietnam") or {}
    g = manual.get("global") or {}
    gp = (_read_json(MANUAL_INPUTS_PREV).get("global") or {})
    _, cg_warn = rf.fmt_credit_growth(v.get("credit_growth_yoy"))
    if cg_warn:
        warnings.append(cg_warn)
    try:
        dxy = float(g.get("dxy") or g.get("dxy_reconstructed") or 0)
        dxy_p = float(gp.get("dxy") or gp.get("dxy_reconstructed") or 0)
        if gp and abs(dxy - dxy_p) > 5:
            warnings.append(f"DXY WoW delta {dxy - dxy_p:+.2f} looks suspicious — check stale prev or scale")
    except (TypeError, ValueError):
        pass
    if v.get("omo_net") is not None and "omo_unit" not in v:
        warnings.append("OMO net unit not confirmed in manual_inputs — displayed as VND bn (assumed)")
    return warnings


def build_market_pulse(payload: Dict[str, Any]) -> Dict[str, Any]:
    manual = _read_json(MANUAL_INPUTS)
    prev = _read_json(MANUAL_INPUTS_PREV)
    prev_mkt = prev.get("market") or {}
    levels = dict(manual.get("market") or {})
    ms_levels = (payload.get("market_structure") or {}).get("levels") or {}
    for k, v in ms_levels.items():
        if v is not None:
            levels[k] = v
    g = manual.get("global") or {}
    gp = prev.get("global") or {}
    v = manual.get("vietnam") or {}
    vp = prev.get("vietnam") or {}
    scan_rows, scan_path, _ = load_scan_rows()
    panel = _scan_panel_summary(scan_rows)
    sanity = _macro_sanity_warnings(manual)

    def pulse_row(
        metric: str,
        current: Any,
        last: Any,
        signal: str,
        implication: str,
        metric_id: str,
    ) -> Dict[str, Any]:
        delta = None
        if current is not None and last is not None and not rf.is_missing(last):
            try:
                delta = float(current) - float(last)
            except (TypeError, ValueError):
                delta = None
        cur_fmt = _format_metric_value(metric_id, current)
        d_fmt = rf.fmt_delta_display(delta, metric_id) if delta is not None else "Missing"
        sig = signal
        if metric_id == "DXY" and delta is not None and abs(delta) > 5:
            sig = "Suspicious Δ — verify source"
        if metric_id == "CREDIT_GROWTH" and current is not None:
            _, w = rf.fmt_credit_growth(current)
            if w:
                sig = "Check scale"
        return {
            "metric": metric,
            "current": cur_fmt,
            "delta_1w": d_fmt,
            "direction": rf.direction_arrow(delta),
            "signal": sig,
            "portfolio_implication": implication,
            "metric_id": metric_id,
        }

    rows = [
        pulse_row(
            "VNINDEX",
            levels.get("vnindex_level"),
            prev_mkt.get("vnindex_level"),
            "Market level",
            "Index trend / breakout context",
            "VNINDEX",
        ),
        pulse_row("VN30", levels.get("vn30_level"), prev_mkt.get("vn30_level"), "Large-cap", "Leader vs broad market", "VN30"),
        pulse_row(
            "Dist days (20)",
            levels.get("distribution_days_rolling_20"),
            prev_mkt.get("distribution_days_rolling_20"),
            "Distribution",
            "Trim weak names if rising",
            "DIST_DAYS_20",
        ),
        pulse_row(
            "Breadth (VN30>MA20)",
            levels.get("vn30_trend_ok"),
            None,
            "Breadth",
            "Allow only leaders if weak",
            "BREADTH",
        ),
        pulse_row("UST 10Y", g.get("ust_10y"), gp.get("ust_10y"), "Global rates", "Valuation pressure on EM", "UST10Y"),
        pulse_row(
            "DXY",
            g.get("dxy_reconstructed") or g.get("dxy"),
            gp.get("dxy_reconstructed") or gp.get("dxy"),
            "USD",
            "FX / foreign flow sensitivity",
            "DXY",
        ),
        pulse_row("Interbank ON", v.get("interbank_on"), vp.get("interbank_on"), "VN rates", "Funding cost", "INTERBANK_ON"),
        pulse_row(
            "USD/VND (SBV ref)",
            v.get("sbv_reference_usd_vnd") or v.get("fx_usd_vnd"),
            vp.get("sbv_reference_usd_vnd"),
            "FX",
            "FX relief or pressure on adds",
            "USD_VND",
        ),
        pulse_row("OMO net, VND bn", v.get("omo_net"), vp.get("omo_net"), "Liquidity", "Daily SBV impulse (noisy alone)", "OMO_NET"),
        pulse_row(
            "Credit growth YoY",
            v.get("credit_growth_yoy"),
            vp.get("credit_growth_yoy"),
            "Credit",
            "Risk appetite / bank lending",
            "CREDIT_GROWTH",
        ),
    ]
    if panel.get("pct_cloud_bull_a3") is not None:
        rows.append(
            pulse_row(
                "% A3 cloud bull",
                panel.get("pct_cloud_bull_a3"),
                None,
                panel.get("breadth_zone") or "Cloud breadth",
                "B_cloud20_100 offensive threshold context",
                "PCT_CLOUD_BULL_A3",
            )
        )

    warning = None
    if not prev:
        warning = "manual_inputs_prev.json missing — WoW deltas incomplete for macro/liquidity."
    if sanity:
        warning = (warning + " " if warning else "") + "; ".join(sanity[:2])
    return {
        "title": "What Changed / Market Pulse",
        "rows": rows[:12],
        "warning": warning,
        "macro_sanity_warnings": sanity,
        "scan_source": str(scan_path.relative_to(REPO)) if scan_path else None,
        "scan_asof": panel.get("scan_asof"),
    }


def _format_metric_value(metric_id: str, v: Any) -> str:
    if rf.is_missing(v):
        return "Missing"
    if metric_id in ("VNINDEX", "VN30"):
        return rf.fmt_index(v)
    if metric_id in ("UST10Y", "UST2Y", "INTERBANK_ON"):
        return rf.fmt_rate(v)
    if metric_id in ("DXY", "USD_VND"):
        return rf.fmt_index(v)
    if metric_id == "OMO_NET":
        return rf.fmt_omo_bn(v)
    if metric_id == "PCT_CLOUD_BULL_A3":
        x = float(v)
        return rf.fmt_pct(x * 100 if x <= 1 else x, 1)
    if metric_id == "CREDIT_GROWTH":
        disp, _ = rf.fmt_credit_growth(v)
        return disp
    if metric_id == "DIST_DAYS_20":
        return str(v)
    if metric_id == "BREADTH":
        return str(v)
    return str(v)


def build_smart_kpi_board(payload: Dict[str, Any]) -> Dict[str, Any]:
    manual = _read_json(MANUAL_INPUTS)
    g = manual.get("global") or {}
    v = manual.get("vietnam") or {}
    probs = (payload.get("probability_allocation") or {}).get("probabilities") or {}
    scan_rows, _, _ = load_scan_rows()
    panel = _scan_panel_summary(scan_rows)
    cg_disp, cg_warn = rf.fmt_credit_growth(v.get("credit_growth_yoy"))
    cg_meta = "YoY · check scale" if cg_warn else "YoY"

    global_drivers = [
        {"label": "UST 10Y", "value": rf.fmt_rate(g.get("ust_10y")), "meta": g.get("ust_10y_value_date", "—")},
        {"label": "UST 2Y", "value": rf.fmt_rate(g.get("ust_2y")), "meta": g.get("ust_2y_value_date", "—")},
        {"label": "DXY", "value": rf.fmt_index(g.get("dxy_reconstructed") or g.get("dxy")), "meta": "recon/proxy"},
        {"label": "Fed cut 3m", "value": rf.fmt_prob(probs.get("fed_cut_3m"), 0), "meta": "model"},
    ]
    vn_liquidity = [
        {"label": "Interbank ON", "value": rf.fmt_rate(v.get("interbank_on")), "meta": "SBV · %"},
        {"label": "OMO net, VND bn", "value": rf.fmt_omo_bn(v.get("omo_net")), "meta": "daily"},
        {"label": "USD/VND ref", "value": rf.fmt_index(v.get("sbv_reference_usd_vnd") or v.get("fx_usd_vnd")), "meta": "SBV"},
        {"label": "Credit growth YoY", "value": cg_disp, "meta": cg_meta},
        {"label": "Liquidity signal", "value": _vn_liquidity_signal_label(v), "meta": "derived"},
    ]
    levels = (payload.get("market_structure") or {}).get("levels") or {}
    dist = levels.get("distribution_days_rolling_20")
    market_internals = [
        {"label": "Dist days (20)", "value": str(dist) if dist is not None else "Missing", "meta": "VN30 proxy"},
        {"label": "VN30 > MA20", "value": str(levels.get("vn30_trend_ok", "Missing")), "meta": "breadth"},
        {"label": "% cloud bull A3", "value": rf.fmt_pct(panel.get("pct_cloud_bull_a3"), 1) if panel.get("pct_cloud_bull_a3") is not None else "Missing", "meta": "scan"},
        {"label": "A3 universe forced exits", "value": str(panel.get("a3_forced_exits_count", "Missing")), "meta": "scan universe"},
        {"label": "A3 new T1 signals", "value": str(panel.get("a3_new_t1_count", "Missing")), "meta": "scan"},
    ]
    return {
        "global_drivers": global_drivers,
        "vn_liquidity": vn_liquidity,
        "market_internals": market_internals,
        "note": "VNINDEX/VN30 levels appear only in Market Pulse. Macro raw numbers not repeated in narrative panels.",
    }


def _vn_liquidity_signal_label(v: Dict[str, Any]) -> str:
    on = v.get("interbank_on")
    omo = v.get("omo_net")
    try:
        on_f = float(on) if on is not None else None
        omo_f = float(omo) if omo is not None else None
    except (TypeError, ValueError):
        return "Mixed"
    if on_f is not None and on_f > 6.5:
        return "Tightening"
    if omo_f is not None and omo_f > 0:
        return "Easing"
    if omo_f is not None and omo_f < 0:
        return "Tightening"
    return "Neutral"


def build_vn_liquidity_narrative(payload: Dict[str, Any]) -> Dict[str, Any]:
    manual = _read_json(MANUAL_INPUTS)
    v = manual.get("vietnam") or {}
    signal = _vn_liquidity_signal_label(v)
    interp = (
        f"Liquidity signal: {signal}. "
        "Interbank ON and OMO impulse are in Smart KPI / Market Pulse — this panel is interpretation only."
    )
    impl = {
        "Easing": "Selective adds within regime band if breadth confirms.",
        "Tightening": "Reduce high-beta adds; preserve cash.",
        "Neutral": "Stay selective; leaders with valid A3 setups only.",
        "Mixed": "No clear impulse — maintain band.",
    }.get(signal, "Stay selective.")
    return {"facts": [], "interpretation": interp, "portfolio_implication": impl, "signal": signal}


def build_global_macro_narrative(payload: Dict[str, Any]) -> Dict[str, Any]:
    interp = (
        "UST curve and DXY set EM risk appetite and FX sensitivity for Vietnam. "
        "See Market Pulse for current levels and WoW deltas (not repeated here)."
    )
    impl = "Maintain regime gross band; do not chase extended high-beta without valid B_cloud20_100 setup."
    return {"facts": [], "interpretation": interp, "portfolio_implication": impl}


def build_portfolio_summary(
    payload: Dict[str, Any],
    positions_block: Dict[str, Any],
    sector_block: Dict[str, Any],
    scan_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    risk = payload.get("portfolio_risk_summary") or {}
    rows = positions_block.get("rows") or []
    scan_map = scan_by_symbol(scan_rows)
    panel = _scan_panel_summary(scan_rows)

    portfolio_forced = 0
    near_trail = 0
    for r in rows:
        fa = (r.get("scan_final_action") or "").upper()
        if fa in FORCED_EXIT_ACTIONS:
            portfolio_forced += 1
        dist = r.get("distance_to_trail_pct")
        if isinstance(dist, str) and dist != "Missing":
            try:
                pct = float(dist.replace("%", "").strip())
                if 0 <= pct <= 5:
                    near_trail += 1
            except ValueError:
                pass

    a3_held = sum(
        1
        for r in rows
        if scan_map.get(r.get("ticker", ""), {}).get("strategy_classification") == "A3_PRODUCTION"
    )
    scan_missing_n = sum(1 for r in rows if r.get("scan_missing"))
    warnings: List[str] = list(positions_block.get("scan_missing_warning") or [])
    if sector_block.get("warning"):
        warnings.append(sector_block["warning"])
    if positions_block.get("warning"):
        warnings.append(positions_block["warning"])
    if positions_block.get("mismatch_warning"):
        warnings.append(positions_block["mismatch_warning"])

    gross = risk.get("gross_exposure")
    cc = payload.get("portfolio_command_center") or {}
    if portfolio_forced or cc.get("gross_exposure_status") not in (None, "Within band"):
        verdict = "Action required" if portfolio_forced else "Watchful"
    elif warnings:
        verdict = "Watchful"
    else:
        verdict = "Healthy"

    n = len(rows)
    near_pct = round(100.0 * near_trail / n, 0) if n else None
    summary_line = (
        f"Portfolio Health: {verdict} — "
        f"gross {rf.fmt_pct(gross * 100 if gross is not None and gross <= 1 else gross, 0) if gross is not None else 'Missing'}, "
        f"{n} positions, {portfolio_forced} portfolio forced exit(s), "
        f"{panel.get('a3_forced_exits_count', 0)} A3 universe forced exit(s)."
    )
    not_ready = execution_not_ready_message(scan_missing_n, n)
    if not_ready:
        warnings.insert(0, not_ready)
        summary_line = f"Portfolio Health: {verdict} — {not_ready}"
    elif scan_missing_n:
        summary_line += f" Scan missing: {scan_missing_n}/{n}."

    return {
        "health_verdict": verdict,
        "summary_line": summary_line,
        "n_positions": n,
        "gross_exposure": gross,
        "cash": risk.get("cash"),
        "largest_position_weight_pct": rf.fmt_weight_pct(risk.get("largest_position_weight_pct")),
        "top3_positions_weight_pct": risk.get("top3_positions_weight_pct"),
        "max_sector_name": risk.get("max_sector_name"),
        "max_sector_weight_pct": risk.get("max_sector_weight_pct"),
        "a3_production_positions": a3_held,
        "forced_exit_count": portfolio_forced,
        "universe_forced_exit_count": panel.get("a3_forced_exits_count", 0),
        "near_trail_count": near_trail,
        "near_trail_pct": near_pct,
        "scan_missing_count": scan_missing_n,
        "positions_below_ma20": risk.get("positions_below_ma20"),
        "avg_r_multiple": risk.get("avg_r_multiple_open"),
        "warnings": warnings,
        "sector_rows": (sector_block.get("rows") or [])[:8],
    }


def build_compact_data_quality(
    payload: Dict[str, Any],
    scan_path: Optional[Path],
    execution: Dict[str, Any],
    sanity_warnings: List[str],
) -> Dict[str, Any]:
    asof = (payload.get("metadata") or {}).get("asof_date") or ""
    mismatches = execution.get("mismatch_count") or 0
    scan_missing = execution.get("scan_missing_count") or 0
    scan_absent = execution.get("scan_absent_count") or 0
    scan_research = execution.get("scan_research_only_count") or 0
    missing_prices = sum(
        1 for r in execution.get("rows") or [] if rf.is_missing(r.get("current_price"))
    )

    critical_issues: List[str] = []
    warnings_extra: List[str] = []
    if mismatches:
        critical_issues.append(f"{mismatches} scan/report action mismatch")
    n_positions = len(execution.get("rows") or [])
    if scan_absent:
        if n_positions and scan_absent == n_positions:
            critical_issues.append(
                f"Position execution not decision-ready: {scan_absent}/{n_positions} "
                "holdings absent from phase36 scan file."
            )
        else:
            critical_issues.append(f"{scan_absent} holding(s) absent from phase36 scan file")
    if scan_research:
        warnings_extra.append(
            f"{scan_research} holding(s) in scan as S3/research only (not A3 production book)"
        )
    if missing_prices:
        critical_issues.append(f"{missing_prices} missing current price(s)")
    if scan_path is None or not scan_path.exists():
        critical_issues.append("phase36 scan CSV missing")
    if not CURRENT_POSITIONS_PATH.exists():
        critical_issues.append("current_positions_derived.json missing")

    stale_critical = 0
    if scan_path and scan_path.exists() and asof:
        mtime = datetime.fromtimestamp(scan_path.stat().st_mtime).strftime("%Y-%m-%d")
        if mtime < asof:
            stale_critical += 1
            critical_issues.append("scan file older than report asof")

    optional_stale = 0
    if TECH_STATUS_PATH.exists() and asof:
        mtime = datetime.fromtimestamp(TECH_STATUS_PATH.stat().st_mtime).strftime("%Y-%m-%d")
        if mtime < asof:
            optional_stale += 1

    for w in sanity_warnings:
        if "suspicious" in w.lower() or "verify" in w.lower():
            critical_issues.append(w[:80])

    if critical_issues:
        status = "Critical"
    elif optional_stale or execution.get("warning") or warnings_extra:
        status = "Warning"
    else:
        status = "Good"

    strip = (
        f"Data Quality: {status} · {len(critical_issues)} critical issue(s)"
        f" · scan {scan_path.name if scan_path else 'Missing'}"
        f" · portfolio {CURRENT_POSITIONS_PATH.name if CURRENT_POSITIONS_PATH.exists() else 'Missing'}"
    )
    if scan_absent:
        strip += f" · {scan_absent} absent from scan"
    if scan_research:
        strip += f" · {scan_research} S3-only"
    full = payload.get("data_freshness") or []
    return {
        "status": status,
        "strip": strip,
        "stale_critical": stale_critical,
        "missing_critical": len([x for x in critical_issues if "missing" in x.lower()]),
        "scan_mismatches": mismatches,
        "scan_missing_holdings": scan_missing,
        "scan_absent_holdings": scan_absent,
        "scan_research_only_holdings": scan_research,
        "warnings_extra": warnings_extra,
        "critical_issues": critical_issues,
        "optional_stale_legacy": optional_stale,
        "last_scan_date": _scan_panel_summary(load_scan_rows()[0]).get("scan_asof") if scan_path else None,
        "macro_sanity": sanity_warnings,
        "full_table": full,
    }


def build_execution_scan_aligned(
    payload: Dict[str, Any],
    positions_block: Dict[str, Any],
) -> Dict[str, Any]:
    base = positions_block
    scan_rows, scan_path, _ = load_scan_rows()
    scan_map = scan_by_symbol(scan_rows)
    full_scan_map, _ = load_scan_lookup_all(scan_path)
    pos_raw = _load_positions_by_ticker()
    signals = (payload.get("execution_monitoring") or {}).get("sell_trim_signals") or []
    sig_by = {str(s.get("ticker", "")).upper(): s for s in signals if isinstance(s, dict)}

    mismatches = 0
    scan_missing_tickers: List[str] = []
    scan_absent_tickers: List[str] = []
    scan_research_only_tickers: List[str] = []
    out_rows: List[Dict[str, Any]] = []

    for row in base.get("rows") or []:
        ticker = (row.get("ticker") or "").upper()
        scan = scan_map.get(ticker, {})
        pos = pos_raw.get(ticker, {})
        scan_missing = not bool(scan)
        gap_kind = portfolio_scan_gap_kind(ticker, scan_map, full_scan_map) if scan_missing else "matched"
        gap_reason = portfolio_scan_gap_reason(ticker, scan_map, full_scan_map) if scan_missing else ""
        if scan_missing:
            scan_missing_tickers.append(ticker)
            if gap_kind == "absent":
                scan_absent_tickers.append(ticker)
            elif gap_kind == "research_only":
                scan_research_only_tickers.append(ticker)

        fa = (scan.get("final_action") or "").strip()
        fa_upper = fa.upper()
        op_action, op_note = map_operator_action(fa) if fa else ("HOLD / Review", "No production scan match")
        report_action = row.get("action") or sig_by.get(ticker, {}).get("action") or "HOLD"
        mismatch = False
        if fa and op_action and not scan_missing:
            ra = str(report_action).upper()
            oa = op_action.upper()
            if ("EXIT" in oa or "SELL" in oa) and not ("EXIT" in ra or "SELL" in ra):
                mismatch = True
            if ("TRIM" in oa) and "TRIM" not in ra and "SELL" not in ra:
                mismatch = True
            # Production scan is SSOT: stale legacy HOLD must not block forced exits in UI
            if mismatch and fa_upper in FORCED_EXIT_ACTIONS:
                report_action = op_action
                mismatch = False
        if mismatch:
            mismatches += 1

        book = _strategy_book_for_holding(ticker, scan, pos)
        if scan_missing:
            book = "UNKNOWN" if book == "B_cloud20_100" else book
            fa_display = "Missing"
            required = "HOLD / Review"
            if "S3_RESEARCH_ONLY" in gap_reason:
                required = "REVIEW — S3 only (not A3 production)"
        else:
            fa_display = fa or "Missing"
            required = op_action

        trail_raw = scan.get("trail_price") if scan else None
        if rf.is_missing(trail_raw):
            trail_raw = row.get("stop_price")
        tp1_raw = scan.get("tp1_price") if scan else None
        pb_raw = scan.get("pb_trigger_price") if scan else None

        dist_trail = "Missing"
        try:
            cur = row.get("current_price")
            trail_vnd = rf.scan_price_kVND_to_vnd(trail_raw)
            if cur is not None and trail_vnd is not None and float(cur) > 0:
                dist_trail = rf.fmt_pct(100.0 * (float(cur) - trail_vnd) / float(cur), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

        reason = scan.get("final_action_reason") if scan else gap_reason or "No production scan match"
        if rf.is_missing(reason) or reason == "No production scan match":
            reason = gap_reason or "No production scan match" if scan_missing else "Missing"

        out_rows.append({
            **row,
            "weight_pct": rf.fmt_weight_pct(row.get("weight_pct")),
            "strategy_book": book,
            "scan_final_action": fa_display,
            "scan_reason": reason,
            "scan_gap_reason": gap_reason,
            "scan_gap_kind": gap_kind,
            "scan_missing": scan_missing,
            "row_class": "row-noscan" if scan_missing else ("row-mismatch" if mismatch else ""),
            "cloud_status": rf.cloud_label(scan.get("a3_cloud_bull") if scan else None),
            "trail_price": rf.price_or_missing(rf.scan_price_kVND_to_vnd(trail_raw)),
            "tp1_price": rf.price_or_missing(rf.scan_price_kVND_to_vnd(tp1_raw)),
            "pb_trigger_price": rf.price_or_missing(rf.scan_price_kVND_to_vnd(pb_raw)),
            "stop_price": rf.price_or_missing(row.get("stop_price")),
            "distance_to_trail_pct": dist_trail,
            "r_multiple": rf.fmt_multiple(row.get("r_multiple")) if row.get("r_multiple") is not None else "Missing",
            "operator_action": op_action,
            "operator_note": op_note,
            "report_action": report_action,
            "action_mismatch": mismatch,
            "required_operator_action": required,
            "breadth_zone": scan.get("breadth_zone") if scan else "Missing",
            "a3_rank_score": rf.fmt_score(scan.get("a3_rank_score")) if scan.get("a3_rank_score") not in (None, "") else "Missing",
        })

    warning = base.get("warning")
    miss_msg = None
    if scan_missing_tickers:
        parts = [f"{len(scan_missing_tickers)}/{len(out_rows)} without A3 production scan"]
        if scan_absent_tickers:
            parts.append(f"{len(scan_absent_tickers)} absent from CSV: {', '.join(scan_absent_tickers[:8])}")
        if scan_research_only_tickers:
            parts.append(
                f"{len(scan_research_only_tickers)} S3/research only: {', '.join(scan_research_only_tickers[:8])}"
            )
        miss_msg = "Scan gap — " + "; ".join(parts)
        warning = f"{warning} {miss_msg}".strip() if warning else miss_msg
    mismatch_warning = None
    if mismatches:
        mismatch_warning = (
            f"CRITICAL: {mismatches} position(s) report action != scan final_action."
        )

    return {
        "rows": out_rows,
        "warning": warning,
        "mismatch_warning": mismatch_warning,
        "scan_missing_warning": [miss_msg] if miss_msg else [],
        "scan_missing_tickers": scan_missing_tickers,
        "scan_missing_count": len(scan_missing_tickers),
        "scan_absent_count": len(scan_absent_tickers),
        "scan_research_only_count": len(scan_research_only_tickers),
        "scan_absent_tickers": scan_absent_tickers,
        "scan_research_only_tickers": scan_research_only_tickers,
        "n_positions": len(out_rows),
        "mismatch_count": mismatches,
        "scan_source": str(scan_path.relative_to(REPO)) if scan_path else None,
        "weight_basis": base.get("weight_basis"),
    }


def _build_immediate_actions(execution_rows: List[Dict[str, Any]]) -> List[str]:
    forced: List[Tuple[int, str, Dict[str, Any]]] = []
    for r in execution_rows:
        fa = (r.get("scan_final_action") or "").upper()
        if fa in FORCED_EXIT_ACTIONS or fa in FORCED_TRIM_ACTIONS:
            pri = ACTION_PRIORITY.get(fa, 9)
            forced.append((pri, r.get("ticker", ""), r))
    forced.sort(key=lambda x: (x[0], x[1]))
    actions: List[str] = []
    for _, ticker, r in forced:
        actions.append(
            f"{ticker}: {r.get('required_operator_action')} — scan {r.get('scan_final_action')} — {r.get('scan_reason')}"
        )
    for r in execution_rows:
        if r.get("action_mismatch"):
            t = r.get("ticker", "")
            line = f"{t}: RESOLVE scan/report mismatch — scan {r.get('scan_final_action')} vs report {r.get('report_action')}"
            if line not in actions:
                actions.append(line)
    for r in execution_rows:
        if r.get("scan_missing"):
            t = r.get("ticker", "")
            gap = r.get("scan_reason") or "no production scan match (do not treat as confirmed A3 hold)"
            line = f"{t}: REVIEW — {gap}"
            if line not in actions:
                actions.append(line)
    return actions[:20]


def _patch_command_center(payload: Dict[str, Any], execution: Dict[str, Any], dq: Dict[str, Any]) -> None:
    cc = payload.get("portfolio_command_center") or {}
    rows = execution.get("rows") or []
    forced_tickers = [
        r.get("ticker")
        for r in rows
        if (r.get("scan_final_action") or "").upper() in FORCED_EXIT_ACTIONS | FORCED_TRIM_ACTIONS
    ]
    cc["has_forced_exit"] = bool(forced_tickers)
    cc["forced_exit_count"] = len([t for t in forced_tickers if t])
    if forced_tickers:
        first = next(
            r for r in rows if (r.get("scan_final_action") or "").upper() in FORCED_EXIT_ACTIONS | FORCED_TRIM_ACTIONS
        )
        n = len(forced_tickers)
        preview = ", ".join(forced_tickers[:3])
        cc["highest_priority_action"] = (
            f"{first.get('ticker')}: {first.get('required_operator_action')} — {first.get('scan_reason', '')[:60]}"
            + (f" (+{n - 1} more: {preview})" if n > 1 else "")
        ).strip()
    else:
        cc["highest_priority_action"] = "No scan-forced exit/trim on holdings"
    cc["data_quality_status"] = dq.get("status", "Unknown")
    cc["scan_missing_holdings"] = execution.get("scan_missing_count", 0)
    n_pos = len(rows)
    sm = execution.get("scan_missing_count") or 0
    not_ready = execution_not_ready_message(sm, n_pos)
    if not_ready:
        cc["execution_readiness"] = not_ready
        if sm == n_pos:
            cc["new_buy_mode"] = "Blocked — no production scan on holdings"
    payload["portfolio_command_center"] = cc


def build_watchlist_a3(payload: Dict[str, Any]) -> Dict[str, Any]:
    scan_rows, scan_path, cfg = load_scan_rows()
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "Buy Now Candidate": [],
        "Buy on Pullback": [],
        "Buy on Reclaim": [],
        "Hold / Monitor": [],
        "Blocked by Breadth": [],
        "Avoid / Remove": [],
    }
    for row in scan_rows:
        sym = (row.get("symbol") or "").upper()
        fa = row.get("final_action") or ""
        if fa.upper().startswith("SKIP_"):
            continue
        bucket = watchlist_bucket(fa, row.get("strategy_classification") or "")
        try:
            score = float(row.get("a3_rank_score")) if row.get("a3_rank_score") not in (None, "") else None
        except (TypeError, ValueError):
            score = None
        buckets.setdefault(bucket, []).append({
            "ticker": sym,
            "sector": row.get("sector_l1") or "—",
            "bucket": bucket,
            "final_action": fa,
            "_score_raw": score or 0,
            "a3_rank_score": rf.fmt_score(score) if score is not None else "Missing",
            "a3_cloud_bull": rf.cloud_label(row.get("a3_cloud_bull")),
            "breadth_zone": row.get("breadth_zone"),
            "pct_cloud_bull_a3": row.get("pct_cloud_bull_a3"),
            "trigger_price": watchlist_trigger_label(fa, row),
            "technical_setup": row.get("final_action_reason") or fa,
            "fundamental_overlay": "Missing",
            "minervini_overlay": "Missing",
            "action": fa,
        })
    for b in buckets:
        buckets[b].sort(key=lambda x: (-(x.get("_score_raw") or 0), x.get("ticker", "")))
    flat = [it for items in buckets.values() for it in items]
    buy_now = len(buckets.get("Buy Now Candidate") or [])
    note = None
    if not flat:
        note = "No A3_PRODUCTION watchlist rows. Expected phase36 scan CSV."
    elif buy_now == 0:
        note = "No Buy Now Candidates under A3_PRODUCTION / B_cloud20_100 this week."
    return {
        "buckets": buckets,
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
        "buy_now_count": buy_now,
        "candidates": flat[:40],
        "scan_source": str(scan_path.relative_to(REPO)) if scan_path else None,
        "note": note,
        "filter": cfg.get("production_classification", "A3_PRODUCTION"),
    }


def build_visualizations(payload: Dict[str, Any], positions_block: Dict[str, Any]) -> Dict[str, Any]:
    manual = _read_json(MANUAL_INPUTS)
    v = manual.get("vietnam") or {}
    probs = (payload.get("probability_allocation") or {}).get("probabilities") or {}
    scan_rows, _, _ = load_scan_rows()
    panel = _scan_panel_summary(scan_rows)
    rows = positions_block.get("rows") or []
    action_counts: Dict[str, int] = {}
    for r in rows:
        k = r.get("operator_action") or r.get("required_operator_action") or "Missing"
        action_counts[k] = action_counts.get(k, 0) + 1

    charts: List[Dict[str, Any]] = []
    if probs.get("fed_cut_3m") is not None:
        charts.append({
            "id": "fed",
            "title": "Fed cut probability",
            "data": {"fed_cut_3m": probs.get("fed_cut_3m"), "vn_tighten_1m": probs.get("vn_tightening_1m")},
            "interpretation": "Scenario probabilities for macro overlay — not entry triggers.",
            "available": True,
        })
    if v.get("omo_net") is not None:
        charts.append({
            "id": "liq-omo",
            "title": "OMO net (VND bn)",
            "data": {"omo_net": v.get("omo_net"), "unit": "VND bn"},
            "interpretation": "Daily OMO net impulse — prefer 7D/20D rolling when available in manual_inputs.",
            "available": True,
        })
    if v.get("interbank_on") is not None:
        charts.append({
            "id": "liq-ib",
            "title": "Interbank ON (%)",
            "data": {"interbank_on": v.get("interbank_on"), "unit": "%"},
            "interpretation": f"Funding cost vs liquidity signal {_vn_liquidity_signal_label(v)}.",
            "available": True,
        })
    if panel.get("pct_cloud_bull_a3") is not None:
        charts.append({
            "id": "breadth",
            "title": "A3 cloud breadth",
            "data": {"pct_cloud_bull_a3": panel.get("pct_cloud_bull_a3"), "breadth_zone": panel.get("breadth_zone")},
            "interpretation": "Cloud breadth drives B_cloud20_100 add permission; defense zone → restricted buys.",
            "available": True,
        })
    if action_counts:
        charts.append({
            "id": "actions",
            "title": "Portfolio actions (holdings)",
            "data": action_counts,
            "interpretation": (
                f"{panel.get('a3_forced_exits_count', 0)} A3 universe forced exits; "
                f"{sum(1 for r in rows if (r.get('scan_final_action') or '').upper() in FORCED_EXIT_ACTIONS)} "
                "in current portfolio — prioritize Execution table."
            ),
            "available": True,
        })
    return {"charts": charts[:6], "all_charts": charts}


def build_decision_plan(payload: Dict[str, Any], command_center: Dict[str, Any], execution: Dict[str, Any]) -> Dict[str, Any]:
    base = payload.get("decision_layer") or {}
    stance = (
        f"Maintain {command_center.get('gross_exposure_target_band', '50–60%')} gross; "
        f"execute scan-forced exits/trims; review only A3_PRODUCTION cloud-valid candidates; "
        f"no broad risk-up until breadth confirms."
    )
    conditional = [
        "If VNINDEX confirms with breadth → allow limited leader adds within band.",
        "If distribution days rise → cut laggards.",
        "If USD/VND pressure returns → reduce high-beta liquidity names.",
        "If pct_cloud_bull_a3 improves → expand watchlist review only.",
        "If A3 forced exits increase → preserve cash.",
    ]
    do_not = [
        "Do not add to laggards.",
        "Do not buy extended names without valid base/pullback.",
        "Do not increase gross above regime band.",
        "Do not override A3 final_action without written reason.",
        "Do not mix S3 research into production.",
    ]
    if execution.get("mismatch_count"):
        do_not.append("Do not ignore scan/report action mismatches — resolve before trading.")
    if execution.get("scan_missing_count"):
        do_not.append("Do not treat scan-missing holdings as confirmed A3 holds.")

    immediate = _build_immediate_actions(execution.get("rows") or [])
    if not immediate:
        immediate = ["No scan-forced exit/trim on current holdings — maintain band and monitor watchlist."]

    return {
        **base,
        "immediate_actions": immediate,
        "conditional_actions": conditional,
        "do_not_do": do_not,
        "weekly_stance": stance,
    }


def attach_lean_report(
    payload: Dict[str, Any],
    positions_block: Dict[str, Any],
    sector_block: Dict[str, Any],
) -> Dict[str, Any]:
    scan_rows, scan_path, _ = load_scan_rows()
    manual = _read_json(MANUAL_INPUTS)
    sanity = _macro_sanity_warnings(manual)

    execution = build_execution_scan_aligned(payload, positions_block)
    portfolio_summary = build_portfolio_summary(payload, execution, sector_block, scan_rows)

    command_center = payload.get("portfolio_command_center") or {}
    letter = str(command_center.get("current_regime") or "STATE B").replace("STATE ", "").strip()[:1] or "B"
    rule = next((r for r in (payload.get("regime_rules") or {}).get("rows") or [] if r.get("is_current")), {})
    command_center["regime_one_liner"] = (
        f"Regime {letter}: {rule.get('description', 'Fragile uptrend')}. "
        f"Target gross {rule.get('gross_band', '50–60%')}. "
        f"New buys {rule.get('new_buys', 'Restricted')}. "
        f"Adds {rule.get('adds', 'Only leaders / confirmed setups')}. "
        f"Trims {rule.get('trims', 'Active')}."
    )
    payload["portfolio_command_center"] = command_center

    payload["market_pulse"] = build_market_pulse(payload)
    payload["wow_since_last_week"] = payload["market_pulse"]
    payload["position_decisions"] = execution
    payload["portfolio_summary"] = portfolio_summary
    payload["watchlist_board"] = build_watchlist_a3(payload)
    payload["smart_kpi_board"] = build_smart_kpi_board(payload)
    payload["global_macro_narrative"] = build_global_macro_narrative(payload)
    payload["vn_liquidity_narrative"] = build_vn_liquidity_narrative(payload)
    payload["visualizations_smart"] = build_visualizations(payload, execution)
    payload["data_quality_compact"] = build_compact_data_quality(payload, scan_path, execution, sanity)
    _patch_command_center(payload, execution, payload["data_quality_compact"])
    payload["decision_layer"] = build_decision_plan(payload, command_center, execution)

    prev = _read_json(MANUAL_INPUTS_PREV)
    levels = (payload.get("market_structure") or {}).get("levels") or {}
    payload["metric_registry"] = build_metric_registry(
        manual=manual, manual_prev=prev, levels=levels, scan_panel=_scan_panel_summary(scan_rows)
    )

    payload["monitoring_next_week"] = (payload.get("monitoring_next_week") or [])[:8]
    payload["playbook_if_x_then_y"] = (payload.get("playbook_if_x_then_y") or [])[:5]
    payload["open_questions"] = (payload.get("open_questions") or [])[:5]

    return payload
