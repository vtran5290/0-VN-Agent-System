from __future__ import annotations

"""
fireant_index_proxy
===================

Central mapping for:
- Special VN indices that do NOT exist as native index symbols in FireAnt
- Sector-style indices proxied via FireAnt /industries endpoints
- World indices that are available directly (for completeness)

This module is intended to be the SSOT for:
- report layer (weekly/daily)
- backtest/analytics when they need an index series

Only encode facts that are confirmed by FireAnt API behaviour.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class IndexProxy:
    """
    Logical index → how to fetch it from FireAnt.

    kind:
      - "symbol"      → use /symbols/{symbol}/historical-quotes
      - "etf"         → use ETF symbol via /symbols/{symbol}/historical-quotes
      - "icb"         → use /icb/{industryCode}/historical-index
      - "industry"    → use /industries/{code}/historical-stats
      - "unavailable" → not present in FireAnt; requires external source
    """

    kind: str
    code: Optional[str] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Core VN market indices: exist as native index symbols in FireAnt
# ---------------------------------------------------------------------------

VN_INDEX_PROXIES: Dict[str, IndexProxy] = {
    "VNINDEX": IndexProxy(kind="symbol", code="VNINDEX"),
    "VN30": IndexProxy(kind="symbol", code="VN30"),
    "HNXINDEX": IndexProxy(kind="symbol", code="HNXINDEX"),
    "HNX30": IndexProxy(kind="symbol", code="HNX30"),
    "UPINDEX": IndexProxy(kind="symbol", code="UPINDEX"),
}


# ---------------------------------------------------------------------------
# Special VN indices that do NOT exist as native index symbols
# → proxied via ETFs with good liquidity
# ---------------------------------------------------------------------------

VN_SPECIAL_PROXIES: Dict[str, IndexProxy] = {
    # Broad indices
    "VN100": IndexProxy(
        kind="etf",
        code="FUEVN100",
        note="VINACAPITAL VN100 ETF; VN100 not available as index symbol",
    ),
    "VNMID": IndexProxy(
        kind="etf",
        code="FUEDCMID",
        note="DCVFM VNMIDCAP ETF; VNMID index not available as symbol",
    ),
    "VNSML": IndexProxy(
        kind="unavailable",
        code=None,
        note="No dedicated ETF or index symbol in FireAnt",
    ),
    "VNALL": IndexProxy(
        kind="unavailable",
        code=None,
        note="VNALL index not present; use VNINDEX + breadth metrics instead",
    ),
    "VNXALL": IndexProxy(
        kind="unavailable",
        code=None,
        note="VNXALL not present in FireAnt",
    ),
    # Thematic / FTSE-style
    "VNDIAMOND": IndexProxy(
        kind="etf",
        code="FUEVFVND",
        note="DCVFMVN DIAMOND ETF; VN DIAMOND index itself is not exposed",
    ),
    "VNFINLEAD": IndexProxy(
        kind="etf",
        code="FUESSVFL",
        note="SSIAM VNFIN LEAD ETF; VNFINLEAD index not exposed",
    ),
    "VNFINSELECT": IndexProxy(
        kind="etf",
        code="FUEKIVFS",
        note="KIM Growth VNFINSELECT ETF; VNFINSELECT index not exposed",
    ),
    "VNX50": IndexProxy(
        kind="etf",
        code="FUESSV50",
        note="SSIAM VNX50 ETF; VNX50 index not exposed",
    ),
    # Sustainability / other HOSE-branded indices: not present
    "VNSI": IndexProxy(
        kind="unavailable",
        code=None,
        note="VNSI sustainability index not present in FireAnt REST",
    ),
    "VNDIVIDEND": IndexProxy(
        kind="unavailable",
        code=None,
        note="Dividend index not present in FireAnt REST",
    ),
    "VN50GROWTH": IndexProxy(
        kind="unavailable",
        code=None,
        note="Growth index not present in FireAnt REST",
    ),
    "VNMITECH": IndexProxy(
        kind="unavailable",
        code=None,
        note="Tech thematic index not present in FireAnt REST",
    ),
}


# ---------------------------------------------------------------------------
# Sector-style proxies via /industries/{code}/historical-stats
# (HOSE-style sector blocks; exact mapping is approximate)
# ---------------------------------------------------------------------------

VN_SECTOR_PROXIES: Dict[str, IndexProxy] = {
    # Codes 0001, 1000, ..., 9000 are confirmed in /industries
    "VNENE": IndexProxy(
        kind="industry",
        code="0001",
        note="Dầu khí; closest to Energy",
    ),
    "VNMAT": IndexProxy(
        kind="industry",
        code="1000",
        note="Vật liệu cơ bản",
    ),
    "VNIND": IndexProxy(
        kind="industry",
        code="2000",
        note="Công nghiệp",
    ),
    "VNCONS": IndexProxy(
        kind="industry",
        code="3000",
        note="Hàng tiêu dùng (staples + discretionary)",
    ),
    "VNCOND": IndexProxy(
        kind="industry",
        code="3000",
        note="Hàng tiêu dùng (staples + discretionary)",
    ),
    "VNHEAL": IndexProxy(
        kind="industry",
        code="4000",
        note="Y tế",
    ),
    "VNFIN": IndexProxy(
        kind="industry",
        code="8000",
        note="Tài chính (bao gồm ngân hàng, bảo hiểm, v.v.)",
    ),
    "VNREAL": IndexProxy(
        kind="industry",
        code="8000",
        note="No separate real-estate block in /industries; reuse Tài chính as coarse proxy",
    ),
    "VNIT": IndexProxy(
        kind="industry",
        code="9000",
        note="Công nghệ",
    ),
    "VNUTI": IndexProxy(
        kind="industry",
        code="7000",
        note="Các dịch vụ hạ tầng",
    ),
    "VNTELE": IndexProxy(
        kind="industry",
        code="6000",
        note="Viễn thông",
    ),
}


def resolve_index(name: str) -> IndexProxy:
    """
    Resolve a logical index name (VNINDEX/VN30/VN100/VNIT/...) to a proxy definition.

    If no mapping is found, returns IndexProxy(kind="unavailable").
    """
    key = name.upper().strip()
    if key in VN_INDEX_PROXIES:
        return VN_INDEX_PROXIES[key]
    if key in VN_SPECIAL_PROXIES:
        return VN_SPECIAL_PROXIES[key]
    if key in VN_SECTOR_PROXIES:
        return VN_SECTOR_PROXIES[key]
    return IndexProxy(kind="unavailable", code=None, note="No mapping defined for this index name")


__all__ = [
    "IndexProxy",
    "VN_INDEX_PROXIES",
    "VN_SPECIAL_PROXIES",
    "VN_SECTOR_PROXIES",
    "resolve_index",
]

