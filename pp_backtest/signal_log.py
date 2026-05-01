from __future__ import annotations

"""
pp_backtest/signal_log.py

Signal feature logging for weekly Pocket Pivot candidate entries.
This module defines helpers to:
- load sector/exchange metadata (if available; otherwise "UNKNOWN"),
- compute base length, base depth, 3-week tightness, extension vs MA10/EMA21,
- append a row per weekly bar with PP candidate info to a CSV log.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent


def _compute_base_features(wdf: pd.DataFrame, idx: int, max_lookback_weeks: int = 30) -> dict:
    """
    Compute base length/depth/tightness for week at position idx (0-based).
    Base window is the preceding max_lookback_weeks (exclusive of current bar).
    """
    if idx == 0 or wdf.empty:
        return {"base_length": 0, "base_depth_pct": np.nan, "tightness_3w_pct": np.nan}
    start = max(0, idx - max_lookback_weeks)
    base = wdf.iloc[start:idx].copy()
    if base.empty:
        return {"base_length": 0, "base_depth_pct": np.nan, "tightness_3w_pct": np.nan}

    close = base["close"].astype(float).values
    high = base["high"].astype(float).values
    low = base["low"].astype(float).values
    base_length = len(base)
    peak = float(high.max())
    trough = float(low.min())
    base_depth_pct = (peak - trough) / peak if peak > 0 else np.nan

    # 3-week tightness on last 3 completed weeks (before current bar)
    tail = base.tail(3)
    if len(tail) < 3:
        tightness_3w_pct = np.nan
    else:
        t_high = tail["high"].astype(float).max()
        t_low = tail["low"].astype(float).min()
        last_close = float(tail["close"].astype(float).iloc[-1])
        tightness_3w_pct = (t_high - t_low) / last_close if last_close > 0 else np.nan

    return {
        "base_length": base_length,
        "base_depth_pct": base_depth_pct,
        "tightness_3w_pct": tightness_3w_pct,
    }


def _compute_extension_features(
    wdf: pd.DataFrame,
    idx: int,
    ma10: pd.Series,
    ema21: Optional[pd.Series] = None,
) -> dict:
    row = wdf.iloc[idx]
    close = float(row["close"])
    ma10_val = float(ma10.iloc[idx]) if not pd.isna(ma10.iloc[idx]) else np.nan
    ext10 = (close - ma10_val) / ma10_val if ma10_val and not np.isnan(ma10_val) else np.nan
    if ema21 is not None and len(ema21) > idx:
        ema21_val = float(ema21.iloc[idx]) if not pd.isna(ema21.iloc[idx]) else np.nan
        ext21 = (close - ema21_val) / ema21_val if ema21_val and not np.isnan(ema21_val) else np.nan
    else:
        ext21 = np.nan
    return {"ext_vs_ma10": ext10, "ext_vs_ema21": ext21}


def _load_symbol_metadata() -> pd.DataFrame:
    """
    Placeholder: try to load symbol -> exchange/sector mapping if present.
    For now, returns empty; caller should default to UNKNOWN.
    """
    # If a metadata file exists later (e.g. data/symbol_metadata.csv), load here.
    return pd.DataFrame(columns=["symbol", "exchange", "sector"])


_META = _load_symbol_metadata()


def _get_meta(sym: str) -> tuple[str, str]:
    if _META.empty:
        return "UNKNOWN", "UNKNOWN"
    row = _META[_META["symbol"] == sym]
    if row.empty:
        return "UNKNOWN", "UNKNOWN"
    r = row.iloc[0]
    return str(r.get("exchange") or "UNKNOWN"), str(r.get("sector") or "UNKNOWN")


def append_signal_log_row(
    log_path: Path,
    sym: str,
    row: pd.Series,
    idx: int,
    wdf: pd.DataFrame,
    ma10: pd.Series,
    ema21: Optional[pd.Series],
    regime_state: str,
    rs_score: Optional[float],
    chosen_flag: bool,
    reject_reason: str,
    future_ret: Optional[float],
) -> None:
    """
    Append one candidate-entry row to CSV log.
    """
    exchange, sector = _get_meta(sym)
    base_feats = _compute_base_features(wdf, idx)
    ext_feats = _compute_extension_features(wdf, idx, ma10, ema21)

    d = {
        "symbol": sym,
        "entry_date": pd.to_datetime(row["date"]).strftime("%Y-%m-%d"),
        "exchange": exchange,
        "sector": sector,
        "regime_state": regime_state,
        "adtv20": np.nan,  # placeholder; can be filled from monthly universe later
        "adtv50": np.nan,
        "rs_score": rs_score,
        "weekly_pp": bool(row.get("weekly_pp", False)),
        "pp_volume": float(row.get("volume", np.nan)),
        "close": float(row.get("close", np.nan)),
        "base_length": base_feats["base_length"],
        "base_depth_pct": base_feats["base_depth_pct"],
        "tightness_3w_pct": base_feats["tightness_3w_pct"],
        "ext_vs_ma10": ext_feats["ext_vs_ma10"],
        "ext_vs_ema21": ext_feats["ext_vs_ema21"],
        "chosen_flag": bool(chosen_flag),
        "reject_reason": reject_reason,
        "future_ret": future_ret if future_ret is not None else np.nan,
    }

    df_row = pd.DataFrame([d])
    if log_path.exists():
        df_row.to_csv(log_path, mode="a", header=False, index=False)
    else:
        df_row.to_csv(log_path, mode="w", header=True, index=False)

