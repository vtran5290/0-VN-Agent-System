"""
Open positions hygiene: facts-only snapshot for weekly review.
r_multiple missing rate, stop missing rate, tier coverage, sector concentration, regime compliance.
Useful when n_closed=0 (no lesson from exits yet).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR, RAW_DIR, REPO
from .trade_build_input import TRADE_REVIEW_INPUT_PATH

logger = logging.getLogger(__name__)

TECH_STATUS_PATH = RAW_DIR / "tech_status.json"
OPEN_HYGIENE_PATH = DECISION_DIR / "open_positions_hygiene.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_open_hygiene(input_path: Optional[Path] = None, out_path: Optional[Path] = None) -> Path:
    """
    Read trade_review_input.json positions_open + tech_status; write open_positions_hygiene.json.
    Facts-only: portfolio_hygiene + regime_compliance.
    """
    p = input_path or TRADE_REVIEW_INPUT_PATH
    if not p.exists():
        logger.debug("No trade_review_input.json; skip open hygiene")
        out_path = out_path or OPEN_HYGIENE_PATH
        payload = {"asof_date": "", "portfolio_hygiene": {}, "regime_compliance": {}, "notes": ["No input; run build-input first."]}
        DECISION_DIR.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return out_path

    data = _load_json(p)
    positions = data.get("positions_open") or []
    tech_status = _load_json(TECH_STATUS_PATH)
    tickers_tech = {str(t.get("ticker", "")).upper(): t for t in (tech_status.get("tickers") or []) if isinstance(t, dict)}

    n = len(positions)
    if n == 0:
        payload = {
            "asof_date": data.get("asof_date", ""),
            "portfolio_hygiene": {"n_positions": 0, "r_multiple_missing_rate": None, "stop_missing_rate": None, "tier_coverage": {}, "sector_concentration": {}},
            "regime_compliance": {"risk_flag_now": None, "dist_days_20_now": None},
            "notes": [],
        }
    else:
        r_missing = sum(1 for pos in positions if pos.get("r_multiple") is None)
        stop_missing = sum(1 for pos in positions if pos.get("stop_price") is None)
        tiers: Dict[str, int] = {}
        sectors: Dict[str, int] = {}
        for pos in positions:
            ticker = (pos.get("ticker") or "").upper()
            t = tickers_tech.get(ticker) or {}
            tier = t.get("tier")
            if tier is not None:
                key = f"tier_{tier}"
                tiers[key] = tiers.get(key, 0) + 1
            sector = t.get("sector") or "Unknown"
            sectors[sector] = sectors.get(sector, 0) + 1

        ctx = (positions[0].get("context") or {}) if positions else {}
        payload = {
            "asof_date": data.get("asof_date", ""),
            "portfolio_hygiene": {
                "n_positions": n,
                "r_multiple_missing_rate": round(r_missing / n, 4) if n else None,
                "stop_missing_rate": round(stop_missing / n, 4) if n else None,
                "tier_coverage": tiers,
                "sector_concentration": sectors,
            },
            "regime_compliance": {
                "risk_flag_now": ctx.get("risk_flag_now"),
                "dist_days_20_now": ctx.get("dist_days_20_now"),
            },
            "notes": [],
        }

    out_path = out_path or OPEN_HYGIENE_PATH
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (n_positions=%d)", out_path.name, n)
    return out_path
