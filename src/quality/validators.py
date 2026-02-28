"""
Quality validators: vote_card, weekly_report_json, input_hash canonicalizer.
No decision logic; representation and schema only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

EVIDENCE_FORBIDDEN = frozenset({"likely", "maybe", "seems", "good", "bad"})
LOW_SAMPLE_THRESHOLD = 20


def validate_vote_card(card: Dict[str, Any], brain_name: str = "") -> Tuple[bool, List[str]]:
    """
    Validate council vote card. Returns (ok, list of violation messages).
    Guardrails: change_my_mind required non-empty; evidence must not contain vague words.
    """
    errors: List[str] = []
    if not card:
        return False, ["vote_card is empty"]
    change = (card.get("change_my_mind") or "").strip()
    if not change:
        errors.append(f"[{brain_name}] change_my_mind is required and must be non-empty (quality anchor)")
    evidence = card.get("top_3_evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    for i, bullet in enumerate(evidence):
        if not isinstance(bullet, str):
            continue
        lower = bullet.lower()
        for word in EVIDENCE_FORBIDDEN:
            if word in lower:
                errors.append(f"[{brain_name}] top_3_evidence[{i}] contains vague word '{word}': evidence must be fact-type only")
                break
    return len(errors) == 0, errors


def validate_weekly_report_json(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate weekly_report.json structure. Returns (ok, list of violation messages).
    what_changed must be list of {metric, delta, direction, source}.
    """
    errors: List[str] = []
    if not payload:
        return False, ["payload is empty"]
    wc = payload.get("what_changed")
    if wc is not None and not isinstance(wc, list):
        errors.append("what_changed must be a list of {metric, delta, direction, source}")
    if isinstance(wc, list):
        for i, item in enumerate(wc):
            if not isinstance(item, dict):
                errors.append(f"what_changed[{i}] must be a dict")
                continue
            for key in ("metric", "direction", "source"):
                if key not in item:
                    errors.append(f"what_changed[{i}] missing '{key}'")
    return len(errors) == 0, errors


def canonicalize_input_hash(manual_inputs: Dict[str, Any], tech_status: Dict[str, Any], watchlist_scores: Dict[str, Any]) -> str:
    """
    Stable hash of the three payloads. Canonical JSON: sort_keys, no whitespace.
    Use this for auditability; same inputs → same hash across runs.
    """
    blob = json.dumps(
        {"manual_inputs": manual_inputs, "tech_status": tech_status, "watchlist_scores": watchlist_scores},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def validate_backtest_low_sample_flag(record: Dict[str, Any]) -> bool:
    """True if n_trades/num_trades < LOW_SAMPLE_THRESHOLD (caller should append '(low sample)' in display)."""
    st = record.get("stats", {})
    n = st.get("n_trades") or st.get("num_trades") or record.get("n_trades")
    if n is None:
        return False
    try:
        return int(n) < LOW_SAMPLE_THRESHOLD
    except (TypeError, ValueError):
        return False


def validate_trade_review_input(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate trade_review_input.json schema. Returns (ok, list of errors).
    """
    errors: List[str] = []
    if not payload:
        return False, ["payload is empty"]
    for key in ("asof_date", "review_window", "input_hash", "trades_closed", "positions_open", "notes"):
        if key not in payload:
            errors.append(f"missing '{key}'")
    rw = payload.get("review_window")
    if rw is not None and not isinstance(rw, dict):
        errors.append("review_window must be object")
    if isinstance(payload.get("trades_closed"), list):
        for i, t in enumerate(payload["trades_closed"]):
            if not isinstance(t, dict):
                errors.append(f"trades_closed[{i}] must be object")
                continue
            if "ticker" not in t or "trade_id" not in t:
                errors.append(f"trades_closed[{i}] missing ticker or trade_id")
            risk = t.get("risk") or {}
            src = risk.get("stop_source")
            if src is not None and src not in ("manual", "system_default", "unknown"):
                errors.append(f"trades_closed[{i}].risk.stop_source must be manual|system_default|unknown")
    if isinstance(payload.get("positions_open"), list):
        for i, p in enumerate(payload["positions_open"]):
            if not isinstance(p, dict) or "ticker" not in p:
                errors.append(f"positions_open[{i}] must be object with ticker")
    return len(errors) == 0, errors


def validate_trade_diagnostic(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate trade_diagnostic JSON. Returns (ok, list of errors).
    """
    errors: List[str] = []
    if not payload:
        return False, ["payload is empty"]
    for key in ("summary_stats", "patterns", "trade_cards"):
        if key not in payload:
            errors.append(f"missing '{key}'")
    ss = payload.get("summary_stats")
    if ss is not None and not isinstance(ss, dict):
        errors.append("summary_stats must be object")
    elif isinstance(ss, dict) and ss.get("n_closed"):
        # When there are closed trades, expect compliance metrics to be present
        for key in ("stop_present_rate", "stop_manual_rate", "reason_tag_present_rate"):
            if key not in ss:
                errors.append(f"summary_stats missing '{key}'")
    if isinstance(payload.get("trade_cards"), list):
        for i, c in enumerate(payload["trade_cards"]):
            if not isinstance(c, dict):
                errors.append(f"trade_cards[{i}] must be object")
            elif "trade_id" not in c or "what_could_be_better" not in c:
                errors.append(f"trade_cards[{i}] missing trade_id or what_could_be_better")
    return len(errors) == 0, errors


def validate_meta_perf(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate meta_perf JSON. Returns (ok, list of errors).
    """
    errors: List[str] = []
    if not payload:
        return False, ["payload is empty"]
    for key in ("asof_date", "month", "input_hash", "data_quality", "process_compliance", "edge_r_distribution", "regime_interaction"):
        if key not in payload:
            errors.append(f"missing '{key}'")
    dq = payload.get("data_quality")
    if dq is not None and not isinstance(dq, dict):
        errors.append("data_quality must be object")
    elif isinstance(dq, dict):
        for fld in ("process_gate_on", "interpret_with_caution", "manual_stop_gate_on"):
            if fld in dq and not isinstance(dq[fld], bool):
                errors.append(f"data_quality.{fld} must be bool")
        cr = dq.get("caution_reasons")
        if cr is not None:
            if not isinstance(cr, list):
                errors.append("data_quality.caution_reasons must be list")
            else:
                allowed = {
                    "process_gate_on",
                    "manual_stop_gate_on",
                    "low_r_coverage",
                    "low_sample",
                    "low_manual_stop_share",
                }
                for r in cr:
                    if r not in allowed:
                        errors.append(f"data_quality.caution_reasons contains invalid value '{r}'")
    pc = payload.get("process_compliance")
    if pc is not None and not isinstance(pc, dict):
        errors.append("process_compliance must be object")
    labels = (pc or {}).get("labels") or {}
    for name, lab in labels.items():
        if lab not in ("RED", "YELLOW", "GREEN"):
            errors.append(f"labels.{name} must be RED|YELLOW|GREEN")
    for rate_key in ("stop_present_rate", "stop_manual_rate", "reason_tag_present_rate"):
        rate = (pc or {}).get(rate_key)
        if rate is not None and not (0.0 <= float(rate) <= 1.0):
            errors.append(f"{rate_key} must be between 0 and 1")
    rdist = payload.get("edge_r_distribution") or {}
    for k in ("n_closed", "n_with_r"):
        if k in rdist and rdist[k] is not None and int(rdist[k]) < 0:
            errors.append(f"edge_r_distribution.{k} must be non-negative")
    r_manual = payload.get("edge_r_distribution_manual_only") or {}
    if r_manual:
        for k in ("n_closed", "n_with_r"):
            if k in r_manual and r_manual[k] is not None and int(r_manual[k]) < 0:
                errors.append(f"edge_r_distribution_manual_only.{k} must be non-negative")
    reg_all = payload.get("regime_interaction") or {}
    reg_norm = reg_all.get("by_regime_at_entry_norm") or reg_all.get("by_regime_at_entry") or {}
    if not isinstance(reg_norm, dict):
        errors.append("regime_interaction.by_regime_at_entry_norm must be object")
    else:
        for g, st in reg_norm.items():
            if not isinstance(st, dict):
                errors.append(f"regime_interaction.by_regime_at_entry_norm['{g}'] must be object")
            elif "n" not in st:
                errors.append(f"regime_interaction.by_regime_at_entry_norm['{g}'] missing 'n'")
    return len(errors) == 0, errors


def validate_trade_history_full(payload: Any) -> Tuple[bool, List[str]]:
    """
    Validate full trade history (array). Returns (ok, list of errors).
    Required: non-empty array; each item has ticker and at least one of entry_date, exit_date.
    """
    errors: List[str] = []
    if not isinstance(payload, list):
        return False, ["trade_history_full must be a list"]
    if len(payload) == 0:
        return False, ["trade_history_full must be non-empty"]
    for i, row in enumerate(payload):
        if not isinstance(row, dict):
            errors.append(f"row[{i}] must be object")
            continue
        ticker = row.get("ticker") or row.get("symbol")
        if not ticker:
            errors.append(f"row[{i}] missing ticker/symbol")
        entry_d = row.get("entry_date")
        exit_d = row.get("exit_date")
        if not entry_d and not exit_d:
            errors.append(f"row[{i}] must have at least one of entry_date, exit_date")
    return len(errors) == 0, errors


def validate_export_month(payload: Any, month: str) -> Tuple[bool, List[str]]:
    """
    Validate export-month output: all trades have exit_date strictly in month window.
    month format: YYYY-MM.
    """
    errors: List[str] = []
    if not isinstance(payload, list):
        return False, ["export must be a list"]
    import calendar
    try:
        y, m = int(month[:4]), int(month[5:7])
        start = f"{month}-01"
        end = f"{month}-{calendar.monthrange(y, m)[1]:02d}"
    except (ValueError, IndexError):
        return False, [f"invalid month format: {month}"]
    for i, row in enumerate(payload):
        if not isinstance(row, dict):
            errors.append(f"trade[{i}] must be object")
            continue
        exit_d = (row.get("exit_date") or "")[:10]
        if not exit_d or not (start <= exit_d <= end):
            errors.append(f"trade[{i}] exit_date {exit_d!r} not in window {start}..{end}")
    return len(errors) == 0, errors


def validate_current_positions(payload: Any) -> Tuple[bool, List[str]]:
    """
    Validate current_positions_derived.json (array of open positions).
    Checks: entry_date valid (YYYY-MM-DD or null), lots > 0, ticker non-empty, holding_days >= 0.
    """
    errors: List[str] = []
    if not isinstance(payload, list):
        return False, ["current_positions must be a list"]
    for i, row in enumerate(payload):
        if not isinstance(row, dict):
            errors.append(f"position[{i}] must be object")
            continue
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            errors.append(f"position[{i}] ticker must be non-empty")
        lots = row.get("lots")
        if lots is not None:
            try:
                n = int(lots)
                if n <= 0:
                    errors.append(f"position[{i}] lots must be > 0 when present")
            except (TypeError, ValueError):
                errors.append(f"position[{i}] lots must be integer > 0 when present")
        entry_d = row.get("entry_date")
        if entry_d is not None and isinstance(entry_d, str) and len(entry_d) >= 10:
            if entry_d[4] != "-" or entry_d[7] != "-":
                errors.append(f"position[{i}] entry_date must be YYYY-MM-DD")
        holding_days = row.get("holding_days")
        if holding_days is not None:
            try:
                if int(holding_days) < 0:
                    errors.append(f"position[{i}] holding_days must be >= 0")
            except (TypeError, ValueError):
                errors.append(f"position[{i}] holding_days must be non-negative integer")
    return len(errors) == 0, errors


def validate_open_risk(payload: Any) -> Tuple[bool, List[str]]:
    """
    Validate open_risk dashboard JSON (light). Required keys and n_positions == len(position_risk_cards).
    Concentration metrics may be null.
    """
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["open_risk payload must be object"]
    for key in ("asof_date", "coverage_quality", "holding_age", "regime_overlay", "position_risk_cards"):
        if key not in payload:
            errors.append(f"missing '{key}'")
    cq = payload.get("coverage_quality")
    if isinstance(cq, dict):
        for f in ("n_positions", "lots_missing_count"):
            if f not in cq:
                errors.append(f"coverage_quality missing '{f}'")
    ha = payload.get("holding_age")
    if isinstance(ha, dict) and "distribution_buckets" not in ha:
        errors.append("holding_age missing 'distribution_buckets'")
    cards = payload.get("position_risk_cards")
    if isinstance(cards, list) and isinstance(cq, dict) and "n_positions" in cq:
        if cq["n_positions"] != len(cards):
            errors.append(f"n_positions ({cq['n_positions']}) != len(position_risk_cards) ({len(cards)})")
    return len(errors) == 0, errors
