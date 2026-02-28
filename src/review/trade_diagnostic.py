"""
Diagnostics: what could have been done better (entry/exit/sizing/regime).
Facts-first; no invented data. Output: trade_diagnostic_YYYY-MM.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR
from .trade_build_input import TRADE_REVIEW_INPUT_PATH

logger = logging.getLogger(__name__)


def _load_input(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or TRADE_REVIEW_INPUT_PATH
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _summary_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(trades)
    if n == 0:
        return {
            "n_closed": 0,
            "win_rate": None,
            "avg_r_multiple": None,
            "median_r_multiple": None,
            "worst_3": [],
            "best_3": [],
            "stop_present_rate": None,
            "stop_manual_rate": None,
            "reason_tag_present_rate": None,
        }
    pnls = []
    r_mults = []
    stop_present_count = 0
    stop_manual_count = 0
    reason_present_count = 0
    for t in trades:
        pct = (t.get("pnl") or {}).get("pct")
        if pct is not None:
            pnls.append((t.get("trade_id"), pct))
        r_val = (t.get("risk") or {}).get("r_multiple")
        if r_val is not None:
            try:
                r_mults.append((t.get("trade_id"), float(r_val)))
            except (TypeError, ValueError):
                pass

        risk = t.get("risk") or {}
        stop_present = risk.get("stop_present")
        stop_manual = risk.get("stop_manual")
        stop_src = (risk.get("stop_source") or "").lower()
        if stop_present is True or (stop_present is None and risk.get("stop_price") is not None):
            stop_present_count += 1
            if stop_manual is True or stop_src == "manual":
                stop_manual_count += 1

        reason = (t.get("entry") or {}).get("reason_tag")
        if reason and str(reason).strip().lower() not in ("unknown", "na", "n/a"):
            reason_present_count += 1

    win_rate = None
    if pnls:
        wins = sum(1 for _, p in pnls if p > 0)
        win_rate = wins / len(pnls)

    avg_r = None
    median_r = None
    if r_mults:
        vals = [v for _, v in r_mults]
        avg_r = sum(vals) / len(vals)
        vals_sorted = sorted(vals)
        mid = len(vals_sorted) // 2
        median_r = (vals_sorted[mid] + vals_sorted[mid - 1]) / 2 if len(vals_sorted) > 1 else vals_sorted[0]

    pnls_sorted = sorted(pnls, key=lambda x: x[1])
    worst_3 = [{"trade_id": tid, "pct": pct} for tid, pct in pnls_sorted[:3]]
    best_3 = [{"trade_id": tid, "pct": pct} for tid, pct in pnls_sorted[-3:][::-1]]
    if r_mults:
        r_sorted = sorted(r_mults, key=lambda x: x[1])
        worst_3 = [{"trade_id": tid, "r_multiple": r} for tid, r in r_sorted[:3]]
        best_3 = [{"trade_id": tid, "r_multiple": r} for tid, r in r_sorted[-3:][::-1]]

    stop_present_rate = round(stop_present_count / n, 4) if n else None
    stop_manual_rate = round(stop_manual_count / n, 4) if n else None
    reason_tag_present_rate = round(reason_present_count / n, 4) if n else None

    return {
        "n_closed": n,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_r_multiple": round(avg_r, 4) if avg_r is not None else None,
        "median_r_multiple": round(median_r, 4) if median_r is not None else None,
        "worst_3": worst_3,
        "best_3": best_3,
        "stop_present_rate": stop_present_rate,
        "stop_manual_rate": stop_manual_rate,
        "reason_tag_present_rate": reason_tag_present_rate,
    }


def _detect_patterns(trades: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    entry_quality: List[Dict[str, Any]] = []
    exit_quality: List[Dict[str, Any]] = []
    sizing: List[Dict[str, Any]] = []
    process: List[Dict[str, Any]] = []

    buy_risk_high = []
    buy_dist_high = []
    held_ma20_breach = []
    missing_stop = []
    no_reason = []

    for t in trades:
        tid = t.get("trade_id", "")
        ctx = t.get("context") or {}
        risk = (ctx.get("risk_flag_at_entry") or "").strip()
        dist = ctx.get("dist_days_20_at_entry")
        tech = (ctx.get("ticker_tech_at_entry") or {})
        day2 = tech.get("day2_trigger")
        close_below = tech.get("close_below_ma20")

        if risk and risk != "Normal" and risk != "unknown":
            buy_risk_high.append(tid)
        if dist is not None and dist >= 4:
            buy_dist_high.append(tid)
        if day2 is True or close_below is True:
            held_ma20_breach.append(tid)
        if (t.get("risk") or {}).get("stop_price") is None and (t.get("risk") or {}).get("R") is None:
            missing_stop.append(tid)
        reason = (t.get("entry") or {}).get("reason_tag")
        if not reason or str(reason).strip().lower() in ("unknown", "na", "n/a"):
            no_reason.append(tid)

    if buy_risk_high:
        entry_quality.append({
            "pattern": "BUY in risk_flag!=Normal",
            "count": len(buy_risk_high),
            "examples": buy_risk_high[:5],
            "severity": "high",
        })
    if buy_dist_high:
        entry_quality.append({
            "pattern": "BUY with dist_days_20>=4",
            "count": len(buy_dist_high),
            "examples": buy_dist_high[:5],
            "severity": "med",
        })
    if held_ma20_breach:
        exit_quality.append({
            "pattern": "Held through MA20 day2 breach",
            "count": len(held_ma20_breach),
            "examples": held_ma20_breach[:5],
            "severity": "med",
        })
    if missing_stop:
        process.append({
            "pattern": "Missing stop recorded",
            "count": len(missing_stop),
            "examples": missing_stop[:5],
            "severity": "med",
        })
    if no_reason:
        process.append({
            "pattern": "No reason_tag",
            "count": len(no_reason),
            "examples": no_reason[:5],
            "severity": "low",
        })

    return {
        "entry_quality": entry_quality,
        "exit_quality": exit_quality,
        "sizing": sizing,
        "process": process,
    }


def _trade_cards(trades: List[Dict[str, Any]], patterns: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    cards = []
    pattern_tids = set()
    for pat_list in patterns.values():
        for p in pat_list:
            for tid in p.get("examples") or []:
                pattern_tids.add(tid)

    for t in trades:
        tid = t.get("trade_id", "")
        flags: List[str] = []
        facts: List[str] = []
        better: List[str] = []
        ctx = t.get("context") or {}
        risk = ctx.get("risk_flag_at_entry")
        dist = ctx.get("dist_days_20_at_entry")
        tech = ctx.get("ticker_tech_at_entry") or {}

        if risk and risk != "Normal" and risk != "unknown":
            flags.append("regime_mismatch")
            facts.append(f"risk_flag_at_entry={risk}")
            better.append("Set no_new_buys when risk_flag!=Normal")
        if dist is not None and dist >= 4:
            facts.append(f"dist_days_20_at_entry={dist}")
        if tech.get("day2_trigger") is True:
            facts.append("close_below_ma20_day2=true")
            better.append("Hard exit on day2 breach")
        if (t.get("risk") or {}).get("stop_price") is None:
            flags.append("missing_stop")
            better.append("Record stop at entry for R-multiple audit")

        if t.get("quality_flags", {}).get("missing_context"):
            flags.append("insufficient data")
        if not facts:
            facts.append("No context snapshot")

        confidence = 80 if tid not in pattern_tids and not flags else (40 if "insufficient data" in flags else 60)
        confidence = min(100, max(0, confidence))

        cards.append({
            "trade_id": tid,
            "ticker": t.get("ticker", ""),
            "r_multiple": (t.get("risk") or {}).get("r_multiple"),
            "flags": flags[:5],
            "facts": facts[:5],
            "what_could_be_better": better[:3],
            "confidence": confidence,
        })
    return cards


def run_diagnostic(
    month: Optional[str] = None,
    input_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> Path:
    """Produce trade_diagnostic_YYYY-MM.json. Idempotent."""
    data = _load_input(input_path)
    if not data:
        logger.warning("No trade_review_input.json; run build-input first")
        payload = {"asof_date": "", "review_window": {}, "input_hash": "", "summary_stats": {}, "patterns": {}, "trade_cards": []}
    else:
        trades = data.get("trades_closed") or []
        review_window = data.get("review_window") or {}
        month_key = (review_window.get("month") or month or "")[:7]
        if not month_key and data.get("asof_date"):
            month_key = data["asof_date"][:7]

        summary_stats = _summary_stats(trades)
        patterns = _detect_patterns(trades)
        trade_cards = _trade_cards(trades, patterns)

        payload = {
            "asof_date": data.get("asof_date", ""),
            "review_window": review_window,
            "input_hash": data.get("input_hash", ""),
            "summary_stats": summary_stats,
            "patterns": patterns,
            "trade_cards": trade_cards,
        }

    if month:
        month_key = month[:7]
    else:
        month_key = (payload.get("review_window") or {}).get("month") or (payload.get("asof_date") or "unknown")[:7]

    out_path = out_path or DECISION_DIR / f"trade_diagnostic_{month_key}.json"
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (n_closed=%d)", out_path.name, payload.get("summary_stats", {}).get("n_closed", 0))
    return out_path
