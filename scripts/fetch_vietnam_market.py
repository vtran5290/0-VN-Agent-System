"""
Fetch VN index levels (VNINDEX, VN30). Prefer vnstock3/vnstock; fallback FireAnt.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)

REPO_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


def _index_level_via_stock_api(symbol: str, source: str = "TCBS") -> float | None:
    """Try vnstock3 first, then vnstock. Both use .stock().quote.history()."""
    for pkg in ("vnstock3", "vnstock"):
        try:
            mod = __import__(pkg)
            Vnstock = getattr(mod, "Vnstock", None)
            if Vnstock is None:
                continue
            s = Vnstock().stock(symbol=symbol, source=source)
            df = s.quote.history(
                start=(date.today() - timedelta(days=5)).isoformat(),
                end=date.today().isoformat(),
            )
            if df is None or df.empty:
                continue
            close_col = "close" if "close" in df.columns else "Close"
            if close_col not in df.columns:
                continue
            return float(df[close_col].iloc[-1])
        except ImportError:
            continue
        except Exception as e:
            logger.warning("%s %s: %s", pkg, symbol, e)
            continue
    return None


def _vnstock_index_level(symbol: str) -> float | None:
    """Prefer vnstock3/vnstock for index level; avoids FireAnt VNI None issue."""
    return _index_level_via_stock_api(symbol)


def _fireant_index(symbol: str, asof: str) -> float | None:
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fireant_historical import fetch_historical
        end_dt = date.fromisoformat(asof)
        start = (end_dt - timedelta(days=10)).isoformat()
        rows = fetch_historical(symbol, start, asof)
        if not rows or rows[-1].c is None:
            return None
        return float(rows[-1].c)
    except Exception as e:
        logger.warning("FireAnt %s: %s", symbol, e)
        return None


def fetch_vietnam_market(asof: str | None = None) -> Dict[str, Any]:
    """
    Return {"market": {"vnindex_level", "vn30_level"}}.
    VNINDEX: vnstock then FireAnt VNI. VN30: vnstock then FireAnt VN30.
    """
    if asof is None:
        asof = date.today().isoformat()
    out: Dict[str, Any] = {"market": {}}
    vni = _vnstock_index_level("VNINDEX")
    if vni is None:
        vni = _fireant_index("VNI", asof)
    out["market"]["vnindex_level"] = vni
    vn30 = _vnstock_index_level("VN30")
    if vn30 is None:
        vn30 = _fireant_index("VN30", asof)
    out["market"]["vn30_level"] = vn30
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = fetch_vietnam_market()
    for k, v in r.get("market", {}).items():
        print(f"  {k}: {v}")
