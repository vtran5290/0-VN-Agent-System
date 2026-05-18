"""
Portfolio decision enrichments for weekly report schema v1.0.
Builds command center, regime rules, WoW table, position-level execution,
risk summary, sector mapping, watchlist board, decision review, and data freshness.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Load REPO/.env into os.environ when keys are not already set."""
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
SECTOR_MAP_PATH = REPO / "data" / "master" / "sector_map.csv"
CURRENT_POSITIONS_PATH = REPO / "data" / "raw" / "current_positions_derived.json"
MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"
MANUAL_INPUTS_PREV = REPO / "data" / "raw" / "manual_inputs_prev.json"
TECH_STATUS_PATH = REPO / "data" / "raw" / "tech_status.json"
SELL_SIGNALS_PATH = REPO / "data" / "alerts" / "sell_signals.json"
DECISION_LOG_DIR = REPO / "decision_log"
DECISION_DIGEST_PATH = REPO / "data" / "decision" / "decision_digest.csv"
WATCHLIST_CONFIG = REPO / "config" / "watchlist.txt"
MAX_SINGLE_POSITION_PCT = 12.0
MAX_SECTOR_PCT = 30.0

REGIME_RULES: List[Dict[str, Any]] = [
    {
        "regime": "A",
        "description": "Risk-on",
        "gross_band": "70–90%",
        "gross_min": 0.70,
        "gross_max": 0.90,
        "new_buys": "Allowed",
        "adds": "Allowed on valid breakouts/reclaims",
        "trims": "Only weak names",
        "stops": "Normal",
    },
    {
        "regime": "B",
        "description": "Fragile uptrend",
        "gross_band": "50–60%",
        "gross_min": 0.50,
        "gross_max": 0.60,
        "new_buys": "Restricted",
        "adds": "Only leaders / confirmed setups",
        "trims": "Active",
        "stops": "Normal to tight",
    },
    {
        "regime": "C",
        "description": "Tight+tight",
        "gross_band": "20–40%",
        "gross_min": 0.20,
        "gross_max": 0.40,
        "new_buys": "No",
        "adds": "No",
        "trims": "Aggressive",
        "stops": "Tight",
    },
    {
        "regime": "D",
        "description": "Correction",
        "gross_band": "0–25%",
        "gross_min": 0.0,
        "gross_max": 0.25,
        "new_buys": "No",
        "adds": "No",
        "trims": "Exit weak names",
        "stops": "Hard stop",
    },
    {
        "regime": "E",
        "description": "Recovery attempt",
        "gross_band": "30–50%",
        "gross_min": 0.30,
        "gross_max": 0.50,
        "new_buys": "Pilot only",
        "adds": "Small test buys only",
        "trims": "Still strict",
        "stops": "Normal",
    },
]


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _file_freshness(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"source": str(path), "last_updated": None, "status": "Missing", "method": "file"}
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return {"source": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path), "last_updated": mtime, "status": "Fresh", "method": "file"}


def _regime_letter(regime: Optional[str]) -> str:
    if not regime:
        return "?"
    s = str(regime).upper().replace("STATE ", "").strip()
    return s[:1] if s else "?"


def _gross_cash(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    alloc = (payload.get("probability_allocation") or {}).get("allocation") or {}
    gross = alloc.get("gross_exposure_override")
    if gross is None:
        gross = alloc.get("gross_exposure")
    cash = alloc.get("cash_weight_override")
    if cash is None:
        cash = alloc.get("cash_weight")
    try:
        g = float(gross) if gross is not None else None
    except (TypeError, ValueError):
        g = None
    try:
        c = float(cash) if cash is not None else None
    except (TypeError, ValueError):
        c = None
    return g, c


def _exposure_band_status(gross: Optional[float], rmin: float, rmax: float) -> str:
    if gross is None:
        return "Unknown"
    if gross < rmin:
        return "Raise exposure"
    if gross > rmax:
        return "Reduce exposure"
    return "Within band"


def build_regime_rules(current_regime: Optional[str]) -> Dict[str, Any]:
    letter = _regime_letter(current_regime)
    rows = []
    for rule in REGIME_RULES:
        row = dict(rule)
        row["is_current"] = row["regime"] == letter
        rows.append(row)
    current = next((r for r in rows if r["is_current"]), None)
    return {"current_regime": letter, "rows": rows, "current_rule": current}


def build_portfolio_command_center(payload: Dict[str, Any]) -> Dict[str, Any]:
    regime_engine = payload.get("regime_engine") or {}
    current = regime_engine.get("current_regime") or regime_engine.get("regime")
    suggested = regime_engine.get("suggested_regime")
    letter = _regime_letter(current)
    rule = next((r for r in REGIME_RULES if r["regime"] == letter), None)
    gross, cash = _gross_cash(payload)
    band = rule or REGIME_RULES[1]
    exposure_status = _exposure_band_status(gross, band["gross_min"], band["gross_max"])

    signals = payload.get("execution_monitoring") or {}
    sell_rows = signals.get("sell_trim_signals") or signals.get("position_signals") or []
    forced = [
        s for s in sell_rows
        if isinstance(s, dict) and ("SELL" in str(s.get("action", "")).upper() or "EXIT" in str(s.get("action", "")).upper())
    ]
    priority = None
    if forced:
        s0 = forced[0]
        priority = f"{s0.get('ticker')}: {s0.get('action')} — {s0.get('reason', '')}".strip(" —")

    missing: List[str] = []
    if gross is None:
        missing.append("gross_exposure")
    if cash is None:
        missing.append("cash_weight")
    if not CURRENT_POSITIONS_PATH.exists():
        missing.append("current_positions_derived.json")
    meta = payload.get("metadata") or {}
    if meta.get("data_confidence") == "Low":
        missing.append("low_data_confidence")

    mismatch = bool(regime_engine.get("mismatch"))
    conf_note = "Mismatch current vs suggested" if mismatch else "Aligned"
    if suggested and _regime_letter(suggested) != letter:
        conf_note = "Mismatch current vs suggested"

    data_quality = "Complete" if not missing else f"Data incomplete: {', '.join(missing)}"

    return {
        "current_regime": current,
        "suggested_regime": suggested,
        "regime_confidence": conf_note,
        "gross_exposure_current": gross,
        "gross_exposure_target_band": band["gross_band"],
        "gross_exposure_status": exposure_status,
        "cash_current": cash,
        "new_buy_mode": band["new_buys"],
        "add_mode": band["adds"],
        "trim_mode": band["trims"],
        "stop_mode": band["stops"],
        "cash_stance": "Preserve optionality, deploy only on confirmed setups" if letter == "B" else None,
        "highest_priority_action": priority or "No forced exit/trim signal active",
        "data_quality_status": data_quality,
        "missing_inputs": missing,
        "has_forced_exit": bool(forced),
    }


def _load_sector_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not SECTOR_MAP_PATH.exists():
        return out
    with SECTOR_MAP_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            sec = (row.get("primary_sector") or "").strip()
            if sym and sec:
                out[sym] = sec
    return out


def _latest_scan_csv() -> Optional[Path]:
    candidates = list((REPO / "data" / "research").rglob("phase36*daily_scan*.csv"))
    candidates = [p for p in candidates if "schema" not in p.name.lower()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _fetch_last_closes(symbols: List[str], asof: str) -> Dict[str, Optional[float]]:
    """Best-effort FireAnt last close; returns empty on failure."""
    _load_dotenv()
    out: Dict[str, Optional[float]] = {s: None for s in symbols}
    try:
        from src.intake.fireant_historical import fetch_historical
    except ImportError:
        return out
    end_d = datetime.strptime(asof[:10], "%Y-%m-%d")
    start = (end_d - timedelta(days=30)).strftime("%Y-%m-%d")
    for sym in symbols:
        try:
            bars = fetch_historical(sym, start, asof)
            if bars:
                last = bars[-1]
                out[sym] = float(getattr(last, "c", None) or getattr(last, "close", None))
        except Exception:
            continue
    return out


def _ma_status(close_below: Optional[bool]) -> str:
    if close_below is None:
        return "Missing"
    return "Below" if close_below else "Above"


def _technical_status(row: Dict[str, Any]) -> str:
    if row.get("day2_trigger"):
        return "Day-2 confirmation breach"
    if row.get("day1_trigger"):
        return "Below MA20"
    if row.get("close_below_ma") is True:
        return "Below MA20"
    if row.get("close_below_ma") is False:
        return "Constructive"
    return "Missing"


def build_position_decisions(payload: Dict[str, Any], fetch_prices: bool = True) -> Dict[str, Any]:
    positions = []
    if CURRENT_POSITIONS_PATH.exists():
        try:
            raw = json.loads(CURRENT_POSITIONS_PATH.read_text(encoding="utf-8"))
            positions = raw if isinstance(raw, list) else []
        except Exception:
            positions = []

    tech = _read_json(TECH_STATUS_PATH)
    tech_by = {str(t.get("ticker", "")).upper(): t for t in (tech.get("tickers") or []) if isinstance(t, dict)}

    signals = (payload.get("execution_monitoring") or {}).get("sell_trim_signals") or []
    sig_by = {str(s.get("ticker", "")).upper(): s for s in signals if isinstance(s, dict)}

    sector_map = _load_sector_map()
    asof = (payload.get("metadata") or {}).get("asof_date") or datetime.now().strftime("%Y-%m-%d")
    symbols = [str(p.get("ticker", "")).upper() for p in positions if p.get("ticker")]
    prices: Dict[str, Optional[float]] = _fetch_last_closes(symbols, asof) if fetch_prices and symbols else {s: None for s in symbols}

    cost_values: List[float] = []
    rows_out: List[Dict[str, Any]] = []
    for pos in positions:
        ticker = str(pos.get("ticker") or "").upper()
        if not ticker:
            continue
        tech_r = tech_by.get(ticker, {})
        sig_r = sig_by.get(ticker, {})
        entry = pos.get("entry_price")
        lots = pos.get("lots") or 0
        try:
            lots_f = float(lots)
        except (TypeError, ValueError):
            lots_f = 0.0
        try:
            entry_f = float(entry) if entry is not None else None
        except (TypeError, ValueError):
            entry_f = None

        sector = sector_map.get(ticker) or (pos.get("reason_tag") or "").strip() or None
        if not sector:
            sector = tech_r.get("sector")
        sector_display = sector if sector else "—"
        mapped = sector_display != "—"

        current = prices.get(ticker)
        unrealized_pct = None
        if entry_f and current and entry_f > 0:
            unrealized_pct = round(100.0 * (current - entry_f) / entry_f, 2)

        stop = pos.get("stop_price_at_entry") or tech_r.get("stop_price")
        try:
            stop_f = float(stop) if stop is not None else None
        except (TypeError, ValueError):
            stop_f = None

        initial_risk_pct = None
        if entry_f and stop_f and entry_f > 0:
            initial_risk_pct = abs(entry_f - stop_f) / entry_f * 100.0
        r_mult = tech_r.get("r_multiple")
        if r_mult is None and unrealized_pct is not None and initial_risk_pct and initial_risk_pct > 0:
            r_mult = round(unrealized_pct / initial_risk_pct, 2)

        dist_stop = None
        if current and stop_f and current > 0:
            dist_stop = round(100.0 * (current - stop_f) / current, 2)

        cost_val = (entry_f or 0) * lots_f
        if cost_val > 0:
            cost_values.append(cost_val)

        action = sig_r.get("action") or "HOLD"
        reason = sig_r.get("reason") or ""
        next_trigger = "Exit if stop breached" if "SELL" in str(action).upper() or "EXIT" in str(action).upper() else (
            "Trim if closes below MA20" if tech_r.get("close_below_ma") else "Hold while structure intact"
        )

        rows_out.append({
            "ticker": ticker,
            "sector": sector_display,
            "sector_mapped": mapped,
            "weight_pct": None,
            "cost_price": entry_f,
            "current_price": current,
            "unrealized_pl_pct": unrealized_pct,
            "r_multiple": r_mult,
            "stop_price": stop_f,
            "distance_to_stop_pct": dist_stop,
            "ma20_status": _ma_status(tech_r.get("close_below_ma")),
            "ma50_status": "Missing",
            "technical_status": _technical_status({**tech_r, **sig_r}),
            "fundamental_status": "Missing",
            "action": action,
            "reason": reason,
            "next_trigger": next_trigger,
        })

    total_cost = sum(cost_values) if cost_values else None
    if total_cost and total_cost > 0:
        for row in rows_out:
            ep = row.get("cost_price")
            lots_i = next((float(p.get("lots") or 0) for p in positions if str(p.get("ticker", "")).upper() == row["ticker"]), 0)
            if ep:
                row["weight_pct"] = round(100.0 * float(ep) * lots_i / total_cost, 2)

    has_prices = any(r.get("current_price") is not None for r in rows_out)
    has_stops = any(r.get("stop_price") is not None for r in rows_out)
    warning = None
    if rows_out and (not has_prices or not has_stops):
        warning = (
            "Position-level risk metrics partially unavailable: "
            + ("current price missing (FireAnt fetch failed or token unset). " if not has_prices else "")
            + ("stop price missing in positions/tech_status. " if not has_stops else "")
        ).strip()

    return {
        "rows": rows_out,
        "warning": warning,
        "weight_basis": "cost-weighted proxy (lots × entry_price)" if total_cost else None,
        "n_positions": len(rows_out),
    }


def build_portfolio_risk_summary(payload: Dict[str, Any], positions_block: Dict[str, Any]) -> Dict[str, Any]:
    gross, cash = _gross_cash(payload)
    rows = positions_block.get("rows") or []
    weights = [r.get("weight_pct") for r in rows if r.get("weight_pct") is not None]
    below_ma20 = sum(1 for r in rows if r.get("ma20_status") == "Below")
    below_ma50 = sum(1 for r in rows if r.get("ma50_status") == "Below")
    sell_active = sum(
        1 for r in rows if "SELL" in str(r.get("action", "")).upper() or "EXIT" in str(r.get("action", "")).upper()
    )
    r_vals = [r.get("r_multiple") for r in rows if r.get("r_multiple") is not None]
    avg_r = None
    if r_vals:
        try:
            avg_r = round(sum(float(x) for x in r_vals) / len(r_vals), 2)
        except (TypeError, ValueError):
            pass

    sector_block = build_sector_exposure(payload, positions_block)
    max_sector = None
    if sector_block.get("rows"):
        max_sector = max(sector_block["rows"], key=lambda x: x.get("weight_pct") or 0)

    top3 = sorted([w for w in weights if w is not None], reverse=True)[:3]
    top3_sum = round(sum(top3), 2) if top3 else None
    largest = top3[0] if top3 else None

    return {
        "n_positions": len(rows),
        "gross_exposure": gross,
        "cash": cash,
        "largest_position_weight_pct": largest,
        "top3_positions_weight_pct": top3_sum,
        "max_sector_weight_pct": max_sector.get("weight_pct") if max_sector else None,
        "max_sector_name": max_sector.get("sector") if max_sector else None,
        "positions_below_ma20": below_ma20,
        "positions_below_ma50": below_ma50,
        "active_sell_trim_count": sell_active,
        "avg_r_multiple_open": avg_r,
        "portfolio_distance_to_stop_pct": "Missing",
        "high_beta_exposure_note": "Missing — beta map not loaded",
    }


def build_sector_exposure(payload: Dict[str, Any], positions_block: Dict[str, Any]) -> Dict[str, Any]:
    rows = positions_block.get("rows") or []
    unmapped = [r["ticker"] for r in rows if not r.get("sector_mapped")]
    by_sector: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sec = r.get("sector") or "—"
        w = r.get("weight_pct") or 0.0
        if sec not in by_sector:
            by_sector[sec] = {"sector": sec, "count": 0, "weight_pct": 0.0}
        by_sector[sec]["count"] += 1
        by_sector[sec]["weight_pct"] = round(by_sector[sec]["weight_pct"] + float(w), 2)

    table = []
    for sec, agg in sorted(by_sector.items(), key=lambda x: -x[1]["weight_pct"]):
        w = agg["weight_pct"]
        limit = MAX_SECTOR_PCT
        status = "OK" if w <= limit else "Over limit"
        if sec == "—":
            status = "Unmapped"
        table.append({
            "sector": sec,
            "position_count": agg["count"],
            "weight_pct": w,
            "limit_pct": limit,
            "status": status,
        })

    n = len(rows)
    warning = None
    if unmapped:
        warning = f"Sector mapping incomplete: {len(unmapped)}/{n} positions unmapped."

    return {
        "rows": table,
        "unmapped_tickers": unmapped,
        "warning": warning,
        "sector_map_path": str(SECTOR_MAP_PATH.relative_to(REPO)) if SECTOR_MAP_PATH.exists() else None,
    }


def _bucket_from_scan_action(action: str) -> str:
    a = (action or "").upper()
    if any(x in a for x in ("NEW_T1", "FULL_T1", "BUY_NOW")):
        return "Buy Now Candidate"
    if "PULLBACK" in a:
        return "Buy on Pullback"
    if "RECLAIM" in a:
        return "Buy on Reclaim"
    if any(x in a for x in ("TRAIL_EXIT", "EXIT", "AVOID", "NO_T2")):
        return "Avoid / Remove"
    return "Hold / Monitor"


def _legacy_build_watchlist_board_unused(payload: Dict[str, Any]) -> Dict[str, Any]:
    scan_path = _latest_scan_csv()
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "Buy Now Candidate": [],
        "Buy on Pullback": [],
        "Buy on Reclaim": [],
        "Hold / Monitor": [],
        "Avoid / Remove": [],
    }
    if scan_path and scan_path.exists():
        with scan_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get("symbol") or "").strip().upper()
                if not sym:
                    continue
                action = row.get("final_action") or ""
                bucket = _bucket_from_scan_action(action)
                score = row.get("a3_rank_score") or row.get("ed_score")
                try:
                    score_f = float(score) if score not in (None, "") else None
                except (TypeError, ValueError):
                    score_f = None
                item = {
                    "ticker": sym,
                    "sector": row.get("sector_l1") or "—",
                    "bucket": bucket,
                    "setup_type": row.get("strategy_classification") or row.get("recommendation") or "—",
                    "fundamental_thesis": "Missing",
                    "technical_setup": row.get("final_action_reason") or action,
                    "trigger_price": row.get("tp1_price") or row.get("pb_trigger_price"),
                    "invalid_price": row.get("trail_price"),
                    "score": score_f,
                    "action": action,
                }
                buckets[bucket].append(item)
        for b in buckets:
            buckets[b].sort(key=lambda x: (-(x.get("score") or 0), x.get("ticker", "")))

    flat = []
    for b, items in buckets.items():
        for it in items:
            flat.append(it)

    if not flat and WATCHLIST_CONFIG.exists():
        for line in WATCHLIST_CONFIG.read_text(encoding="utf-8").splitlines():
            sym = line.strip().upper()
            if sym and not sym.startswith("#"):
                flat.append({
                    "ticker": sym,
                    "sector": "—",
                    "bucket": "Hold / Monitor",
                    "setup_type": "config/watchlist.txt",
                    "fundamental_thesis": "Missing",
                    "technical_setup": "Missing",
                    "trigger_price": None,
                    "invalid_price": None,
                    "score": None,
                    "action": "Monitor",
                })

    note = None
    if not flat:
        note = (
            "No watchlist candidates loaded. Expected: phase36 daily scan CSV under data/research/ "
            "or config/watchlist.txt."
        )

    return {
        "buckets": buckets,
        "candidates": flat,
        "scan_source": str(scan_path.relative_to(REPO)) if scan_path else None,
        "note": note,
    }


def _metric_from_manual(manual: Dict[str, Any], key_path: Tuple[str, ...]) -> Any:
    cur: Any = manual
    for k in key_path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def build_wow_changes(payload: Dict[str, Any]) -> Dict[str, Any]:
    manual = _read_json(MANUAL_INPUTS)
    prev = _read_json(MANUAL_INPUTS_PREV)
    mkt = payload.get("market_structure") or {}
    levels = mkt.get("levels") or {}
    vn = levels.get("vnindex_level")
    vn30 = levels.get("vn30_level")
    dist = levels.get("distribution_days_rolling_20")
    g = manual.get("global") or {}
    v = manual.get("vietnam") or {}
    gp = prev.get("global") or {}
    vp = prev.get("vietnam") or {}

    def row(metric: str, this_v: Any, last_v: Any, interp: str, impl: str) -> Dict[str, Any]:
        ch = None
        if this_v is not None and last_v is not None:
            try:
                ch = float(this_v) - float(last_v)
            except (TypeError, ValueError):
                ch = None
        return {
            "metric": metric,
            "this_week": this_v,
            "last_week": last_v if prev else "Missing",
            "change": ch,
            "interpretation": interp if this_v is not None else "Missing",
            "portfolio_implication": impl,
        }

    rows = [
        row("VNINDEX", vn, _metric_from_manual(prev, ("market", "vnindex_level")), "Index level", "Breakout risk context"),
        row("VN30", vn30, _metric_from_manual(prev, ("market", "vn30_level")), "Large-cap proxy", "Leader vs broad"),
        row("Dist days 20", dist, _metric_from_manual(prev, ("market", "distribution_days_rolling_20")), "Distribution pressure", "Trim weak breakouts if rising"),
        row("UST 2Y", g.get("ust_2y"), gp.get("ust_2y"), "Global rates", "External pressure on EM"),
        row("UST 10Y", g.get("ust_10y"), gp.get("ust_10y"), "Global rates", "Risk-free discount rate"),
        row("DXY", g.get("dxy"), gp.get("dxy"), "USD strength", "FX / foreign flow sensitivity"),
        row("USD/VND", v.get("sbv_reference_usd_vnd") or v.get("fx_usd_vnd"), vp.get("sbv_reference_usd_vnd"), "FX", "FX relief or pressure"),
        row("Interbank ON", v.get("interbank_on"), vp.get("interbank_on"), "VN short rate", "Liquidity cost"),
        row("OMO net", v.get("omo_net"), vp.get("omo_net"), "SBV liquidity", "Liquidity improving/worsening"),
        row("Credit growth YoY", v.get("credit_growth_yoy"), vp.get("credit_growth_yoy"), "Credit impulse", "Risk appetite"),
    ]
    breadth_note = "Missing"
    if mkt.get("levels", {}).get("vn30_trend_ok") is not None:
        breadth_note = f"VN30 trend_ok={mkt.get('levels', {}).get('vn30_trend_ok')}"
    rows.append(row("Breadth", breadth_note, "Missing", "—", "Allow only confirmed leaders if weak"))

    if not prev:
        return {"rows": rows, "warning": "manual_inputs_prev.json missing — last-week column unavailable."}
    return {"rows": rows, "warning": None}


def build_decision_review(asof: str) -> Dict[str, Any]:
    logs = sorted(DECISION_LOG_DIR.glob("*.json"), key=lambda p: p.name)
    prev_log = None
    for p in reversed(logs):
        if p.stem < asof:
            prev_log = p
            break
    if not prev_log:
        return {
            "rows": [],
            "note": "No prior decision log found.",
            "schema": "date, decision_type, decision, expected_outcome, actual_outcome, good_decision, lesson, process_adjustment",
        }
    data = _read_json(prev_log)
    rec = {
        "last_week_decision": data.get("council", {}).get("final_recommendation") or f"Regime {data.get('regime')} gross cap {data.get('gross_cap')}",
        "expected_outcome": "Maintain risk band per regime",
        "actual_outcome": "See current week metrics",
        "good_decision": "Unknown",
        "lesson": "Log explicit expected/actual outcomes weekly",
        "process_adjustment": "Fill decision_review rows in decision_log",
    }
    return {"rows": [rec], "note": f"Loaded from {prev_log.name}", "schema": "date, decision_type, decision, expected_outcome, actual_outcome, good_decision, lesson, process_adjustment"}


def build_enhanced_decision_layer(payload: Dict[str, Any], command_center: Dict[str, Any], positions_block: Dict[str, Any]) -> Dict[str, Any]:
    base = payload.get("decision_layer") or {}
    forced = [
        f"{r['ticker']}: {r['action']} — {r['reason']}"
        for r in (positions_block.get("rows") or [])
        if "SELL" in str(r.get("action", "")).upper() or "EXIT" in str(r.get("action", "")).upper()
    ]
    gross_status = command_center.get("gross_exposure_status")
    immediate = list(base.get("top_actions") or [])[:2]
    if forced:
        immediate = forced + immediate
    if gross_status == "Reduce exposure":
        immediate.append("Rebalance: reduce gross toward regime band")
    elif gross_status == "Raise exposure":
        immediate.append("Deploy only on confirmed setups within band")

    conditional = [
        "If VNINDEX confirms breakout with dist days stable → allow selective adds (leaders only).",
        "If distribution days rise → cut laggards, raise cash.",
        "If USD/VND pressure returns → reduce high-beta adds.",
        "If breadth improves (VN30 + HNX/UPCOM above MA20) → widen leader-only adds.",
        "If holdings breach stop → exit without thesis attachment.",
    ]
    do_not = [
        "Do not add to laggards.",
        "Do not buy extended names without base/pullback.",
        "Do not increase gross above regime band.",
        "Do not ignore SELL/EXIT signals due to thesis attachment.",
    ]
    return {
        **base,
        "immediate_actions": immediate,
        "conditional_actions": conditional,
        "do_not_do": do_not,
    }


def build_data_freshness(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    asof = (payload.get("metadata") or {}).get("asof_date")
    blocks = [
        ("manual_inputs.json (macro)", MANUAL_INPUTS, "scraped/FRED merge"),
        ("current_positions_derived.json", CURRENT_POSITIONS_PATH, "FQuery Excel derive"),
        ("vnindex_downtrend_probability_v2.json", REPO / "data" / "decision" / "vnindex_downtrend_probability_v2.json", "computed"),
        ("market_flags / sell_signals", SELL_SIGNALS_PATH, "computed"),
        ("tech_status.json", TECH_STATUS_PATH, "computed/manual"),
    ]
    out = []
    for label, path, method in blocks:
        fr = _file_freshness(path)
        status = fr["status"]
        if status == "Fresh" and fr.get("last_updated") and asof and fr["last_updated"] < asof:
            status = "Stale"
        out.append({"block": label, "method": method, **fr, "freshness": status})
    return out


def enrich_portfolio_decision_sections(payload: Dict[str, Any], fetch_prices: bool = True) -> Dict[str, Any]:
    """Attach portfolio command-center sections to normalized weekly payload."""
    regime_engine = payload.get("regime_engine") or {}
    current_regime = regime_engine.get("current_regime")

    command_center = build_portfolio_command_center(payload)
    payload["portfolio_command_center"] = command_center
    payload["regime_rules"] = build_regime_rules(current_regime)
    payload["wow_since_last_week"] = build_wow_changes(payload)

    positions_block = build_position_decisions(payload, fetch_prices=fetch_prices)
    payload["position_decisions"] = positions_block
    exec_mon = payload.get("execution_monitoring") or {}
    exec_mon["position_signals"] = positions_block.get("rows") or []
    exec_mon["position_metrics_warning"] = positions_block.get("warning")
    payload["execution_monitoring"] = exec_mon

    payload["portfolio_risk_summary"] = build_portfolio_risk_summary(payload, positions_block)
    sector_exp = build_sector_exposure(payload, positions_block)
    payload["sector_exposure"] = sector_exp
    ph = payload.get("portfolio_health") or {}
    ph["sector_concentration"] = sector_exp.get("rows") or ph.get("sector_concentration")
    ph["sector_warning"] = sector_exp.get("warning")
    ph["unmapped_tickers"] = sector_exp.get("unmapped_tickers")
    payload["portfolio_health"] = ph

    asof = (payload.get("metadata") or {}).get("asof_date") or datetime.now().strftime("%Y-%m-%d")
    payload["decision_review"] = build_decision_review(asof)
    payload["decision_layer"] = build_enhanced_decision_layer(payload, command_center, positions_block)
    payload["data_freshness"] = build_data_freshness(payload)

    from scripts.ingest.weekly_lean_sections import attach_lean_report

    return attach_lean_report(payload, positions_block, sector_exp)
