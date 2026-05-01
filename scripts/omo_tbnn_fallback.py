"""
Fallback OMO net (tỷ VND) from a public money-market article when SBV HTML has no table.

Configure:
  TBNN_OMO_ARTICLE_URL — full URL to a Thời báo Ngân hàng (or similar) article HTML.

Parser is heuristic: looks for phrases like "ròng", "bơm ròng", "hút ròng", "OMO" near a VN-formatted number.
If URL unset or parse fails, returns None with explicit reason (fail-closed).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def _parse_vn_int_ty(text: str) -> Optional[int]:
    s = re.sub(r"\s+", "", text.strip())
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").split(",")[0]
    else:
        s = s.replace(".", "")
    s = re.sub(r"[^\d\-]", "", s)
    if not s or s == "-":
        return None
    try:
        v = int(s)
        return v if abs(v) < 10_000_000 else None
    except ValueError:
        return None


def try_tbnn_omo_fallback() -> Optional[Dict[str, Any]]:
    url = (os.getenv("TBNN_OMO_ARTICLE_URL") or "").strip()
    if not url:
        return None
    try:
        import requests
        from bs4 import BeautifulSoup

        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        candidate = None
        for i, ln in enumerate(lines):
            low = ln.lower()
            if "omo" not in low and "thị trường mở" not in low and "ròng" not in low:
                continue
            # Try same line
            for m in re.finditer(r"([+-]?\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*tỷ", ln, re.I):
                v = _parse_vn_int_ty(m.group(1))
                if v is not None:
                    candidate = v
                    break
            if candidate is not None:
                break
            # Try next line
            if i + 1 < len(lines):
                v = _parse_vn_int_ty(lines[i + 1])
                if v is not None and ("ròng" in low or "omo" in low):
                    candidate = v
                    break
        if candidate is None:
            return {
                "omo_net": None,
                "verification_status": "fallback_failed",
                "source_name": "tbnn_article",
                "source_detail": url,
                "article_date": None,
                "value_date": None,
                "reason": "no_parseable_omo_number",
            }
        return {
            "omo_net": int(candidate),
            "verification_status": "fallback_used",
            "source_name": "ThoiBaoNganHang_article",
            "source_detail": url,
            "article_date": None,
            "value_date": None,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as e:
        logger.warning("TBNN OMO fallback: %s", e)
        return {
            "omo_net": None,
            "verification_status": "fallback_failed",
            "source_name": "tbnn_article",
            "source_detail": url,
            "reason": str(e),
        }
