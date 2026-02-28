"""
Open Risk Dashboard: position risk × regime × concentration.
Structure-only (no PnL). Outputs: open_risk_YYYY-MM.json, open_risk_latest.json; optional .md with --render.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR, RAW_DIR, REPO

logger = logging.getLogger(__name__)

CURRENT_POSITIONS_JSON = RAW_DIR / "current_positions_derived.json"
CURRENT_POSITIONS_PROVENANCE_JSON = RAW_DIR / "current_positions_provenance.json"
MANUAL_INPUTS_PATH = RAW_DIR / "manual_inputs.json"
REGIME_STATE_PATH = REPO / "data" / "state" / "regime_state.json"
REVIEW_POLICY_PATH = DECISION_DIR / "review_policy.json"

# Flag enums for position_risk_card
FLAG_MISSING_LOTS = "missing_lots"
FLAG_MISSING_ENTRY_PRICE = "missing_entry_price"
FLAG_VERY_OLD_POSITION = "very_old_position"
FLAG_SIZE_CONCENTRATION = "size_concentration"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_policy_open_risk() -> Dict[str, Any]:
    defaults = {
        "very_old_days": 60,
        "concentration_top1_share_red": 0.25,
        "concentration_hhi_red": 0.12,
    }
    if not REVIEW_POLICY_PATH.exists():
        return defaults
    try:
        data = json.loads(REVIEW_POLICY_PATH.read_text(encoding="utf-8"))
        cfg = data.get("open_risk") or {}
        for k, v in defaults.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return defaults


def _infer_risk_flag(manual_inputs: Dict[str, Any]) -> str:
    mkt = manual_inputs.get("market") or {}
    dd = mkt.get("distribution_days_rolling_20")
    if dd is not None:
        if dd >= 6:
            return "High"
        if dd >= 4:
            return "Elevated"
    return "Normal"


def _herfindahl(shares: List[float]) -> float:
    """HHI: sum of squared shares (share = portion of total)."""
    if not shares:
        return 0.0
    total = sum(shares)
    if total <= 0:
        return 0.0
    return sum((x / total) ** 2 for x in shares)


def run_open_risk(month: Optional[str] = None, render: bool = False) -> tuple[Path, Path]:
    """
    Build open risk dashboard. Writes open_risk_YYYY-MM.json and open_risk_latest.json.
    If month is None, uses asof_date from manual_inputs or regime_state.
    Returns (month_path, latest_path).
    """
    positions_path = CURRENT_POSITIONS_JSON
    if not positions_path.exists():
        logger.warning("current_positions_derived.json not found; run derive-current first.")
        payload = _empty_payload(month or "latest")
        out_month = DECISION_DIR / f"open_risk_{month or 'latest'}.json"
        out_latest = DECISION_DIR / "open_risk_latest.json"
        DECISION_DIR.mkdir(parents=True, exist_ok=True)
        for p in (out_month, out_latest):
            p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        if render:
            _render_md(payload, out_month.with_suffix(".md"))
            _render_md(payload, out_latest.with_suffix(".md"))
        return out_month, out_latest

    positions: List[Dict[str, Any]] = json.loads(positions_path.read_text(encoding="utf-8"))
    if not isinstance(positions, list):
        positions = []

    manual = _load_json(MANUAL_INPUTS_PATH)
    regime_state = _load_json(REGIME_STATE_PATH)
    provenance = _load_json(CURRENT_POSITIONS_PROVENANCE_JSON)
    policy = _load_policy_open_risk()

    asof = (manual.get("asof_date") or regime_state.get("asof_date") or "").strip()[:10]
    if not asof:
        from datetime import datetime
        asof = datetime.now().strftime("%Y-%m-%d")
    if not month:
        month = asof[:7] if len(asof) >= 7 else "latest"

    n_positions = len(positions)
    lots_missing_count = sum(1 for p in positions if p.get("lots") is None)
    def _missing_ep(p: Dict[str, Any]) -> bool:
        ep = p.get("entry_price")
        if ep is None:
            return True
        try:
            return float(ep) <= 0
        except (TypeError, ValueError):
            return True

    entry_price_missing_count = sum(1 for p in positions if _missing_ep(p))
    duplicates_consolidated = provenance.get("source") in ("current_positions_excel", "trade_history_full")

    # Concentration from positions with valid lots only; null if coverage too low
    positions_with_lots = [p for p in positions if p.get("lots") is not None and (int(p.get("lots")) or 0) > 0]
    concentration_low_coverage = len(positions_with_lots) < 3
    if not concentration_low_coverage and positions_with_lots:
        lots_list = [int(p["lots"]) for p in positions_with_lots]
        total_lots = sum(lots_list)
        sorted_by_lots = sorted(positions_with_lots, key=lambda p: int(p["lots"]), reverse=True)
        top10_by_lots = [{"ticker": p["ticker"], "lots": p["lots"]} for p in sorted_by_lots[:10]]
        single_name_lots_share_max = max((int(p["lots"]) / total_lots for p in positions_with_lots), default=0.0)
        herfindahl_lots = _herfindahl(lots_list)
    else:
        top10_by_lots = []
        single_name_lots_share_max = None
        herfindahl_lots = None
    total_lots = sum(int(p.get("lots")) for p in positions if p.get("lots") is not None and (int(p.get("lots")) or 0) > 0)

    very_old_days = int(policy.get("very_old_days", 60))
    concentration_top1_red = float(policy.get("concentration_top1_share_red", 0.25))
    concentration_hhi_red = float(policy.get("concentration_hhi_red", 0.12))

    buckets = {"0_5d": 0, "6_20d": 0, "21_60d": 0, "60d_plus": 0}
    oldest_positions: List[Dict[str, Any]] = []
    position_risk_cards: List[Dict[str, Any]] = []

    for p in positions:
        hd = p.get("holding_days")
        if hd is not None:
            if hd <= 5:
                buckets["0_5d"] += 1
            elif hd <= 20:
                buckets["6_20d"] += 1
            elif hd <= 60:
                buckets["21_60d"] += 1
            else:
                buckets["60d_plus"] += 1

    sorted_by_age = sorted(
        [p for p in positions if p.get("holding_days") is not None],
        key=lambda p: (p.get("holding_days") or 0),
        reverse=True,
    )
    oldest_positions = [
        {"ticker": p["ticker"], "holding_days": p.get("holding_days"), "entry_date": p.get("entry_date")}
        for p in sorted_by_age[:5]
    ]

    for p in positions:
        ticker = p.get("ticker") or ""
        lots = p.get("lots")
        entry_price = p.get("entry_price")
        holding_days = p.get("holding_days")
        flags: List[str] = []
        if lots is None:
            flags.append(FLAG_MISSING_LOTS)
        if entry_price is None or (isinstance(entry_price, (int, float)) and float(entry_price) <= 0):
            flags.append(FLAG_MISSING_ENTRY_PRICE)
        if holding_days is not None and holding_days >= very_old_days:
            flags.append(FLAG_VERY_OLD_POSITION)
        if total_lots > 0 and lots is not None and single_name_lots_share_max is not None:
            share = int(lots) / total_lots
            if share >= concentration_top1_red:
                flags.append(FLAG_SIZE_CONCENTRATION)
        position_risk_cards.append({
            "ticker": ticker,
            "lots": lots,
            "entry_price": entry_price,
            "holding_days": holding_days,
            "flags": flags,
        })

    regime = regime_state.get("regime") or "unknown"
    risk_flag = _infer_risk_flag(manual)
    dist_days_20 = (manual.get("market") or {}).get("distribution_days_rolling_20")
    risk_posture_note = "tighten/defensive posture" if risk_flag != "Normal" else ""

    top_actions: List[Dict[str, Any]] = []
    if lots_missing_count > 0:
        tickers_missing = [p["ticker"] for p in positions if p.get("lots") is None][:10]
        top_actions.append({"priority": "P0", "action": f"Fill lots for {lots_missing_count} tickers", "tickers_sample": tickers_missing})
    if concentration_low_coverage:
        top_actions.append({"priority": "P1", "action": "Concentration stats unavailable (fewer than 3 positions with lots); fill lots for coverage."})
    elif single_name_lots_share_max is not None and herfindahl_lots is not None and (single_name_lots_share_max >= concentration_top1_red or herfindahl_lots >= concentration_hhi_red):
        top_actions.append({"priority": "P1", "action": f"Reduce concentration: top1 lots share {single_name_lots_share_max:.2%}, HHI {herfindahl_lots:.4f}"})
    if risk_flag != "Normal":
        top_actions.append({"priority": "P1", "action": "Reduce gross / no new buys (risk_flag != Normal)"})
    top_actions = top_actions[:3]

    payload: Dict[str, Any] = {
        "asof_date": asof,
        "month": month,
        "coverage_quality": {
            "n_positions": n_positions,
            "lots_missing_count": lots_missing_count,
            "entry_price_missing_count": entry_price_missing_count,
            "duplicates_consolidated": duplicates_consolidated,
            "concentration_low_coverage": concentration_low_coverage,
        },
        "exposure_concentration": {
            "top10_by_lots": top10_by_lots,
            "herfindahl_lots": round(herfindahl_lots, 6) if herfindahl_lots is not None else None,
            "single_name_lots_share_max": round(single_name_lots_share_max, 4) if single_name_lots_share_max is not None else None,
        },
        "holding_age": {
            "distribution_buckets": buckets,
            "oldest_positions": oldest_positions,
        },
        "regime_overlay": {
            "regime": regime,
            "risk_flag": risk_flag,
            "dist_days_20": dist_days_20,
            "risk_posture_note": risk_posture_note,
        },
        "position_risk_cards": position_risk_cards,
        "top_actions": top_actions,
    }

    out_month = DECISION_DIR / f"open_risk_{month}.json"
    out_latest = DECISION_DIR / "open_risk_latest.json"
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    for p in (out_month, out_latest):
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if render:
        _render_md(payload, out_month.with_suffix(".md"))
        _render_md(payload, out_latest.with_suffix(".md"))

    logger.info("Wrote open_risk %s and open_risk_latest.json (n_positions=%d)", out_month.name, n_positions)
    return out_month, out_latest


def _empty_payload(month: str) -> Dict[str, Any]:
    return {
        "asof_date": "",
        "month": month,
        "coverage_quality": {"n_positions": 0, "lots_missing_count": 0, "entry_price_missing_count": 0, "duplicates_consolidated": False, "concentration_low_coverage": True},
        "exposure_concentration": {"top10_by_lots": [], "herfindahl_lots": None, "single_name_lots_share_max": None},
        "holding_age": {"distribution_buckets": {"0_5d": 0, "6_20d": 0, "21_60d": 0, "60d_plus": 0}, "oldest_positions": []},
        "regime_overlay": {"regime": "unknown", "risk_flag": "Normal", "dist_days_20": None, "risk_posture_note": ""},
        "position_risk_cards": [],
        "top_actions": [],
    }


def _render_md(payload: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Open Risk Dashboard",
        "",
        f"**As of:** {payload.get('asof_date', '')} | **Month:** {payload.get('month', '')}",
        "",
        "## Coverage / Quality",
        f"- n_positions: {payload.get('coverage_quality', {}).get('n_positions', 0)}",
        f"- lots_missing_count: {payload.get('coverage_quality', {}).get('lots_missing_count', 0)}",
        f"- entry_price_missing_count: {payload.get('coverage_quality', {}).get('entry_price_missing_count', 0)}",
        f"- duplicates_consolidated: {payload.get('coverage_quality', {}).get('duplicates_consolidated', False)}",
        "",
        "## Exposure concentration",
    ]
    exp = payload.get("exposure_concentration", {})
    sm = exp.get("single_name_lots_share_max")
    hhi = exp.get("herfindahl_lots")
    lines.append(f"- single_name_lots_share_max: {f'{sm:.2%}' if sm is not None else 'null'}")
    lines.append(f"- herfindahl_lots: {f'{hhi:.4f}' if hhi is not None else 'null'}")
    lines.append("- top10_by_lots: " + str(exp.get("top10_by_lots", []))[:200] + ("..." if len(str(exp.get("top10_by_lots", []))) > 200 else ""))
    lines.extend(["", "## Holding age (buckets)", str(payload.get("holding_age", {}).get("distribution_buckets", {})), ""])
    lines.extend(["## Regime overlay", str(payload.get("regime_overlay", {})), ""])
    lines.extend(["## Top actions"])
    for a in payload.get("top_actions", []):
        lines.append(f"- [{a.get('priority', '')}] {a.get('action', '')}")
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Rendered %s", path.name)
