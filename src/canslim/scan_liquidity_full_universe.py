from __future__ import annotations

"""
Scan full FireAnt symbol universe (HOSE, HNX, UPCOM) for average daily traded
value over the last 50 trading days, and report counts above multiple thresholds.

Thresholds (VND):
- >= 1e9
- >= 2e9
- >= 3e9
- >= 4e9
- >= 5e9
- >= 6e9
"""

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.canslim.fireant_fetcher import fetch_all_symbols, fetch_ohlcv  # type: ignore  # noqa: E402

try:
    from pp_backtest.config import BacktestConfig  # type: ignore  # noqa: E402
except ImportError:
    BacktestConfig = None  # type: ignore


LOOKBACK_BARS = 50
THRESHOLDS = [1_000_000_000, 2_000_000_000, 3_000_000_000, 4_000_000_000, 5_000_000_000, 6_000_000_000]


def _get_date_range() -> tuple[str, str]:
    if BacktestConfig is not None:
        cfg = BacktestConfig()  # type: ignore[call-arg]
        end_ts = pd.Timestamp(cfg.end)
    else:
        end_ts = pd.Timestamp.today().normalize()
    start_ts = end_ts - pd.Timedelta(days=365)
    return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")


def _fetch_universe() -> List[str]:
    symbols: Dict[str, None] = {}
    for ex in ("HOSE", "HNX", "UPCOM"):
        try:
            lst = fetch_all_symbols(ex)
        except Exception:
            continue
        for sym in lst:
            s = str(sym).strip().upper()
            if not s:
                continue
            symbols[s] = None
    return sorted(symbols.keys())


def main():
    start, end = _get_date_range()
    universe = _fetch_universe()
    print(
        f"[scan_liquidity_full_universe] start={start} end={end} "
        f"symbols={len(universe)} thresholds={','.join(str(t) for t in THRESHOLDS)}"
    )

    values: Dict[str, float] = {}
    for sym in universe:
        try:
            df = fetch_ohlcv(sym, start, end, resolution="D")
        except Exception as e:
            # Many symbols will have bad/missing data; skip quietly
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
        values[sym] = avg_value

    print(f"\n[summary_counts] (full FireAnt universe, last {LOOKBACK_BARS} trading days):")
    for thr in THRESHOLDS:
        cnt = sum(1 for v in values.values() if v >= thr)
        print(f"threshold>={thr:.0f}\tcount={cnt}")


if __name__ == "__main__":
    main()

