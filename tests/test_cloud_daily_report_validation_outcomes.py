"""Tests for cloud daily report validation — forward return outcomes.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.data_loader import LABEL_RECONSTRUCTED
from src.research.cloud_daily_report_validation.outcomes import (
    MIN_EVENTS_FOR_STAT,
    compute_forward_returns,
    label_blocked_if_small_n,
)
from src.research.cloud_daily_report_validation.schema import EvidenceLabel, RESEARCH_ONLY_LABEL


def _make_ohlcv(symbols: list[str], start: str = "2026-01-02", n_days: int = 80) -> pd.DataFrame:
    """Build a minimal OHLCV panel for testing."""
    rows = []
    dates = pd.bdate_range(start, periods=n_days)
    for sym in symbols:
        price = 100.0
        for dt in dates:
            rows.append({
                "symbol": sym,
                "date": dt,
                "open": round(price, 2),
                "close": round(price * 1.001, 2),
                "high": round(price * 1.01, 2),
                "low": round(price * 0.99, 2),
                "volume": 1_000_000,
            })
            price *= 1.001
    return pd.DataFrame(rows)


def _make_events(symbols: list[str], date_str: str = "2026-01-10") -> pd.DataFrame:
    """Build a minimal events DataFrame with one event per symbol."""
    return pd.DataFrame([
        {"symbol": sym, "as_of_date": date_str, "final_action": "NEW_T1"}
        for sym in symbols
    ])


def test_forward_returns_use_t1_timing():
    """Signal at T → entry at T+1 open (not same-day close)."""
    ohlcv = _make_ohlcv(["AAA"], start="2026-01-02", n_days=40)
    events = _make_events(["AAA"], date_str="2026-01-10")

    result = compute_forward_returns(events, ohlcv, horizons=[5])

    assert "forward_entry_open_price" in result.columns, "Must have forward_entry_open_price"
    assert "forward_ret_5d" in result.columns, "Must have forward_ret_5d"

    # The entry price should be the OPEN on T+1, not the CLOSE on T
    entry_price = result.iloc[0]["forward_entry_open_price"]
    assert entry_price is not None and not pd.isna(entry_price), "Entry price should not be NaN"

    # Verify T+1 timing: find what T close and T+1 open are in the OHLCV
    ohlcv_aaa = ohlcv[ohlcv["symbol"] == "AAA"].copy()
    ohlcv_aaa["date"] = pd.to_datetime(ohlcv_aaa["date"])
    ohlcv_aaa = ohlcv_aaa.sort_values("date")

    signal_date = pd.Timestamp("2026-01-10")
    t_row = ohlcv_aaa[ohlcv_aaa["date"] == signal_date]
    t1_row = ohlcv_aaa[ohlcv_aaa["date"] > signal_date].iloc[:1]

    if not t_row.empty and not t1_row.empty:
        t_close = float(t_row.iloc[0]["close"])
        t1_open = float(t1_row.iloc[0]["open"])
        # Entry should be T+1 open, not T close
        assert abs(entry_price - t1_open) < 0.01, (
            f"Entry price {entry_price} should equal T+1 open {t1_open}, not T close {t_close}"
        )


def test_missing_ohlcv_returns_empty():
    """If OHLCV is empty, forward returns should be NaN (graceful handling)."""
    events = _make_events(["BBB"], date_str="2026-01-15")
    empty_ohlcv = pd.DataFrame()

    result = compute_forward_returns(events, empty_ohlcv, horizons=[5, 10])

    assert len(result) == len(events), "Must return same number of rows as events"
    assert "forward_ret_5d" in result.columns
    # All returns should be NaN
    assert result["forward_ret_5d"].isna().all(), "All forward returns should be NaN with empty OHLCV"


def test_reconstructed_label_present():
    """All outcomes must carry signal_integrity = RECONSTRUCTED_NOT_LIVE_SCAN."""
    ohlcv = _make_ohlcv(["CCC"], n_days=30)
    events = _make_events(["CCC"], date_str="2026-01-05")

    result = compute_forward_returns(events, ohlcv, horizons=[5])

    assert "signal_integrity" in result.columns, "signal_integrity column must be present"
    assert "research_label" in result.columns, "research_label column must be present"
    assert (result["signal_integrity"] == LABEL_RECONSTRUCTED).all(), (
        f"All rows must have signal_integrity='{LABEL_RECONSTRUCTED}'"
    )
    assert (result["research_label"] == RESEARCH_ONLY_LABEL).all(), (
        f"All rows must have research_label='{RESEARCH_ONLY_LABEL}'"
    )


def test_blocked_when_n_lt_5():
    """label_blocked_if_small_n must assign BLOCKED_BY_DATA when group N < MIN_EVENTS_FOR_STAT."""
    # Create a DataFrame with one group having N < 5
    df = pd.DataFrame([
        {"final_action": "NEW_T1", "val": i}
        for i in range(3)  # Only 3 rows — below MIN_EVENTS_FOR_STAT
    ])

    labeled = label_blocked_if_small_n(df, group_col="final_action", min_n=MIN_EVENTS_FOR_STAT)

    assert "evidence_label" in labeled.columns
    assert (labeled["evidence_label"] == EvidenceLabel.BLOCKED_BY_DATA.value).all(), (
        f"All rows with N=3 < {MIN_EVENTS_FOR_STAT} should be BLOCKED_BY_DATA"
    )


def test_blocked_when_n_gte_5_not_blocked():
    """label_blocked_if_small_n must NOT assign BLOCKED_BY_DATA when group N >= MIN_EVENTS_FOR_STAT."""
    df = pd.DataFrame([
        {"final_action": "NEW_T1", "val": i}
        for i in range(MIN_EVENTS_FOR_STAT + 2)  # 7 rows — above threshold
    ])

    labeled = label_blocked_if_small_n(df, group_col="final_action", min_n=MIN_EVENTS_FOR_STAT)

    assert "evidence_label" in labeled.columns
    assert (labeled["evidence_label"] != EvidenceLabel.BLOCKED_BY_DATA.value).all(), (
        f"Rows with N>={MIN_EVENTS_FOR_STAT} should not be BLOCKED_BY_DATA"
    )
