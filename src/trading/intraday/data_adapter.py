"""FireAnt intraday quote adapter (read-only, no EOD panel writes)."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from src.data.fireant_client import FireAntClient, RESTV2_BASE, _BROWSER_HEADERS, _load_token
from src.trading.intraday.schema import INTRADAY_QUOTE_COLUMNS, IntradayQuote
from src.trading.intraday.session import detect_session_phase, now_hcm

logger = logging.getLogger(__name__)

_CANDIDATE_QUOTE_PATHS = [
    "/symbols/{symbol}/quotes",
    "/symbols/{symbol}/quote",
    "/symbols/{symbol}/priceboard",
    "/markets/quotes",
    "/markets/priceboard",
]


def _probe_url(path: str, symbol: str, headers: Dict[str, str], timeout: int = 12) -> Dict[str, Any]:
    url = f"{RESTV2_BASE}{path.format(symbol=symbol)}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        body_preview = r.text[:400] if r.text else ""
        ok_json = False
        parsed = None
        if r.status_code == 200:
            try:
                parsed = r.json()
                ok_json = True
            except json.JSONDecodeError:
                ok_json = False
        return {
            "url": url,
            "status": r.status_code,
            "ok_json": ok_json,
            "summary": _summarize_payload(parsed),
            "body_preview": body_preview,
        }
    except requests.RequestException as exc:
        return {"url": url, "status": None, "error": str(exc)}


def _summarize_payload(data: Any) -> str:
    if data is None:
        return "null"
    if isinstance(data, list):
        return f"list[{len(data)}]"
    if isinstance(data, dict):
        return f"dict keys={list(data.keys())[:20]}"
    return type(data).__name__


def detect_intraday_source_capability(
    symbols: Optional[List[str]] = None,
    *,
    save_probe_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Probe FireAnt for intraday-capable endpoints (read-only, limited symbols).
    """
    symbols = symbols or ["HPG", "VPB", "FPT"]
    token = _load_token(None)
    today = now_hcm().strftime("%Y-%m-%d")
    result: Dict[str, Any] = {
        "timestamp": now_hcm().isoformat(),
        "source": "FireAnt",
        "token_present": bool(token),
        "partial_daily_bar": {"available": False, "detail": ""},
        "dedicated_quote_endpoint": {"available": False, "detail": "", "probes": []},
        "available": False,
        "recommended_method": None,
        "latency": "unknown",
    }

    if not token:
        result["partial_daily_bar"]["detail"] = "FIREANT_TOKEN missing"
        result["dedicated_quote_endpoint"]["detail"] = "skipped — no token"
        if save_probe_path:
            save_probe_path.parent.mkdir(parents=True, exist_ok=True)
            save_probe_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    headers = {**_BROWSER_HEADERS, "Authorization": f"Bearer {token}"}
    client = FireAntClient(token=token)

    # 1) Partial daily bar via historical-quotes (today only)
    sym = symbols[0]
    try:
        df = client.get_ohlcv(sym, today, today)
        if not df.empty:
            row = df.iloc[-1]
            result["partial_daily_bar"] = {
                "available": True,
                "detail": f"historical-quotes returned {len(df)} row(s) for {sym} on {today}",
                "sample": {
                    "symbol": sym,
                    "date": str(row["date"])[:10],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                },
            }
            result["available"] = True
            result["recommended_method"] = "historical_quotes_partial_daily"
            result["latency"] = "delayed_or_eod_aggregated_unknown"
        else:
            result["partial_daily_bar"]["detail"] = f"empty historical-quotes for {sym} {today}"
    except Exception as exc:
        result["partial_daily_bar"]["detail"] = f"error: {exc}"

    # 2) Candidate dedicated endpoints (404-safe)
    probes = []
    for path in _CANDIDATE_QUOTE_PATHS[:3]:
        probes.append(_probe_url(path, sym, headers))
        time.sleep(0.2)
    result["dedicated_quote_endpoint"]["probes"] = probes
    ok_probe = next((p for p in probes if p.get("status") == 200 and p.get("ok_json")), None)
    if ok_probe:
        result["dedicated_quote_endpoint"]["available"] = True
        result["dedicated_quote_endpoint"]["detail"] = ok_probe["url"]
        result["available"] = True
        result["recommended_method"] = "dedicated_quote_endpoint"
    else:
        result["dedicated_quote_endpoint"]["detail"] = "no 200 JSON on probed paths"

    if save_probe_path:
        save_probe_path.parent.mkdir(parents=True, exist_ok=True)
        save_probe_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def _row_to_quote(symbol: str, row: pd.Series, *, source: str, ts: datetime, stale_sec: float) -> IntradayQuote:
    last = float(row.get("close") or row.get("last_price_kvnd") or 0)
    vol = row.get("volume")
    vol_f = float(vol) if vol is not None and not pd.isna(vol) else None
    quote_ts = str(row.get("timestamp") or ts.isoformat())
    try:
        qdt_raw = pd.Timestamp(quote_ts)
        date_only = len(quote_ts.strip()) <= 10 or (
            qdt_raw.hour == 0 and qdt_raw.minute == 0 and qdt_raw.second == 0
        )
    except Exception:
        date_only = len(quote_ts.strip()) <= 10
    try:
        qdt = pd.Timestamp(quote_ts)
        if date_only:
            # Partial daily bar has no intraday timestamp — do not treat as stale.
            qdt = ts
            latency = 0.0
        else:
            if qdt.tzinfo is None and ts.tzinfo is not None:
                qdt = qdt.tz_localize(ts.tzinfo)
            elif qdt.tzinfo is not None and ts.tzinfo is not None:
                qdt = qdt.tz_convert(ts.tzinfo)
            qdt = qdt.to_pydatetime()
            latency = (ts - qdt).total_seconds()
    except Exception:
        qdt = ts
        latency = 0.0
    is_stale = (not date_only) and abs(latency) > stale_sec
    phase = detect_session_phase(ts)
    dq = "STALE" if is_stale else "OK"
    if last <= 0:
        dq = "MISSING_PRICE"
    if vol_f is None or vol_f <= 0:
        dq = "MISSING_VOLUME" if dq == "OK" else dq
    return IntradayQuote(
        symbol=symbol.upper(),
        exchange=str(row.get("exchange") or "HOSE"),
        timestamp=quote_ts,
        source=source,
        source_latency_sec=round(latency, 1),
        last_price_kvnd=last if last > 0 else None,
        open_price_kvnd=_f(row, "open", "open_price_kvnd"),
        high_price_kvnd=_f(row, "high", "high_price_kvnd"),
        low_price_kvnd=_f(row, "low", "low_price_kvnd"),
        cumulative_volume=vol_f,
        cumulative_value_vnd=_f(row, "value", "cumulative_value_vnd"),
        data_quality=dq,
        is_stale=is_stale,
        is_intraday=True,
        session_phase=phase,
        raw_fields={k: row[k] for k in row.index if k not in INTRADAY_QUOTE_COLUMNS},
    )


def _f(row: pd.Series, *keys: str) -> Optional[float]:
    for k in keys:
        if k in row and row[k] is not None and not pd.isna(row[k]):
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    return None


def fetch_intraday_quote(
    symbol: str,
    *,
    client: Optional[FireAntClient] = None,
    stale_threshold_sec: float = 300,
) -> dict:
    sym = symbol.upper().strip()
    ts = now_hcm()
    today = ts.strftime("%Y-%m-%d")
    client = client or FireAntClient()
    df = client.get_ohlcv(sym, today, today)
    if df.empty:
        return IntradayQuote(
            symbol=sym,
            timestamp=ts.isoformat(),
            source="FireAnt",
            data_quality="SOURCE_UNAVAILABLE",
            session_phase=detect_session_phase(ts),
        ).to_dict()
    row = df.iloc[-1].copy()
    row["timestamp"] = str(row["date"])
    q = _row_to_quote(sym, row, source="FireAnt", ts=ts, stale_sec=stale_threshold_sec)
    return q.to_dict()


def fetch_intraday_quotes(
    symbols: List[str],
    *,
    stale_threshold_sec: float = 300,
    delay_sec: float = 0.15,
) -> pd.DataFrame:
    client = FireAntClient()
    rows = []
    for sym in symbols:
        rows.append(
            fetch_intraday_quote(sym, client=client, stale_threshold_sec=stale_threshold_sec)
        )
        time.sleep(delay_sec)
    return validate_intraday_quotes(pd.DataFrame(rows))


def validate_intraday_quotes(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=INTRADAY_QUOTE_COLUMNS)
    out = df.copy()
    for col in INTRADAY_QUOTE_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out["symbol"] = out["symbol"].astype(str).str.upper()
    if "data_quality" not in out.columns:
        out["data_quality"] = "OK"
    mask_no_price = out["last_price_kvnd"].isna() | (out["last_price_kvnd"] <= 0)
    out.loc[mask_no_price, "data_quality"] = out.loc[mask_no_price, "data_quality"].replace(
        {"OK": "MISSING_PRICE"}
    )
    return out[INTRADAY_QUOTE_COLUMNS + [c for c in out.columns if c not in INTRADAY_QUOTE_COLUMNS]]
