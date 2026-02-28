"""
Update data/raw/tech_status.json from portfolio tickers: close_below_ma20, day1_trigger, day2_trigger.
TODO: r_multiple (requires entry & stop per position). TODO: sector from manual mapping file.
Pure OHLC math; no broker scraping.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.safe_json_io import atomic_write_json, safe_read_json

logger = logging.getLogger(__name__)

TECH_STATUS_PATH = REPO_ROOT / "data" / "raw" / "tech_status.json"
WATCHLIST_PATH = REPO_ROOT / "data" / "raw" / "watchlist.json"
MA_PERIOD = 20


def _ohlc_for(symbol: str, asof: str, days: int = 30) -> List[tuple]:
    """Return [(date, close), ...] newest last. FireAnt."""
    try:
        from src.intake.fireant_historical import fetch_historical
        end_dt = date.fromisoformat(asof)
        start = (end_dt - timedelta(days=days)).isoformat()
        rows = fetch_historical(symbol, start, asof)
        if not rows:
            return []
        out = []
        for r in rows:
            c = getattr(r, "c", None)
            d = getattr(r, "d", None)
            if c is not None and d:
                out.append((d, float(c)))
        return out
    except Exception as e:
        logger.warning("OHLC %s: %s", symbol, e)
        return []


def _ma20(closes: List[float]) -> float | None:
    if len(closes) < MA_PERIOD:
        return None
    return sum(closes[-MA_PERIOD:]) / MA_PERIOD


def evaluate_ticker(symbol: str, asof: str) -> Dict[str, Any]:
    """One row for tech_status.tickers: close_below_ma, day1_trigger, day2_trigger. tier/r_multiple/sector = TODO."""
    row: Dict[str, Any] = {
        "ticker": symbol,
        "tier": None,
        "close_below_ma": False,
        "day1_trigger": False,
        "day2_trigger": False,
        "r_multiple": None,
        "sector": None,
        "notes": "",
    }
    ohlc = _ohlc_for(symbol, asof)
    if len(ohlc) < MA_PERIOD + 2:
        return row
    closes = [c for _, c in ohlc]
    ma = _ma20(closes)
    if ma is None:
        return row
    last_c = closes[-1]
    row["close_below_ma"] = last_c < ma
    row["day1_trigger"] = last_c < ma
    prev_c = closes[-2] if len(closes) >= 2 else None
    row["day2_trigger"] = prev_c is not None and prev_c < _ma20(closes[:-1]) and last_c < ma
    return row


def run(asof: str | None, portfolio_tickers: List[str] | None = None) -> None:
    if asof is None:
        asof = date.today().isoformat()
    if not portfolio_tickers:
        wl = safe_read_json(WATCHLIST_PATH)
        portfolio_tickers = wl.get("tickers", [])
    if not portfolio_tickers:
        logger.warning("No tickers; tech_status unchanged.")
        return
    tickers = [evaluate_ticker(s, asof) for s in portfolio_tickers]
    payload = {"asof_date": asof, "tickers": tickers}
    atomic_write_json(TECH_STATUS_PATH, payload)
    logger.info("Updated %s with %d tickers", TECH_STATUS_PATH, len(tickers))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None)
    ap.add_argument("--tickers", nargs="*", help="Override portfolio tickers")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.asof, getattr(args, "tickers", None) or None)
