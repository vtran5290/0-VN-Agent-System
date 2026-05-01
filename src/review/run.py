from __future__ import annotations

"""
Council Performance Review — weekly record builder (CPR v1.0).

Reads:
- decision_log/YYYY-MM-DD.json
- data/decision/weekly_report.json (payload_version + regime/risk snapshot)
- data/market/weekly_returns.csv (market proxy outcome, e.g. VN30)
- optional: review/council/YYYY-MM-DD.json (structured council output)

Writes:
- review/records/YYYY-MM-DD.json  (one JSON record per week)
- review/index.csv                (flat table for monthly aggregation)
"""

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import REPO

logger = logging.getLogger(__name__)

DECISION_LOG_DIR = REPO / "decision_log"
WEEKLY_PAYLOAD_PATH = REPO / "data" / "decision" / "weekly_report.json"
MARKET_RETURNS_PATH = REPO / "data" / "market" / "weekly_returns.csv"

REVIEW_ROOT = REPO / "review"
RECORDS_DIR = REVIEW_ROOT / "records"
COUNCIL_DIR = REVIEW_ROOT / "council"
INDEX_PATH = REVIEW_ROOT / "index.csv"

INDEX_COLUMNS: List[str] = [
    "asof_date",
    "payload_version",
    "regime",
    "suggested_regime",
    "mismatch",
    "risk_flag",
    "gross_cap",
    "new_buys_allowed",
    "dist_composite",
    "dist_vn30",
    "dist_hnx",
    "dist_upcom",
    "dist_leader",
    "vn30_trend_ok",
    "hnx_trend_ok",
    "upcom_trend_ok",
    "n_positions",
    "pct_below_ma20",
    "pct_sell_trim_active",
    "avg_r_multiple_open",
    "next_week_ret",
    "next_4w_ret",
    "next_12w_ret",
    "drawdown_4w",
]


@dataclass
class OutcomeRow:
    asof_date: str
    next_week_ret: Optional[float]
    next_4w_ret: Optional[float]
    next_12w_ret: Optional[float]
    drawdown_4w: Optional[float]


def _parse_float(value: str | None) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _latest_asof_from_decision_log() -> Optional[str]:
    if not DECISION_LOG_DIR.exists():
        return None
    paths = sorted(
        [p for p in DECISION_LOG_DIR.glob("*.json") if p.is_file()], key=lambda p: p.stem
    )
    if not paths:
        return None
    return paths[-1].stem


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_weekly_payload() -> Dict[str, Any]:
    return _load_json(WEEKLY_PAYLOAD_PATH)


def _load_decision_log(asof_date: str) -> Dict[str, Any]:
    return _load_json(DECISION_LOG_DIR / f"{asof_date}.json")


def _load_council(asof_date: str) -> Dict[str, Any]:
    """
    Optional structured council output (copy-pasted from Cursor).
    Schema is intentionally loose in v1.0; record builder only attaches it.
    """
    path = COUNCIL_DIR / f"{asof_date}.json"
    return _load_json(path)


def _load_returns() -> Dict[str, OutcomeRow]:
    """
    Load market proxy returns (Option A).
    Expected columns (minimum):
        asof_date,next_week_ret,next_4w_ret,next_12w_ret
    Optional:
        drawdown_4w
    """
    out: Dict[str, OutcomeRow] = {}
    if not MARKET_RETURNS_PATH.exists():
        logger.warning("weekly_returns.csv missing at %s", MARKET_RETURNS_PATH)
        return out
    with MARKET_RETURNS_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asof = (row.get("asof_date") or "").strip()
            if not asof:
                continue
            out[asof] = OutcomeRow(
                asof_date=asof,
                next_week_ret=_parse_float(row.get("next_week_ret")),
                next_4w_ret=_parse_float(row.get("next_4w_ret")),
                next_12w_ret=_parse_float(row.get("next_12w_ret")),
                drawdown_4w=_parse_float(row.get("drawdown_4w")),
            )
    return out


def build_record(asof_date: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Build a single CPR record for a given asof_date.
    Returns (record, warnings).
    """
    warnings: List[str] = []

    decision_log = _load_decision_log(asof_date)
    if not decision_log:
        warnings.append(f"decision_log missing for {asof_date}")

    payload = _load_weekly_payload()
    if not payload:
        warnings.append("weekly_report.json payload missing or invalid")

    if payload:
        payload_asof = str(payload.get("asof_date") or "").strip()
        if payload_asof and payload_asof != asof_date:
            warnings.append(
                f"weekly_report.json asof_date={payload_asof} != requested {asof_date}"
            )

    returns = _load_returns()
    outcome_row = returns.get(asof_date)
    if not outcome_row:
        warnings.append(f"Outcome row missing in weekly_returns.csv for {asof_date}")

    # Decision snapshot: prefer weekly payload (schema-versioned),
    # fall back to decision_log for some fields if needed.
    regime = payload.get("regime") if isinstance(payload, dict) else None
    suggested = payload.get("suggested_regime") if isinstance(payload, dict) else None
    mismatch = payload.get("regime_mismatch") if isinstance(payload, dict) else None
    risk_flag = payload.get("risk_flag") if isinstance(payload, dict) else None
    gross_cap = payload.get("gross_cap") if isinstance(payload, dict) else None
    new_buys_allowed = (
        payload.get("new_buys_allowed") if isinstance(payload, dict) else None
    )
    dist = payload.get("dist_summary") if isinstance(payload, dict) else None
    breadth = payload.get("breadth_summary") if isinstance(payload, dict) else None
    portfolio_health = (
        payload.get("portfolio_health") if isinstance(payload, dict) else None
    )

    # Fallbacks from decision_log if payload missing.
    if regime is None:
        regime = decision_log.get("regime")
    if risk_flag is None:
        risk_flag = decision_log.get("risk_flag")
    if new_buys_allowed is None and isinstance(decision_log.get("new_buys_allowed"), bool):
        new_buys_allowed = decision_log.get("new_buys_allowed")
    if portfolio_health is None and isinstance(
        decision_log.get("portfolio_health"), dict
    ):
        portfolio_health = decision_log.get("portfolio_health")

    decision_snapshot: Dict[str, Any] = {
        "asof_date": asof_date,
        "payload_version": payload.get("payload_version") if isinstance(payload, dict) else None,
        "regime": regime,
        "suggested_regime": suggested,
        "mismatch": mismatch,
        "risk_flag": risk_flag,
        "gross_cap": gross_cap,
        "new_buys_allowed": new_buys_allowed,
        "dist": dist,
        "breadth": breadth,
        "portfolio_health": portfolio_health,
    }

    outcome: Dict[str, Any] = {}
    if outcome_row:
        outcome = {
            "next_week_ret": outcome_row.next_week_ret,
            "next_4w_ret": outcome_row.next_4w_ret,
            "next_12w_ret": outcome_row.next_12w_ret,
            "realized_drawdown_4w": outcome_row.drawdown_4w,
        }

    council = _load_council(asof_date)

    record: Dict[str, Any] = {
        "asof_date": asof_date,
        "decision": decision_snapshot,
        "outcome": outcome,
    }
    if council:
        record["council"] = council
    if warnings:
        record["warnings"] = warnings

    return record, warnings


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_record(record: Dict[str, Any]) -> Path:
    asof_date = record.get("asof_date") or "unknown_date"
    path = RECORDS_DIR / f"{asof_date}.json"
    _ensure_parent(path)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _row_from_record(record: Dict[str, Any]) -> Dict[str, str]:
    decision = record.get("decision") or {}
    outcome = record.get("outcome") or {}
    dist = decision.get("dist") or {}
    breadth = decision.get("breadth") or {}
    ph = decision.get("portfolio_health") or {}

    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    row: Dict[str, str] = {
        "asof_date": _fmt(decision.get("asof_date")),
        "payload_version": _fmt(decision.get("payload_version")),
        "regime": _fmt(decision.get("regime")),
        "suggested_regime": _fmt(decision.get("suggested_regime")),
        "mismatch": _fmt(decision.get("mismatch")),
        "risk_flag": _fmt(decision.get("risk_flag")),
        "gross_cap": _fmt(decision.get("gross_cap")),
        "new_buys_allowed": _fmt(decision.get("new_buys_allowed")),
        "dist_composite": _fmt(dist.get("composite")),
        "dist_vn30": _fmt(dist.get("vn30")),
        "dist_hnx": _fmt(dist.get("hnx")),
        "dist_upcom": _fmt(dist.get("upcom")),
        "dist_leader": _fmt(dist.get("proxy")),
        "vn30_trend_ok": _fmt(breadth.get("vn30_trend_ok")),
        "hnx_trend_ok": _fmt(breadth.get("hnx_trend_ok")),
        "upcom_trend_ok": _fmt(breadth.get("upcom_trend_ok")),
        "n_positions": _fmt(ph.get("n_positions")),
        "pct_below_ma20": _fmt(ph.get("pct_below_ma20")),
        "pct_sell_trim_active": _fmt(ph.get("pct_sell_trim_active")),
        "avg_r_multiple_open": _fmt(ph.get("avg_r_multiple_open")),
        "next_week_ret": _fmt(outcome.get("next_week_ret")),
        "next_4w_ret": _fmt(outcome.get("next_4w_ret")),
        "next_12w_ret": _fmt(outcome.get("next_12w_ret")),
        "drawdown_4w": _fmt(outcome.get("realized_drawdown_4w")),
    }
    return row


def _read_index() -> List[Dict[str, str]]:
    if not INDEX_PATH.exists():
        return []
    with INDEX_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _write_index(rows: List[Dict[str, str]]) -> None:
    _ensure_parent(INDEX_PATH)
    with INDEX_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in INDEX_COLUMNS})


def _upsert_index(row: Dict[str, str]) -> None:
    rows = _read_index()
    asof = row.get("asof_date")
    rows = [r for r in rows if r.get("asof_date") != asof]
    rows.append(row)
    rows.sort(key=lambda r: r.get("asof_date") or "")
    _write_index(rows)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Council Performance Review — weekly record builder (CPR v1.0)."
    )
    parser.add_argument(
        "--asof",
        default=None,
        help="YYYY-MM-DD (default: latest from decision_log/*.json)",
    )
    args = parser.parse_args(argv)

    asof = args.asof or _latest_asof_from_decision_log()
    if not asof:
        logger.error("No decision_log/*.json found; run `make weekly` first.")
        return 1

    record, warnings = build_record(asof)
    path = _write_record(record)
    row = _row_from_record(record)
    _upsert_index(row)

    logger.info("CPR record written: %s", path)
    logger.info("Index updated: %s", INDEX_PATH)
    if warnings:
        for w in warnings:
            logger.warning("Warning: %s", w)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())

