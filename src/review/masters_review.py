"""
Masters brains review in LEAN mode: Buffett, O'Neil, Minervini, Morales.
No transcript; facts only + 1 rule adjustment per master per trade.
Output: trade_masters_review_YYYY-MM.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR, REPO
from .trade_build_input import TRADE_REVIEW_INPUT_PATH

logger = logging.getLogger(__name__)


def _load_trades(input_path: Optional[Path] = None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    p = input_path or TRADE_REVIEW_INPUT_PATH
    if not p.exists():
        return [], {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("trades_closed") or [], data


def _one_master_review(trade: Dict[str, Any], master: str, process_gate_on: bool) -> Dict[str, Any]:
    """Rule-based one-line style per master. No LLM."""
    ctx = trade.get("context") or {}
    risk = (ctx.get("risk_flag_at_entry") or "").strip()
    dist = ctx.get("dist_days_20_at_entry")
    tech = ctx.get("ticker_tech_at_entry") or {}
    pnl = (trade.get("pnl") or {}).get("pct")

    mistake = "None noted"
    correct = "Position sized and exited per rules"
    suboptimal = "—"
    rule_adjust = "—"
    confidence = 50

    # Process-first override: if global process gate is ON or this trade missing stop/label,
    # all masters converge on discipline before optimization.
    reason = (trade.get("entry") or {}).get("reason_tag")
    stop_p = (trade.get("risk") or {}).get("stop_price")
    missing_reason = (not reason) or str(reason).strip().lower() in ("unknown", "na", "n/a")
    missing_stop = stop_p is None
    if process_gate_on or missing_reason or missing_stop:
        mistake = "Discipline missing (stop/label not recorded)"
        correct = "Captured entry/exit facts; needs structured fields"
        suboptimal = "Cannot compare setups apples-to-apples without reason_tag; cannot audit R without stop"
        rule_adjust = "Require stop_price_at_entry + reason_tag on every trade; do not optimize strategy until compliance improves"
        confidence = 90
        return {
            "mistake_type": mistake,
            "what_correct": correct,
            "what_suboptimal": suboptimal,
            "1_rule_adjust": rule_adjust,
            "confidence": confidence,
        }

    if master == "buffett":
        if risk and risk != "Normal":
            mistake = "Buy when margin of safety unclear (risk elevated)"
            rule_adjust = "No new buys when risk_flag!=Normal"
            confidence = 70
        else:
            rule_adjust = "Stick to circle of competence; avoid overconcentration"
            confidence = 60

    elif master == "oneil":
        if dist is not None and dist >= 4:
            mistake = "Add in distribution (dist_days>=4)"
            rule_adjust = "No new buys when dist_days_20>=4"
            confidence = 75
        elif risk == "High":
            mistake = "Buy when market under pressure"
            rule_adjust = "Follow-through only; no new buys in High risk"
            confidence = 70
        else:
            rule_adjust = "Cut losses short; let winners run"
            confidence = 55

    elif master == "minervini":
        if tech.get("day2_trigger") is True:
            mistake = "Held through day2 breach (close below MA20)"
            rule_adjust = "Hard exit on day2 breach; no hope"
            confidence = 75
        elif pnl is not None and pnl < -0.07:
            mistake = "Let loss exceed typical stop"
            rule_adjust = "Tighten stop or trim on first breach"
            confidence = 65
        else:
            rule_adjust = "Only buy when VCP/setup; respect 50 DMA"
            confidence = 55

    elif master == "morales":
        if risk and risk != "Normal":
            mistake = "Risk not normalized before entry"
            rule_adjust = "Reduce size or skip when risk_flag!=Normal"
            confidence = 70
        else:
            rule_adjust = "Track R-multiple; cap drawdown per name"
            confidence = 55

    return {
        "mistake_type": mistake,
        "what_correct": correct,
        "what_suboptimal": suboptimal,
        "1_rule_adjust": rule_adjust,
        "confidence": confidence,
    }


def run_masters_review(
    month: Optional[str] = None,
    input_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> Path:
    """Produce trade_masters_review_YYYY-MM.json. Idempotent."""
    trades, data = _load_trades(input_path)
    month_key = month[:7] if month else ""
    if not month_key:
        rw = data.get("review_window") or {}
        month_key = (rw.get("month") or data.get("asof_date", ""))[:7]
    if not month_key:
        month_key = "unknown"

    # Process gate from diagnostic/summary (if available)
    summary = (data.get("diagnostic") or {}).get("summary_stats") if isinstance(data.get("diagnostic"), dict) else None
    if summary is None:
        # Fallback: load diagnostic file if present
        diag_path = DECISION_DIR / f"trade_diagnostic_{month_key}.json"
        if diag_path.exists():
            try:
                diag_data = json.loads(diag_path.read_text(encoding="utf-8"))
                summary = diag_data.get("summary_stats") or {}
            except Exception:
                summary = {}
        else:
            summary = {}
    stop_present_rate = summary.get("stop_present_rate")
    reason_present_rate = summary.get("reason_tag_present_rate")
    # Safe defaults if metrics missing
    if stop_present_rate is None or reason_present_rate is None:
        process_gate_on = False
    else:
        # Thresholds aligned with review_policy.process_gate defaults
        stop_min = 0.70
        reason_min = 0.80
        process_gate_on = (stop_present_rate < stop_min) or (reason_present_rate < reason_min)

    results: List[Dict[str, Any]] = []
    for t in trades:
        tid = t.get("trade_id", "")
        row = {"trade_id": tid}
        for m in ("buffett", "oneil", "minervini", "morales"):
            row[m] = _one_master_review(t, m, process_gate_on)
        results.append(row)

    payload = {
        "asof_date": data.get("asof_date", ""),
        "review_window": {"month": month_key},
        "input_hash": data.get("input_hash", ""),
        "reviews": results,
    }

    out_path = out_path or DECISION_DIR / f"trade_masters_review_{month_key}.json"
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d trades)", out_path.name, len(results))
    return out_path
