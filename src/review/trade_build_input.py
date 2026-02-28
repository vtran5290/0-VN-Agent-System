"""
Build canonical trade_review_input.json from parsed trades + context enrichment.
Idempotent: same inputs → same output.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR, RAW_DIR, REPO, TRADE_HISTORY_MD, POSITIONS_DIGEST_MD
from .trade_parse import (
    load_closed_trades,
    parse_open_positions_from_md,
)

logger = logging.getLogger(__name__)

MANUAL_INPUTS_PATH = RAW_DIR / "manual_inputs.json"
TECH_STATUS_PATH = RAW_DIR / "tech_status.json"
REGIME_STATE_PATH = REPO / "data" / "state" / "regime_state.json"
TRADE_REVIEW_INPUT_PATH = DECISION_DIR / "trade_review_input.json"
REVIEW_POLICY_PATH = DECISION_DIR / "review_policy.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_policy() -> Dict[str, Any]:
    """
    Load review_policy.json with safe defaults.
    Only keys needed here: default_stop config.
    """
    if not REVIEW_POLICY_PATH.exists():
        return {
            "default_stop": {"enabled": False, "default_stop_pct": 0.07},
        }
    try:
        data = json.loads(REVIEW_POLICY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"default_stop": {"enabled": False, "default_stop_pct": 0.07}}
    if "default_stop" not in data:
        data["default_stop"] = {"enabled": False, "default_stop_pct": 0.07}
    return data


def _date_str(d: Any) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, str):
        return d[:10] if len(d) >= 10 else d
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _enrich_context_now(
    manual_inputs: Dict[str, Any],
    tech_status: Dict[str, Any],
    regime_state: Dict[str, Any],
) -> Dict[str, Any]:
    mkt = manual_inputs.get("market") or {}
    reg = regime_state or {}
    return {
        "regime_now": reg.get("regime") or "unknown",
        "risk_flag_now": _infer_risk_flag(manual_inputs),
        "dist_days_20_now": mkt.get("distribution_days_rolling_20"),
        "vnindex_level_now": mkt.get("vnindex_level") or mkt.get("vn30_level"),
    }


def _infer_risk_flag(manual_inputs: Dict[str, Any]) -> str:
    mkt = manual_inputs.get("market") or {}
    dd = mkt.get("distribution_days_rolling_20")
    if dd is not None:
        if dd >= 6:
            return "High"
        if dd >= 4:
            return "Elevated"
    return "Normal"


def _tech_for_ticker(tech_status: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    tickers = tech_status.get("tickers") or []
    for t in tickers:
        if isinstance(t, dict) and (t.get("ticker") or "").upper() == ticker.upper():
            return {
                "close_below_ma20": t.get("close_below_ma") if isinstance(t.get("close_below_ma"), bool) else None,
                "day2_trigger": t.get("day2_trigger") if isinstance(t.get("day2_trigger"), bool) else None,
                "tier": t.get("tier"),
                "r_multiple": t.get("r_multiple"),
            }
    return {"close_below_ma20": None, "day2_trigger": None, "tier": None, "r_multiple": None}


def build_trades_closed_canonical(
    raw_trades: List[Dict[str, Any]],
    manual_inputs: Dict[str, Any],
    tech_status: Dict[str, Any],
    regime_state: Dict[str, Any],
    month: Optional[str],
) -> List[Dict[str, Any]]:
    """Convert raw closed trades to canonical schema with context placeholders."""
    out: List[Dict[str, Any]] = []
    mkt = manual_inputs.get("market") or {}
    risk = _infer_risk_flag(manual_inputs)
    reg = regime_state or {}
    regime = reg.get("regime") or "unknown"
    tech_map = {t.get("ticker", "").upper(): t for t in (tech_status.get("tickers") or []) if isinstance(t, dict)}

    policy = _load_policy()
    default_stop_cfg = (policy.get("default_stop") or {})
    default_stop_enabled = bool(default_stop_cfg.get("enabled", False))
    default_stop_pct = float(default_stop_cfg.get("default_stop_pct", 0.07))

    for seq, r in enumerate(raw_trades):
        ticker = (r.get("ticker") or r.get("symbol") or "").upper()
        if not ticker:
            continue
        entry_d = _date_str(r.get("entry_date"))
        exit_d = _date_str(r.get("exit_date"))
        entry_p = r.get("entry_price")
        exit_p = r.get("exit_price")
        lots = r.get("lots", 1)
        stop_p = r.get("stop_price_at_entry")
        stop_source = (r.get("stop_source") or "unknown").lower()
        try:
            lots = int(lots)
        except (TypeError, ValueError):
            lots = 1

        pct = None
        if entry_p is not None and exit_p is not None and float(entry_p) != 0:
            try:
                pct = (float(exit_p) - float(entry_p)) / float(entry_p)
            except (TypeError, ValueError):
                pass

        # Stop provenance and optional system_default stop
        if stop_p is not None and stop_source not in ("manual", "system_default"):
            stop_source = "manual"

        if stop_p is None and default_stop_enabled and entry_p is not None:
            try:
                stop_p = float(entry_p) * (1.0 - float(default_stop_pct))
                stop_source = "system_default"
            except (TypeError, ValueError):
                stop_p = None

        if stop_p is None and stop_source not in ("manual", "system_default"):
            stop_source = "unknown"

        R = None
        r_multiple = None
        if entry_p is not None and stop_p is not None:
            try:
                R = float(entry_p) - float(stop_p)
                if R <= 0:
                    R = None
            except (TypeError, ValueError):
                R = None
        if R is not None and exit_p is not None:
            try:
                r_multiple = (float(exit_p) - float(entry_p)) / float(R)
            except (TypeError, ValueError):
                r_multiple = None

        date_part = (exit_d or entry_d or "unknown").replace("-", "")[:8]
        trade_id = f"{date_part}-{ticker}-{seq}"

        tech = _tech_for_ticker(tech_status, ticker)
        quality = {
            "missing_prices": entry_p is None or exit_p is None,
            "missing_context": True,
            "partial_fill": False,
        }

        stop_present = stop_p is not None
        stop_manual = stop_present and stop_source == "manual"

        out.append({
            "trade_id": trade_id,
            "ticker": ticker,
            "side": "LONG",
            "entry": {
                "date": entry_d,
                "price": entry_p,
                "lots": lots,
                "reason_tag": (r.get("reason_tag") or "unknown"),
            },
            "exit": {
                "date": exit_d,
                "price": exit_p,
                "lots": lots,
                "exit_tag": (r.get("exit_tag") or "unknown"),
            },
            "pnl": {"pct": pct, "vnd": None},
            "risk": {
                "stop_price": stop_p,
                "stop_source": stop_source,
                "stop_present": stop_present,
                "stop_manual": stop_manual,
                "R": R,
                "r_multiple": r_multiple,
            },
            "context": {
                "regime_at_entry": regime,
                "risk_flag_at_entry": risk,
                "dist_days_20_at_entry": mkt.get("distribution_days_rolling_20"),
                "vnindex_level_at_entry": mkt.get("vnindex_level") or mkt.get("vn30_level"),
                "ticker_tech_at_entry": tech,
                "regime_at_exit": regime,
                "risk_flag_at_exit": risk,
                "dist_days_20_at_exit": mkt.get("distribution_days_rolling_20"),
            },
            "quality_flags": quality,
        })
    return out


def build_positions_open_canonical(
    open_positions: List[Dict[str, Any]],
    manual_inputs: Dict[str, Any],
    tech_status: Dict[str, Any],
    regime_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Enrich open positions with context. Respect review_policy current_positions.default_lots_if_missing for null lots."""
    policy = _load_policy()
    default_lots = 1 if (policy.get("current_positions") or {}).get("default_lots_if_missing") else None
    ctx = _enrich_context_now(manual_inputs, tech_status, regime_state)
    out: List[Dict[str, Any]] = []
    for p in open_positions:
        ticker = (p.get("ticker") or p.get("symbol") or "").upper()
        if not ticker:
            continue
        lots_raw = p.get("lots")
        lots = int(lots_raw) if lots_raw is not None else default_lots
        tech = _tech_for_ticker(tech_status, ticker)
        out.append({
            "ticker": ticker,
            "lots": lots,
            "avg_entry_price": None,
            "stop_price": None,
            "current_price": None,
            "r_multiple": tech.get("r_multiple") if isinstance(tech, dict) else None,
            "context": {**ctx},
        })
    return out


def review_window_for_month(month: str) -> Dict[str, Any]:
    """Return review_window dict for monthly mode."""
    start = f"{month}-01"
    try:
        y, m = int(month[:4]), int(month[5:7])
        if m == 12:
            end = f"{y}-12-31"
        else:
            from calendar import monthrange
            end = f"{month}-{monthrange(y, m)[1]:02d}"
    except Exception:
        end = start
    return {"mode": "monthly", "month": month, "start": start, "end": end}


def build_input(
    month: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    out_path: Optional[Path] = None,
) -> Path:
    """
    Build trade_review_input.json. Idempotent.
    If month provided use it; else use start/end; else use latest from manual_inputs.
    """
    manual_inputs = _load_json(MANUAL_INPUTS_PATH)
    tech_status = _load_json(TECH_STATUS_PATH)
    regime_state = _load_json(REGIME_STATE_PATH)

    asof = (manual_inputs.get("asof_date") or datetime.now().strftime("%Y-%m-%d"))[:10]

    if month:
        review_window = review_window_for_month(month)
    elif start and end:
        review_window = {"mode": "ad_hoc", "month": None, "start": start, "end": end}
    else:
        review_window = review_window_for_month(asof[:7])

    open_positions, parse_warn = parse_open_positions_from_md()
    closed_raw, closed_warn = load_closed_trades()
    all_warnings = parse_warn + closed_warn
    assumptions = []
    if not closed_raw:
        assumptions.append("No trade_history_closed.json; trades_closed empty. Add file or export from Excel.")

    # Filter closed trades to review window by exit_date (facts-first; drop rows without required dates)
    win_start = (review_window.get("start") or "")[:10]
    win_end = (review_window.get("end") or "")[:10]
    closed_in_window: List[Dict[str, Any]] = []
    dropped_missing_dates = 0
    dropped_outside_window = 0
    for t in closed_raw:
        if not isinstance(t, dict):
            continue
        ex = _date_str(t.get("exit_date"))
        en = _date_str(t.get("entry_date"))
        if not ex or not en:
            dropped_missing_dates += 1
            continue
        if win_start and win_end and not (win_start <= ex <= win_end):
            dropped_outside_window += 1
            continue
        closed_in_window.append(t)
    if dropped_missing_dates:
        all_warnings.append(f"dropped_closed_trades_missing_dates={dropped_missing_dates}")
    if dropped_outside_window:
        all_warnings.append(f"dropped_closed_trades_outside_window={dropped_outside_window}")

    trades_closed = build_trades_closed_canonical(
        closed_in_window, manual_inputs, tech_status, regime_state, review_window.get("month")
    )
    positions_open = build_positions_open_canonical(
        open_positions, manual_inputs, tech_status, regime_state
    )

    # Provenance for open positions (written by derive-current)
    positions_open_provenance: Dict[str, Any] = {}
    prov_path = RAW_DIR / "current_positions_provenance.json"
    if prov_path.exists():
        try:
            positions_open_provenance = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    open_position_warnings: List[str] = []
    warn_path = RAW_DIR / "current_positions_warnings.json"
    if warn_path.exists():
        try:
            open_position_warnings = json.loads(warn_path.read_text(encoding="utf-8"))
            if not isinstance(open_position_warnings, list):
                open_position_warnings = []
        except Exception:
            pass

    notes = {"parser_warnings": all_warnings, "assumptions": assumptions, "open_position_warnings": open_position_warnings}
    payload = {
        "asof_date": asof,
        "review_window": review_window,
        "input_hash": "",
        "source_files": {
            "trade_history_md": str(TRADE_HISTORY_MD.relative_to(REPO)) if TRADE_HISTORY_MD.exists() else "",
            "positions_digest_md": str(POSITIONS_DIGEST_MD.relative_to(REPO)) if POSITIONS_DIGEST_MD.exists() else "",
        },
        "trades_closed": trades_closed,
        "positions_open": positions_open,
        "positions_open_provenance": positions_open_provenance,
        "notes": notes,
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["input_hash"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]

    out_path = out_path or TRADE_REVIEW_INPUT_PATH
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (n_closed=%d, n_open=%d)", out_path.name, len(trades_closed), len(positions_open))
    return out_path
