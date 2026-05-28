from __future__ import annotations

import pandas as pd


def build_benchmark_regimes(benchmark: pd.DataFrame) -> pd.DataFrame:
    b = benchmark.copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce")
    b = b.dropna(subset=["date"]).sort_values("date")
    b["ma200"] = b["close"].rolling(200, min_periods=200).mean()
    b["vnindex_above_200dma"] = b["close"] >= b["ma200"]
    b["vnindex_below_200dma"] = b["close"] < b["ma200"]
    b["covid_shock"] = (b["date"] >= "2020-01-01") & (b["date"] <= "2020-06-30")
    b["fragile_uptrend_narrow_leadership_proxy"] = b["vnindex_above_200dma"] & (b["close"].pct_change(60) < 0.08)
    b["correction_or_bear"] = b["vnindex_below_200dma"]
    b["normal_regime"] = ~b["correction_or_bear"]
    cols = [
        "date",
        "vnindex_above_200dma",
        "vnindex_below_200dma",
        "covid_shock",
        "fragile_uptrend_narrow_leadership_proxy",
        "correction_or_bear",
        "normal_regime",
    ]
    return b[cols]

