"""
Fetch Vietnam liquidity from SBV (OMO, interbank overnight, credit growth, FX).
No API — scrape HTML with requests + BeautifulSoup. See docs/SBV_LIQUIDITY_SOURCES.md.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
REPO_ROOT = str(Path(__file__).resolve().parent.parent)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}
TIMEOUT = 30
RETRIES = 3
RETRY_DELAY_SEC = 5

# SBV URLs (decoded paths for reference: nghiep-vu-thi-truong-mo, lai-suat1, du-no-tin-dung..., ty-gia)
URL_OMO = "https://www.sbv.gov.vn/vi/web/sbv_portal/nghi%E1%BB%87p-v%E1%BB%A5-th%E1%BB%8B-tr%C6%B0%E1%BB%9Dng-m%E1%BB%9F"
URL_INTERBANK = "https://www.sbv.gov.vn/vi/l%C3%A3i-su%E1%BA%A5t1"
URL_CREDIT = "https://www.sbv.gov.vn/vi/du-no-tin-dung-doi-voi-nen-kt-dttktt"
URL_FX = "https://www.sbv.gov.vn/vi/t%E1%BB%B7-gi%C3%A1"


def _get_soup(url: str) -> Optional[Any]:
    try:
        import requests
        from bs4 import BeautifulSoup

        with requests.Session() as s:
            for i in range(RETRIES):
                try:
                    r = s.get(url, headers=HEADERS, timeout=TIMEOUT)
                    r.raise_for_status()
                    r.encoding = r.apparent_encoding or "utf-8"
                    return BeautifulSoup(r.text, "html.parser")
                except Exception:
                    if i + 1 >= RETRIES:
                        raise
                    time.sleep(RETRY_DELAY_SEC)
    except Exception as e:
        logger.warning("SBV fetch %s: %s", url[:50], e)
        return None


def _parse_number_vn(text: str) -> Optional[float]:
    """Parse Vietnamese number: 1.000,00 = 1000 (dot=thousands, comma=decimal)."""
    if not text:
        return None
    s = re.sub(r"\s+", "", str(text).strip())
    if "," in s:
        # VN format: 3.000,00 -> remove dots then comma to dot
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_omo_net() -> Optional[int]:
    """OMO net (tỷ đồng). Mua = inject, Bán/Hút = withdraw. Uses `src.intake.sbv_omo_scrape`."""
    try:
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.sbv_omo_scrape import fetch_sbv_omo_parsed

        data, _logs = fetch_sbv_omo_parsed()
        if not data:
            return None
        n = data.get("omo_net")
        if n is None:
            return None
        return int(round(float(n)))
    except Exception as e:
        logger.warning("OMO parse: %s", e)
        return None


def _fetch_interbank_on() -> Optional[float]:
    """Interbank overnight rate (%). Row 'Qua đêm' in table."""
    soup = _get_soup(URL_INTERBANK)
    if not soup:
        return None
    try:
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                texts = [c.get_text(strip=True) for c in tds]
                if not texts:
                    continue
                if "qua đêm" in texts[0].lower() or "overnight" in texts[0].lower():
                    for i, t in enumerate(texts[1:], 1):
                        val = _parse_number_vn(t)
                        if val is not None and 0 <= val <= 30:
                            return round(val, 2)
                    break
        return None
    except Exception as e:
        logger.warning("Interbank parse: %s", e)
        return None


def _fetch_credit_growth_yoy() -> Optional[float]:
    """Credit growth (%). SBV reports YTD vs end of prior year — stored as credit_growth_yoy in pipeline."""
    soup = _get_soup(URL_CREDIT)
    if not soup:
        return None
    try:
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                texts = [c.get_text(strip=True) for c in tds]
                if any("tổng cộng" in t.lower() for t in texts):
                    for t in texts:
                        val = _parse_number_vn(t)
                        if val is not None and -50 <= val <= 100:
                            return round(val, 2)
                    break
        return None
    except Exception as e:
        logger.warning("Credit growth parse: %s", e)
        return None


def _fetch_fx_usd_vnd() -> Optional[int]:
    """USD/VND central rate (integer). Row '1 Đô la Mỹ'. SBV may show 25.065 = 25065 VND."""
    soup = _get_soup(URL_FX)
    if not soup:
        return None
    try:
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                texts = [c.get_text(strip=True) for c in tds]
                row_str = " ".join(texts).lower()
                if "đô la" in row_str or "usd" in row_str or "dollar" in row_str:
                    for t in texts:
                        val = _parse_number_vn(t)
                        if val is None:
                            continue
                        if 20_000 <= val <= 30_000:
                            return int(round(val))
                        if 20 <= val <= 30:
                            return int(round(val * 1000))
        return None
    except Exception as e:
        logger.warning("FX parse: %s", e)
        return None


def fetch_vietnam_liquidity(asof: str | None = None) -> Dict[str, Any]:
    """
    Return vietnam liquidity plus _omo_provenance for auditing (SBV primary, optional TBNN article fallback).

    Set TBNN_OMO_ARTICLE_URL to a public money-market article URL when SBV OMO table is missing from static HTML.
    Partial data on failure; never raise. asof unused (SBV pages are point-in-time).
    """
    omo_net = _fetch_omo_net()
    omo_prov: Dict[str, Any]
    if omo_net is not None:
        omo_prov = {
            "verification_status": "parsed",
            "source_detail": "SBV nghiệp vụ thị trường mở (HTML scrape)",
            "chosen_source": "sbv",
        }
    else:
        try:
            from scripts.omo_tbnn_fallback import try_tbnn_omo_fallback
        except ImportError:
            try_tbnn_omo_fallback = None  # type: ignore[assignment]
        fb = try_tbnn_omo_fallback() if try_tbnn_omo_fallback else None
        if fb and fb.get("omo_net") is not None:
            omo_net = int(fb["omo_net"])
            omo_prov = {
                "verification_status": str(fb.get("verification_status") or "fallback_used"),
                "source_detail": str(fb.get("source_detail") or ""),
                "source_name": fb.get("source_name"),
                "article_date": fb.get("article_date"),
                "value_date": fb.get("value_date"),
                "chosen_source": "tbnn_article",
            }
        elif isinstance(fb, dict):
            omo_prov = {
                "verification_status": str(fb.get("verification_status") or "fallback_failed"),
                "source_detail": str(fb.get("source_detail") or fb.get("reason") or ""),
                "chosen_source": "tbnn_article",
            }
        else:
            omo_prov = {
                "verification_status": "primary_missing",
                "source_detail": "SBV OMO table not available in static HTML; optional: TBNN_OMO_ARTICLE_URL for article fallback",
                "chosen_source": "sbv",
            }

    out: Dict[str, Any] = {
        "vietnam": {
            "omo_net": omo_net,
            "interbank_on": _fetch_interbank_on(),
            "credit_growth_yoy": _fetch_credit_growth_yoy(),
            "fx_usd_vnd": _fetch_fx_usd_vnd(),
        },
        "_omo_provenance": omo_prov,
    }
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    r = fetch_vietnam_liquidity()
    print(json.dumps(r, indent=2, ensure_ascii=False))
