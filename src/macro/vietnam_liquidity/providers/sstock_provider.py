from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..models import VIETNAM_LIQUIDITY_FIELDS, VietnamFieldProvenance, VietnamLiquidityFacts


SSOCKT_GENERAL_ENDPOINT = "https://api-feature.sstock.vn/api/v1/chart/general-data-series"


@dataclass(frozen=True)
class SStockAuth:
    cookie_header: Optional[str]  # raw Cookie header value (e.g. better-auth.session-token=...)
    better_auth_token: Optional[str]  # token value injected as better-auth.session-token


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat() + "Z"


def _read_auth_from_env() -> SStockAuth:
    # User guidance mentions session cookie / better-auth session.
    # We keep names flexible to avoid hardcoding to a single env var.
    token = os.getenv("SSOCKT_SESSION_TOKEN") or os.getenv("SSTOCK_SESSION_TOKEN") or None
    cookie = os.getenv("SSOCKT_COOKIE") or os.getenv("SSTOCK_COOKIE") or None

    # If only token exists, we inject it into better-auth cookie name.
    if token and not cookie:
        cookie_header = f"better-auth.session-token={token}"
        return SStockAuth(cookie_header=cookie_header, better_auth_token=token)

    return SStockAuth(cookie_header=cookie, better_auth_token=token)


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.strip()
            if x == "":
                return None
        v = float(x)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def _normalize_field_value(field: str, v: float) -> Any:
    """
    Normalize to repo expectations:
      - omo_net: int (tỷ VND)
      - interbank_on: float (percent; 2 decimals)
      - credit_growth_yoy: float (percent; 2 decimals)
      - fx_usd_vnd: int
    """
    if field in ("omo_net", "fx_usd_vnd"):
        return int(round(v))
    if field in ("interbank_on", "credit_growth_yoy"):
        return round(float(v), 2)
    return v


def _extract_latest_point_from_series_item(
    item: Dict[str, Any], *, asof: _dt.date
) -> Optional[Tuple[str, float]]:
    """
    Best-effort extraction:
      - find a date field in point list-like structures
      - take the latest point with date <= asof
    Returns (date_iso_YYYY-MM-DD, value_float).
    """
    # Common candidates for points list.
    for points_key in ("data", "values", "series", "points"):
        points = item.get(points_key)
        if not isinstance(points, list):
            continue
        latest_val: Optional[Tuple[str, float]] = None
        for p in points:
            if not isinstance(p, dict):
                continue
            date_raw = p.get("date") or p.get("day") or p.get("time") or p.get("timestamp")
            if date_raw is None:
                continue
            try:
                # Allow yyyy-mm-dd or ISO-like.
                date_str = str(date_raw)[:10]
                d = _dt.date.fromisoformat(date_str)
            except Exception:
                continue
            if d > asof:
                continue
            val_raw = p.get("value") if "value" in p else (p.get("y") if "y" in p else p.get("v"))
            val = _safe_float(val_raw)
            if val is None:
                continue
            if latest_val is None or d >= _dt.date.fromisoformat(latest_val[0]):
                latest_val = (date_str, val)
        if latest_val is not None:
            return latest_val
    return None


def _label_matches_field(label: str, field: str) -> bool:
    l = (label or "").lower()
    if field == "omo_net":
        keywords = ["omo", "nghiệp vụ thị trường mở", "open market operation", "omo net"]
    elif field == "interbank_on":
        keywords = ["interbank", "overnight", "qua đêm", "on", "liên ngân hàng"]
    elif field == "fx_usd_vnd":
        keywords = ["usd/vnd", "usd", "fx", "tỷ giá", "tien te", "foreign exchange", "đô la"]
    elif field == "credit_growth_yoy":
        keywords = ["credit", "tín dụng", "tăng trưởng tín dụng", "growth", "yoy", "ytd", "tốc độ tăng"]
    else:
        keywords = [field]
    return any(k.lower() in l for k in keywords)


def _extract_fields_from_response(response_json: Any, *, asof: _dt.date) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Return:
      - facts: {field: value|None}
      - series_names_used: {field: matched_series_label}
    """
    facts: Dict[str, Any] = {f: None for f in VIETNAM_LIQUIDITY_FIELDS}
    used_labels: Dict[str, str] = {}

    # Try to find series items inside response.
    candidates: List[Any] = []
    if isinstance(response_json, dict):
        for k in ("data", "items", "series", "result", "chart", "payload"):
            v = response_json.get(k)
            if isinstance(v, list):
                candidates.extend(v)
        # Also consider response_json itself as iterable container.
        if isinstance(response_json.get("data"), list):
            candidates.extend(response_json["data"])
    elif isinstance(response_json, list):
        candidates = response_json

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        # Identify series label.
        label = (
            cand.get("name")
            or cand.get("seriesName")
            or cand.get("title")
            or cand.get("label")
            or cand.get("key")
            or cand.get("seriesCode")
            or cand.get("code")
        )
        if not label:
            continue
        for field in VIETNAM_LIQUIDITY_FIELDS:
            if facts[field] is not None:
                continue
            if _label_matches_field(str(label), field):
                latest = _extract_latest_point_from_series_item(cand, asof=asof)
                if latest is not None:
                    date_iso, val = latest
                    facts[field] = _normalize_field_value(field, float(val))
                    used_labels[field] = str(label)
                else:
                    # As a last resort, if item has a direct numeric value.
                    direct = _safe_float(cand.get("value") or cand.get("latest") or cand.get(field))
                    if direct is not None:
                        facts[field] = _normalize_field_value(field, float(direct))
                        used_labels[field] = str(label)

    return facts, used_labels


def fetch_vietnam_liquidity_sstock(
    *,
    asof: str,
    session_cookie: Optional[str] = None,
    session_token: Optional[str] = None,
    timeout_s: int = 30,
) -> VietnamLiquidityFacts:
    """
    Experimental SStock provider.
    Non-authenticated calls are expected to fail (better-auth); we must fail gracefully.
    """
    asof_date = _dt.date.fromisoformat(asof[:10])
    auth = _read_auth_from_env()
    cookie_header = session_cookie or auth.cookie_header

    if not cookie_header:
        # Auth missing; return null facts and explicit verification status.
        meta = {}
        for f in VIETNAM_LIQUIDITY_FIELDS:
            meta[f] = VietnamFieldProvenance(
                field=f,
                chosen_source="sstock",
                existing_source=None,
                sstock_source="sstock",
                series_name=None,
                as_of=asof,
                fetched_at=_now_iso(),
                verification_status="auth_missing",
            )
        return VietnamLiquidityFacts(values={f: None for f in VIETNAM_LIQUIDITY_FIELDS}, meta=meta, errors=["SSOCKT auth missing"])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://sstock.vn",
        "Referer": "https://sstock.vn/",
        "Cookie": cookie_header,
    }

    # Best-effort request body: we try field ids as seriesCodes.
    # If SStock expects different keys, parsing will fail and we return nulls.
    request_bodies = [
        {"seriesCodes": VIETNAM_LIQUIDITY_FIELDS},
        {"series": VIETNAM_LIQUIDITY_FIELDS},
        {"from": asof, "to": asof, "series": VIETNAM_LIQUIDITY_FIELDS},
        {"from": asof, "to": asof, "seriesCodes": VIETNAM_LIQUIDITY_FIELDS},
    ]

    errors: List[str] = []
    latest_facts: Dict[str, Any] = {f: None for f in VIETNAM_LIQUIDITY_FIELDS}
    latest_labels: Dict[str, str] = {}

    with requests.Session() as sess:
        for body in request_bodies:
            try:
                r = sess.post(SSOCKT_GENERAL_ENDPOINT, headers=headers, timeout=timeout_s, json=body)
                if r.status_code != 200:
                    errors.append(f"sstock_status_{r.status_code}")
                    continue
                payload = r.json()
                facts, used_labels = _extract_fields_from_response(payload, asof=asof_date)
                # If at least one field parsed, accept this payload.
                if any(v is not None for v in facts.values()):
                    latest_facts = facts
                    latest_labels = used_labels
                    break
            except Exception as e:
                errors.append(f"sstock_request_failed:{type(e).__name__}")

    meta: Dict[str, VietnamFieldProvenance] = {}
    for f in VIETNAM_LIQUIDITY_FIELDS:
        meta[f] = VietnamFieldProvenance(
            field=f,
            chosen_source="sstock",
            existing_source=None,
            sstock_source="sstock",
            series_name=latest_labels.get(f),
            as_of=asof,
            fetched_at=_now_iso(),
            verification_status="parsed" if latest_facts.get(f) is not None else "request_failed_or_missing",
        )
    return VietnamLiquidityFacts(values=latest_facts, meta=meta, errors=errors)


__all__ = ["fetch_vietnam_liquidity_sstock"]

