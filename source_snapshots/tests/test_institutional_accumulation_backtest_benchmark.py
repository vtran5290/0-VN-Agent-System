from __future__ import annotations

import pandas as pd

from src.research.institutional_accumulation_backtest.audits import benchmark_validation_csv


def test_benchmark_validation_not_all_nan_when_data_exists(tmp_path) -> None:
    bench = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-02"]), "open": [1, 2], "close": [1, 2]})
    out = pd.DataFrame({"vnindex_ret_5d": [0.1, None], "vnindex_ret_10d": [None, None]})
    p = tmp_path / "benchmark_validation.csv"
    df = benchmark_validation_csv(bench, out, p)
    assert p.is_file()
    assert df.iloc[0]["status"] == "OK"
