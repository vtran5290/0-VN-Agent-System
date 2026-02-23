from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Dict, Any
import hashlib
import json
import requests
import xml.etree.ElementTree as ET

BASE = "https://www.fireant.vn/api/Data/Markets/HistoricalQuotes"
CACHE_DIR = Path("data/cache/fireant")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _cache_path(symbol: str, start: str, end: str) -> Path:
    key = f"{symbol}_{start}_{end}".encode("utf-8")
    h = hashlib.md5(key).hexdigest()
    return CACHE_DIR / f"{symbol}_{h}.xml"

@dataclass
class OHLC:
    d: str
    o: float
    h: float
    l: float
    c: float
    v: float | None = None

def fetch_historical(symbol: str, start: str, end: str, timeout: int = 20) -> List[OHLC]:
    """
    start/end format: YYYY-MM-DD
    """
    params = {"symbol": symbol, "startDate": start, "endDate": end}

    # Some sites behave oddly without headers; keep it browser-like but minimal.
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }

    cp = _cache_path(symbol, start, end)
    if cp.exists():
        text = cp.read_text(encoding="utf-8").strip()
    else:
        r = requests.get(BASE, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        text = r.text.strip()
        cp.write_text(text, encoding="utf-8")

    out: List[OHLC] = []

    # Try JSON first (FireAnt API often returns JSON)
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
            rows = data if isinstance(data, list) else data.get("data", data.get("items", []))
            for row in rows if isinstance(rows, list) else [rows]:
                if not isinstance(row, dict):
                    continue
                # Accept various key styles (Date/date, Open/open, etc.)
                d = row.get("Date") or row.get("date") or row.get("tradingDate") or ""
                o = row.get("Open") or row.get("open")
                h = row.get("High") or row.get("high")
                l_ = row.get("Low") or row.get("low")
                c = row.get("Close") or row.get("close")
                v = row.get("Volume") or row.get("Vol") or row.get("volume")
                if d is None or o is None or h is None or l_ is None or c is None:
                    continue
                d = str(d)[:10]
                out.append(OHLC(d=d, o=float(o), h=float(h), l=float(l_), c=float(c), v=float(v) if v is not None else None))
            out.sort(key=lambda x: x.d)
            return out
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Fallback: XML
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ValueError(f"API returned neither valid JSON nor XML. First 200 chars: {text[:200]!r}")

    def find_text(node, tag):
        for child in node.iter():
            if child.tag.endswith(tag):
                return child.text
        return None

    for node in root.iter():
        if node.tag.endswith("OHLC"):
            d = find_text(node, "Date")
            o = find_text(node, "Open")
            h = find_text(node, "High")
            l_ = find_text(node, "Low")
            c = find_text(node, "Close")
            v = find_text(node, "Volume") or find_text(node, "Vol")
            if not (d and o and h and l_ and c):
                continue
            out.append(
                OHLC(
                    d=d[:10],
                    o=float(o), h=float(h), l=float(l_), c=float(c),
                    v=float(v) if v is not None else None,
                )
            )

    out.sort(key=lambda x: x.d)
    return out

def latest_close(symbol: str, start: str, end: str) -> float | None:
    bars = fetch_historical(symbol, start, end)
    return bars[-1].c if bars else None
