from __future__ import annotations

import pandas as pd

from src.research.institutional_accumulation_backtest.outcomes import compute_forward_outcomes


def test_entry_price_open_t1_base_timing() -> None:
    panel = pd.DataFrame([{"scan_date": "2024-01-02", "ticker": "AAA"}])
    px = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "open": [10.0, 11.0, 12.0],
            "close": [10.5, 11.5, 12.5],
        }
    )
    bench = px.copy()
    out = compute_forward_outcomes(panel, {"AAA": px}, bench)
    assert float(out.iloc[0]["entry_price_open_t1"]) == 11.0
