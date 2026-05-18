"""VNINDEX in-memory overlay for intraday macro (never writes ta_vnindex.parquet)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from pp_backtest.portfolio_optimization_phase1 import vnindex_regime_gate
from src.trading.intraday.data_adapter import fetch_intraday_quote


def build_vnindex_intraday_overlay(
    vnx_eod: pd.DataFrame,
    *,
    target_date: Optional[pd.Timestamp] = None,
    run_timestamp: Optional[datetime] = None,
    stale_threshold_sec: float = 300,
    quote: Optional[dict] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Append/replace today's VNINDEX bar from FireAnt partial daily quote.
    Does not write data/fireant_ssot/ta_vnindex.parquet.
    """
    if run_timestamp is None:
        from src.trading.intraday.session import now_hcm
        run_timestamp = now_hcm()
    target_date = pd.Timestamp(target_date or run_timestamp.date()).normalize()
    vnx = vnx_eod.sort_values("date").reset_index(drop=True).copy()
    vnx["date"] = pd.to_datetime(vnx["date"]).dt.normalize()

    gate_eod, regime_eod_last = vnindex_regime_gate(vnx)
    eod_last = pd.Timestamp(vnx["date"].max()).normalize() if len(vnx) else None
    eod_close = float(vnx["close"].iloc[-1]) if len(vnx) else None
    eod_regime_at_target = bool(gate_eod.get(target_date, regime_eod_last))

    meta: Dict[str, Any] = {
        "vnindex_symbol": "VNINDEX",
        "target_date": str(target_date.date()),
        "vnindex_eod_asof_date": str(eod_last.date()) if eod_last is not None else None,
        "vnindex_eod_close": eod_close,
        "vnindex_eod_regime_bull": eod_regime_at_target,
        "vnindex_overlay_applied": False,
        "vnindex_intraday_close": None,
        "vnindex_intraday_regime_bull": None,
        "vnindex_quote_quality": "SOURCE_UNAVAILABLE",
    }

    if quote is None:
        quote = fetch_intraday_quote("VNINDEX", stale_threshold_sec=stale_threshold_sec)
    if not quote or quote.get("data_quality") in ("SOURCE_UNAVAILABLE", "MISSING_PRICE"):
        meta["vnindex_quote_quality"] = quote.get("data_quality", "SOURCE_UNAVAILABLE") if quote else "SOURCE_UNAVAILABLE"
        return vnx, meta

    last_px = float(quote.get("last_price_kvnd") or 0)
    if last_px <= 0:
        meta["vnindex_quote_quality"] = "MISSING_PRICE"
        return vnx, meta

    o = quote.get("open_price_kvnd") or last_px
    h = quote.get("high_price_kvnd") or last_px
    l = quote.get("low_price_kvnd") or last_px
    vol = quote.get("cumulative_volume") or 0.0

    mask = vnx["date"] == target_date
    if mask.any():
        idx = vnx.index[mask][0]
        vnx.at[idx, "close"] = last_px
        vnx.at[idx, "high"] = max(float(vnx.at[idx, "high"]), float(h), last_px)
        vnx.at[idx, "low"] = min(float(vnx.at[idx, "low"]), float(l), last_px)
        vnx.at[idx, "open"] = float(o)
        if "volume" in vnx.columns:
            vnx.at[idx, "volume"] = float(vol)
    else:
        row = {"date": target_date, "open": float(o), "high": float(h), "low": float(l), "close": last_px}
        if "volume" in vnx.columns:
            row["volume"] = float(vol)
        vnx = pd.concat([vnx, pd.DataFrame([row])], ignore_index=True)

    gate_new, regime_new = vnindex_regime_gate(vnx)
    intraday_regime_bull = bool(gate_new.get(target_date, regime_new))
    meta.update(
        {
            "vnindex_overlay_applied": True,
            "vnindex_intraday_close": last_px,
            "vnindex_intraday_regime_bull": intraday_regime_bull,
            "vnindex_quote_quality": quote.get("data_quality", "OK"),
            "vnindex_price_source_time": quote.get("timestamp"),
            "vnindex_regime_changed": eod_regime_at_target != intraday_regime_bull,
        }
    )
    return vnx, meta


def breadth_zone_from_pct(pct: float) -> str:
    if pct >= 0.40:
        return "normal"
    if pct >= 0.35:
        return "caution"
    return "defense"
