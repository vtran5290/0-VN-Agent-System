"""
Parse SBV static HTML for Open Market Operations (OMO) auction table.

URL: nghiệp vụ thị trường mở (SBV portal).
Does not use PDFs or deprecated portal paths.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SBV_OMO_URL = (
    "https://www.sbv.gov.vn/vi/web/sbv_portal/"
    "nghi%E1%BB%87p-v%E1%BB%A5-th%E1%BB%8B-tr%C6%B0%E1%BB%9Dng-m%E1%BB%9F"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}
TIMEOUT_SEC = 30
RETRIES = 3
RETRY_DELAY_SEC = 5


def _parse_number_vn(text: str) -> Optional[float]:
    if not text:
        return None
    s = re.sub(r"\s+", "", str(text).strip())
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _parse_auction_date_vn(text: str) -> Optional[str]:
    """'Ngày 10 tháng 04 năm 2026' -> 2026-04-10."""
    m = re.search(
        r"Ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        text,
        re.I,
    )
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _tenor_days(cell: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*ngày", cell, re.I)
    if m:
        return int(m.group(1))
    return None


def parse_omo_from_soup(soup: Any) -> Dict[str, Any]:
    """
    soup: BeautifulSoup of full page.
    Returns keys: omo_value_date, omo_inject, omo_withdraw, omo_net, omo_rate, omo_breakdown, errors.
    """
    out: Dict[str, Any] = {
        "omo_value_date": None,
        "omo_inject": None,
        "omo_withdraw": None,
        "omo_net": None,
        "omo_rate": None,
        "omo_breakdown": [],
        "errors": [],
    }
    raw = soup.get_text("\n", strip=True)
    out["omo_value_date"] = _parse_auction_date_vn(raw)

    main = soup.find("main") or soup.find("article")
    scope = main if main else soup
    tables = scope.find_all("table")
    if not tables:
        tables = soup.find_all("table")
    target = None
    for t in tables:
        txt = t.get_text(" ", strip=True).lower()
        if "mua kỳ hạn" in txt or "bán kỳ hạn" in txt or "khối lượng trúng thầu" in txt:
            target = t
            break
    if target is None and tables:
        target = tables[0]

    if target is None:
        out["errors"].append("no_omo_table_found")
        return out

    mode: Optional[str] = None  # inject | withdraw
    inject_sum = 0.0
    withdraw_sum = 0.0
    rates: List[float] = []

    for tr in target.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        row_join = " ".join(cells).lower()

        if len(cells) == 1:
            t = cells[0].lower()
            if "mua kỳ hạn" in t:
                mode = "inject"
            elif "bán kỳ hạn" in t:
                mode = "withdraw"
            elif "hút tiền" in t or t.strip() == "hút kỳ hạn":
                mode = "withdraw"
            continue

        if "loại hình giao dịch" in row_join and "khối lượng" in row_join:
            continue

        if "tổng cộng" in cells[0].lower():
            continue

        if not (cells[0].strip().startswith("-") and "kỳ hạn" in cells[0].lower()):
            continue

        tenor = _tenor_days(cells[0])
        vol: Optional[float] = None
        rate: Optional[float] = None
        if len(cells) >= 4:
            vol = _parse_number_vn(cells[2])
            rate = _parse_number_vn(cells[3])
        elif len(cells) >= 3:
            vol = _parse_number_vn(cells[2])

        if vol is None:
            for c in cells[1:]:
                v = _parse_number_vn(c)
                if v is not None and v > 50:
                    vol = v
                    break
        if rate is None:
            for c in reversed(cells):
                v = _parse_number_vn(c)
                if v is not None and 0 < v <= 30:
                    rate = v
                    break

        if mode == "inject" and vol is not None:
            inject_sum += vol
        elif mode == "withdraw" and vol is not None:
            withdraw_sum += vol
        elif mode is None and vol is not None:
            out["errors"].append("omo_row_without_section_mode")

        if tenor is not None and vol is not None:
            out["omo_breakdown"].append(
                {
                    "tenor_days": tenor,
                    "volume_bn_vnd": round(vol, 2),
                    "rate_pct": round(rate, 4) if rate is not None else None,
                }
            )
        if rate is not None:
            rates.append(rate)

    out["omo_inject"] = round(inject_sum, 2) if inject_sum else None
    out["omo_withdraw"] = round(withdraw_sum, 2) if withdraw_sum else 0.0
    inj = out["omo_inject"] or 0.0
    wdr = float(out["omo_withdraw"])
    if out["omo_inject"] is not None or wdr:
        out["omo_net"] = round(inj - wdr, 2)
    if rates:
        uniq = sorted(set(round(r, 4) for r in rates))
        out["omo_rate"] = uniq[0] if len(uniq) == 1 else round(sum(rates) / len(rates), 4)
    return out


def fetch_sbv_omo_parsed() -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """HTTP GET + parse. Returns (result_dict, log_lines)."""
    logs: List[str] = []
    try:
        import requests
        from bs4 import BeautifulSoup

        with requests.Session() as s:
            for i in range(RETRIES):
                try:
                    r = s.get(SBV_OMO_URL, headers=HEADERS, timeout=TIMEOUT_SEC)
                    r.raise_for_status()
                    r.encoding = r.apparent_encoding or "utf-8"
                    if "Request Rejected" in r.text[:500]:
                        logs.append("sbv_waf_rejected")
                        return None, logs
                    soup = BeautifulSoup(r.text, "html.parser")
                    data = parse_omo_from_soup(soup)
                    if data.get("errors"):
                        logs.extend(data["errors"])
                    if data.get("omo_net") is None and not data.get("omo_breakdown"):
                        logs.append("omo_parse_empty")
                    return data, logs
                except Exception as e:
                    if i + 1 >= RETRIES:
                        raise
                    logs.append(f"retry_{i+1}:{e}")
                    time.sleep(RETRY_DELAY_SEC)
    except Exception as e:
        logger.warning("SBV OMO: %s", e)
        logs.append(str(e))
        return None, logs


__all__ = [
    "SBV_OMO_URL",
    "HEADERS",
    "parse_omo_from_soup",
    "fetch_sbv_omo_parsed",
]
