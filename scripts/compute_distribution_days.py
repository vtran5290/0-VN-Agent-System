"""
Distribution days from OHLC: Close < Previous Close AND Volume > Previous Volume.
Rolling 20-day count. VN30 as proxy. No vendor lock-in; pure math.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

REPO_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
LB = 20


def _ohlc_vn30(asof: str, days: int = 35) -> List[tuple]:
    """Return list of (close, volume) last-first. Prefer FireAnt (project standard)."""
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fireant_historical import fetch_historical
        end_dt = date.fromisoformat(asof)
        start = (end_dt - timedelta(days=days)).isoformat()
        rows = fetch_historical("VN30", start, asof)
        if not rows or len(rows) < LB + 1:
            return []
        out = []
        for r in rows:
            c = getattr(r, "c", None)
            v = getattr(r, "v", None)
            if c is not None and v is not None:
                out.append((float(c), float(v)))
            elif c is not None:
                out.append((float(c), 0.0))
            else:
                return []
        return out
    except Exception as e:
        logger.warning("OHLC VN30: %s", e)
        return []


def distribution_days_rolling_20(close_vol: List[tuple]) -> int:
    """Count days in last LB where close < prev close and volume > prev volume."""
    if len(close_vol) < LB + 1:
        return 0
    window = close_vol[-(LB + 1) :]
    cnt = 0
    for i in range(1, len(window)):
        c0, v0 = window[i - 1]
        c1, v1 = window[i]
        if c1 < c0 and v1 > v0:
            cnt += 1
    return cnt


def compute_distribution_days(asof: str | None = None) -> Dict[str, Any]:
    """Return {"market": {"distribution_days_rolling_20": int, "dist_proxy_symbol": "VN30"}}."""
    if asof is None:
        asof = date.today().isoformat()
    out: Dict[str, Any] = {"market": {"dist_proxy_symbol": "VN30"}}
    cv = _ohlc_vn30(asof)
    if not cv:
        out["market"]["distribution_days_rolling_20"] = None
        return out
    out["market"]["distribution_days_rolling_20"] = distribution_days_rolling_20(cv)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = compute_distribution_days()
    print("  distribution_days_rolling_20:", r["market"].get("distribution_days_rolling_20"))
    print("  dist_proxy_symbol:", r["market"].get("dist_proxy_symbol"))
