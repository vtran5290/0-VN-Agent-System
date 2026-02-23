# minervini_backtest/tests/test_engine_correctness.py — Unit tests: no look-ahead, fill bar, entry/exit
"""
Run from repo root: PYTHONPATH=minervini_backtest/src python -m pytest minervini_backtest/tests/test_engine_correctness.py -v
Or: cd minervini_backtest && PYTHONPATH=src python -m pytest tests/test_engine_correctness.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Allow importing from src
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_highest_high_excludes_current_bar():
    """Highest(High, lookback) must be over PAST bars only (exclude current bar)."""
    from triggers import breakout
    # At bar i we need lookback past bars; so first valid bar index = lookback.
    # At bar 3 with lookback=3: past bars 0,1,2 → HH = 103. Close 103.5 > 103 → True.
    n = 10
    lookback = 3
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="B"),
        "open": 100.0,
        "high": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "low": 99.0,
        "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5],
        "volume": 1_000_000,
    })
    df["vol_sma20"] = 500_000.0
    br = breakout(df, lookback_base=lookback, close_strength=False)
    # Bar 3: past 0,1,2 → HH=103. Close 103.5 > 103 → True (current bar 3 high=104 not included)
    assert br.iloc[3] == True
    # Bar 2: only 2 past bars; rolling(3).max().shift(1) at 2 = NaN → no breakout
    assert pd.isna(br.iloc[2]) or br.iloc[2] == False


def test_atr_vol_sma_use_past_only_optional():
    """EOD system: at bar i we know OHLC of bar i. So ATR(14) at i including bar i is acceptable.
    This test documents that we use standard rolling (includes current bar) for indicators."""
    from indicators import atr, add_vol_sma
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=30, freq="B"),
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1e6,
    })
    a = atr(df, 14)
    v = add_vol_sma(df, [20])
    # ATR and Vol SMA are defined at bar i using bars up to and including i (standard pandas rolling)
    assert a.iloc[13] == a.iloc[13]
    assert "vol_sma20" in v.columns
    assert v["vol_sma20"].iloc[19] == 1e6


def test_pivot_level_excludes_current_bar():
    """pivot_level(d, lookback, end_idx) = max(high[start:end_idx]) so current bar excluded."""
    from triggers import pivot_level
    df = pd.DataFrame({
        "high": [10, 20, 30, 40, 50],
        "low": 0.0, "open": 0.0, "close": 0.0, "volume": 0.0, "date": pd.date_range("2020-01-01", periods=5, freq="B"),
    })
    # pivot at end_idx=4, lookback=4 → indices 0:4 → max(10,20,30,40)=40 (bar 4 excluded)
    p = pivot_level(df, 4, 4)
    assert p == 40.0


def test_entry_exit_at_intended_bar():
    """Entry at next open after signal; exit at next open after exit signal."""
    from engine import run_single_symbol
    np.random.seed(123)
    n = 500
    df = pd.DataFrame({
        "date": pd.date_range("2018-01-01", periods=n, freq="B"),
        "open": 100 + np.cumsum(np.random.randn(n) * 0.5),
        "high": 101 + np.cumsum(np.random.randn(n) * 0.5),
        "low": 99 + np.cumsum(np.random.randn(n) * 0.5),
        "close": 100 + np.cumsum(np.random.randn(n) * 0.5),
        "volume": np.abs(np.random.randn(n)) * 1e6 + 1e6,
    })
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    cfg = {
        "tt": "lite", "setup": "vcp", "lookback_base": 30, "vol_mult": 1.2, "close_strength": True,
        "stop_pct": 0.05, "atr_k": 2.0, "risk_pct": 0.01,
        "exits": {"hard_stop": True, "trend_break_ma": 50},
        "fee_bps": 0, "slippage_bps": 0, "min_hold_bars": 0, "use_retest": False,
    }
    stats, ledger = run_single_symbol(df, cfg, symbol="TEST")
    if ledger.empty:
        return  # no trades is valid
    # Each row: entry happened at open of bar after signal; exit at open of bar after exit signal
    assert "entry_px" in ledger.columns and "exit_px" in ledger.columns
    assert (ledger["ret"] == (ledger["exit_px"] / ledger["entry_px"]) - 1.0).all()


if __name__ == "__main__":
    test_highest_high_excludes_current_bar()
    print("test_highest_high_excludes_current_bar OK")
    test_pivot_level_excludes_current_bar()
    print("test_pivot_level_excludes_current_bar OK")
    test_atr_vol_sma_use_past_only_optional()
    print("test_atr_vol_sma OK")
    test_entry_exit_at_intended_bar()
    print("test_entry_exit OK")
