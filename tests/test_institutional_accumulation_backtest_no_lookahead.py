from __future__ import annotations

import pandas as pd

from src.scans.institutional_accumulation.indicators import slice_through


def test_slice_through_avoids_future_rows() -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "close": [1, 2, 3],
            "open": [1, 2, 3],
            "high": [1, 2, 3],
            "low": [1, 2, 3],
            "volume": [1, 1, 1],
        }
    )
    out = slice_through(df, "2024-01-02")
    assert out["date"].max() <= pd.Timestamp("2024-01-02")
