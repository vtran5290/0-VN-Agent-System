from __future__ import annotations

import pandas as pd

from src.research.institutional_accumulation_backtest.audits import run_coverage_audit


def test_run_complete_when_full_run_gates_pass() -> None:
    panel = pd.DataFrame(
        [
            {"scan_date": "2024-01-05", "ticker": "AAA", "universe_full": True, "universe_ex_vin": True, "is_vin": False},
            {"scan_date": "2024-01-12", "ticker": "BBB", "universe_full": True, "universe_ex_vin": True, "is_vin": False},
        ]
    )
    outcomes = pd.DataFrame(
        [
            {"ticker": "AAA", "vnindex_ret_20d": 0.01},
            {"ticker": "BBB", "vnindex_ret_20d": 0.02},
            {"ticker": "CCC", "vnindex_ret_20d": 0.03},
            {"ticker": "DDD", "vnindex_ret_20d": 0.04},
            {"ticker": "EEE", "vnindex_ret_20d": 0.05},
        ]
        * 1200
    )
    _, summary, status = run_coverage_audit(
        panel=panel,
        outcomes=outcomes,
        requested_start="2012-01-01",
        requested_end="2024-12-31",
        cadence="weekly",
        context_mode="OHLCV_ONLY",
        max_symbols_used=None,
        source_ticker_count=2,
        vnindex_available=True,
        vnindex_non_null_rows=100,
    )
    assert status == "RUN_COMPLETE"
    assert summary["run_status"] == "RUN_COMPLETE"
