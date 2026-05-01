"""
Yahoo Finance quote page scrape for DX-Y.NYB (DXY futures on ICE; third-party proxy).

Not licensed ICE spot index. Uses HTML regex + fin-streamer fallback per weekly macro agent spec.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

YAHOO_DXY_URL = "https://finance.yahoo.com/quote/DX-Y.NYB/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _regex_price_fields(html: str) -> Tuple[Optional[float], Optional[float]]:
    price = prev = None
    m = re.search(r'"regularMarketPrice":\{"raw":([\d.]+)', html)
    if m:
        try:
            price = float(m.group(1))
        except ValueError:
            pass
    m2 = re.search(r'"regularMarketPreviousClose":\{"raw":([\d.]+)', html)
    if m2:
        try:
            prev = float(m2.group(1))
        except ValueError:
            pass
    return price, prev


def _regex_market_time_date(html: str) -> Optional[str]:
    m = re.search(r'"regularMarketTime":\{[^}]*"raw":(\d+)', html)
    if not m:
        return None
    try:
        ts = int(m.group(1))
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (ValueError, OSError):
        return None


def _bs_fallback(html: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        price = prev = None
        for tag in soup.find_all("fin-streamer"):
            if tag.get("data-symbol") != "DX-Y.NYB":
                continue
            field = tag.get("data-field")
            raw = tag.get("value")
            if raw is None:
                raw = tag.get_text(strip=True)
            if not raw:
                continue
            try:
                v = float(str(raw).replace(",", ""))
            except ValueError:
                continue
            if field == "regularMarketPrice":
                price = v
            elif field == "regularMarketPreviousClose":
                prev = v
        return price, prev
    except Exception as e:
        logger.debug("fin-streamer fallback: %s", e)
        return None, None


def fetch_dxy_yahoo_quote_page() -> Tuple[
    Optional[float],
    Optional[float],
    Optional[str],
    List[str],
]:
    """
    Returns (price, previous_close, value_date_yyyy_mm_dd, logs).
    On HTTP 429: sleep 30s, retry once with ?guccounter=1; on repeat failure return nulls + log.
    """
    import requests

    logs: List[str] = []
    url = YAHOO_DXY_URL

    for attempt in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 429:
                logs.append("yahoo_429")
                if attempt == 0:
                    time.sleep(30)
                    url = YAHOO_DXY_URL + "?guccounter=1"
                    continue
                logs.append("Yahoo 429 — manual input required")
                return None, None, None, logs
            r.raise_for_status()
            text = r.text
            price, prev = _regex_price_fields(text)
            if price is None or prev is None:
                bp, bprev = _bs_fallback(text)
                price = price or bp
                prev = prev or bprev
            vd = _regex_market_time_date(text)
            if price is None and prev is None:
                logs.append("yahoo_parse_empty")
            return price, prev, vd, logs
        except Exception as e:
            logger.warning("Yahoo DXY quote: %s", e)
            logs.append(str(e))
            return None, None, None, logs

    return None, None, None, logs


__all__ = ["YAHOO_DXY_URL", "HEADERS", "fetch_dxy_yahoo_quote_page"]
