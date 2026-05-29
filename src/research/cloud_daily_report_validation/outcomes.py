"""Forward return computation for cloud daily report validation.

Signal at close T → entry at T+1 open → forward return to T+N close.

RESEARCH_ONLY_NOT_PRODUCTION
All outputs labeled RECONSTRUCTED_NOT_LIVE_SCAN.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED
from .schema import EvidenceLabel, RESEARCH_ONLY_LABEL

logger = logging.getLogger(__name__)

# Minimum events required to compute statistics; below this use BLOCKED_BY_DATA
MIN_EVENTS_FOR_STAT = 5

DEFAULT_HORIZONS = [5, 10, 20, 60]


def _resolve_ohlcv_index(ohlcv: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build a dict of {symbol -> sorted DataFrame with date index}."""
    if ohlcv.empty:
        return {}
    sym_col = None
    for candidate in ("symbol", "ticker", "Symbol", "Ticker"):
        if candidate in ohlcv.columns:
            sym_col = candidate
            break
    if sym_col is None:
        logger.warning("OHLCV panel has no recognized symbol column")
        return {}
    date_col = None
    for candidate in ("date", "Date", "trading_date"):
        if candidate in ohlcv.columns:
            date_col = candidate
            break
    if date_col is None:
        logger.warning("OHLCV panel has no recognized date column")
        return {}

    index: dict[str, pd.DataFrame] = {}
    for sym, grp in ohlcv.groupby(sym_col):
        g = grp.copy()
        g[date_col] = pd.to_datetime(g[date_col], errors="coerce")
        g = g.dropna(subset=[date_col]).sort_values(date_col)
        g = g.set_index(date_col)
        index[str(sym)] = g
    return index


def compute_forward_returns(
    events_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Compute forward returns for a set of events.

    Parameters
    ----------
    events_df:
        DataFrame with at minimum columns 'symbol' and 'as_of_date' (signal date T).
    ohlcv:
        Full OHLCV panel DataFrame with symbol, date, open, close columns.
    horizons:
        List of forward-day horizons. Defaults to [5, 10, 20, 60].

    Returns
    -------
    events_df with extra columns:
        forward_entry_open_price, forward_ret_{N}d for each horizon N,
        signal_integrity = RECONSTRUCTED_NOT_LIVE_SCAN,
        research_label = RESEARCH_ONLY_NOT_PRODUCTION
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    result = events_df.copy()
    # Initialize output columns
    result["forward_entry_open_price"] = np.nan
    for h in horizons:
        result[f"forward_ret_{h}d"] = np.nan
    result["signal_integrity"] = LABEL_RECONSTRUCTED
    result["research_label"] = RESEARCH_ONLY_LABEL

    if ohlcv.empty:
        logger.warning("OHLCV panel is empty — all forward returns will be NaN")
        result["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
        return result

    sym_index = _resolve_ohlcv_index(ohlcv)
    if not sym_index:
        logger.warning("Could not build OHLCV symbol index")
        result["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
        return result

    # Resolve column names
    sym_col = "symbol" if "symbol" in events_df.columns else events_df.columns[0]
    date_col = "as_of_date" if "as_of_date" in events_df.columns else None
    if date_col is None:
        logger.warning("events_df missing 'as_of_date' column")
        result["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
        return result

    open_col = "open" if "open" in ohlcv.columns else None
    close_col = "close" if "close" in ohlcv.columns else None
    if open_col is None or close_col is None:
        logger.warning("OHLCV panel missing open/close columns")
        result["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
        return result

    entry_prices: list[float | None] = []
    fwd_rets: dict[int, list[float | None]] = {h: [] for h in horizons}

    for _, row in events_df.iterrows():
        sym = str(row.get(sym_col, ""))
        sig_date = pd.Timestamp(row[date_col])
        sym_df = sym_index.get(sym)

        if sym_df is None or sym_df.empty:
            entry_prices.append(None)
            for h in horizons:
                fwd_rets[h].append(None)
            continue

        # Find T+1 (next trading day after signal date)
        future_idx = sym_df.index[sym_df.index > sig_date]
        if len(future_idx) < 1:
            entry_prices.append(None)
            for h in horizons:
                fwd_rets[h].append(None)
            continue

        t1_date = future_idx[0]
        entry_open = float(sym_df.loc[t1_date, open_col])
        entry_prices.append(entry_open)

        for h in horizons:
            # Forward return from T+1 open to T+N close (N days from T+1)
            target_idx_pos = sym_df.index.get_loc(t1_date)
            exit_pos = target_idx_pos + h
            if exit_pos >= len(sym_df):
                fwd_rets[h].append(None)
                continue
            exit_close = float(sym_df.iloc[exit_pos][close_col])
            if entry_open <= 0:
                fwd_rets[h].append(None)
                continue
            fwd_rets[h].append(float(exit_close / entry_open - 1.0))

    result["forward_entry_open_price"] = entry_prices
    for h in horizons:
        result[f"forward_ret_{h}d"] = fwd_rets[h]

    return result


def compute_vnindex_returns(
    ohlcv: pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Compute VNINDEX forward returns for benchmark comparison.

    Returns a DataFrame with columns: date, vnindex_ret_{N}d for each horizon,
    labeled RECONSTRUCTED_NOT_LIVE_SCAN.
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    if ohlcv.empty:
        return pd.DataFrame()

    # Try to find VNINDEX rows
    sym_col = None
    for candidate in ("symbol", "ticker"):
        if candidate in ohlcv.columns:
            sym_col = candidate
            break

    vni = None
    if sym_col:
        for name in ("VNINDEX", "VNI", "^VNINDEX"):
            mask = ohlcv[sym_col].astype(str).str.upper() == name
            if mask.any():
                vni = ohlcv[mask].copy()
                break

    if vni is None or vni.empty:
        logger.warning("VNINDEX not found in OHLCV panel for benchmark computation")
        return pd.DataFrame()

    date_col = "date" if "date" in vni.columns else "Date"
    vni[date_col] = pd.to_datetime(vni[date_col], errors="coerce")
    vni = vni.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)

    open_arr = vni["open"].astype(float).values
    close_arr = vni["close"].astype(float).values
    dates = vni[date_col].values
    rows = []

    for i in range(len(vni)):
        row: dict = {"date": str(pd.Timestamp(dates[i]).date())}
        for h in horizons:
            exit_pos = i + h
            if exit_pos >= len(close_arr) or open_arr[i] <= 0:
                row[f"vnindex_ret_{h}d"] = None
            else:
                row[f"vnindex_ret_{h}d"] = float(close_arr[exit_pos] / open_arr[i] - 1.0)
        row["signal_integrity"] = LABEL_RECONSTRUCTED
        rows.append(row)

    return pd.DataFrame(rows)


def label_blocked_if_small_n(df: pd.DataFrame, group_col: str, min_n: int = MIN_EVENTS_FOR_STAT) -> pd.DataFrame:
    """Add evidence_label = BLOCKED_BY_DATA for groups with N < min_n."""
    df = df.copy()
    if group_col not in df.columns:
        df["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
        return df
    counts = df[group_col].value_counts()
    labels = []
    for val in df[group_col]:
        if counts.get(val, 0) < min_n:
            labels.append(EvidenceLabel.BLOCKED_BY_DATA.value)
        else:
            labels.append(EvidenceLabel.INCONCLUSIVE.value)
    df["evidence_label"] = labels
    return df
