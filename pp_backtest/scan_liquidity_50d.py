from __future__ import annotations

"""
Scan current universe for symbols whose average daily traded value over the last
50 trading days is at least a given threshold (default 5e9 VND).
Uses the same watchlist and FireAnt fetcher as the weekly PP backtest.
"""

import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.universe_liquidity import load_candidates
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant
    from universe_liquidity import load_candidates


LOOKBACK_BARS = 50
THRESHOLDS = [
    1_000_000_000,
    2_000_000_000,
    3_000_000_000,
    4_000_000_000,
    5_000_000_000,
    6_000_000_000,
]  # 1–6 tỷ VND


def main():
    cfg = BacktestConfig()
    end_ts = pd.Timestamp(cfg.end)
    # Fetch roughly 1 year back to ensure we have at least 50 trading days.
    start_ts = end_ts - pd.Timedelta(days=365)
    start = start_ts.strftime("%Y-%m-%d")
    end = end_ts.strftime("%Y-%m-%d")

    tickers = load_candidates("config/universe_186.txt", _REPO)
    results: list[tuple[str, float]] = []

    print(f"[scan_liquidity_50d] start={start} end={end} symbols={len(tickers)} thresholds={','.join(str(t) for t in THRESHOLDS)}")

    for sym in tickers:
        try:
            df = fetch_ohlcv_fireant(sym, start, end)
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            continue
        if df.empty or len(df) < LOOKBACK_BARS:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        tail = df.tail(LOOKBACK_BARS)
        if len(tail) < LOOKBACK_BARS:
            continue
        value = tail["close"].astype(float) * tail["volume"].astype(float)
        avg_value = float(value.mean())
        results.append((sym, avg_value))

    results.sort(key=lambda x: -x[1])

    # Summary counts per threshold
    print("\n[summary_counts] (universe_186, last 50 trading days):")
    for thr in THRESHOLDS:
        cnt = sum(1 for _, v in results if v >= thr)
        print(f"threshold>={thr:.0f}\tcount={cnt}")

    # Optional: print top symbols for context
    print("\n[top_by_avg_value] (symbol, avg_value):")
    for sym, avg_val in results[:50]:
        print(f"{sym}\t{avg_val:.0f}")


if __name__ == "__main__":
    main()

