# pp_backtest/universe_liquidity.py — Liquidity Top-N universe by year (research-grade, no forward bias)
"""
Universe = Top N by median(matched_value_60d) per year, frozen for that year.
Inclusion: median over 60 trading days before first trading day of year;
           close >= min_price (VND); >= min_bars_before trading bars before year start.
"""
from __future__ import annotations

import pandas as pd
from typing import Callable

# Defaults from VN Universe Spec (docs)
MIN_PRICE_VND = 5000
MIN_BARS_BEFORE = 250
LIQUIDITY_WINDOW = 60


def get_trading_calendar(fetch: Callable[[str, str, str], pd.DataFrame], start: str, end: str) -> pd.DatetimeIndex:
    """Trading dates from VN30 over [start, end]. Sorted."""
    df = fetch("VN30", start, end)
    if df.empty or "date" not in df.columns:
        return pd.DatetimeIndex([])
    out = pd.to_datetime(df["date"]).dt.normalize().unique()
    return pd.DatetimeIndex(sorted(out))


def _first_trading_day_of_year(calendar: pd.DatetimeIndex, year: int) -> pd.Timestamp | None:
    """First calendar date with year == year."""
    for t in calendar:
        if t.year == year:
            return t
    return None


def _last_n_trading_days_before(calendar: pd.DatetimeIndex, before_date: pd.Timestamp, n: int) -> list[pd.Timestamp]:
    """Last n trading dates strictly before before_date."""
    before = calendar[calendar < before_date]
    if len(before) < n:
        return list(before)
    return list(before[-n:])


def build_liquidity_universe_by_year(
    candidates: list[str],
    start: str,
    end: str,
    top_n: int | dict[int, int],
    fetch: Callable[[str, str, str], pd.DataFrame],
    min_price: float = MIN_PRICE_VND,
    min_bars_before: int = MIN_BARS_BEFORE,
    liquidity_window: int = LIQUIDITY_WINDOW,
    calendar_symbol: str = "VN30",
) -> dict[int, list[str]]:
    """
    Build per-year universe: for each year Y, take top N symbols by median(volume*close)
    over the last `liquidity_window` trading days before the first trading day of Y.
    - Require close (last day of window) >= min_price.
    - Require at least min_bars_before trading bars before first day of Y.
    - top_n: int (same for all years) or dict[year, N].
    Returns dict[year, list[symbol]].
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    start_year = start_ts.year
    end_year = end_ts.year
    lookback_start = f"{start_year - 1}-01-01"

    # Trading calendar from lookback to end
    cal_df = fetch(calendar_symbol, lookback_start, end)
    if cal_df.empty or "date" not in cal_df.columns:
        return {y: [] for y in range(start_year, end_year + 1)}
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(cal_df["date"]).dt.normalize().unique()))

    def get_top_n(y: int) -> int:
        if isinstance(top_n, dict):
            return top_n.get(y, 50)
        return top_n

    # Fetch each candidate once for full range
    data_by_sym: dict[str, pd.DataFrame] = {}
    for sym in candidates:
        try:
            df = fetch(sym, lookback_start, end)
        except Exception:
            continue
        if df.empty or "date" not in df.columns or "volume" not in df.columns or "close" not in df.columns:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.sort_values("date").reset_index(drop=True)
        data_by_sym[sym] = df

    result: dict[int, list[str]] = {}
    for year in range(start_year, end_year + 1):
        first_day = _first_trading_day_of_year(calendar, year)
        if first_day is None:
            result[year] = []
            continue
        window_dates = _last_n_trading_days_before(calendar, first_day, liquidity_window)
        if len(window_dates) < liquidity_window:
            result[year] = []
            continue

        set_dates = set(window_dates)
        scores: list[tuple[str, float]] = []

        for sym, df in data_by_sym.items():
            bars_before = (df["date"] < first_day).sum()
            if bars_before < min_bars_before:
                continue

            slice_df = df[df["date"].isin(set_dates)]
            if len(slice_df) < liquidity_window:
                continue

            slice_df = slice_df.sort_values("date").tail(liquidity_window)
            if len(slice_df) < liquidity_window:
                continue

            matched_value = slice_df["volume"].astype(float) * slice_df["close"].astype(float)
            med_val = matched_value.median()
            last_close = float(slice_df.iloc[-1]["close"])

            if last_close < min_price or not (med_val > 0):
                continue
            scores.append((sym, float(med_val)))

        scores.sort(key=lambda x: -x[1])
        n = get_top_n(year)
        result[year] = [s[0] for s in scores[:n]]

    return result


def load_candidates(path: str | None, repo_root: object) -> list[str]:
    """Load candidate symbols from file (one per line). path relative to repo_root or absolute."""
    from pathlib import Path
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    p = Path(path) if path else root / "config" / "universe_186.txt"
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
