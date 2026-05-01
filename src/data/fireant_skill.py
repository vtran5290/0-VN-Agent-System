from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from src.data.fireant_client import get_client


logger = logging.getLogger(__name__)


def _ok(mode: str, data: Any, warnings: List[str] | None = None) -> Dict[str, Any]:
    return {
        "status": "ok",
        "mode": mode,
        "data": data,
        "warnings": warnings or [],
        "errors": [],
    }


def _err(mode: str, errors: List[str], data: Any = None) -> Dict[str, Any]:
    return {
        "status": "error",
        "mode": mode,
        "data": data if data is not None else _empty_data(mode),
        "warnings": [],
        "errors": errors,
    }


def _empty_data(mode: str) -> Any:
    if mode == "ohlcv":
        return {}
    if mode == "fundamentals":
        return {}
    if mode == "universe":
        return {"symbols": [], "details": []}
    if mode == "macro":
        return {"market": {}}
    if mode == "rs":
        return {"ratings": []}
    return {}


def _df_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    df = df.copy()
    for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]):
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def _handle_ohlcv(params: Dict[str, Any], client) -> Dict[str, Any]:
    symbols = params.get("symbols") or []
    start = params.get("start")
    end = params.get("end") or datetime.today().strftime("%Y-%m-%d")
    resolution = str(params.get("resolution", "D")).upper()

    if not symbols:
        return _err("ohlcv", ["'symbols' list is required"])
    if not start:
        return _err("ohlcv", ["'start' date is required"])

    all_warnings: List[str] = []
    result: Dict[str, List[Dict[str, Any]]] = {}
    for sym in symbols:
        df = client.get_ohlcv(sym, start, end, timeframe=resolution)
        result[sym] = _df_to_records(df)
        all_warnings.extend(
            f"{sym}: {w}" for w in df.attrs.get("warnings", []) if df.attrs.get("warnings")
        )

    return _ok("ohlcv", result, all_warnings)


def _handle_fundamentals(params: Dict[str, Any], client) -> Dict[str, Any]:
    symbols = params.get("symbols") or []
    n_quarters = int(params.get("n_quarters", 6))
    n_years = int(params.get("n_years", 4))
    mode_sub = str(params.get("sub_mode", "quarterly")).lower()  # "quarterly"|"annual"|"both"

    if not symbols:
        return _err("fundamentals", ["'symbols' list is required"])

    all_warnings: List[str] = []
    result: Dict[str, Any] = {}

    for sym in symbols:
        entry: Dict[str, Any] = {}
        if mode_sub in ("quarterly", "both"):
            df_q = client.get_fundamentals_quarterly(sym, n_quarters=n_quarters)
            entry["quarterly"] = _df_to_records(df_q)
            all_warnings.extend(
                f"{sym}/Q: {w}"
                for w in df_q.attrs.get("warnings", [])
                if df_q.attrs.get("warnings")
            )
        if mode_sub in ("annual", "both"):
            df_a = client.get_fundamentals_annual(sym, n_years=n_years)
            entry["annual"] = _df_to_records(df_a)
            all_warnings.extend(
                f"{sym}/A: {w}"
                for w in df_a.attrs.get("warnings", [])
                if df_a.attrs.get("warnings")
            )
        result[sym] = entry

    return _ok("fundamentals", result, all_warnings)


def _handle_universe(params: Dict[str, Any], client) -> Dict[str, Any]:
    exchanges = params.get("exchanges") or params.get("exchange")
    if isinstance(exchanges, str):
        exchanges = [e.strip() for e in exchanges.split(",") if e.strip()]

    start = params.get("start")
    end = params.get("end") or datetime.today().strftime("%Y-%m-%d")
    adv20_min = float(params.get("adv20_min", 5_000_000_000))

    df = client.build_universe(
        exchanges=exchanges, start=start, end=end, adv20_min=adv20_min
    )
    records = _df_to_records(df)
    symbols = [r["symbol"] for r in records]
    return _ok("universe", {"symbols": symbols, "details": records})


def _handle_rs(params: Dict[str, Any], client) -> Dict[str, Any]:
    symbols = params.get("symbols") or []
    end_date = params.get("end") or datetime.today().strftime("%Y-%m-%d")
    lookback = int(params.get("lookback_days", 252))
    skip = int(params.get("skip_recent_days", 21))

    if not symbols:
        return _err("rs", ["'symbols' list is required"])

    series = client.compute_rs_ratings(symbols, end_date, lookback, skip)
    records = series.reset_index().rename(columns={"index": "symbol"}).to_dict(
        orient="records"
    )
    return _ok("rs", {"ratings": records})


def _handle_macro(params: Dict[str, Any], client) -> Dict[str, Any]:
    asof = params.get("asof") or params.get("end")
    result = client.get_macro_snapshot(asof=asof)
    return _ok("macro", result.get("market", {}), result.get("warnings", []))


_HANDLERS = {
    "ohlcv": _handle_ohlcv,
    "fundamentals": _handle_fundamentals,
    "universe": _handle_universe,
    "rs": _handle_rs,
    "macro": _handle_macro,
}


def run_skill(params: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(params.get("mode", "")).lower()
    if mode not in _HANDLERS:
        return _err(
            mode or "unknown",
            [f"Unknown mode '{mode}'. Valid: {sorted(_HANDLERS.keys())}"],
        )

    try:
        client = get_client()
        handler = _HANDLERS[mode]
        return handler(params, client)
    except Exception as exc:
        logger.exception("run_skill(%s) unexpected error", mode)
        return _err(mode, [f"Unexpected error: {exc}"])

