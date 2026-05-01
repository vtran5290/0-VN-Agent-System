from __future__ import annotations

"""
Scan a custom symbol universe (from text file, one symbol per line) for
average daily traded value over the last 50 trading days, and report counts
above multiple thresholds (1–6 billion VND).
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
]


def main():
    cfg = BacktestConfig()
    end_ts = pd.Timestamp(cfg.end)
    start_ts = end_ts - pd.Timedelta(days=365)
    start = start_ts.strftime("%Y-%m-%d")
    end = end_ts.strftime("%Y-%m-%d")

    universe_path = "config/universe_full_from_user.txt"
    tickers = load_candidates(universe_path, _REPO)

    print(
        f"[scan_liquidity_50d_from_file] start={start} end={end} "
        f"symbols={len(tickers)} thresholds={','.join(str(t) for t in THRESHOLDS)}"
    )

    values: dict[str, float] = {}
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
        values[sym] = avg_value

    print(f"\n[summary_counts] (custom universe, last {LOOKBACK_BARS} trading days):")
    for thr in THRESHOLDS:
        cnt = sum(1 for v in values.values() if v >= thr)
        print(f"threshold>={thr:.0f}\tcount={cnt}")

    # Persist universe for ADV >= 4bn
    thr4 = 4_000_000_000
    adv4_syms = sorted(sym for sym, v in values.items() if v >= thr4)
    out_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    out_text = "\n".join(adv4_syms) + ("\n" if adv4_syms else "")
    out_path.write_text(out_text, encoding="utf-8")
    print(f"\n[write] ADV>=4bn universe: {len(adv4_syms)} symbols -> {out_path}")


if __name__ == "__main__":
    main()

