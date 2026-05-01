"""
Backward-compatible shim — logic is now implemented in src.data.fireant_client.

Existing imports continue to work:

    from src.canslim.fireant_fetcher import fetch_ohlcv, fetch_all_symbols, ...
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

from src.data.fireant_client import get_client

logger = logging.getLogger(__name__)


def fetch_ohlcv(
    symbol: str,
    start: str,
    end: str,
    resolution: str = "D",
) -> pd.DataFrame:
    return get_client().get_ohlcv(symbol, start, end, timeframe=resolution)


def fetch_financial_statements(
    symbol: str,
    year: int,
    quarter: int,
    limit: int = 10,
    report_type: int = 2,
) -> list:
    return get_client()._raw_financials(symbol, year, quarter, limit)  # type: ignore[attr-defined]


def fetch_multi_quarters(symbol: str, n_quarters: int = 6) -> pd.DataFrame:
    return get_client().get_fundamentals_quarterly(symbol, n_quarters=n_quarters)


def fetch_annual_CA(symbol: str, n_years: int = 4) -> pd.DataFrame:
    return get_client().get_fundamentals_annual(symbol, n_years=n_years)


def compute_rs_ratings(
    symbols: List[str],
    end_date: str,
    lookback_days: int = 252,
    skip_recent_days: int = 21,
) -> pd.Series:
    return get_client().compute_rs_ratings(
        symbols,
        end_date,
        lookback_days=lookback_days,
        skip_recent_days=skip_recent_days,
    )


def fetch_all_symbols(exchange: str = "HOSE") -> List[str]:
    return get_client().get_symbols(exchange)


